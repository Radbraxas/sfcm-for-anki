// SPDX-License-Identifier: AGPL-3.0-or-later
//! Engine process lifecycle: spawn, handshake, route, restart with backoff, shut down.

use std::collections::HashMap;
use std::path::PathBuf;
use std::process::Stdio;
use std::sync::{Arc, Mutex as StdMutex};
use std::time::{Duration, Instant};

use serde::Serialize;
use serde_json::{json, Value};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, ChildStdin, Command};
use tokio::sync::{oneshot, watch, Mutex};

use crate::messages::{Incoming, RpcError};
use crate::{ENGINE_UNAVAILABLE, PROTOCOL_VERSION};

/// What the UI shows about the engine. Serialized as `{"state": "ready", ...}`.
#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(tag = "state", rename_all = "camelCase")]
pub enum EngineStatus {
    Starting,
    #[serde(rename_all = "camelCase")]
    Ready {
        engine_version: String,
        protocol_version: u64,
    },
    #[serde(rename_all = "camelCase")]
    Restarting {
        attempt: u32,
        reason: String,
    },
    #[serde(rename_all = "camelCase")]
    Failed {
        reason: String,
    },
}

#[derive(Debug, Clone)]
pub struct EngineConfig {
    pub program: PathBuf,
    pub args: Vec<String>,
    pub env: Vec<(String, String)>,
    pub cwd: Option<PathBuf>,
    /// Consecutive failed starts before giving up and reporting `Failed`.
    pub max_attempts: u32,
    /// A run at least this long resets the attempt counter.
    pub stable_after: Duration,
}

impl EngineConfig {
    pub fn new(program: impl Into<PathBuf>, args: Vec<String>) -> Self {
        Self {
            program: program.into(),
            args,
            env: Vec::new(),
            cwd: None,
            max_attempts: 5,
            stable_after: Duration::from_secs(60),
        }
    }
}

/// Receives status changes and engine notifications (the app forwards them to the UI).
pub trait EventSink: Send + Sync + 'static {
    fn status(&self, status: &EngineStatus);
    fn notification(&self, method: &str, params: &Value);
}

/// Answers requests the engine makes to the shell. Runs on a blocking thread, so it
/// may do slow work such as reading the OS keychain.
pub trait ShellHandler: Send + Sync + 'static {
    fn handle(&self, method: &str, params: &Value) -> Result<Value, RpcError>;
}

/// Delay before restart attempt `attempt` (1-based): 1, 2, 4, 8, 16, then 30 seconds.
pub fn backoff(attempt: u32) -> Duration {
    let secs = 1u64 << attempt.saturating_sub(1).min(5);
    Duration::from_secs(secs.min(30))
}

type Pending = HashMap<String, oneshot::Sender<Result<Value, RpcError>>>;

struct Inner {
    config: EngineConfig,
    sink: Arc<dyn EventSink>,
    shell: Arc<dyn ShellHandler>,
    stdin: Mutex<Option<ChildStdin>>,
    pending: StdMutex<Pending>,
    status: StdMutex<EngineStatus>,
    shutdown: watch::Sender<bool>,
}

enum Outcome {
    Shutdown,
    Exited(String),
    /// Restarting would not help (e.g. protocol mismatch).
    Fatal(String),
}

fn unavailable(message: &str) -> RpcError {
    RpcError::new(ENGINE_UNAVAILABLE, message)
}

#[derive(Clone)]
pub struct EngineHost {
    inner: Arc<Inner>,
}

impl EngineHost {
    /// Starts the engine and supervises it until [`EngineHost::shutdown`].
    /// Must be called from inside a Tokio runtime.
    pub fn start(
        config: EngineConfig,
        sink: Arc<dyn EventSink>,
        shell: Arc<dyn ShellHandler>,
    ) -> Self {
        let (shutdown, _) = watch::channel(false);
        let host = Self {
            inner: Arc::new(Inner {
                config,
                sink,
                shell,
                stdin: Mutex::new(None),
                pending: StdMutex::new(HashMap::new()),
                status: StdMutex::new(EngineStatus::Starting),
                shutdown,
            }),
        };
        let supervisor = host.clone();
        tokio::spawn(async move { supervisor.supervise().await });
        host
    }

    pub fn status(&self) -> EngineStatus {
        self.inner.status.lock().expect("status lock").clone()
    }

    /// Forwards a request and waits for the engine's reply. `id` must be unique among
    /// in-flight requests; the UI uses it to cancel and to match progress events.
    pub async fn request(
        &self,
        id: String,
        method: &str,
        params: Value,
    ) -> Result<Value, RpcError> {
        if !matches!(self.status(), EngineStatus::Ready { .. }) {
            return Err(unavailable("engine is not running"));
        }
        let (tx, rx) = oneshot::channel();
        {
            let mut pending = self.inner.pending.lock().expect("pending lock");
            if pending.contains_key(&id) {
                return Err(RpcError::new(-32600, format!("duplicate request id {id}")));
            }
            pending.insert(id.clone(), tx);
        }
        let msg = json!({"jsonrpc": "2.0", "id": id, "method": method, "params": params});
        if let Err(err) = self.write(&msg).await {
            self.inner.pending.lock().expect("pending lock").remove(&id);
            return Err(err);
        }
        rx.await
            .unwrap_or_else(|_| Err(unavailable("engine stopped")))
    }

    /// Asks the engine to cancel an in-flight request. The request then completes
    /// with a "cancelled" error.
    pub async fn cancel(&self, id: &str) -> Result<(), RpcError> {
        self.write(&json!({"jsonrpc": "2.0", "method": "$/cancelRequest", "params": {"id": id}}))
            .await
    }

    /// Stops the engine (closing its stdin, then killing it after 3 s) and the supervisor.
    pub fn shutdown(&self) {
        let _ = self.inner.shutdown.send(true);
    }

    async fn write(&self, msg: &Value) -> Result<(), RpcError> {
        let mut line = serde_json::to_vec(msg).expect("JSON values always serialize");
        line.push(b'\n');
        let mut guard = self.inner.stdin.lock().await;
        let stdin = guard
            .as_mut()
            .ok_or_else(|| unavailable("engine is not running"))?;
        stdin
            .write_all(&line)
            .await
            .map_err(|e| unavailable(&format!("write to engine failed: {e}")))?;
        stdin
            .flush()
            .await
            .map_err(|e| unavailable(&format!("write to engine failed: {e}")))
    }

    fn set_status(&self, status: EngineStatus) {
        *self.inner.status.lock().expect("status lock") = status.clone();
        self.inner.sink.status(&status);
    }

    fn fail_pending(&self, reason: &str) {
        let drained: Vec<_> = self
            .inner
            .pending
            .lock()
            .expect("pending lock")
            .drain()
            .collect();
        for (_, tx) in drained {
            let _ = tx.send(Err(unavailable(reason)));
        }
    }

    async fn supervise(self) {
        let mut shutdown_rx = self.inner.shutdown.subscribe();
        let mut attempt = 0u32;
        loop {
            if *shutdown_rx.borrow() {
                break;
            }
            self.set_status(EngineStatus::Starting);
            let started = Instant::now();
            let outcome = match self.spawn() {
                Ok(child) => self.run(child, &mut shutdown_rx).await,
                Err(err) => Outcome::Exited(format!(
                    "could not start {}: {err}",
                    self.inner.config.program.display()
                )),
            };
            *self.inner.stdin.lock().await = None;
            self.fail_pending("engine stopped");
            let reason = match outcome {
                Outcome::Shutdown => break,
                Outcome::Fatal(reason) => {
                    log::error!(target: "engine", "{reason}");
                    self.set_status(EngineStatus::Failed { reason });
                    break;
                }
                Outcome::Exited(reason) => reason,
            };
            if started.elapsed() >= self.inner.config.stable_after {
                attempt = 0;
            }
            attempt += 1;
            if attempt > self.inner.config.max_attempts {
                self.set_status(EngineStatus::Failed {
                    reason: format!("the engine keeps stopping: {reason}"),
                });
                break;
            }
            log::warn!(target: "engine", "{reason}; restart attempt {attempt}");
            self.set_status(EngineStatus::Restarting { attempt, reason });
            tokio::select! {
                _ = tokio::time::sleep(backoff(attempt)) => {}
                _ = shutdown_rx.changed() => break,
            }
        }
    }

    fn spawn(&self) -> std::io::Result<Child> {
        let config = &self.inner.config;
        let mut cmd = Command::new(&config.program);
        cmd.args(&config.args)
            .envs(config.env.iter().cloned())
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);
        if let Some(cwd) = &config.cwd {
            cmd.current_dir(cwd);
        }
        #[cfg(windows)]
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW: no console flash
        cmd.spawn()
    }

    async fn run(&self, mut child: Child, shutdown_rx: &mut watch::Receiver<bool>) -> Outcome {
        *self.inner.stdin.lock().await = child.stdin.take();
        if let Some(stderr) = child.stderr.take() {
            tokio::spawn(async move {
                let mut lines = BufReader::new(stderr).lines();
                while let Ok(Some(line)) = lines.next_line().await {
                    log::info!(target: "engine", "{line}");
                }
            });
        }
        let Some(stdout) = child.stdout.take() else {
            return Outcome::Exited("engine has no stdout".into());
        };
        let mut lines = BufReader::new(stdout).lines();
        loop {
            tokio::select! {
                line = lines.next_line() => match line {
                    Ok(Some(line)) => {
                        if let Some(fatal) = self.on_line(&line) {
                            let _ = child.kill().await;
                            return Outcome::Fatal(fatal);
                        }
                    }
                    Ok(None) | Err(_) => break,
                },
                _ = shutdown_rx.changed() => {
                    // EOF on stdin tells the engine to exit; kill it if it lingers.
                    *self.inner.stdin.lock().await = None;
                    if tokio::time::timeout(Duration::from_secs(3), child.wait()).await.is_err() {
                        let _ = child.kill().await;
                    }
                    return Outcome::Shutdown;
                }
            }
        }
        match child.wait().await {
            Ok(status) => Outcome::Exited(format!("engine exited ({status})")),
            Err(err) => Outcome::Exited(format!("engine lost: {err}")),
        }
    }

    /// Handles one stdout line. Returns a reason when the engine must not be restarted.
    fn on_line(&self, line: &str) -> Option<String> {
        match Incoming::parse(line) {
            Incoming::Response { id, result } => {
                let tx = self.inner.pending.lock().expect("pending lock").remove(&id);
                match tx {
                    Some(tx) => {
                        let _ = tx.send(result);
                    }
                    None => log::debug!(target: "engine", "reply for unknown request {id}"),
                }
            }
            Incoming::Notification { method, params } if method == "$/ready" => {
                let protocol = params.get("protocolVersion").and_then(Value::as_u64);
                if protocol != Some(PROTOCOL_VERSION) {
                    return Some(format!(
                        "the engine speaks protocol {}, but this app needs {PROTOCOL_VERSION}; reinstall the app",
                        protocol.map_or("unknown".into(), |p| p.to_string())
                    ));
                }
                let engine_version = params
                    .get("engineVersion")
                    .and_then(Value::as_str)
                    .unwrap_or("unknown")
                    .to_string();
                self.set_status(EngineStatus::Ready {
                    engine_version,
                    protocol_version: PROTOCOL_VERSION,
                });
            }
            Incoming::Notification { method, params } => {
                self.inner.sink.notification(&method, &params);
            }
            Incoming::Request { id, method, params } => {
                let host = self.clone();
                tokio::spawn(async move {
                    let shell = host.inner.shell.clone();
                    let result =
                        tokio::task::spawn_blocking(move || shell.handle(&method, &params))
                            .await
                            .unwrap_or_else(|e| Err(RpcError::new(-32603, e.to_string())));
                    let reply = match result {
                        Ok(value) => json!({"jsonrpc": "2.0", "id": id, "result": value}),
                        Err(err) => json!({"jsonrpc": "2.0", "id": id, "error": err}),
                    };
                    if let Err(err) = host.write(&reply).await {
                        log::warn!(target: "engine", "could not answer engine request: {}", err.message);
                    }
                });
            }
            Incoming::Invalid(why) => log::warn!(target: "engine", "ignoring line: {why}"),
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn backoff_doubles_then_caps() {
        let secs: Vec<u64> = (1..=8).map(|a| backoff(a).as_secs()).collect();
        assert_eq!(secs, vec![1, 2, 4, 8, 16, 30, 30, 30]);
    }

    #[test]
    fn status_serializes_for_the_ui() {
        let ready = EngineStatus::Ready {
            engine_version: "0.1.0".into(),
            protocol_version: 1,
        };
        assert_eq!(
            serde_json::to_value(ready).unwrap(),
            json!({"state": "ready", "engineVersion": "0.1.0", "protocolVersion": 1})
        );
        assert_eq!(
            serde_json::to_value(EngineStatus::Starting).unwrap(),
            json!({"state": "starting"})
        );
    }
}

// SPDX-License-Identifier: AGPL-3.0-or-later
//! Supervisor tests against a fake engine script (needs Python 3 on PATH, or $PYTHON).

use std::sync::{Arc, Mutex};
use std::time::Duration;

use serde_json::{json, Value};
use sfcm_engine_host::{
    EngineConfig, EngineHost, EngineStatus, EventSink, RpcError, ShellHandler, ENGINE_UNAVAILABLE,
};

#[derive(Default)]
struct Recorder {
    statuses: Mutex<Vec<EngineStatus>>,
    notifications: Mutex<Vec<(String, Value)>>,
}

impl EventSink for Recorder {
    fn status(&self, status: &EngineStatus) {
        self.statuses.lock().unwrap().push(status.clone());
    }
    fn notification(&self, method: &str, params: &Value) {
        self.notifications
            .lock()
            .unwrap()
            .push((method.to_string(), params.clone()));
    }
}

struct Secrets;

impl ShellHandler for Secrets {
    fn handle(&self, method: &str, params: &Value) -> Result<Value, RpcError> {
        match method {
            "secrets/get" if params["service"] == "anthropic" => Ok(json!({"value": "sk-test"})),
            _ => Err(RpcError::new(-32601, "unknown")),
        }
    }
}

fn python() -> String {
    std::env::var("PYTHON").unwrap_or_else(|_| {
        if cfg!(windows) {
            "python".into()
        } else {
            "python3".into()
        }
    })
}

fn start(mode: &str) -> (EngineHost, Arc<Recorder>) {
    let script = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/fixtures/fake_engine.py");
    let mut config = EngineConfig::new(python(), vec![script.to_string()]);
    config.env.push(("FAKE_MODE".into(), mode.into()));
    config.max_attempts = 2;
    let sink = Arc::new(Recorder::default());
    let host = EngineHost::start(config, sink.clone(), Arc::new(Secrets));
    (host, sink)
}

async fn wait_for(host: &EngineHost, pred: impl Fn(&EngineStatus) -> bool) -> EngineStatus {
    for _ in 0..200 {
        let status = host.status();
        if pred(&status) {
            return status;
        }
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
    panic!("timed out; last status {:?}", host.status());
}

fn is_ready(s: &EngineStatus) -> bool {
    matches!(s, EngineStatus::Ready { .. })
}

#[tokio::test(flavor = "multi_thread")]
async fn round_trip_and_progress_notifications() {
    let (host, sink) = start("normal");
    wait_for(&host, is_ready).await;
    let result = host
        .request("ui-1".into(), "echo", json!({"hello": "world"}))
        .await;
    assert_eq!(result, Ok(json!({"hello": "world"})));
    let notes = sink.notifications.lock().unwrap().clone();
    assert_eq!(notes[0].0, "$/progress");
    assert_eq!(notes[0].1["requestId"], "ui-1");
    host.shutdown();
}

#[tokio::test(flavor = "multi_thread")]
async fn cancel_ends_a_request() {
    let (host, _) = start("normal");
    wait_for(&host, is_ready).await;
    let pending = {
        let host = host.clone();
        tokio::spawn(async move { host.request("ui-slow".into(), "slow", json!({})).await })
    };
    tokio::time::sleep(Duration::from_millis(100)).await;
    host.cancel("ui-slow").await.unwrap();
    let result = tokio::time::timeout(Duration::from_secs(1), pending)
        .await
        .expect("cancel answered within a second")
        .unwrap();
    assert_eq!(result.unwrap_err().code, -32800);
    host.shutdown();
}

#[tokio::test(flavor = "multi_thread")]
async fn engine_can_ask_the_shell_for_a_secret() {
    let (host, _) = start("normal");
    wait_for(&host, is_ready).await;
    let result = host.request("ui-2".into(), "ask_secret", json!({})).await;
    assert_eq!(result, Ok(json!({"value": "sk-test"})));
    host.shutdown();
}

#[tokio::test(flavor = "multi_thread")]
async fn crash_restarts_and_fails_in_flight_requests() {
    let (host, sink) = start("normal");
    wait_for(&host, is_ready).await;
    let err = host
        .request("ui-3".into(), "crash", json!({}))
        .await
        .unwrap_err();
    assert_eq!(err.code, ENGINE_UNAVAILABLE);
    wait_for(&host, |s| {
        matches!(s, EngineStatus::Restarting { attempt: 1, .. })
    })
    .await;
    wait_for(&host, is_ready).await;
    assert_eq!(
        host.request("ui-4".into(), "echo", json!(1)).await,
        Ok(json!(1))
    );
    let statuses = sink.statuses.lock().unwrap().clone();
    assert!(statuses
        .iter()
        .any(|s| matches!(s, EngineStatus::Restarting { .. })));
    host.shutdown();
}

#[tokio::test(flavor = "multi_thread")]
async fn protocol_mismatch_fails_without_restarting() {
    let (host, sink) = start("bad_protocol");
    let status = wait_for(&host, |s| matches!(s, EngineStatus::Failed { .. })).await;
    let EngineStatus::Failed { reason } = status else {
        unreachable!()
    };
    assert!(reason.contains("protocol 999"), "{reason}");
    tokio::time::sleep(Duration::from_millis(300)).await;
    assert!(!sink
        .statuses
        .lock()
        .unwrap()
        .iter()
        .any(|s| matches!(s, EngineStatus::Restarting { .. })));
}

#[tokio::test(flavor = "multi_thread")]
async fn missing_program_gives_up_after_max_attempts() {
    let mut config = EngineConfig::new("/definitely/not/a/real/engine", vec![]);
    config.max_attempts = 1;
    let host = EngineHost::start(config, Arc::new(Recorder::default()), Arc::new(Secrets));
    let status = wait_for(&host, |s| matches!(s, EngineStatus::Failed { .. })).await;
    assert!(
        matches!(status, EngineStatus::Failed { reason } if reason.contains("could not start"))
    );
}

#[tokio::test(flavor = "multi_thread")]
async fn requests_before_ready_are_rejected() {
    let mut config = EngineConfig::new("/definitely/not/a/real/engine", vec![]);
    config.max_attempts = 0;
    let host = EngineHost::start(config, Arc::new(Recorder::default()), Arc::new(Secrets));
    let err = host
        .request("x".into(), "echo", json!({}))
        .await
        .unwrap_err();
    assert_eq!(err.code, ENGINE_UNAVAILABLE);
}

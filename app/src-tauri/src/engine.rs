// SPDX-License-Identifier: AGPL-3.0-or-later
//! Finds the engine for this build and connects it to the window (roadmap A06).

use std::error::Error;
use std::path::PathBuf;
use std::sync::Arc;

use serde_json::{json, Value};
use sfcm_engine_host::{EngineConfig, EngineHost, EngineStatus, EventSink};
use tauri::{AppHandle, Emitter, Manager};

use crate::secrets::KeychainShell;

pub const STATUS_EVENT: &str = "engine://status";
pub const NOTIFICATION_EVENT: &str = "engine://notification";

struct WindowSink(AppHandle);

impl EventSink for WindowSink {
    fn status(&self, status: &EngineStatus) {
        let _ = self.0.emit(STATUS_EVENT, status);
    }
    fn notification(&self, method: &str, params: &Value) {
        let _ = self.0.emit(
            NOTIFICATION_EVENT,
            json!({"method": method, "params": params}),
        );
    }
}

/// How to launch the engine:
/// - `SFCM_ENGINE_CMD` (whitespace-separated) overrides everything, for debugging;
/// - debug builds run the source checkout through `uv`;
/// - release builds run the PyInstaller bundle shipped as a resource.
fn engine_config(app: &AppHandle) -> Result<EngineConfig, Box<dyn Error>> {
    if let Ok(cmd) = std::env::var("SFCM_ENGINE_CMD") {
        let mut parts = cmd.split_whitespace().map(String::from);
        let program = parts.next().ok_or("SFCM_ENGINE_CMD is empty")?;
        return Ok(EngineConfig::new(program, parts.collect()));
    }
    if cfg!(debug_assertions) {
        let engine_dir = PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/../../engine"));
        return Ok(EngineConfig::new(
            "uv",
            vec![
                "run".into(),
                "--project".into(),
                engine_dir.display().to_string(),
                "python".into(),
                "-m".into(),
                "sfcm_engine".into(),
            ],
        ));
    }
    let exe = if cfg!(windows) {
        "sfcm-engine.exe"
    } else {
        "sfcm-engine"
    };
    let path = app.path().resource_dir()?.join("engine").join(exe);
    Ok(EngineConfig::new(path, Vec::new()))
}

pub fn start(app: &AppHandle) -> Result<EngineHost, Box<dyn Error>> {
    let mut config = engine_config(app)?;
    let data_dir = app.path().app_data_dir()?;
    config
        .env
        .push(("SFCM_DATA_DIR".into(), data_dir.display().to_string()));
    let sink = Arc::new(WindowSink(app.clone()));
    // EngineHost::start spawns Tokio tasks, so it must run inside Tauri's runtime.
    let host = tauri::async_runtime::block_on(async move {
        EngineHost::start(config, sink, Arc::new(KeychainShell))
    });
    Ok(host)
}

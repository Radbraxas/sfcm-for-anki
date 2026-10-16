// SPDX-License-Identifier: AGPL-3.0-or-later
//! Commands the webview can call. Keep this list short: every command is attack
//! surface for content rendered in the UI.

use serde_json::Value;
use sfcm_engine_host::{EngineHost, EngineStatus, RpcError};
use tauri::State;

use crate::secrets;

/// Forwards one JSON-RPC request to the engine. `request_id` is chosen by the UI so
/// it can cancel the request and match `$/progress` notifications to it.
#[tauri::command]
pub async fn engine_request(
    host: State<'_, EngineHost>,
    method: String,
    params: Value,
    request_id: String,
) -> Result<Value, RpcError> {
    host.request(request_id, &method, params).await
}

#[tauri::command]
pub async fn engine_cancel(
    host: State<'_, EngineHost>,
    request_id: String,
) -> Result<(), RpcError> {
    host.cancel(&request_id).await
}

#[tauri::command]
pub fn engine_status(host: State<'_, EngineHost>) -> EngineStatus {
    host.status()
}

async fn blocking<T: Send + 'static>(
    f: impl FnOnce() -> Result<T, String> + Send + 'static,
) -> Result<T, String> {
    tauri::async_runtime::spawn_blocking(f)
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
pub async fn secrets_set(service: String, value: String) -> Result<(), String> {
    blocking(move || secrets::set(&service, &value)).await
}

#[tauri::command]
pub async fn secrets_delete(service: String) -> Result<(), String> {
    blocking(move || secrets::delete(&service)).await
}

/// Whether a key is stored. Never returns the key itself to the webview.
#[tauri::command]
pub async fn secrets_has(service: String) -> Result<bool, String> {
    blocking(move || secrets::get(&service).map(|v| v.is_some())).await
}

// SPDX-License-Identifier: AGPL-3.0-or-later
//! SFCM for Anki desktop shell (roadmap A03).
//!
//! The shell owns the window, the OS keychain and the engine process. It never
//! parses documents or calls AI providers: that is the Python engine's job.

mod commands;
mod engine;
mod secrets;

use sfcm_engine_host::EngineHost;
use tauri::Manager;

pub fn run() {
    tauri::Builder::default()
        .plugin(
            tauri_plugin_log::Builder::new()
                .level(log::LevelFilter::Info)
                .build(),
        )
        .setup(|app| {
            let host = engine::start(app.handle())?;
            app.manage(host);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::engine_request,
            commands::engine_cancel,
            commands::engine_status,
            commands::secrets_set,
            commands::secrets_delete,
            commands::secrets_has,
        ])
        .build(tauri::generate_context!())
        .expect("error while building SFCM for Anki")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                if let Some(host) = app.try_state::<EngineHost>() {
                    host.shutdown();
                }
            }
        });
}

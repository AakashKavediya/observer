pub mod commands;
pub mod mouse_controller;
pub mod os_signals;
pub mod settings;
pub mod sidecar;

use commands::*;
use mouse_controller::NativeMouseController;
use os_signals::OsSignalCollector;
use settings::SettingsManager;
use sidecar::SidecarManager;
#[cfg(debug_assertions)]
use tauri::Manager;

use std::sync::Arc;
use std::thread;
use std::time::Duration;

pub fn run() {
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .init();

    println!("[Observer] Initializing Observer desktop core...");

    let settings_mgr = SettingsManager::new();
    let signal_collector = Arc::new(OsSignalCollector::new());
    let mouse_controller = Arc::new(NativeMouseController::new());
    let sidecar_manager = Arc::new(SidecarManager::new(mouse_controller.clone()));

    let sidecar_for_os_signals = sidecar_manager.clone();
    let collector_for_thread = signal_collector.clone();

    let sidecar_for_setup = sidecar_manager.clone();

    tauri::Builder::default()
        .manage(settings_mgr)
        .manage(sidecar_manager)
        .manage(signal_collector)
        .manage(mouse_controller)
        .setup(move |app| {
            println!("[Observer] App setup complete. Starting sidecar manager...");
            sidecar_for_setup.start(app.handle().clone());

            #[cfg(debug_assertions)]
            {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.open_devtools();
                }
            }

            // Periodic OS signals worker: polls every 1s, sends to engine & emits to frontend
            let app_handle = app.handle().clone();
            thread::spawn(move || {
                loop {
                    thread::sleep(Duration::from_secs(1));
                    let payload = collector_for_thread.collect_signals();
                    if let Ok(json_str) = serde_json::to_string(&payload) {
                        let _ = sidecar_for_os_signals.send_line(&json_str);
                    }
                    use tauri::Emitter;
                    let _ = app_handle.emit("os_signals", payload);
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            send_engine_command,
            delete_all_data,
            load_settings,
            save_settings,
            record_ui_activity,
            native_mouse_move,
            native_mouse_click,
            native_mouse_scroll,
            check_accessibility_permission,
            native_mouse_emergency_stop
        ])
        .run(tauri::generate_context!())
        .expect("error while running observer application");
}

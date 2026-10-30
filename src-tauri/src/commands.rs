//! commands.rs
//! Tauri commands callable from the React UI.

use crate::mouse_controller::{NativeMouseController, PermissionStatus};
use crate::settings::{AppSettings, SettingsManager};
use crate::sidecar::SidecarManager;
use std::sync::Arc;
use tauri::State;

#[tauri::command]
pub fn send_engine_command(
    command: serde_json::Value,
    sidecar: State<'_, Arc<SidecarManager>>,
) -> Result<(), String> {
    let serialized = serde_json::to_string(&command)
        .map_err(|e| format!("Command serialization failed: {}", e))?;
    sidecar.send_line(&serialized)
}

#[tauri::command]
pub fn delete_all_data(
    settings_mgr: State<'_, SettingsManager>,
    sidecar: State<'_, Arc<SidecarManager>>,
) -> Result<(), String> {
    // Notify engine to delete internal calibration state
    let _ = sidecar.send_line("{\"schema_version\":\"1.0.0\",\"type\":\"command\",\"name\":\"delete_all_data\"}");
    // Wipe local host JSON data
    settings_mgr.delete_all_data()
}

#[tauri::command]
pub fn load_settings(settings_mgr: State<'_, SettingsManager>) -> AppSettings {
    settings_mgr.load_settings()
}

#[tauri::command]
pub fn record_ui_activity(
    event_type: String,
    signal_collector: State<'_, Arc<crate::os_signals::OsSignalCollector>>,
) -> Result<(), String> {
    signal_collector.record_input_event(&event_type);
    Ok(())
}

#[tauri::command]
pub fn save_settings(
    settings: AppSettings,
    settings_mgr: State<'_, SettingsManager>,
    sidecar: State<'_, Arc<SidecarManager>>,
) -> Result<(), String> {
    let res = settings_mgr.save_settings(&settings);
    // Forward updated settings to engine
    let forward_cmd = serde_json::json!({
        "schema_version": "1.0.0",
        "type": "command",
        "name": "set_settings",
        "settings": settings
    });
    let _ = sidecar.send_line(&forward_cmd.to_string());
    res
}

#[tauri::command]
pub fn native_mouse_move(
    norm_x: f64,
    norm_y: f64,
    mouse: State<'_, Arc<NativeMouseController>>,
) -> Result<(), String> {
    mouse.move_cursor(norm_x, norm_y)
}

#[tauri::command]
pub fn native_mouse_click(
    button: String,
    double: bool,
    mouse: State<'_, Arc<NativeMouseController>>,
) -> Result<(), String> {
    mouse.click(&button, double)
}

#[tauri::command]
pub fn native_mouse_scroll(
    delta_y: i32,
    mouse: State<'_, Arc<NativeMouseController>>,
) -> Result<(), String> {
    mouse.scroll(delta_y)
}

#[tauri::command]
pub fn check_accessibility_permission(
    mouse: State<'_, Arc<NativeMouseController>>,
) -> PermissionStatus {
    mouse.check_permission()
}

#[tauri::command]
pub fn native_type_text(
    text: String,
    mouse: State<'_, Arc<NativeMouseController>>,
) -> Result<(), String> {
    mouse.type_text(&text)
}

#[tauri::command]
pub fn native_key_press(
    key: String,
    mouse: State<'_, Arc<NativeMouseController>>,
) -> Result<(), String> {
    mouse.press_key(&key)
}

#[tauri::command]
pub fn native_key_combo(
    combo: String,
    mouse: State<'_, Arc<NativeMouseController>>,
) -> Result<(), String> {
    mouse.key_combo(&combo)
}

#[tauri::command]
pub fn native_mouse_emergency_stop(
    mouse: State<'_, Arc<NativeMouseController>>,
    sidecar: State<'_, Arc<SidecarManager>>,
) -> Result<(), String> {
    mouse.set_emergency_stop(true);
    let stop_cmd = serde_json::json!({
        "schema_version": "1.0.0",
        "type": "command",
        "name": "emergency_stop"
    });
    let _ = sidecar.send_line(&stop_cmd.to_string());
    Ok(())
}


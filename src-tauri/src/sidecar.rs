//! sidecar.rs
//! Manages the lifecycle of the Python observer-engine sidecar:
//! - Spawns child process with piped stdin/stdout/stderr
//! - Emits NDJSON lines over Tauri event bus
//! - Forwards UI commands to child stdin
//! - Auto-restarts on crash with backoff
//! - Cleanly kills child on shutdown or drop

use crate::mouse_controller::NativeMouseController;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;
use tauri::{AppHandle, Emitter};

pub struct SidecarManager {
    stdin_writer: Arc<Mutex<Option<ChildStdin>>>,
    running: Arc<AtomicBool>,
    child_handle: Arc<Mutex<Option<Child>>>,
    pub mouse_controller: Arc<NativeMouseController>,
}

impl SidecarManager {
    pub fn new(mouse_controller: Arc<NativeMouseController>) -> Self {
        Self {
            stdin_writer: Arc::new(Mutex::new(None)),
            running: Arc::new(AtomicBool::new(true)),
            child_handle: Arc::new(Mutex::new(None)),
            mouse_controller,
        }
    }

    fn resolve_engine_command() -> (String, Vec<String>) {
        // 1. Check for bundled production sidecar executable
        let target_triple = if cfg!(target_os = "windows") {
            "x86_64-pc-windows-msvc"
        } else if cfg!(target_os = "macos") {
            "x86_64-apple-darwin"
        } else {
            "x86_64-unknown-linux-gnu"
        };

        let exe_name = if cfg!(target_os = "windows") {
            format!("observer-engine-{}.exe", target_triple)
        } else {
            format!("observer-engine-{}", target_triple)
        };

        // Check relative to current exe or workspace
        let possible_bins = vec![
            PathBuf::from(&exe_name),
            PathBuf::from("bin").join(&exe_name),
            PathBuf::from("../engine/dist/observer_engine/observer_engine.exe"),
            PathBuf::from("engine/dist/observer_engine/observer_engine.exe"),
        ];

        for p in possible_bins {
            if p.exists() {
                return (p.to_string_lossy().to_string(), vec![]);
            }
        }

        // 2. Development fallback: invoke python directly with fake/demo engine
        let python_cmd = if cfg!(target_os = "windows") {
            "python".to_string()
        } else if Path::new("/usr/local/bin/python3").exists() {
            "/usr/local/bin/python3".to_string()
        } else if Path::new("/opt/homebrew/bin/python3").exists() {
            "/opt/homebrew/bin/python3".to_string()
        } else {
            "python3".to_string()
        };

        let known_abs_engine = Path::new("/Users/admin/Documents/Drishti/observer/engine/observer_engine/main.py");

        let engine_script = if known_abs_engine.exists() {
            known_abs_engine.to_string_lossy().to_string()
        } else if Path::new("engine/observer_engine/main.py").exists() {
            "engine/observer_engine/main.py".to_string()
        } else if Path::new("../engine/observer_engine/main.py").exists() {
            "../engine/observer_engine/main.py".to_string()
        } else {
            "observer_engine/main.py".to_string()
        };

        (
            python_cmd,
            vec!["-u".to_string(), engine_script, "--live".to_string()],
        )
    }

    pub fn start(&self, app: AppHandle) {
        let running = self.running.clone();
        let stdin_writer = self.stdin_writer.clone();
        let child_handle = self.child_handle.clone();
        let mouse_controller = self.mouse_controller.clone();

        thread::spawn(move || {
            let mut backoff_secs = 1u64;

            while running.load(Ordering::SeqCst) {
                let (program, args) = Self::resolve_engine_command();
                println!("[Sidecar] Launching sidecar: {} {:?}", program, args);

                let mut cmd = Command::new(&program);
                cmd.args(&args)
                    .stdin(Stdio::piped())
                    .stdout(Stdio::piped())
                    .stderr(Stdio::piped());

                let current_path = std::env::var("PATH").unwrap_or_default();
                let full_path = format!("/usr/local/bin:/opt/homebrew/bin:{}", current_path);
                cmd.env("PATH", full_path);
                cmd.env("PYTHONUNBUFFERED", "1");

                let workspace_engine = Path::new("/Users/admin/Documents/Drishti/observer/engine");
                if workspace_engine.exists() {
                    cmd.env("PYTHONPATH", workspace_engine);
                    cmd.current_dir("/Users/admin/Documents/Drishti/observer");
                }

                match cmd.spawn() {
                    Ok(mut child) => {
                        println!("[Sidecar] Spawned child PID: {}", child.id());

                        if let Some(stdin) = child.stdin.take() {
                            let mut writer = stdin_writer.lock().unwrap();
                            *writer = Some(stdin);
                        }

                        let stdout = child.stdout.take();
                        let stderr = child.stderr.take();

                        // Stdout forwarding thread
                        let app_clone = app.clone();
                        let mouse_for_stdout = mouse_controller.clone();
                        let stdout_thread = thread::spawn(move || {
                            if let Some(out) = stdout {
                                let reader = BufReader::new(out);
                                for line in reader.lines() {
                                    if let Ok(l) = line {
                                        let trimmed = l.trim();
                                        if !trimmed.is_empty() {
                                            match serde_json::from_str::<serde_json::Value>(trimmed) {
                                                Ok(val) => {
                                                    let event_type = val.get("type").and_then(|t| t.as_str()).unwrap_or("unknown");
                                                    // Handle native cursor movement and input from sidecar events directly for ultra-low latency
                                                    if let Some(name) = val.get("name").and_then(|n| n.as_str()) {
                                                        match name {
                                                            "gaze_cursor_move" => {
                                                                if let (Some(x), Some(y)) = (
                                                                    val.get("norm_x").and_then(|v| v.as_f64()),
                                                                    val.get("norm_y").and_then(|v| v.as_f64()),
                                                                ) {
                                                                    let _ = mouse_for_stdout.move_cursor(x, y);
                                                                }
                                                            }
                                                            "gaze_cursor_click" => {
                                                                let button = val.get("button").and_then(|v| v.as_str()).unwrap_or("left");
                                                                let double = val.get("double").and_then(|v| v.as_bool()).unwrap_or(false);
                                                                let _ = mouse_for_stdout.click(button, double);
                                                            }
                                                            "gaze_cursor_scroll" => {
                                                                let delta_y = val.get("delta_y").and_then(|v| v.as_i64()).unwrap_or(0) as i32;
                                                                let _ = mouse_for_stdout.scroll(delta_y);
                                                            }
                                                            "native_type_text" => {
                                                                if let Some(text) = val.get("text").and_then(|v| v.as_str()) {
                                                                    let _ = mouse_for_stdout.type_text(text);
                                                                }
                                                            }
                                                            "native_key_combo" => {
                                                                if let Some(combo) = val.get("combo").and_then(|v| v.as_str()) {
                                                                    let _ = mouse_for_stdout.key_combo(combo);
                                                                }
                                                            }
                                                            "native_key_press" => {
                                                                if let Some(key) = val.get("key").and_then(|v| v.as_str()) {
                                                                    let _ = mouse_for_stdout.press_key(key);
                                                                }
                                                            }
                                                            _ => {}
                                                        }
                                                    }
                                                    if let Err(e) = app_clone.emit("engine://event", &val) {
                                                        eprintln!("[Sidecar Emit Error] Failed to emit {}: {:?}", event_type, e);
                                                    }
                                                }
                                                Err(e) => {
                                                    eprintln!("[Sidecar JSON Parse Error] {}: {}", e, trimmed);
                                                }
                                            }
                                        }
                                    } else {
                                        break;
                                    }
                                }
                            }
                        });

                        // Stderr logging thread
                        let stderr_thread = thread::spawn(move || {
                            if let Some(err) = stderr {
                                let reader = BufReader::new(err);
                                for line in reader.lines() {
                                    if let Ok(l) = line {
                                        eprintln!("[Sidecar Error] {}", l);
                                    }
                                }
                            }
                        });

                        {
                            let mut handle = child_handle.lock().unwrap();
                            *handle = Some(child);
                        }

                        let _ = stdout_thread.join();
                        let _ = stderr_thread.join();

                        // Child exited
                        println!("[Sidecar] Child process exited.");
                        {
                            let mut writer = stdin_writer.lock().unwrap();
                            *writer = None;
                        }

                        if !running.load(Ordering::SeqCst) {
                            break;
                        }

                        // Emit crash event to UI
                        let crash_event = serde_json::json!({
                            "schema_version": "1.0.0",
                            "type": "error",
                            "code": "SIDECAR_CRASHED",
                            "message_friendly": "The background engine stopped unexpectedly. Restarting in a moment..."
                        });
                        let _ = app.emit("engine://event", crash_event);

                        // Backoff before restart
                        thread::sleep(Duration::from_secs(backoff_secs));
                        backoff_secs = (backoff_secs * 2).min(16);
                    }
                    Err(e) => {
                        eprintln!("[Sidecar] Failed to spawn {}: {}", program, e);
                        thread::sleep(Duration::from_secs(backoff_secs));
                        backoff_secs = (backoff_secs * 2).min(16);
                    }
                }
            }
        });
    }

    pub fn send_line(&self, json_str: &str) -> Result<(), String> {
        let mut writer_lock = self.stdin_writer.lock().unwrap();
        if let Some(ref mut stdin) = *writer_lock {
            writeln!(stdin, "{}", json_str)
                .and_then(|_| stdin.flush())
                .map_err(|e| format!("Failed to write to sidecar stdin: {}", e))
        } else {
            Err("Sidecar stdin is not connected".to_string())
        }
    }

    pub fn stop(&self) {
        self.running.store(false, Ordering::SeqCst);
        let _ = self.send_line("{\"schema_version\":\"1.0.0\",\"type\":\"command\",\"name\":\"shutdown\"}");

        // Wait a short moment then kill if still alive
        thread::sleep(Duration::from_millis(200));
        let mut child_lock = self.child_handle.lock().unwrap();
        if let Some(ref mut child) = *child_lock {
            let _ = child.kill();
        }
    }
}

impl Drop for SidecarManager {
    fn drop(&mut self) {
        self.stop();
    }
}

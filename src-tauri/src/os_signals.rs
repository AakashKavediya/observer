//! os_signals.rs
//! Gathers aggregate OS context signals:
//! 1. Inactivity timers (idle_seconds, seconds_since_last_key, seconds_since_last_mouse)
//! 2. Activity counts over a sliding window
//! 3. Window switch counts over the last 60 seconds (handle changes only)
//!
//! STRICT PRIVACY RULES:
//! - NEVER reads window titles, process names, executable paths, or screen contents.
//! - NEVER logs or inspects keystroke characters.
//! - Platform-aware: Uses Windows GetLastInputInfo on Windows, and CoreGraphics on macOS.

use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OsSignalsPayload {
    pub schema_version: String,
    pub r#type: String,
    pub seq: u64,
    pub ts: f64,
    pub idle_seconds: f64,
    pub seconds_since_last_key: f64,
    pub seconds_since_last_mouse: f64,
    pub seconds_since_last_scroll: f64,
    pub key_count_window: usize,
    pub mouse_move_count_window: usize,
    pub mouse_click_count_window: usize,
    pub mouse_scroll_count_window: usize,
    pub window_switch_count: usize,
    pub productive_input_score: f64,
    pub fullscreen_media: bool,
    pub monitor_status: String,
}

pub struct OsSignalCollector {
    state: Arc<Mutex<CollectorState>>,
}

struct CollectorState {
    seq: u64,
    #[allow(dead_code)]
    last_handle: usize,
    switch_timestamps: VecDeque<Instant>,

    // Activity timestamp tracking
    last_key_time: Instant,
    last_mouse_time: Instant,
    last_scroll_time: Instant,

    // Rolling window activity counts (last 60s)
    key_events_60s: VecDeque<Instant>,
    mouse_move_events_60s: VecDeque<Instant>,
    mouse_click_events_60s: VecDeque<Instant>,
    mouse_scroll_events_60s: VecDeque<Instant>,
}

impl OsSignalCollector {
    pub fn new() -> Self {
        let now = Instant::now();
        Self {
            state: Arc::new(Mutex::new(CollectorState {
                seq: 0,
                last_handle: 0,
                switch_timestamps: VecDeque::new(),
                last_key_time: now,
                last_mouse_time: now,
                last_scroll_time: now,
                key_events_60s: VecDeque::new(),
                mouse_move_events_60s: VecDeque::new(),
                mouse_click_events_60s: VecDeque::new(),
                mouse_scroll_events_60s: VecDeque::new(),
            })),
        }
    }

    /// Record a local user interaction event from UI or window listener
    pub fn record_input_event(&self, event_type: &str) {
        let mut st = self.state.lock().unwrap();
        let now = Instant::now();
        match event_type {
            "key" => {
                st.last_key_time = now;
                st.key_events_60s.push_back(now);
            }
            "mouse_move" => {
                st.last_mouse_time = now;
                st.mouse_move_events_60s.push_back(now);
            }
            "mouse_click" => {
                st.last_mouse_time = now;
                st.mouse_click_events_60s.push_back(now);
            }
            "scroll" => {
                st.last_scroll_time = now;
                st.mouse_scroll_events_60s.push_back(now);
            }
            _ => {}
        }
    }

    #[cfg(windows)]
    pub fn get_os_idle_seconds(&self) -> f64 {
        use windows::Win32::System::SystemInformation::GetTickCount;
        use windows::Win32::UI::Input::KeyboardAndMouse::{GetLastInputInfo, LASTINPUTINFO};

        unsafe {
            let mut lii = LASTINPUTINFO {
                cbSize: std::mem::size_of::<LASTINPUTINFO>() as u32,
                dwTime: 0,
            };
            if GetLastInputInfo(&mut lii).as_bool() {
                let current_tick = GetTickCount();
                let elapsed_ms = current_tick.saturating_sub(lii.dwTime);
                (elapsed_ms as f64) / 1000.0
            } else {
                0.0
            }
        }
    }

    #[cfg(target_os = "macos")]
    pub fn get_os_idle_seconds(&self) -> f64 {
        // Query native macOS CoreGraphics framework for genuine system-wide idle time
        #[link(name = "CoreGraphics", kind = "framework")]
        extern "C" {
            fn CGEventSourceSecondsSinceLastEventType(source_state_id: i32, event_type: u32) -> f64;
        }

        // kCGEventSourceStateCombinedSessionState = 0
        // kCGAnyInputEventType = 0xFFFFFFFF
        unsafe {
            let idle = CGEventSourceSecondsSinceLastEventType(0, 0xFFFFFFFF);
            if idle.is_finite() && idle >= 0.0 {
                idle
            } else {
                0.0
            }
        }
    }

    #[cfg(all(not(windows), not(target_os = "macos")))]
    pub fn get_os_idle_seconds(&self) -> f64 {
        let st = self.state.lock().unwrap();
        let idle_k = st.last_key_time.elapsed().as_secs_f64();
        let idle_m = st.last_mouse_time.elapsed().as_secs_f64();
        idle_k.min(idle_m)
    }

    #[cfg(target_os = "macos")]
    pub fn get_key_idle_seconds(&self) -> f64 {
        #[link(name = "CoreGraphics", kind = "framework")]
        extern "C" {
            fn CGEventSourceSecondsSinceLastEventType(source_state_id: i32, event_type: u32) -> f64;
        }
        // kCGEventKeyDown = 10
        unsafe {
            let val = CGEventSourceSecondsSinceLastEventType(0, 10);
            if val.is_finite() && val >= 0.0 { val } else { 0.0 }
        }
    }

    #[cfg(not(target_os = "macos"))]
    pub fn get_key_idle_seconds(&self) -> f64 {
        let st = self.state.lock().unwrap();
        st.last_key_time.elapsed().as_secs_f64()
    }

    #[cfg(target_os = "macos")]
    pub fn get_mouse_idle_seconds(&self) -> f64 {
        #[link(name = "CoreGraphics", kind = "framework")]
        extern "C" {
            fn CGEventSourceSecondsSinceLastEventType(source_state_id: i32, event_type: u32) -> f64;
        }
        // kCGEventLeftMouseDown = 1, kCGEventMouseMoved = 5
        unsafe {
            let move_val = CGEventSourceSecondsSinceLastEventType(0, 5);
            let click_val = CGEventSourceSecondsSinceLastEventType(0, 1);
            let val = move_val.min(click_val);
            if val.is_finite() && val >= 0.0 { val } else { 0.0 }
        }
    }

    #[cfg(not(target_os = "macos"))]
    pub fn get_mouse_idle_seconds(&self) -> f64 {
        let st = self.state.lock().unwrap();
        st.last_mouse_time.elapsed().as_secs_f64()
    }

    #[cfg(windows)]
    pub fn poll_active_window(&self) {
        use windows::Win32::UI::WindowsAndMessaging::GetForegroundWindow;

        let hwnd = unsafe { GetForegroundWindow() };
        let handle_val = hwnd.0 as usize;

        let mut st = self.state.lock().unwrap();
        let now = Instant::now();

        // Prune switches older than 60 seconds
        while let Some(&ts) = st.switch_timestamps.front() {
            if now.duration_since(ts).as_secs() > 60 {
                st.switch_timestamps.pop_front();
            } else {
                break;
            }
        }

        if handle_val != 0 && handle_val != st.last_handle {
            st.last_handle = handle_val;
            st.switch_timestamps.push_back(now);
        }
    }

    #[cfg(not(windows))]
    pub fn poll_active_window(&self) {
        let mut st = self.state.lock().unwrap();
        let now = Instant::now();
        while let Some(&ts) = st.switch_timestamps.front() {
            if now.duration_since(ts).as_secs() > 60 {
                st.switch_timestamps.pop_front();
            } else {
                break;
            }
        }
    }

    pub fn collect_signals(&self) -> OsSignalsPayload {
        self.poll_active_window();

        let os_idle = self.get_os_idle_seconds();
        let key_idle = self.get_key_idle_seconds();
        let mouse_idle = self.get_mouse_idle_seconds();

        let mut st = self.state.lock().unwrap();
        st.seq += 1;
        let seq = st.seq;

        let now_inst = Instant::now();
        let prune_cutoff = Duration::from_secs(60);

        // Prune 60s activity queues
        let prune_queue = |q: &mut VecDeque<Instant>| {
            while let Some(&t) = q.front() {
                if now_inst.duration_since(t) > prune_cutoff {
                    q.pop_front();
                } else {
                    break;
                }
            }
        };

        prune_queue(&mut st.key_events_60s);
        prune_queue(&mut st.mouse_move_events_60s);
        prune_queue(&mut st.mouse_click_events_60s);
        prune_queue(&mut st.mouse_scroll_events_60s);

        let key_count = st.key_events_60s.len();
        let mouse_move_count = st.mouse_move_events_60s.len();
        let mouse_click_count = st.mouse_click_events_60s.len();
        let mouse_scroll_count = st.mouse_scroll_events_60s.len();
        let window_switches = st.switch_timestamps.len();

        let scroll_idle = st.last_scroll_time.elapsed().as_secs_f64();

        // Effective idle seconds: minimum between OS global idle and tracked inputs
        let effective_idle = os_idle.min(key_idle).min(mouse_idle);

        // Productive input score: 1.0 when active input exists, ramp to 0.0 at 15s idle
        let productive_input_score = (1.0 - (effective_idle / 15.0)).clamp(0.0, 1.0);

        let ts = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64();

        OsSignalsPayload {
            schema_version: "1.0.0".to_string(),
            r#type: "os_signals".to_string(),
            seq,
            ts,
            idle_seconds: effective_idle,
            seconds_since_last_key: key_idle,
            seconds_since_last_mouse: mouse_idle,
            seconds_since_last_scroll: scroll_idle,
            key_count_window: key_count,
            mouse_move_count_window: mouse_move_count,
            mouse_click_count_window: mouse_click_count,
            mouse_scroll_count_window: mouse_scroll_count,
            window_switch_count: window_switches,
            productive_input_score,
            fullscreen_media: false,
            monitor_status: "active".to_string(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_collect_signals_payload_format() {
        let collector = OsSignalCollector::new();
        collector.record_input_event("key");
        collector.record_input_event("mouse_click");

        let signals = collector.collect_signals();
        assert_eq!(signals.schema_version, "1.0.0");
        assert_eq!(signals.r#type, "os_signals");
        assert!(signals.idle_seconds >= 0.0);
        assert_eq!(signals.monitor_status, "active");
        assert_eq!(signals.seq, 1);
    }
}

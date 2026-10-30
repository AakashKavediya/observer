//! mouse_controller.rs
//! Native OS mouse control for Observer Track 4 (Hands-Free Eye-Gaze Mouse).
//! Moves the native desktop mouse cursor, performs clicks and scrolls across macOS and Windows.
//! Includes Accessibility permission checking and safety bounds clamping.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

pub struct NativeMouseController {
    emergency_stopped: Arc<AtomicBool>,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct PermissionStatus {
    pub granted: bool,
    pub message: String,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct ScreenDimensions {
    pub width: f64,
    pub height: f64,
}

impl NativeMouseController {
    pub fn new() -> Self {
        Self {
            emergency_stopped: Arc::new(AtomicBool::new(false)),
        }
    }

    pub fn set_emergency_stop(&self, stopped: bool) {
        self.emergency_stopped.store(stopped, Ordering::SeqCst);
    }

    pub fn is_emergency_stopped(&self) -> bool {
        self.emergency_stopped.load(Ordering::SeqCst)
    }

    /// Check if accessibility permissions are granted on the host OS.
    pub fn check_permission(&self) -> PermissionStatus {
        #[cfg(target_os = "macos")]
        {
            let granted = unsafe { macos_ffi::AXIsProcessTrusted() };
            if granted {
                PermissionStatus {
                    granted: true,
                    message: "macOS Accessibility permission granted.".to_string(),
                }
            } else {
                PermissionStatus {
                    granted: false,
                    message: "macOS Accessibility permission needed. Please enable Observer in System Settings -> Privacy & Security -> Accessibility.".to_string(),
                }
            }
        }
        #[cfg(not(target_os = "macos"))]
        {
            PermissionStatus {
                granted: true,
                message: "Accessibility permissions available.".to_string(),
            }
        }
    }

    /// Get primary display pixel bounds.
    pub fn get_screen_dimensions(&self) -> ScreenDimensions {
        #[cfg(target_os = "macos")]
        {
            unsafe {
                let display_id = macos_ffi::CGMainDisplayID();
                let width = macos_ffi::CGDisplayPixelsWide(display_id) as f64;
                let height = macos_ffi::CGDisplayPixelsHigh(display_id) as f64;
                ScreenDimensions {
                    width: if width > 0.0 { width } else { 1920.0 },
                    height: if height > 0.0 { height } else { 1080.0 },
                }
            }
        }
        #[cfg(target_os = "windows")]
        {
            use windows::Win32::UI::WindowsAndMessaging::{GetSystemMetrics, SM_CXSCREEN, SM_CYSCREEN};
            let width = unsafe { GetSystemMetrics(SM_CXSCREEN) } as f64;
            let height = unsafe { GetSystemMetrics(SM_CYSCREEN) } as f64;
            ScreenDimensions {
                width: if width > 0.0 { width } else { 1920.0 },
                height: if height > 0.0 { height } else { 1080.0 },
            }
        }
        #[cfg(not(any(target_os = "macos", target_os = "windows")))]
        {
            ScreenDimensions { width: 1920.0, height: 1080.0 }
        }
    }

    /// Move the OS mouse pointer given normalized [0.0, 1.0] coordinates.
    pub fn move_cursor(&self, norm_x: f64, norm_y: f64) -> Result<(), String> {
        if self.is_emergency_stopped() {
            return Err("Cursor movement blocked: Emergency stop active".to_string());
        }

        // Clamp to normalized unit interval
        let cx = norm_x.clamp(0.0, 1.0);
        let cy = norm_y.clamp(0.0, 1.0);

        let dims = self.get_screen_dimensions();
        let target_x = (cx * (dims.width - 1.0)).round();
        let target_y = (cy * (dims.height - 1.0)).round();

        #[cfg(target_os = "macos")]
        {
            unsafe {
                let point = macos_ffi::CGPoint { x: target_x, y: target_y };
                let res = macos_ffi::CGWarpMouseCursorPosition(point);
                if res != 0 {
                    // Fallback to posting a mouse moved event
                    let event = macos_ffi::CGEventCreateMouseEvent(
                        std::ptr::null(),
                        macos_ffi::K_CG_EVENT_MOUSE_MOVED,
                        point,
                        macos_ffi::K_CG_MOUSE_BUTTON_LEFT,
                    );
                    if !event.is_null() {
                        macos_ffi::CGEventPost(macos_ffi::K_CG_HID_EVENT_TAP, event);
                        macos_ffi::CFRelease(event);
                    }
                }
            }
            Ok(())
        }
        #[cfg(target_os = "windows")]
        {
            use windows::Win32::UI::WindowsAndMessaging::SetCursorPos;
            let ok = unsafe { SetCursorPos(target_x as i32, target_y as i32) };
            if ok.as_bool() {
                Ok(())
            } else {
                Err("SetCursorPos failed on Windows".to_string())
            }
        }
        #[cfg(not(any(target_os = "macos", target_os = "windows")))]
        {
            let _ = (target_x, target_y);
            Ok(())
        }
    }

    /// Execute a mouse click at the current cursor position.
    pub fn click(&self, button: &str, double: bool) -> Result<(), String> {
        if self.is_emergency_stopped() {
            return Err("Mouse click blocked: Emergency stop active".to_string());
        }

        #[cfg(target_os = "macos")]
        {
            unsafe {
                // Get current cursor location
                let current_event = macos_ffi::CGEventCreate(std::ptr::null());
                let point = if !current_event.is_null() {
                    let pt = macos_ffi::CGEventGetLocation(current_event);
                    macos_ffi::CFRelease(current_event);
                    pt
                } else {
                    macos_ffi::CGPoint { x: 0.0, y: 0.0 }
                };

                let is_right = button.eq_ignore_ascii_case("right");
                let (down_type, up_type, mouse_button) = if is_right {
                    (
                        macos_ffi::K_CG_EVENT_RIGHT_MOUSE_DOWN,
                        macos_ffi::K_CG_EVENT_RIGHT_MOUSE_UP,
                        macos_ffi::K_CG_MOUSE_BUTTON_RIGHT,
                    )
                } else {
                    (
                        macos_ffi::K_CG_EVENT_LEFT_MOUSE_DOWN,
                        macos_ffi::K_CG_EVENT_LEFT_MOUSE_UP,
                        macos_ffi::K_CG_MOUSE_BUTTON_LEFT,
                    )
                };

                let clicks = if double { 2 } else { 1 };
                for click_idx in 1..=clicks {
                    // Down event
                    let down_ev = macos_ffi::CGEventCreateMouseEvent(
                        std::ptr::null(),
                        down_type,
                        point,
                        mouse_button,
                    );
                    if !down_ev.is_null() {
                        macos_ffi::CGEventSetIntegerValueField(
                            down_ev,
                            macos_ffi::K_CG_MOUSE_EVENT_CLICK_STATE,
                            click_idx,
                        );
                        macos_ffi::CGEventPost(macos_ffi::K_CG_HID_EVENT_TAP, down_ev);
                        macos_ffi::CFRelease(down_ev);
                    }

                    std::thread::sleep(std::time::Duration::from_millis(20));

                    // Up event
                    let up_ev = macos_ffi::CGEventCreateMouseEvent(
                        std::ptr::null(),
                        up_type,
                        point,
                        mouse_button,
                    );
                    if !up_ev.is_null() {
                        macos_ffi::CGEventSetIntegerValueField(
                            up_ev,
                            macos_ffi::K_CG_MOUSE_EVENT_CLICK_STATE,
                            click_idx,
                        );
                        macos_ffi::CGEventPost(macos_ffi::K_CG_HID_EVENT_TAP, up_ev);
                        macos_ffi::CFRelease(up_ev);
                    }

                    if double && click_idx == 1 {
                        std::thread::sleep(std::time::Duration::from_millis(50));
                    }
                }
            }
            Ok(())
        }
        #[cfg(target_os = "windows")]
        {
            use windows::Win32::UI::Input::KeyboardAndMouse::{
                SendInput, INPUT, INPUT_MOUSE, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP,
                MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP, MOUSEINPUT,
            };

            let is_right = button.eq_ignore_ascii_case("right");
            let (down_flag, up_flag) = if is_right {
                (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP)
            } else {
                (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)
            };

            let clicks = if double { 2 } else { 1 };
            for click_idx in 0..clicks {
                let mut inputs = [
                    INPUT {
                        r#type: INPUT_MOUSE,
                        Anonymous: windows::Win32::UI::Input::KeyboardAndMouse::INPUT_0 {
                            mi: MOUSEINPUT {
                                dx: 0,
                                dy: 0,
                                mouseData: 0,
                                dwFlags: down_flag,
                                time: 0,
                                dwExtraInfo: 0,
                            },
                        },
                    },
                    INPUT {
                        r#type: INPUT_MOUSE,
                        Anonymous: windows::Win32::UI::Input::KeyboardAndMouse::INPUT_0 {
                            mi: MOUSEINPUT {
                                dx: 0,
                                dy: 0,
                                mouseData: 0,
                                dwFlags: up_flag,
                                time: 0,
                                dwExtraInfo: 0,
                            },
                        },
                    },
                ];

                unsafe {
                    SendInput(&inputs, std::mem::size_of::<INPUT>() as i32);
                }

                if double && click_idx == 0 {
                    std::thread::sleep(std::time::Duration::from_millis(50));
                }
            }
            Ok(())
        }
        #[cfg(not(any(target_os = "macos", target_os = "windows")))]
        {
            let _ = (button, double);
            Ok(())
        }
    }

    /// Scroll vertically by delta lines (positive = up, negative = down).
    pub fn scroll(&self, delta_y: i32) -> Result<(), String> {
        if self.is_emergency_stopped() {
            return Err("Scroll blocked: Emergency stop active".to_string());
        }

        #[cfg(target_os = "macos")]
        {
            unsafe {
                let scroll_ev = macos_ffi::CGEventCreateScrollWheelEvent(
                    std::ptr::null(),
                    macos_ffi::K_CG_SCROLL_EVENT_UNIT_LINE,
                    1,
                    delta_y,
                );
                if !scroll_ev.is_null() {
                    macos_ffi::CGEventPost(macos_ffi::K_CG_HID_EVENT_TAP, scroll_ev);
                    macos_ffi::CFRelease(scroll_ev);
                }
            }
            Ok(())
        }
        #[cfg(target_os = "windows")]
        {
            use windows::Win32::UI::Input::KeyboardAndMouse::{
                SendInput, INPUT, INPUT_MOUSE, MOUSEEVENTF_WHEEL, MOUSEINPUT,
            };

            let input = INPUT {
                r#type: INPUT_MOUSE,
                Anonymous: windows::Win32::UI::Input::KeyboardAndMouse::INPUT_0 {
                    mi: MOUSEINPUT {
                        dx: 0,
                        dy: 0,
                        mouseData: (delta_y * 120) as u32,
                        dwFlags: MOUSEEVENTF_WHEEL,
                        time: 0,
                        dwExtraInfo: 0,
                    },
                },
            };
            unsafe {
                SendInput(&[input], std::mem::size_of::<INPUT>() as i32);
            }
            Ok(())
        }
        #[cfg(not(any(target_os = "macos", target_os = "windows")))]
        {
            let _ = delta_y;
            Ok(())
        }
    }

    /// Type arbitrary Unicode text (e.g., English words, Hindi or Marathi Devanagari script).
    pub fn type_text(&self, text: &str) -> Result<(), String> {
        if self.is_emergency_stopped() {
            return Err("Text typing blocked: Emergency stop active".to_string());
        }

        #[cfg(target_os = "macos")]
        {
            unsafe {
                for ch in text.chars() {
                    let mut utf16_buf = [0u16; 2];
                    let encoded = ch.encode_utf16(&mut utf16_buf);

                    let down_ev = macos_ffi::CGEventCreateKeyboardEvent(std::ptr::null(), 0, true);
                    if !down_ev.is_null() {
                        macos_ffi::CGEventKeyboardSetUnicodeString(
                            down_ev,
                            encoded.len(),
                            encoded.as_ptr(),
                        );
                        macos_ffi::CGEventPost(macos_ffi::K_CG_HID_EVENT_TAP, down_ev);
                        macos_ffi::CFRelease(down_ev);
                    }

                    std::thread::sleep(std::time::Duration::from_millis(15));

                    let up_ev = macos_ffi::CGEventCreateKeyboardEvent(std::ptr::null(), 0, false);
                    if !up_ev.is_null() {
                        macos_ffi::CGEventKeyboardSetUnicodeString(
                            up_ev,
                            encoded.len(),
                            encoded.as_ptr(),
                        );
                        macos_ffi::CGEventPost(macos_ffi::K_CG_HID_EVENT_TAP, up_ev);
                        macos_ffi::CFRelease(up_ev);
                    }

                    std::thread::sleep(std::time::Duration::from_millis(15));
                }
            }
            Ok(())
        }
        #[cfg(target_os = "windows")]
        {
            use windows::Win32::UI::Input::KeyboardAndMouse::{
                SendInput, INPUT, INPUT_KEYBOARD, KEYBDINPUT, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE,
            };

            for ch in text.chars() {
                let mut utf16_buf = [0u16; 2];
                let encoded = ch.encode_utf16(&mut utf16_buf);

                for &code in encoded {
                    let down_input = INPUT {
                        r#type: INPUT_KEYBOARD,
                        Anonymous: windows::Win32::UI::Input::KeyboardAndMouse::INPUT_0 {
                            ki: KEYBDINPUT {
                                wVk: 0,
                                wScan: code,
                                dwFlags: KEYEVENTF_UNICODE,
                                time: 0,
                                dwExtraInfo: 0,
                            },
                        },
                    };
                    let up_input = INPUT {
                        r#type: INPUT_KEYBOARD,
                        Anonymous: windows::Win32::UI::Input::KeyboardAndMouse::INPUT_0 {
                            ki: KEYBDINPUT {
                                wVk: 0,
                                wScan: code,
                                dwFlags: KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
                                time: 0,
                                dwExtraInfo: 0,
                            },
                        },
                    };
                    unsafe {
                        SendInput(&[down_input], std::mem::size_of::<INPUT>() as i32);
                        std::thread::sleep(std::time::Duration::from_millis(15));
                        SendInput(&[up_input], std::mem::size_of::<INPUT>() as i32);
                        std::thread::sleep(std::time::Duration::from_millis(15));
                    }
                }
            }
            Ok(())
        }
        #[cfg(not(any(target_os = "macos", target_os = "windows")))]
        {
            let _ = text;
            Ok(())
        }
    }

    /// Press a special virtual key: "backspace", "enter", "space", "tab", "escape", "left", "right", "up", "down".
    pub fn press_key(&self, key: &str) -> Result<(), String> {
        if self.is_emergency_stopped() {
            return Err("Key press blocked: Emergency stop active".to_string());
        }

        #[cfg(target_os = "macos")]
        {
            let vk: u16 = match key.to_lowercase().as_str() {
                "backspace" | "back" | "delete" => 51,
                "enter" | "return" => 36,
                "space" => 49,
                "tab" => 48,
                "escape" | "esc" => 53,
                "left" => 123,
                "right" => 124,
                "down" => 125,
                "up" => 126,
                _ => return Err(format!("Unsupported special key: {}", key)),
            };

            unsafe {
                let down_ev = macos_ffi::CGEventCreateKeyboardEvent(std::ptr::null(), vk, true);
                if !down_ev.is_null() {
                    macos_ffi::CGEventPost(macos_ffi::K_CG_HID_EVENT_TAP, down_ev);
                    macos_ffi::CFRelease(down_ev);
                }
                std::thread::sleep(std::time::Duration::from_millis(25));
                let up_ev = macos_ffi::CGEventCreateKeyboardEvent(std::ptr::null(), vk, false);
                if !up_ev.is_null() {
                    macos_ffi::CGEventPost(macos_ffi::K_CG_HID_EVENT_TAP, up_ev);
                    macos_ffi::CFRelease(up_ev);
                }
            }
            Ok(())
        }
        #[cfg(target_os = "windows")]
        {
            use windows::Win32::UI::Input::KeyboardAndMouse::{
                SendInput, INPUT, INPUT_KEYBOARD, KEYBDINPUT, KEYEVENTF_KEYUP,
                VK_BACK, VK_RETURN, VK_SPACE, VK_TAB, VK_ESCAPE, VK_LEFT, VK_RIGHT, VK_UP, VK_DOWN,
            };

            let vk = match key.to_lowercase().as_str() {
                "backspace" | "back" | "delete" => VK_BACK.0,
                "enter" | "return" => VK_RETURN.0,
                "space" => VK_SPACE.0,
                "tab" => VK_TAB.0,
                "escape" | "esc" => VK_ESCAPE.0,
                "left" => VK_LEFT.0,
                "right" => VK_RIGHT.0,
                "up" => VK_UP.0,
                "down" => VK_DOWN.0,
                _ => return Err(format!("Unsupported special key: {}", key)),
            };

            let down = INPUT {
                r#type: INPUT_KEYBOARD,
                Anonymous: windows::Win32::UI::Input::KeyboardAndMouse::INPUT_0 {
                    ki: KEYBDINPUT {
                        wVk: windows::Win32::UI::Input::KeyboardAndMouse::VIRTUAL_KEY(vk),
                        wScan: 0,
                        dwFlags: Default::default(),
                        time: 0,
                        dwExtraInfo: 0,
                    },
                },
            };
            let up = INPUT {
                r#type: INPUT_KEYBOARD,
                Anonymous: windows::Win32::UI::Input::KeyboardAndMouse::INPUT_0 {
                    ki: KEYBDINPUT {
                        wVk: windows::Win32::UI::Input::KeyboardAndMouse::VIRTUAL_KEY(vk),
                        wScan: 0,
                        dwFlags: KEYEVENTF_KEYUP,
                        time: 0,
                        dwExtraInfo: 0,
                    },
                },
            };
            unsafe {
                SendInput(&[down], std::mem::size_of::<INPUT>() as i32);
                std::thread::sleep(std::time::Duration::from_millis(25));
                SendInput(&[up], std::mem::size_of::<INPUT>() as i32);
            }
            Ok(())
        }
        #[cfg(not(any(target_os = "macos", target_os = "windows")))]
        {
            let _ = key;
            Ok(())
        }
    }

    /// Execute a standard keyboard navigation shortcut: "tab_left", "tab_right", "browser_back".
    pub fn key_combo(&self, combo: &str) -> Result<(), String> {
        if self.is_emergency_stopped() {
            return Err("Key combo blocked: Emergency stop active".to_string());
        }

        #[cfg(target_os = "macos")]
        {
            unsafe {
                match combo.to_lowercase().as_str() {
                    "tab_left" => {
                        // Cmd+Shift+[ (VK 33) or Ctrl+Shift+Tab (VK 48)
                        let vk = 33u16; // '['
                        let flags = macos_ffi::K_CG_EVENT_FLAG_MASK_COMMAND | macos_ffi::K_CG_EVENT_FLAG_MASK_SHIFT;
                        let down_ev = macos_ffi::CGEventCreateKeyboardEvent(std::ptr::null(), vk, true);
                        if !down_ev.is_null() {
                            macos_ffi::CGEventSetFlags(down_ev, flags);
                            macos_ffi::CGEventPost(macos_ffi::K_CG_HID_EVENT_TAP, down_ev);
                            macos_ffi::CFRelease(down_ev);
                        }
                        std::thread::sleep(std::time::Duration::from_millis(30));
                        let up_ev = macos_ffi::CGEventCreateKeyboardEvent(std::ptr::null(), vk, false);
                        if !up_ev.is_null() {
                            macos_ffi::CGEventSetFlags(up_ev, flags);
                            macos_ffi::CGEventPost(macos_ffi::K_CG_HID_EVENT_TAP, up_ev);
                            macos_ffi::CFRelease(up_ev);
                        }
                    }
                    "tab_right" => {
                        // Cmd+Shift+] (VK 30)
                        let vk = 30u16; // ']'
                        let flags = macos_ffi::K_CG_EVENT_FLAG_MASK_COMMAND | macos_ffi::K_CG_EVENT_FLAG_MASK_SHIFT;
                        let down_ev = macos_ffi::CGEventCreateKeyboardEvent(std::ptr::null(), vk, true);
                        if !down_ev.is_null() {
                            macos_ffi::CGEventSetFlags(down_ev, flags);
                            macos_ffi::CGEventPost(macos_ffi::K_CG_HID_EVENT_TAP, down_ev);
                            macos_ffi::CFRelease(down_ev);
                        }
                        std::thread::sleep(std::time::Duration::from_millis(30));
                        let up_ev = macos_ffi::CGEventCreateKeyboardEvent(std::ptr::null(), vk, false);
                        if !up_ev.is_null() {
                            macos_ffi::CGEventSetFlags(up_ev, flags);
                            macos_ffi::CGEventPost(macos_ffi::K_CG_HID_EVENT_TAP, up_ev);
                            macos_ffi::CFRelease(up_ev);
                        }
                    }
                    "browser_back" | "back" => {
                        // Cmd+[ (VK 33)
                        let vk = 33u16; // '['
                        let flags = macos_ffi::K_CG_EVENT_FLAG_MASK_COMMAND;
                        let down_ev = macos_ffi::CGEventCreateKeyboardEvent(std::ptr::null(), vk, true);
                        if !down_ev.is_null() {
                            macos_ffi::CGEventSetFlags(down_ev, flags);
                            macos_ffi::CGEventPost(macos_ffi::K_CG_HID_EVENT_TAP, down_ev);
                            macos_ffi::CFRelease(down_ev);
                        }
                        std::thread::sleep(std::time::Duration::from_millis(30));
                        let up_ev = macos_ffi::CGEventCreateKeyboardEvent(std::ptr::null(), vk, false);
                        if !up_ev.is_null() {
                            macos_ffi::CGEventSetFlags(up_ev, flags);
                            macos_ffi::CGEventPost(macos_ffi::K_CG_HID_EVENT_TAP, up_ev);
                            macos_ffi::CFRelease(up_ev);
                        }
                    }
                    other => return Err(format!("Unsupported key combo: {}", other)),
                }
            }
            Ok(())
        }
        #[cfg(target_os = "windows")]
        {
            // Windows equivalents: Ctrl+Shift+Tab, Ctrl+Tab, Alt+Left
            use windows::Win32::UI::Input::KeyboardAndMouse::{
                SendInput, INPUT, INPUT_KEYBOARD, KEYBDINPUT, KEYEVENTF_KEYUP,
                VK_CONTROL, VK_SHIFT, VK_TAB, VK_MENU, VK_LEFT,
            };

            let make_ki = |vk: u16, up: bool| INPUT {
                r#type: INPUT_KEYBOARD,
                Anonymous: windows::Win32::UI::Input::KeyboardAndMouse::INPUT_0 {
                    ki: KEYBDINPUT {
                        wVk: windows::Win32::UI::Input::KeyboardAndMouse::VIRTUAL_KEY(vk),
                        wScan: 0,
                        dwFlags: if up { KEYEVENTF_KEYUP } else { Default::default() },
                        time: 0,
                        dwExtraInfo: 0,
                    },
                },
            };

            match combo.to_lowercase().as_str() {
                "tab_left" => {
                    let inputs = [
                        make_ki(VK_CONTROL.0, false),
                        make_ki(VK_SHIFT.0, false),
                        make_ki(VK_TAB.0, false),
                        make_ki(VK_TAB.0, true),
                        make_ki(VK_SHIFT.0, true),
                        make_ki(VK_CONTROL.0, true),
                    ];
                    unsafe { SendInput(&inputs, std::mem::size_of::<INPUT>() as i32); }
                }
                "tab_right" => {
                    let inputs = [
                        make_ki(VK_CONTROL.0, false),
                        make_ki(VK_TAB.0, false),
                        make_ki(VK_TAB.0, true),
                        make_ki(VK_CONTROL.0, true),
                    ];
                    unsafe { SendInput(&inputs, std::mem::size_of::<INPUT>() as i32); }
                }
                "browser_back" | "back" => {
                    let inputs = [
                        make_ki(VK_MENU.0, false),
                        make_ki(VK_LEFT.0, false),
                        make_ki(VK_LEFT.0, true),
                        make_ki(VK_MENU.0, true),
                    ];
                    unsafe { SendInput(&inputs, std::mem::size_of::<INPUT>() as i32); }
                }
                other => return Err(format!("Unsupported key combo: {}", other)),
            }
            Ok(())
        }
        #[cfg(not(any(target_os = "macos", target_os = "windows")))]
        {
            let _ = combo;
            Ok(())
        }
    }
}

// -------------------------------------------------------------
// macOS Native CoreGraphics & ApplicationServices FFI
// -------------------------------------------------------------
#[cfg(target_os = "macos")]
mod macos_ffi {
    use std::ffi::c_void;

    pub const K_CG_HID_EVENT_TAP: u32 = 0;
    pub const K_CG_EVENT_LEFT_MOUSE_DOWN: u32 = 1;
    pub const K_CG_EVENT_LEFT_MOUSE_UP: u32 = 2;
    pub const K_CG_EVENT_RIGHT_MOUSE_DOWN: u32 = 3;
    pub const K_CG_EVENT_RIGHT_MOUSE_UP: u32 = 4;
    pub const K_CG_EVENT_MOUSE_MOVED: u32 = 5;
    pub const K_CG_MOUSE_BUTTON_LEFT: u32 = 0;
    pub const K_CG_MOUSE_BUTTON_RIGHT: u32 = 1;
    pub const K_CG_SCROLL_EVENT_UNIT_LINE: u32 = 1;
    pub const K_CG_MOUSE_EVENT_CLICK_STATE: u32 = 1;
    pub const K_CG_EVENT_FLAG_MASK_SHIFT: u64 = 1 << 17;
    #[allow(dead_code)]
    pub const K_CG_EVENT_FLAG_MASK_CONTROL: u64 = 1 << 18;
    #[allow(dead_code)]
    pub const K_CG_EVENT_FLAG_MASK_ALTERNATE: u64 = 1 << 19;
    pub const K_CG_EVENT_FLAG_MASK_COMMAND: u64 = 1 << 20;

    #[repr(C)]
    #[derive(Clone, Copy, Debug)]
    pub struct CGPoint {
        pub x: f64,
        pub y: f64,
    }

    #[link(name = "CoreGraphics", kind = "framework")]
    #[link(name = "ApplicationServices", kind = "framework")]
    extern "C" {
        pub fn CGMainDisplayID() -> u32;
        pub fn CGDisplayPixelsWide(display: u32) -> usize;
        pub fn CGDisplayPixelsHigh(display: u32) -> usize;
        pub fn CGWarpMouseCursorPosition(new_cursor_position: CGPoint) -> i32;
        pub fn CGEventCreate(source: *const c_void) -> *mut c_void;
        pub fn CGEventGetLocation(event: *mut c_void) -> CGPoint;
        pub fn CGEventCreateMouseEvent(
            source: *const c_void,
            mouse_type: u32,
            mouse_cursor_position: CGPoint,
            mouse_button: u32,
        ) -> *mut c_void;
        pub fn CGEventSetIntegerValueField(event: *mut c_void, field: u32, value: i64);
        pub fn CGEventCreateScrollWheelEvent(
            source: *const c_void,
            units: u32,
            wheel_count: u32,
            wheel1: i32,
        ) -> *mut c_void;
        pub fn CGEventPost(tap: u32, event: *mut c_void);
        pub fn CGEventCreateKeyboardEvent(
            source: *const c_void,
            virtual_key: u16,
            key_down: bool,
        ) -> *mut c_void;
        pub fn CGEventKeyboardSetUnicodeString(
            event: *mut c_void,
            string_length: usize,
            unicode_string: *const u16,
        );
        pub fn CGEventSetFlags(event: *mut c_void, flags: u64);
        pub fn CFRelease(cf: *const c_void);
        pub fn AXIsProcessTrusted() -> bool;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mouse_controller_initialization_and_emergency_stop() {
        let controller = NativeMouseController::new();
        assert_eq!(controller.is_emergency_stopped(), false);

        controller.set_emergency_stop(true);
        assert_eq!(controller.is_emergency_stopped(), true);

        // Actions must fail when emergency stopped
        assert!(controller.move_cursor(0.5, 0.5).is_err());
        assert!(controller.click("left", false).is_err());
        assert!(controller.scroll(3).is_err());
        assert!(controller.type_text("hello").is_err());
        assert!(controller.press_key("space").is_err());
        assert!(controller.key_combo("tab_left").is_err());

        controller.set_emergency_stop(false);
        assert_eq!(controller.is_emergency_stopped(), false);
    }

    #[test]
    fn test_screen_dimensions_non_zero() {
        let controller = NativeMouseController::new();
        let dims = controller.get_screen_dimensions();
        assert!(dims.width > 0.0);
        assert!(dims.height > 0.0);
    }

    #[test]
    fn test_permission_check_returns_valid_struct() {
        let controller = NativeMouseController::new();
        let perm = controller.check_permission();
        assert!(!perm.message.is_empty());
    }
}

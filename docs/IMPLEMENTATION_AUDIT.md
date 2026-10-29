# Observer Implementation Audit & Pipeline Analysis

Date: October 2026  
Status: Phase 1 & 2 Remediation

---

## 1. Feature Classification Matrix

| Major Component | Previous Status | Current Assessment | Root Cause for Static/Disconnected Appearance |
| :--- | :--- | :--- | :--- |
| **Camera Hardware Capture** | Partially implemented (3) | Needs recovery loop & frame events | In `LiveEngineRunner.run()`, if camera fails to open or is unplugged, loop hits `if frame is None: continue` and skips state emission completely. |
| **MediaPipe Face & Iris Landmarks** | Implemented but not verified (2) | Verified in unit tests, unexposed to IPC | Model executes and extracts 478 points + iris centers, but landmarks are immediately deleted without passing coordinates to frontend or inspector. |
| **Vision Features (EAR, Blink, Gaze Dispersion, Tension, Head Pose)** | Implemented and verified (1) | Verified in unit tests, unexposed to IPC | Mathematical extraction works in isolation, but no granular metrics (EAR, gaze coordinates, dispersion, tension breakdown) were sent across IPC. |
| **Desktop Input Monitoring (Key, Mouse, Inactivity Timers)** | Mocked or static (4) on non-Windows; Partially implemented (3) on Windows | Broken dataflow (5) | Non-Windows had `idle_seconds = 1.5` hardcoded. Windows lacked click/scroll/keyboard counters. Metrics were never forwarded to frontend. |
| **Window Switching Count** | Partially implemented (3) | Needs platform abstraction & timestamps | Window handle tracking existed only for Windows; not surfaced to UI. |
| **State Estimation Engine (Formulas & Dwell Time)** | Implemented and verified (1) | Verified in unit tests; lack of explanation telemetry | Scoring formulas and dwell time are mathematically sound, but intermediate weights, dwell duration, and decision rules were opaque. |
| **Intervention Engine** | Missing or broken (5) | Missing module | `intervention.py` was not implemented in `observer_engine`; real engine never evaluated cooldowns or triggered offers. |
| **Frontend State & Store Initializers** | Mocked / static initial state (4) | Masking real status | `useObserverStore.ts` initialized with hardcoded `"FOCUSED"` and `"Active keyboard input"`, which remained on screen when backend was idle. |
| **Vision Inspector UI** | Missing (5) | Under construction (Phase 3) | No visual transparency window existed to inspect what the camera sees. |

---

## 2. Identified Pipeline Gaps & Failure Modes

1. **Disconnected Telemetry Gap**:
   The engine only emitted coarse `StateUpdateEvent` (`state, probabilities, confidence, top_signals, ts`). It never exposed the actual numbers (EAR, iris coords, tension weights, idle seconds, window switches).
2. **Infinite Skip on Camera Absence**:
   If the webcam is unavailable (common in VM/sandboxes or when permission is disabled), the backend's main loop stalled at `get_latest_frame()`, preventing input activity and state updates from reaching the frontend.
3. **Rust OS Signals Silo**:
   `os_signals.rs` sent aggregate numbers only into Python's stdin pipe. The Tauri webview never received direct OS signal events.
4. **Static Initial Store Values**:
   When no events arrived, the React UI displayed hardcoded placeholder values rather than showing an explicit "Awaiting sensor data" or "Camera unavailable" state.

---

## 3. Remediation Strategy

- **Phase 1**: Complete this audit, verifying all source files and defects.
- **Phase 2 (Backend Observability)**: Define and implement high-resolution `TelemetryEvent` in IPC schema, Pydantic models, and Python engine. Ensure loop runs at 10 Hz with or without camera.
- **Phase 3 (Vision Inspector)**: Build the floating non-modal "Inspect what the AI sees" overlay with live video preview toggle, real landmark mesh, iris gaze points, and detailed signal breakdown.
- **Phase 4 (Input Monitoring)**: Upgrade Rust OS signal collector with platform-aware keyboard/mouse activity tracking, inactivity timers, and sequence numbering.
- **Phase 5 (State & Intervention Engine)**: Implement `intervention.py`, wire state calculations to real input signals, and eliminate static fallback states.
- **Phase 6 (Testing & Packaging)**: Comprehensive end-to-end testing with video replay harness and unit test suites.

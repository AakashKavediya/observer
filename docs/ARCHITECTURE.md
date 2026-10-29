# Observer Architecture Specification

Version: 1.0.0  
Target: Windows 10/11 x64 (Offline-First)

---

## 1. High-Level System Overview

Observer is a local-only desktop application designed to support neurodivergent individuals facing task paralysis or overload.

```
+-------------------------------------------------------------+
|                      React 18 Frontend                      |
|  (Atkinson Hyperlegible, Strict Calm Palette, WCAG 2.2 AA)  |
+-------------------------------------------------------------+
                              |
                     Tauri 2 IPC Events
                              |
+-------------------------------------------------------------+
|                     Tauri / Rust Core                       |
|   - Sidecar Process Supervisor (Lifecycle, Restart Backoff) |
|   - OS Context Aggregator (Idle Seconds, Window Switches)   |
|   - Strict Capabilities & CSP Sandboxing                    |
+-------------------------------------------------------------+
                              |
               NDJSON over stdin / stdout (Zero Sockets)
                              |
+-------------------------------------------------------------+
|              Python 3.10 Engine Sidecar                     |
|   - OpenCV (DirectShow, 15 FPS, Downsampled 640x480)       |
|   - MediaPipe Face Landmarker (Float16 task model)          |
|   - Feature Aggregator (EAR, Gaze Dispersion, Blendshapes)  |
|   - Transparent State Engine (Hysteresis, Dwell Time)       |
|   - Gentle Intervention Engine (Backoff, Validating Pool)   |
|   - Ephemeral Memory Guard (Zero Disk Frame Writes)         |
+-------------------------------------------------------------+
```

---

## 2. Key Architectural Guarantees

1. **Zero Open Ports / Sockets**: The entire IPC communication between the host shell (Rust) and the analytics engine (Python) occurs exclusively over standard input (`stdin`) and standard output (`stdout`) using newline-delimited JSON. No HTTP servers, WebSocket endpoints, or localhost sockets are ever opened.
2. **Ephemeral Frame Pipeline**: Webcam video frames live strictly in memory during feature extraction and are discarded immediately. No video frames, bounding boxes, or face crops are written to persistent storage or logs.
3. **Transparent Evidence Model**: Estimates are derived via an interpretable weighted formula combining gaze fixation, facial tension proxies, and input stillness. Black-box opaque classifiers are explicitly excluded.
4. **Host OS Context Limits**: Rust measures only aggregate numbers (`idle_seconds` and handle switch counts). It never inspects window titles, keystrokes, active URLs, or process names.
5. **Process Supervision**: If the Python sidecar terminates, Rust applies exponential backoff auto-restarts, notifying the frontend with friendly status indicators.

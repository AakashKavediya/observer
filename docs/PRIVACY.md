# Observer Privacy Guarantee & Architecture

## Core Principles

Observer was architected with a physical privacy-by-design model: privacy is guaranteed by structural limitations in code rather than mere policy statements.

### 1. 100% Local Inference & Zero Network Egress
- **No Network Requests**: Observer does not make telemetry pings, error-reporting calls, licensing handshakes, or auto-update requests.
- **Self-Contained Assets**: UI fonts (Atkinson Hyperlegible) and the MediaPipe model file (`face_landmarker.task`) are shipped inside the app installer. No remote CDNs are contacted.
- **No Network Listeners**: IPC uses standard pipe I/O (`stdin`/`stdout`). No TCP/UDP sockets are opened on loopback or external interfaces.

### 2. Ephemeral Frame Handling
- Webcam frames captured via OpenCV are processed in-memory at 15 FPS.
- Once landmark blendshapes and gaze coordinates are extracted, the frame buffer is immediately dropped.
- At no point are raw frames, compressed images, video streams, or raw landmark time-series saved to disk or written to log files.

### 3. Non-Invasive OS Signals
- **Idle Time**: Calculated using standard Windows API `GetLastInputInfo`. Measures time elapsed since the last user input event. Keystrokes, mouse coordinates, and specific actions are never read.
- **Window Switches**: Polled via `GetForegroundWindow` handle equality. Only the count of handle changes within the last 60 seconds is measured. Window titles, process IDs, file paths, and document contents are strictly untouched.
- **Zero Hooks**: No global keyboard or mouse hooks (`SetWindowsHookEx`) are installed.

### 4. Complete User Agency
- **Instant Camera Pause**: One click or tray toggle immediately stops camera capture and releases the webcam hardware.
- **Data Erasure**: Clicking "Delete All Data" instantly wipes the local settings JSON and calibration baseline files from disk.
- **Explicit Consent**: The webcam stream is never initialized until the user explicitly checks the consent agreement on the welcome screen.

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

---

## 3. Physiological-Behavioral Health-Tech Architecture

Observer features a longitudinal physiological-behavioral observation framework adhering to privacy-first, non-diagnostic principles:

```
[Webcam Frame (Memory Only)]
         │
         ▼
[Signal Quality Evaluator] ──(Low Lighting, Blur, Extreme Pose, Distance Dropout)──► [Gating Flag]
         │
         ▼
[Behavioral Feature Extractor]
  ├── Blink & Eye: EAR (L/R/Avg), Validated Blinks (50-400ms), Rolling Blinks/min (30s/60s/180s),
  │                IBI Distribution (mean/median/std/p10/p90), Closure Duration, Long-Closures (>=500ms)
  ├── Facial Geometry: Lip-Corner Elevation/Asymmetry, Mouth Width Ratio, Smile Blendshapes,
  │                    Brow Elevation/Asymmetry, Mouth Opening Ratio, Neutral Euclidean Deviation
  ├── Head Kinematics: Pitch, Yaw, Roll (SolvePnP), Angular Velocity, Range of Motion,
  │                    Direction Changes/min, Low Movement Intervals
  └── Upper Body Adapter: Modular adapter explicitly reporting `upper_body_outside_camera_frame`
         │
         ├──► [HealthTech Repository] (Atomic JSON storage in ~/.observer/observations/)
         ├──► [Baseline Calibration Manager] (Robust Medians, MAD, Robust Z-Scores)
         ├──► [Conservative Event Engine] (Multi-sample persistence, >=60% coverage, cooldowns)
         └──► [Longitudinal Analyzer & Multi-Table Reports] (Direct Measurements vs Derived vs Self-Reports)
```

### 3.1 Non-Diagnostic Intended Use & Regulatory Boundaries
- **Intended Use**: Observer is an exploratory behavioral observation and self-monitoring platform. It is designed to assist users in tracking self-regulated work patterns, visual focus, and movement dynamics.
- **Regulatory Status**: Observer is **NOT** a medical device, nor has it been cleared or approved by the FDA, EMA, or any other health authority.
- **Medical Disclaimer**: Observer cannot diagnose ADHD, depression, anxiety, neurological disorders, stress, or fatigue. It does not determine true emotional states from facial features.

### 3.2 Robust Statistical Baseline & Deviation Formulation
To withstand natural twitches, yawns, and lighting fluctuations without skewing:
- **Baseline Metric**: Median ($\tilde{x}$) and Median Absolute Deviation ($\text{MAD}$):
  $$\text{MAD} = \text{median}(|x_i - \tilde{x}|)$$
- **Robust Z-Score**:
  $$z_{\text{robust}} = \frac{x - \tilde{x}}{1.4826 \times \text{MAD}}$$
  Where $1.4826 \times \text{MAD}$ is the asymptotically normal scale estimator.
- Baselines are individualized across guided neutral, visual-focus, and natural calibration stages. They are never compared against generalized clinical norms.

### 3.3 Strict Data Provenance Separation
Every observation and export field is tagged with its provenance level:
- `directly_measured`: Physically extracted coordinates/ratios (e.g., EAR, inter-ocular distance, head pose).
- `derived`: Statistically transformed rates (e.g., blinks/minute, IBI std, angular velocity).
- `inferred`: Algorithmic pattern assessments (e.g., prolonged stillness interval).
- `self_reported`: Subjective user context check-ins (e.g., energy, effort, task difficulty, feeling stuck).

Subjective user inputs are strictly quarantined and never conflated with objective sensor signals. Missing camera data is denoted as `tracking_lost` or `low_quality` and is never substituted with zero.

# Observer (Desktop App)

> A privacy-preserving, 100% local "Context-Aware Observer" that uses a standard webcam to estimate whether the user is relaxed or showing signs of task paralysis, offering gentle, optional, low-friction support.

Built for Windows 10/11 x64 as Track 1 of **Drishti**.

---

## Non-Negotiable Privacy & Safety Guarantees

| Rule | Implementation Guarantee |
| :--- | :--- |
| **100% Offline** | Zero network calls, zero telemetry, zero auto-update requests. Fonts (Atkinson Hyperlegible) and models are bundled inside the app. |
| **No Image Persistence** | Frames are discarded immediately after in-memory feature extraction. No raw images, videos, or landmark vectors are written to disk or logs. |
| **Estimates, Not Diagnoses** | Output is always framed as an estimate with confidence. No shaming language (*no "lazy", "failed", streaks, or judgment scores*). Not a medical device. |
| **Low Friction & Optional** | Interventions are silent by default, dismissible, never blocking, and never flash or steal focus. |
| **Zero Screen/Input Spying** | Never reads window titles, process names, typed keys, or screen contents. OS signals are aggregate numbers only (`idle_seconds`, handle switch count). |
| **Data Provenance Separation** | Objective biometric measurements, derived rates, algorithmic inferences, and subjective self-reports are tracked with distinct provenance tags. |
| **Instant Control & Purge** | Camera can be paused instantly with one click; all stored observations and calibration baselines can be permanently erased anytime. |

---

## Tech Stack

- **Desktop Shell**: Tauri 2 (Rust stable) + React 18 + TypeScript + Vite + Tailwind CSS + Zustand.
- **Strict Palette Tokens**:
  - Main background: warm ivory `#F5F2E9`
  - Cards / content panels: white `#FFFFFF`
  - Primary buttons and links: sage green `#496B5A` (text: white)
  - Headings and body text: forest ink `#293B32`
  - Selected highlights: pale sage `#DCE5D8`
  - Decorative accents only: muted clay `#B87559`
- **Analytics Engine**: Python 3.10 sidecar (`observer-engine`) using MediaPipe Face Landmarker (float16 task API) and OpenCV headless.
- **IPC Interface**: NDJSON (Newline-Delimited JSON) over `stdin`/`stdout`. No open ports or sockets.

---

## Repository Layout

```
observer/
  src-tauri/            Rust core (commands, sidecar manager, OS signals, tray, settings, single-instance)
  src/                  React UI (calm palette, Atkinson Hyperlegible, WCAG 2.2 AA)
  engine/               Python 3.10 engine (package `observer_engine`), tests/, models/, requirements.txt, observer_engine.spec
  scripts/              fetch_models.py, build_engine.ps1, build_all.ps1, verify_offline.ps1
  docs/                 ARCHITECTURE.md, PRIVACY.md, ETHICS.md, STORE_CHECKLIST.md, USER_GUIDE.md, IPC_SCHEMA.md, VALIDATION.md
  README.md
```

---

## Quickstart & Installation (Windows 10/11 x64)

### Prerequisites
1. **Python 3.10+**: `python --version`
2. **Node.js 18+ & npm**: `node --version`
3. **Rust & Cargo**: `rustc --version`

### Step 1: Install Dependencies
```powershell
cd observer

# 1. Install Node modules
npm install

# 2. Download MediaPipe model once (verified with SHA-256)
python scripts/fetch_models.py

# 3. Install Python engine requirements
pip install -r engine/requirements.txt
```

### Step 2: Run Development Mode (End-to-End)
To launch the desktop application in development mode with live IPC and the demo timeline engine:
```powershell
npm run tauri dev
```
To run the React web interface directly in your browser:
```powershell
npm run dev
```

### Step 3: Run Test Suites
```powershell
# 1. Python IPC & Engine unit tests
cd engine
pytest

# 2. Rust host core tests (settings, signals, sidecar)
cd ../src-tauri
cargo test

# 3. React frontend component & accessibility tests
cd ..
npm test
```

---

## Track 4: Hands-Free Assistive Mouse & Voice Control

Observer integrates a fully local, hands-free computer-control system for accessible desktop navigation:
- **Mode A (Relative Rate/Velocity)**: Head deflection outside an adaptive dead zone controls cursor speed with zero stationary jitter inside the neutral dead zone.
- **Mode B (Calibrated Absolute)**: Regularized 2D bilinear Ridge regression maps validated head deflections directly to screen coordinates.
- **Mode C (MotionQ Iris Gaze & Dwell Control)**: Integrated from [MotionQ-blink](https://github.com/AakashKavediya/MotionQ-blink) (MIT License, Copyright (c) 2026 Aakash Kavediya). Direct iris tracking with a nonlinear 1.2 curve, dwell engine magnetic attraction, proximity slowdown, vertical head-tilt scrolling, and a multilingual virtual keyboard (English, Hindi, Marathi) with predictive completion.
- **Hands-Free Voice Listener**: Local SpeechRecognition dispatcher for 13 assistive voice commands (`click`, `double click`, `right click`, `scroll up/down`, `pause/resume`, `keyboard`, `recenter`, `emergency stop`).
- **macOS Native CoreGraphics Input**: Rust FFI dispatch for cursor movement, clicks, scrolling, key combinations, and Unicode text entry (`CGEventKeyboardSetUnicodeString`).

---

## Attribution & Licenses

- **Observer Core**: Drishti Accessibility & Calm Focus Companion.
- **MotionQ-blink**: Assistive eye-gaze control logic, multilingual predictions, and dwell engine adapted from [MotionQ-blink](https://github.com/AakashKavediya/MotionQ-blink) under the MIT License. Full license notice preserved in `engine/observer_engine/assets/LICENSE.MotionQ-blink`.


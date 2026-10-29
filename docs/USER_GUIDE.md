# Observer User Guide

Welcome to **Observer**, a calm, privacy-preserving desktop companion designed to notice when you are experiencing task paralysis or overload, and offer gentle, low-friction support.

---

## 1. Getting Started

### 1.1 Welcome & Consent
Upon first launching Observer, you will be greeted by the **Welcome & Consent** screen. Observer will **never** activate your webcam until you explicitly review the permissions and select *"I understand"*.
You can choose which local signals you feel comfortable having Observer monitor:
- **Facial tension and gaze proxies**: Measured locally via MediaPipe Face Landmarker.
- **Keyboard / Mouse idle seconds**: Measured via Windows input counters.
- **Window switch rate**: Measured via window handle count changes.

### 1.2 Guided Calibration
Every neurodivergent individual has a different natural resting face and focus rhythm. The 2-minute guided calibration teaches Observer your personal baseline:
1. **Minute 1 - Relaxed Baseline**: Relax, breathe, and look naturally at your screen.
2. **Minute 2 - Normal Work**: Read or work normally.

All future estimates are z-scored against your own baseline, never against generic population norms.

---

## 2. Reading the Status Display

### 2.1 Current State
- **Settled & Relaxed**: Low tension, regular blinking, comfortable gaze shifts.
- **Engaged in Flow**: Focused work, active keyboard/mouse input, steady gaze.
- **Might Be Stuck**: Heightened facial tension, prolonged gaze fixation on the cursor, and extended input silence.
- **Feeling a Lot**: Elevated switching and tension.

### 2.2 Confidence Estimate
A gentle, non-judgmental bar indicating quality-gated evidence confidence.

### 2.3 Why Observer Thinks So
Click the *"Why Observer thinks so"* drawer at any time to inspect the top 1-2 plain-language cues contributing to the current estimate.

---

## 3. Gentle Offers & Interventions

When Observer estimates you might be stuck:
- A non-blocking, quiet card appears.
- It will **never** play a sound or steal keyboard focus.
- You can click **Tiny step** for a single micro-action, **Rest a bit**, or **Not now**.
- If Observer guessed wrong, click **"That wasn't right"** to teach Observer to raise its threshold.

---

## 4. Privacy & Hardware Controls
- **Pause Camera**: Click the Pause button in the top bar or right-click the system tray icon to pause tracking instantly.
- **Delete All Data**: Under Settings -> Data Management, click **Delete All Stored Data** to completely erase all calibration baselines and preferences.

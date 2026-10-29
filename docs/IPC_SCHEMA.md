# Observer IPC Schema Specification

Version: `1.0.0`
Transport: Newline-Delimited JSON (NDJSON) over standard input (`stdin`) and standard output (`stdout`).

## Design Principles
1. **No Network Sockets**: Communication is strictly restricted to standard I/O between the Tauri host process and the child Python engine. No open ports, no loopback HTTP/WebSocket listeners.
2. **Strict Schema Versioning**: All payloads contain `schema_version: "1.0.0"`. Parsers MUST ignore unknown fields to ensure backwards/forwards resilience.
3. **Privacy First**: No image frames, landmark vectors, raw timestamps of keystrokes, or application window titles ever cross the IPC interface. Only aggregate state estimates, probabilities, and system statuses are transmitted.

---

## 1. Engine -> UI (Events)

Each line emitted by the engine to `stdout` is a serialized JSON object conforming to `EngineEvent`.

### 1.1 Status Event (`type: "status"`)
Indicates camera state, operating mode, frame rate, calibration state, and overall health.
```json
{
  "schema_version": "1.0.0",
  "type": "status",
  "camera": "on",
  "mode": "live",
  "calibrating": false,
  "paused": false,
  "fps": 15.0,
  "engine_ok": true
}
```
Fields:
- `camera`: `"off"` | `"starting"` | `"on"` | `"blocked"` | `"unplugged"`
- `mode`: `"live"` | `"demo"`
- `calibrating`: `boolean`
- `paused`: `boolean`
- `fps`: `number` (actual processed frames per second; 0.0 when off/starting)
- `engine_ok`: `boolean`

### 1.2 High-Resolution Telemetry Event (`type: "telemetry"`)
Provides comprehensive observability for the Vision Inspector and explanation panels.
```json
{
  "schema_version": "1.0.0",
  "type": "telemetry",
  "seq": 1042,
  "ts": 1717000000.123,
  "camera": {
    "status": "on",
    "fps": 14.8,
    "width": 640,
    "height": 480,
    "device_index": 0
  },
  "vision": {
    "face_detected": true,
    "quality_valid": true,
    "quality_reason": "nominal",
    "mean_brightness": 128.4,
    "ear": {
      "left": 0.28,
      "right": 0.29,
      "avg": 0.285,
      "baseline_mean": 0.28,
      "baseline_std": 0.04,
      "is_blink": false
    },
    "blinks": {
      "count_total": 4,
      "rate_30s": 12.0,
      "rate_60s": 14.0,
      "rate_180s": 15.0,
      "irregularity": 1.25
    },
    "gaze": {
      "x": 0.495,
      "y": 0.512,
      "raw_x": 0.502,
      "raw_y": 0.518,
      "iris_l": [0.412, 0.398],
      "iris_r": [0.588, 0.398],
      "dispersion_4s": 0.04,
      "dispersion_30s": 0.08,
      "dispersion_120s": 0.12,
      "shifts_per_min": 6.0,
      "baseline_disp_mean": 0.35
    },
    "tension": {
      "index": 0.22,
      "brow_down": 0.15,
      "mouth_press": 0.20,
      "jaw_clench": 0.10,
      "eye_squint": 0.05,
      "baseline_mean": 0.18,
      "baseline_std": 0.08
    },
    "head_pose": {
      "pitch": 4.2,
      "yaw": -2.1,
      "roll": 0.8,
      "variance_4s": 0.15,
      "variance_30s": 0.45,
      "baseline_var_mean": 1.20
    },
    "landmarks_wireframe": [[0.38, 0.40], [0.46, 0.40], ...],
    "frame_jpeg_base64": null
  },
  "desktop_input": {
    "idle_seconds": 3.2,
    "seconds_since_last_key": 3.2,
    "seconds_since_last_mouse": 1.1,
    "seconds_since_last_scroll": 12.0,
    "key_count_window": 14,
    "mouse_move_count_window": 85,
    "mouse_click_count_window": 2,
    "mouse_scroll_count_window": 0,
    "window_switch_count_60s": 1,
    "productive_input_score": 0.73,
    "monitor_status": "active"
  },
  "prediction": {
    "state": "FOCUSED",
    "frozen_score": 0.28,
    "frozen_components": {
      "fixation": 0.85,
      "idle": 0.05,
      "tension": 0.22,
      "blink_anomaly": 0.10,
      "stillness": 0.30
    },
    "frozen_weights": {
      "fixation": 0.30,
      "idle": 0.25,
      "tension": 0.25,
      "blink_anomaly": 0.10,
      "stillness": 0.10
    },
    "spinning_score": 0.18,
    "spinning_components": {
      "switching": 0.12,
      "tension": 0.22,
      "unproductive": 0.27
    },
    "smoothed_frozen": 0.29,
    "smoothed_spinning": 0.19,
    "enter_threshold": 0.65,
    "exit_threshold": 0.45,
    "dwell_duration_seconds": 0.0,
    "dwell_required_seconds": 90.0,
    "dwell_satisfied": false,
    "confidence": 0.88,
    "top_signals": [
      "Steady work rhythm and active typing",
      "Regular blink cadence (14/min)"
    ],
    "excluded_or_invalid_signals": [],
    "exact_decision_rule": "Productive input score (0.73 >= 0.40) and low idle time (3.2s) classify state as FOCUSED.",
    "intervention_status": {
      "eligible": false,
      "reason": "Suppressed: state is FOCUSED and not in paralysis",
      "cooldown_remaining_s": 0.0
    }
  }
}
```

### 1.2 Calibration Progress Event (`type: "calibration_progress"`)
Emitted during the 2-minute guided baseline calibration routine.
```json
{
  "schema_version": "1.0.0",
  "type": "calibration_progress",
  "phase": "relaxed_baseline",
  "percent": 45.0
}
```
Fields:
- `phase`: `"relaxed_baseline"` | `"normal_work"` | `"complete"`
- `percent`: `number` (0.0 to 100.0)

### 1.3 State Update Event (`type: "state_update"`)
Periodic estimation of the user's focus/tension/paralysis state (emitted every ~1s).
```json
{
  "schema_version": "1.0.0",
  "type": "state_update",
  "state": "PARALYSIS_LIKELY",
  "probabilities": {
    "relaxed": 0.05,
    "focused": 0.15,
    "paralysis": 0.72,
    "overload": 0.08
  },
  "confidence": 0.78,
  "top_signals": [
    "Prolonged gaze fixation on cursor",
    "Elevated facial tension and reduced blink rate"
  ],
  "ts": 1717000000.123
}
```
Fields:
- `state`: `"RELAXED"` | `"FOCUSED"` | `"PARALYSIS_LIKELY"` | `"OVERLOAD_LIKELY"` | `"UNKNOWN"`
- `probabilities`: Object mapping state names to estimated confidence (sum <= 1.0)
- `confidence`: `number` (0.0 to 1.0, quality-gated confidence)
- `top_signals`: `string[]` (top 1-2 explainable contributing signals in plain language)
- `ts`: `number` (Unix timestamp in seconds)

### 1.4 Intervention Event (`type: "intervention"`)
A gentle, non-blocking notification or micro-step offer.
```json
{
  "schema_version": "1.0.0",
  "type": "intervention",
  "tier": 2,
  "id": "intv_20261029_191500_1234",
  "text": "That looks stuck. Want a tiny first step? Totally optional.",
  "actions": [
    { "id": "tiny_step", "label": "Tiny step" },
    { "id": "rest_bit", "label": "Rest a bit" },
    { "id": "not_now", "label": "Not now" }
  ]
}
```
Fields:
- `tier`: `number` (1: ambient cue, 2: gentle offer, 3: micro-step)
- `id`: `string` (unique ID for feedback correlation)
- `text`: `string` (validating, warm, <= 12 words)
- `actions`: Array of `{ id: string, label: string }`

### 1.5 Error Event (`type: "error"`)
User-facing friendly error notification.
```json
{
  "schema_version": "1.0.0",
  "type": "error",
  "code": "CAMERA_UNAVAILABLE",
  "message_friendly": "Your webcam is currently unavailable or used by another application."
}
```

---

## 2. UI -> Engine (Commands)

Commands sent from the Rust host to Python child over `stdin`.

### 2.1 Start Calibration (`name: "start_calibration"`)
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "start_calibration"
}
```

### 2.2 Cancel Calibration (`name: "cancel_calibration"`)
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "cancel_calibration"
}
```

### 2.3 Pause / Resume Camera (`name: "pause"`, `name: "resume"`)
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "pause"
}
```

### 2.4 Update Settings (`name: "set_settings"`)
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "set_settings",
  "settings": {
    "sensitivity": 0.65,
    "cooldown_mins": 20,
    "quiet_hours_enabled": false,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00",
    "intervention_tier": 2,
    "enabled_signals": {
      "gaze_fixation": true,
      "facial_tension": true,
      "blink_anomaly": true,
      "idle_time": true,
      "window_switching": true
    }
  }
}
```

### 2.5 Intervention Feedback (`name: "feedback"`)
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "feedback",
  "id": "intv_20261029_191500_1234",
  "kind": "wrong_guess"
}
```
Allowed `kind`: `"helped"` | `"not_now"` | `"wrong_guess"`

### 2.6 Snooze (`name: "snooze"`)
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "snooze",
  "duration_minutes": 60
}
```

### 2.7 Delete All Data (`name: "delete_all_data"`)
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "delete_all_data"
}
```

### 2.8 Demo Mode (`name: "start_demo"`, `name: "stop_demo"`)
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "start_demo",
  "scenario": "full_walkthrough"
}
```

### 2.9 Shutdown (`name: "shutdown"`)
```json
{
  "schema_version": "1.0.0",
  "type": "command",
  "name": "shutdown"
}
```

---

## 3. Host OS Context -> Engine

Aggregates computed in Rust sent to the engine every 1 second:
```json
{
  "schema_version": "1.0.0",
  "type": "os_signals",
  "idle_seconds": 12.5,
  "window_switch_count": 2,
  "fullscreen_media": false
}
```
Rules:
- `idle_seconds`: aggregate duration since last mouse/keyboard event.
- `window_switch_count`: tally of active window handle changes in the last 60s.
- `fullscreen_media`: coarse heuristic boolean (e.g. video playback detected).
- NEVER sends window titles, keystrokes, URLs, or process names.

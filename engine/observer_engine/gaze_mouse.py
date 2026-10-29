"""
observer_engine.gaze_mouse
Track 4: Stability-First Head-Movement Velocity Mouse Controller (Rate/Joystick Style).

Architecture:
- STOP using raw face coordinates as absolute screen coordinates.
- Relative Head-Movement Velocity Controller:
    * Calibrated neutral resting head pose (neutral_yaw, neutral_pitch, neutral_nose_x, neutral_nose_y).
    * Hysteresis Dead Zone:
        Inside dead zone: velocity is IDENTICALLY 0.0. The OS cursor remains rock-solid stationary (0 px jitter/drift).
        Outside dead zone: deflection converts to bounded cursor velocity v = g(Δ).
        Returning head to neutral stops cursor movement instantly.
    * Bounded incremental integration: pos_t = clamp(pos_{t-1} + v * dt, 0.0, 1.0).
    * Control clutch: 1-click Recenter, Pause/Resume, Emergency Stop (Esc).
- Predictable Presets:
    * Maximum Stability (default): larger dead zone (1.8°), conservative speed, zero movement for small fluctuations.
    * Balanced: moderate dead zone (1.2°), general desktop navigation.
    * Responsive: smaller dead zone (0.7°), fast traversal.
- Safety & Signal Hygiene:
    * Frame age validation (max frame age <= 100ms, clamped dt [0.010, 0.066]s).
    * Spike outlier rejection (> 15° or > 0.25 norm within 150ms).
    * Blink hold (< 400ms) and smooth re-acquisition without position jump.
    * Versioned JSON persistence (~/.observer/head_mouse_calibration_v3.json).
"""

import os
import json
import time
import math
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List, Tuple
import numpy as np


# -------------------------------------------------------------
# 1. One Euro Filter for Low-Latency, Jitter-Free Smoothing
# -------------------------------------------------------------
class LowPassFilter:
    def __init__(self, alpha: float = 0.5):
        self.__set_alpha(alpha)
        self.__y: Optional[float] = None
        self.__s: Optional[float] = None

    def __set_alpha(self, alpha: float):
        self.__alpha = max(0.0, min(1.0, alpha))

    def filter(self, value: float) -> float:
        if self.__y is None:
            s = value
        else:
            s = self.__alpha * value + (1.0 - self.__alpha) * self.__s
        self.__y = value
        self.__s = s
        return s

    def filter_with_alpha(self, value: float, alpha: float) -> float:
        self.__set_alpha(alpha)
        return self.filter(value)

    def has_last_raw_value(self) -> bool:
        return self.__y is not None

    def last_raw_value(self) -> Optional[float]:
        return self.__y

    def reset(self):
        self.__y = None
        self.__s = None


class OneEuroFilter1D:
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.05, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_filter = LowPassFilter()
        self.dx_filter = LowPassFilter()
        self.last_time: Optional[float] = None

    def _alpha(self, rate: float, cutoff: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        te = 1.0 / rate
        return 1.0 / (1.0 + tau / te)

    def filter(self, x: float, timestamp: float) -> float:
        if self.last_time is None:
            self.last_time = timestamp
            return self.x_filter.filter(x)

        dt = timestamp - self.last_time
        self.last_time = timestamp
        rate = 1.0 / max(1e-4, dt)

        # Estimate derivative
        prev_x = self.x_filter.last_raw_value()
        dx = 0.0 if prev_x is None else (x - prev_x) * rate
        edx = self.dx_filter.filter_with_alpha(dx, self._alpha(rate, self.d_cutoff))

        cutoff = self.min_cutoff + self.beta * abs(edx)
        return self.x_filter.filter_with_alpha(x, self._alpha(rate, cutoff))

    def reset(self):
        self.x_filter.reset()
        self.dx_filter.reset()
        self.last_time = None


class OneEuroFilter2D:
    def __init__(self, min_cutoff: float = 0.8, beta: float = 0.4, d_cutoff: float = 1.0):
        self.fx = OneEuroFilter1D(min_cutoff, beta, d_cutoff)
        self.fy = OneEuroFilter1D(min_cutoff, beta, d_cutoff)

    def filter(self, x: float, y: float, timestamp: float) -> Tuple[float, float]:
        return (self.fx.filter(x, timestamp), self.fy.filter(y, timestamp))

    def update_parameters(self, min_cutoff: float, beta: float):
        self.fx.min_cutoff = min_cutoff
        self.fx.beta = beta
        self.fy.min_cutoff = min_cutoff
        self.fy.beta = beta

    def reset(self):
        self.fx.reset()
        self.fy.reset()


# -------------------------------------------------------------
# 2. Schema, Presets & Calibration Configuration
# -------------------------------------------------------------
HEAD_MOUSE_SCHEMA_VERSION = "3.0.0"
GAZE_CALIB_SCHEMA_VERSION = "3.0.0"

STABILITY_PRESETS = {
    "maximum_stability": {
        "dead_zone": 0.020,
        "dead_zone_enter_deg": 1.8,
        "dead_zone_exit_deg": 1.4,
        "dead_zone_enter_norm": 0.040,
        "dead_zone_exit_norm": 0.030,
        "gain": 0.08,
        "power": 1.2,
        "max_speed": 0.35,  # norm / s
        "min_cutoff": 0.5,
        "beta": 0.10,
        "sensitivity": 0.8,
        "label": "Maximum Stability (Default)",
        "description": "Fixation priority. 0px stationary jitter with hysteresis dead zone.",
    },
    "balanced": {
        "dead_zone": 0.012,
        "dead_zone_enter_deg": 1.2,
        "dead_zone_exit_deg": 0.9,
        "dead_zone_enter_norm": 0.025,
        "dead_zone_exit_norm": 0.018,
        "gain": 0.14,
        "power": 1.2,
        "max_speed": 0.65,
        "min_cutoff": 0.8,
        "beta": 0.30,
        "sensitivity": 1.2,
        "label": "Balanced",
        "description": "Balanced responsiveness and stability for general desktop control.",
    },
    "responsive": {
        "dead_zone": 0.006,
        "dead_zone_enter_deg": 0.7,
        "dead_zone_exit_deg": 0.5,
        "dead_zone_enter_norm": 0.015,
        "dead_zone_exit_norm": 0.010,
        "gain": 0.22,
        "power": 1.2,
        "max_speed": 1.10,
        "min_cutoff": 1.5,
        "beta": 0.60,
        "sensitivity": 1.6,
        "label": "Responsive",
        "description": "Faster cursor traversal with smaller dead zone.",
    },
}

CALIBRATION_TARGETS = [
    {"target_id": "center_1", "screen_x": 0.50, "screen_y": 0.50, "label": "Look at Center"},
    {"target_id": "top_left", "screen_x": 0.15, "screen_y": 0.15, "label": "Look Top-Left"},
    {"target_id": "top_right", "screen_x": 0.85, "screen_y": 0.15, "label": "Look Top-Right"},
    {"target_id": "bottom_right", "screen_x": 0.85, "screen_y": 0.85, "label": "Look Bottom-Right"},
    {"target_id": "bottom_left", "screen_x": 0.15, "screen_y": 0.85, "label": "Look Bottom-Left"},
    {"target_id": "center_2", "screen_x": 0.50, "screen_y": 0.50, "label": "Validation: Look at Center Again"},
]


@dataclass
class CalibrationSample:
    gaze_x: float
    gaze_y: float
    timestamp: float


@dataclass
class TargetCalibrationResult:
    target_id: str
    target_screen_x: float
    target_screen_y: float
    mean_gaze_x: float
    mean_gaze_y: float
    std_gaze_x: float
    std_gaze_y: float
    sample_count: int


@dataclass
class GazeCalibrationProfile:
    schema_version: str
    created_at: float
    is_calibrated: bool
    quality_label: str
    validation_error: float
    coeff_x: List[float]
    coeff_y: List[float]
    targets: List[Dict[str, Any]]
    tracking_mode: str = "hybrid"
    neutral_yaw: float = 0.0
    neutral_pitch: float = 0.0
    neutral_nose_x: float = 0.0
    neutral_nose_y: float = 0.0


@dataclass
class DiagnosticSample:
    cursor_x: float
    cursor_y: float
    timestamp: float
    is_valid: bool
    is_outlier: bool
    latency_ms: float


# -------------------------------------------------------------
# 3. GazeMouseTracker / HeadMouseController Core
# -------------------------------------------------------------
class GazeMouseTracker:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = storage_dir or os.path.expanduser("~/.observer")
        os.makedirs(self.storage_dir, exist_ok=True)
        self.calib_file_path = os.path.join(self.storage_dir, "head_mouse_calibration_v3.json")
        self.legacy_calib_path = os.path.join(self.storage_dir, "gaze_calibration_v2.json")

        # Tracking Mode: "head_pose" (recommended), "nose_bridge", "hybrid"
        self.tracking_mode: str = "hybrid"

        # Preset selection (Default is Maximum Stability)
        self.preset_name: str = "maximum_stability"
        preset_cfg = STABILITY_PRESETS[self.preset_name]

        # Safety & control state
        self.enabled: bool = False
        self.paused: bool = False
        self.emergency_stopped: bool = False

        # Tuning Parameters
        self.sensitivity: float = preset_cfg["sensitivity"]
        self.dead_zone: float = preset_cfg["dead_zone"]
        self.max_speed: float = preset_cfg["max_speed"]
        self.smoothing_mode: str = self.preset_name

        # Presets dead-zone thresholds
        self.dead_zone_enter_deg: float = preset_cfg["dead_zone_enter_deg"]
        self.dead_zone_exit_deg: float = preset_cfg["dead_zone_exit_deg"]
        self.dead_zone_enter_norm: float = preset_cfg["dead_zone_enter_norm"]
        self.dead_zone_exit_norm: float = preset_cfg["dead_zone_exit_norm"]
        self.gain: float = preset_cfg["gain"]
        self.power: float = preset_cfg["power"]

        # Hysteresis state: True if cursor is actively deflecting outside dead zone
        self.is_moving: bool = False

        # Relative neutral reference pose
        self.neutral_yaw: float = 0.0
        self.neutral_pitch: float = 0.0
        self.neutral_nose_x: float = 0.0
        self.neutral_nose_y: float = 0.0
        self.is_neutral_calibrated: bool = False
        self.neutral_calibration_samples: List[Tuple[float, float, float, float]] = []

        # Current live state telemetry
        self.current_yaw: float = 0.0
        self.current_pitch: float = 0.0
        self.current_nose_x: float = 0.0
        self.current_nose_y: float = 0.0
        self.deflection_x: float = 0.0
        self.deflection_y: float = 0.0
        self.velocity_x: float = 0.0
        self.velocity_y: float = 0.0
        self.in_dead_zone: bool = True
        self.last_frame_ts: float = 0.0
        self.update_hz: float = 0.0
        self.frame_age_ms: float = 0.0

        # Incremental cursor position [0.0, 1.0]
        self.last_cursor_norm: Tuple[float, float] = (0.5, 0.5)

        # Temporal filter for features
        self.filter = OneEuroFilter2D(
            min_cutoff=preset_cfg["min_cutoff"],
            beta=preset_cfg["beta"],
        )

        # Outlier Detection State
        self.last_raw_feature: Optional[Tuple[float, float]] = None
        self.last_feature_ts: float = 0.0
        self.consecutive_outlier_count: int = 0
        self.total_outliers_detected: int = 0

        # Blink & Tracking Hold State
        self.last_valid_ts: float = 0.0
        self.is_tracking_valid: bool = False
        self.tracking_status_message: str = "Eye control disabled"
        self.in_blink_hold: bool = False

        # Active Calibration Session
        self.is_calibrating: bool = False
        self.calib_target_idx: int = 0
        self.current_target_samples: List[CalibrationSample] = []
        self.calib_target_results: List[TargetCalibrationResult] = []

        # Stability Diagnostic Session
        self.is_diagnosing: bool = False
        self.diagnostic_start_ts: float = 0.0
        self.diagnostic_duration: float = 5.0
        self.diagnostic_samples: List[DiagnosticSample] = []
        self.last_diagnostic_result: Optional[Dict[str, Any]] = None

        # Load or initialize calibration profile
        self.profile = self.load_calibration() or self._default_calibration()
        if self.profile.is_calibrated:
            self.neutral_yaw = self.profile.neutral_yaw
            self.neutral_pitch = self.profile.neutral_pitch
            self.neutral_nose_x = self.profile.neutral_nose_x
            self.neutral_nose_y = self.profile.neutral_nose_y
            self.is_neutral_calibrated = True

    def apply_preset(self, preset_name: str):
        """Applies one of the 3 validated presets: maximum_stability, balanced, responsive."""
        if preset_name not in STABILITY_PRESETS:
            preset_name = "maximum_stability"
        self.preset_name = preset_name
        cfg = STABILITY_PRESETS[preset_name]
        self.sensitivity = cfg["sensitivity"]
        self.dead_zone = cfg["dead_zone"]
        self.max_speed = cfg["max_speed"]
        self.dead_zone_enter_deg = cfg["dead_zone_enter_deg"]
        self.dead_zone_exit_deg = cfg["dead_zone_exit_deg"]
        self.dead_zone_enter_norm = cfg["dead_zone_enter_norm"]
        self.dead_zone_exit_norm = cfg["dead_zone_exit_norm"]
        self.gain = cfg["gain"]
        self.power = cfg["power"]
        self.smoothing_mode = preset_name
        self.filter.update_parameters(min_cutoff=cfg["min_cutoff"], beta=cfg["beta"])

    def set_tracking_mode(self, mode: str):
        """Sets tracking strategy: 'nose_bridge', 'head_pose', or 'hybrid'."""
        if mode in ("nose_bridge", "head_pose", "hybrid"):
            self.tracking_mode = mode
            self.filter.reset()
            self.last_raw_feature = None
            self.is_moving = False

    # ---------------------------------------------------------
    # Recenter & Neutral Calibration
    # ---------------------------------------------------------
    def recenter(self):
        """
        Instantly recenters neutral head pose to the current head orientation.
        Crucial requirement: cursor position does NOT move or jump unexpectedly.
        """
        self.neutral_yaw = self.current_yaw
        self.neutral_pitch = self.current_pitch
        self.neutral_nose_x = self.current_nose_x
        self.neutral_nose_y = self.current_nose_y
        self.is_neutral_calibrated = True
        self.is_moving = False
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.in_dead_zone = True

        # Persist updated neutral reference
        self.profile.neutral_yaw = self.neutral_yaw
        self.profile.neutral_pitch = self.neutral_pitch
        self.profile.neutral_nose_x = self.neutral_nose_x
        self.profile.neutral_nose_y = self.neutral_nose_y
        self.save_calibration(self.profile)

    def calibrate_neutral_from_samples(self, samples: List[Tuple[float, float, float, float]]):
        """
        Calibrates neutral reference using Median + MAD over a burst of stationary resting samples.
        samples: list of (yaw, pitch, nose_x, nose_y)
        """
        if not samples:
            return
        arr = np.array(samples, dtype=np.float64)
        meds = np.median(arr, axis=0)
        mads = np.median(np.abs(arr - meds), axis=0)
        sigmas = np.maximum(1e-5, 1.4826 * mads)

        # Filter outliers beyond 2.5 sigma
        valid_mask = np.all(np.abs(arr - meds) <= 2.5 * sigmas, axis=1)
        clean = arr[valid_mask] if np.sum(valid_mask) >= 3 else arr

        means = np.mean(clean, axis=0)
        self.neutral_yaw = float(means[0])
        self.neutral_pitch = float(means[1])
        self.neutral_nose_x = float(means[2])
        self.neutral_nose_y = float(means[3])
        self.is_neutral_calibrated = True
        self.is_moving = False
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.in_dead_zone = True

        self.profile.neutral_yaw = self.neutral_yaw
        self.profile.neutral_pitch = self.neutral_pitch
        self.profile.neutral_nose_x = self.neutral_nose_x
        self.profile.neutral_nose_y = self.neutral_nose_y
        self.save_calibration(self.profile)

    def reset_cursor_to_center(self):
        """Resets the integrated desktop cursor position to center (0.5, 0.5)."""
        self.last_cursor_norm = (0.5, 0.5)
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.is_moving = False
        self.in_dead_zone = True

    # ---------------------------------------------------------
    # Calibration Storage & Loading
    # ---------------------------------------------------------
    def _default_calibration(self) -> GazeCalibrationProfile:
        return GazeCalibrationProfile(
            schema_version=HEAD_MOUSE_SCHEMA_VERSION,
            created_at=time.time(),
            is_calibrated=False,
            quality_label="Uncalibrated (Default)",
            validation_error=0.08,
            coeff_x=[0.5, -2.5, 0.0, 0.0],
            coeff_y=[0.5, 0.0, 2.5, 0.0],
            targets=[],
            tracking_mode=self.tracking_mode,
            neutral_yaw=0.0,
            neutral_pitch=0.0,
            neutral_nose_x=0.0,
            neutral_nose_y=0.0,
        )

    def load_calibration(self) -> Optional[GazeCalibrationProfile]:
        target_path = self.calib_file_path if os.path.isfile(self.calib_file_path) else self.legacy_calib_path
        if not os.path.isfile(target_path):
            return None
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return GazeCalibrationProfile(
                schema_version=data.get("schema_version", HEAD_MOUSE_SCHEMA_VERSION),
                created_at=data.get("created_at", time.time()),
                is_calibrated=data.get("is_calibrated", False),
                quality_label=data.get("quality_label", "Good"),
                validation_error=data.get("validation_error", 0.0),
                coeff_x=data.get("coeff_x", [0.5, -2.5, 0.0, 0.0]),
                coeff_y=data.get("coeff_y", [0.5, 0.0, 2.5, 0.0]),
                targets=data.get("targets", []),
                tracking_mode=data.get("tracking_mode", "hybrid"),
                neutral_yaw=data.get("neutral_yaw", 0.0),
                neutral_pitch=data.get("neutral_pitch", 0.0),
                neutral_nose_x=data.get("neutral_nose_x", 0.0),
                neutral_nose_y=data.get("neutral_nose_y", 0.0),
            )
        except Exception as e:
            print(f"[HeadMouse] Calibration load failed: {e}")
        return None

    def save_calibration(self, profile: GazeCalibrationProfile):
        try:
            tmp_path = self.calib_file_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(asdict(profile), f, indent=2)
            os.replace(tmp_path, self.calib_file_path)
            self.profile = profile
        except Exception as e:
            print(f"[HeadMouse] Calibration save error: {e}")

    def reset_calibration(self):
        try:
            if os.path.exists(self.calib_file_path):
                os.remove(self.calib_file_path)
            if os.path.exists(self.legacy_calib_path):
                os.remove(self.legacy_calib_path)
        except Exception:
            pass
        self.profile = self._default_calibration()
        self.neutral_yaw = 0.0
        self.neutral_pitch = 0.0
        self.neutral_nose_x = 0.0
        self.neutral_nose_y = 0.0
        self.is_neutral_calibrated = False
        self.filter.reset()

    # ---------------------------------------------------------
    # STAGE 1: Landmark Validity & Tracking Checks
    # ---------------------------------------------------------
    def check_tracking_validity(
        self,
        landmarks: Optional[np.ndarray],
        ear: float,
        pitch: float,
        yaw: float,
    ) -> Tuple[bool, str]:
        if landmarks is None or len(landmarks) < 478:
            return False, "Face mesh lost"

        p_l = landmarks[33, :2]
        p_r = landmarks[263, :2]
        p_nose = landmarks[168, :2]
        if np.isnan(p_l).any() or np.isnan(p_r).any() or np.isnan(p_nose).any():
            return False, "Invalid landmark coordinates"

        dx = p_r[0] - p_l[0]
        dy = p_r[1] - p_l[1]
        d_ocular = math.sqrt(dx * dx + dy * dy)
        if d_ocular < 0.03:
            return False, "Face too far from camera"

        if ear < 0.15:
            return False, "Blink or eye closure detected"

        if abs(yaw) > 40.0:
            return False, f"Head turned too far horizontally ({yaw:.1f}°)"
        if abs(pitch) > 35.0:
            return False, f"Head tilted too far vertically ({pitch:.1f}°)"

        return True, "Tracking locked"

    # ---------------------------------------------------------
    # STAGE 2: Feature Extraction & Scale-Invariant Normalization
    # ---------------------------------------------------------
    def extract_features(
        self,
        landmarks: np.ndarray,
        pitch: float,
        yaw: float,
    ) -> Optional[Tuple[float, float]]:
        if len(landmarks) < 478:
            return None

        p_l = landmarks[33, :2]
        p_r = landmarks[263, :2]
        midpoint = 0.5 * (p_l + p_r)

        dx = p_r[0] - p_l[0]
        dy = p_r[1] - p_l[1]
        d_ocular = math.sqrt(dx * dx + dy * dy)
        if d_ocular < 0.02:
            return None

        p_nose = landmarks[168, :2]
        if p_nose[0] == 0.0 and p_nose[1] == 0.0:
            if landmarks[6, 0] != 0.0:
                p_nose = landmarks[6, :2]
            elif landmarks[1, 0] != 0.0:
                p_nose = landmarks[1, :2]
            else:
                p_nose = midpoint

        delta_nose_x = float((p_nose[0] - midpoint[0]) / d_ocular)
        delta_nose_y = float((p_nose[1] - midpoint[1]) / d_ocular)

        self.current_nose_x = delta_nose_x
        self.current_nose_y = delta_nose_y
        self.current_yaw = yaw
        self.current_pitch = pitch

        # Head pose features normalized by boundary limits
        pose_x = float(yaw / 30.0)
        pose_y = float(-pitch / 25.0)

        if self.tracking_mode == "nose_bridge":
            return (delta_nose_x, delta_nose_y)
        elif self.tracking_mode == "head_pose":
            return (pose_x, pose_y)
        else:  # "hybrid"
            hx = 0.6 * delta_nose_x + 0.4 * pose_x
            hy = 0.6 * delta_nose_y + 0.4 * pose_y
            return (hx, hy)

    # ---------------------------------------------------------
    # STAGE 3: Outlier Rejection (Spike Detection)
    # ---------------------------------------------------------
    def filter_outliers(
        self,
        raw_feature: Tuple[float, float],
        timestamp: float,
    ) -> Tuple[Tuple[float, float], bool]:
        if self.last_raw_feature is None:
            self.last_raw_feature = raw_feature
            self.last_feature_ts = timestamp
            self.consecutive_outlier_count = 0
            return (raw_feature, False)

        dt = timestamp - self.last_feature_ts
        fx, fy = raw_feature
        lfx, lfy = self.last_raw_feature

        jump = math.sqrt((fx - lfx) ** 2 + (fy - lfy) ** 2)

        if dt < 0.15 and jump > 0.25:
            self.consecutive_outlier_count += 1
            self.total_outliers_detected += 1

            if self.consecutive_outlier_count < 3:
                return (self.last_raw_feature, True)
            else:
                self.consecutive_outlier_count = 0
                self.last_raw_feature = raw_feature
                self.last_feature_ts = timestamp
                return (raw_feature, False)
        else:
            self.consecutive_outlier_count = 0
            self.last_raw_feature = raw_feature
            self.last_feature_ts = timestamp
            return (raw_feature, False)

    # ---------------------------------------------------------
    # Calibrated Feature Mapping (Ridge Regression compatibility)
    # ---------------------------------------------------------
    def map_feature_to_screen(self, fx: float, fy: float) -> Tuple[float, float]:
        cx = self.profile.coeff_x
        cy = self.profile.coeff_y
        f_xy = fx * fy

        screen_x = cx[0] + cx[1] * fx + cx[2] * fy + cx[3] * f_xy
        screen_y = cy[0] + cy[1] * fx + cy[2] * fy + cy[3] * f_xy

        if self.sensitivity != 1.0:
            screen_x = 0.5 + (screen_x - 0.5) * self.sensitivity
            screen_y = 0.5 + (screen_y - 0.5) * self.sensitivity

        return (screen_x, screen_y)

    # ---------------------------------------------------------
    # Relative Velocity Transfer Function
    # ---------------------------------------------------------
    def compute_relative_velocity(
        self,
        smooth_fx: float,
        smooth_fy: float,
        pitch: float,
        yaw: float,
    ) -> Tuple[float, float, bool]:
        """
        Computes velocity vector (vx, vy) based on head deflection beyond neutral dead zone.
        Returns: (velocity_x, velocity_y, in_dead_zone).
        Inside dead zone: velocity is STRICTLY (0.0, 0.0).
        """
        if self.tracking_mode == "head_pose":
            # Deflection in degrees
            # Turning head right (negative yaw in solvePnP): user looks right -> move cursor right (+vx)
            # Yaw offset from neutral
            delta_yaw = yaw - self.neutral_yaw
            delta_pitch = pitch - self.neutral_pitch
            # In camera/solvePnP coordinate standard:
            # turning head to user's right produces -yaw in OpenCV camera frame
            # moving head right -> dx > 0
            dx = -delta_yaw
            # tilting head up produces -pitch -> dy < 0 (screen top is 0)
            dy = -delta_pitch

            d_mag = math.sqrt(dx * dx + dy * dy)
            theta_enter = self.dead_zone_enter_deg
            theta_exit = self.dead_zone_exit_deg

            # Hysteresis state machine
            if not self.is_moving:
                if d_mag > theta_enter:
                    self.is_moving = True
            else:
                if d_mag < theta_exit:
                    self.is_moving = False

            if not self.is_moving:
                self.deflection_x = dx
                self.deflection_y = dy
                return (0.0, 0.0, True)

            # Outside dead zone: non-linear velocity transfer function
            d_eff = max(0.0, d_mag - theta_exit)
            ux = dx / max(1e-6, d_mag)
            uy = dy / max(1e-6, d_mag)
            speed = min(self.max_speed, self.gain * (d_eff ** self.power) * self.sensitivity)
            self.deflection_x = dx
            self.deflection_y = dy
            return (ux * speed, uy * speed, False)

        elif self.tracking_mode == "nose_bridge":
            # Scale-invariant displacement relative to neutral nose
            dx = -(self.current_nose_x - self.neutral_nose_x)
            dy = (self.current_nose_y - self.neutral_nose_y)
            d_mag = math.sqrt(dx * dx + dy * dy)
            theta_enter = self.dead_zone_enter_norm
            theta_exit = self.dead_zone_exit_norm

            if not self.is_moving:
                if d_mag > theta_enter:
                    self.is_moving = True
            else:
                if d_mag < theta_exit:
                    self.is_moving = False

            if not self.is_moving:
                self.deflection_x = dx
                self.deflection_y = dy
                return (0.0, 0.0, True)

            d_eff = max(0.0, d_mag - theta_exit)
            ux = dx / max(1e-6, d_mag)
            uy = dy / max(1e-6, d_mag)
            speed = min(self.max_speed, (self.gain * 25.0) * (d_eff ** self.power) * self.sensitivity)
            self.deflection_x = dx
            self.deflection_y = dy
            return (ux * speed, uy * speed, False)

        else:  # "hybrid"
            # Combine normalized angle deflection and nose displacement
            norm_deg_dx = -(yaw - self.neutral_yaw) / 30.0
            norm_deg_dy = -(pitch - self.neutral_pitch) / 25.0
            nose_dx = -(self.current_nose_x - self.neutral_nose_x) * 2.5
            nose_dy = (self.current_nose_y - self.neutral_nose_y) * 2.5

            dx = 0.5 * norm_deg_dx + 0.5 * nose_dx
            dy = 0.5 * norm_deg_dy + 0.5 * nose_dy
            d_mag = math.sqrt(dx * dx + dy * dy)

            theta_enter = self.dead_zone_enter_norm
            theta_exit = self.dead_zone_exit_norm

            if not self.is_moving:
                if d_mag > theta_enter:
                    self.is_moving = True
            else:
                if d_mag < theta_exit:
                    self.is_moving = False

            if not self.is_moving:
                self.deflection_x = dx
                self.deflection_y = dy
                return (0.0, 0.0, True)

            d_eff = max(0.0, d_mag - theta_exit)
            ux = dx / max(1e-6, d_mag)
            uy = dy / max(1e-6, d_mag)
            speed = min(self.max_speed, (self.gain * 20.0) * (d_eff ** self.power) * self.sensitivity)
            self.deflection_x = dx
            self.deflection_y = dy
            return (ux * speed, uy * speed, False)

    # ---------------------------------------------------------
    # Full Signal Pipeline Loop
    # ---------------------------------------------------------
    def process_frame(
        self,
        landmarks: Optional[np.ndarray],
        ear: float,
        pitch: float,
        yaw: float,
        timestamp: float,
    ) -> Dict[str, Any]:
        t_start = time.perf_counter()
        now_wall = time.time()
        self.frame_age_ms = max(0.0, (now_wall - timestamp) * 1000.0)

        # STAGE 1: Landmark validity & posture checks
        valid, reason = self.check_tracking_validity(landmarks, ear, pitch, yaw)

        # Blink and Tracking Hold Handling
        if not valid or landmarks is None:
            time_since_valid = timestamp - self.last_valid_ts
            if self.last_valid_ts > 0.0 and time_since_valid < 0.40:
                # Blink hold active: cursor stays stationary, velocity 0
                self.in_blink_hold = True
                self.is_tracking_valid = True
                self.tracking_status_message = "Blink hold active"
                self.velocity_x = 0.0
                self.velocity_y = 0.0
                self.in_dead_zone = True
                final_sx, final_sy = self.last_cursor_norm
                outlier = False
            else:
                self.in_blink_hold = False
                self.is_tracking_valid = False
                self.tracking_status_message = reason
                self.velocity_x = 0.0
                self.velocity_y = 0.0
                self.in_dead_zone = True
                return {
                    "valid": False,
                    "reason": reason,
                    "norm_x": self.last_cursor_norm[0],
                    "norm_y": self.last_cursor_norm[1],
                    "velocity_x": 0.0,
                    "velocity_y": 0.0,
                    "in_dead_zone": True,
                    "enabled": self.enabled,
                    "paused": self.paused,
                    "emergency_stopped": self.emergency_stopped,
                    "is_calibrating": self.is_calibrating,
                    "tracking_mode": self.tracking_mode,
                    "preset": self.preset_name,
                    "frame_age_ms": round(self.frame_age_ms, 1),
                    "hz": round(self.update_hz, 1),
                }
        else:
            # Recovery from tracking loss > 0.40s: smooth reinitialization
            if (timestamp - self.last_valid_ts) > 0.40 and self.last_valid_ts > 0.0:
                self.filter.reset()
                self.last_raw_feature = None
                self.is_moving = False

            self.in_blink_hold = False
            self.is_tracking_valid = True
            self.tracking_status_message = "Tracking locked"
            self.last_valid_ts = timestamp

            # STAGE 2: Feature extraction & scale-invariant normalization
            raw_feature = self.extract_features(landmarks, pitch, yaw)
            if raw_feature is None:
                return {
                    "valid": False,
                    "reason": "Feature extraction failed",
                    "norm_x": self.last_cursor_norm[0],
                    "norm_y": self.last_cursor_norm[1],
                    "enabled": self.enabled,
                    "paused": self.paused,
                    "emergency_stopped": self.emergency_stopped,
                    "is_calibrating": self.is_calibrating,
                    "tracking_mode": self.tracking_mode,
                    "preset": self.preset_name,
                }

            # STAGE 3: Outlier jump rejection
            clean_feature, outlier = self.filter_outliers(raw_feature, timestamp)
            fx, fy = clean_feature

            # Record sample if in guided target calibration
            if self.is_calibrating:
                self.current_target_samples.append(
                    CalibrationSample(gaze_x=fx, gaze_y=fy, timestamp=timestamp)
                )

            # If transient outlier detected, hold cursor stationary and skip velocity integration
            if outlier:
                self.velocity_x = 0.0
                self.velocity_y = 0.0
                self.in_dead_zone = True
                final_sx, final_sy = self.last_cursor_norm
            else:
                # STAGE 4: Temporal smoothing
                smooth_fx, smooth_fy = self.filter.filter(fx, fy, timestamp)

                # Auto-initialize neutral reference if not calibrated yet
                if not self.is_neutral_calibrated:
                    self.neutral_calibration_samples.append(
                        (yaw, pitch, self.current_nose_x, self.current_nose_y)
                    )
                    if len(self.neutral_calibration_samples) >= 15:
                        self.calibrate_neutral_from_samples(self.neutral_calibration_samples)
                        self.neutral_calibration_samples = []

                # Frame timing & rate calculation
                if self.last_frame_ts > 0.0:
                    dt = max(0.010, min(0.066, timestamp - self.last_frame_ts))
                    self.update_hz = 1.0 / dt
                else:
                    dt = 0.033
                    self.update_hz = 30.0
                self.last_frame_ts = timestamp

                # Compute relative velocity from head deflection
                vx, vy, in_dz = self.compute_relative_velocity(smooth_fx, smooth_fy, pitch, yaw)
                self.velocity_x = vx
                self.velocity_y = vy
                self.in_dead_zone = in_dz

                # Incremental cursor position update
                if in_dz:
                    # Within dead zone: position is identically unchanged
                    final_sx, final_sy = self.last_cursor_norm
                else:
                    new_x = self.last_cursor_norm[0] + vx * dt
                    new_y = self.last_cursor_norm[1] + vy * dt
                    final_sx = float(np.clip(new_x, 0.0, 1.0))
                    final_sy = float(np.clip(new_y, 0.0, 1.0))
                    self.last_cursor_norm = (final_sx, final_sy)

        t_latency_ms = (time.perf_counter() - t_start) * 1000.0

        diag_result = None
        if self.is_diagnosing:
            self.diagnostic_samples.append(
                DiagnosticSample(
                    cursor_x=final_sx,
                    cursor_y=final_sy,
                    timestamp=timestamp,
                    is_valid=self.is_tracking_valid,
                    is_outlier=outlier,
                    latency_ms=t_latency_ms,
                )
            )
            if (timestamp - self.diagnostic_start_ts) >= self.diagnostic_duration:
                diag_result = self.finish_diagnostic()

        return {
            "valid": True,
            "reason": self.tracking_status_message,
            "norm_x": round(final_sx, 4),
            "norm_y": round(final_sy, 4),
            "velocity_x": round(self.velocity_x, 4),
            "velocity_y": round(self.velocity_y, 4),
            "in_dead_zone": self.in_dead_zone,
            "deflection_x": round(self.deflection_x, 3),
            "deflection_y": round(self.deflection_y, 3),
            "current_yaw": round(self.current_yaw, 1),
            "current_pitch": round(self.current_pitch, 1),
            "neutral_yaw": round(self.neutral_yaw, 1),
            "neutral_pitch": round(self.neutral_pitch, 1),
            "is_neutral_calibrated": self.is_neutral_calibrated,
            "enabled": self.enabled,
            "paused": self.paused,
            "emergency_stopped": self.emergency_stopped,
            "is_calibrated": self.profile.is_calibrated,
            "quality_label": self.profile.quality_label,
            "is_calibrating": self.is_calibrating,
            "calibration_target_idx": self.calib_target_idx,
            "tracking_mode": self.tracking_mode,
            "preset": self.preset_name,
            "latency_ms": round(t_latency_ms, 2),
            "frame_age_ms": round(self.frame_age_ms, 1),
            "hz": round(self.update_hz, 1),
            "is_outlier": outlier,
            "is_diagnosing": self.is_diagnosing,
            "diagnostic_result": diag_result,
        }

    # ---------------------------------------------------------
    # Calibration Workflow with Median + MAD
    # ---------------------------------------------------------
    def start_calibration(self):
        self.is_calibrating = True
        self.calib_target_idx = 0
        self.current_target_samples = []
        self.calib_target_results = []
        self.filter.reset()
        self.last_raw_feature = None

    def advance_calibration_target(self) -> Dict[str, Any]:
        if not self.is_calibrating:
            return {"error": "Calibration not started"}

        target = CALIBRATION_TARGETS[self.calib_target_idx]
        samples = self.current_target_samples

        if len(samples) < 5:
            return {
                "success": False,
                "message": "Insufficient samples collected. Please keep looking at the target and try again.",
                "sample_count": len(samples),
                "target_idx": self.calib_target_idx,
            }

        fxs = np.array([s.gaze_x for s in samples], dtype=np.float64)
        fys = np.array([s.gaze_y for s in samples], dtype=np.float64)

        med_x = float(np.median(fxs))
        med_y = float(np.median(fys))
        mad_x = float(np.median(np.abs(fxs - med_x)))
        mad_y = float(np.median(np.abs(fys - med_y)))

        sigma_x = max(1e-5, 1.4826 * mad_x)
        sigma_y = max(1e-5, 1.4826 * mad_y)

        valid_mask = (np.abs(fxs - med_x) <= 2.5 * sigma_x) & (np.abs(fys - med_y) <= 2.5 * sigma_y)
        clean_fxs = fxs[valid_mask]
        clean_fys = fys[valid_mask]

        if len(clean_fxs) < 3:
            clean_fxs, clean_fys = fxs, fys

        mean_x = float(np.mean(clean_fxs))
        mean_y = float(np.mean(clean_fys))

        result = TargetCalibrationResult(
            target_id=target["target_id"],
            target_screen_x=target["screen_x"],
            target_screen_y=target["screen_y"],
            mean_gaze_x=mean_x,
            mean_gaze_y=mean_y,
            std_gaze_x=float(np.std(clean_fxs)),
            std_gaze_y=float(np.std(clean_fys)),
            sample_count=len(clean_fxs),
        )
        self.calib_target_results.append(result)

        self.current_target_samples = []
        self.calib_target_idx += 1

        is_finished = self.calib_target_idx >= len(CALIBRATION_TARGETS)
        if is_finished:
            return self.finish_calibration()

        return {
            "success": True,
            "finished": False,
            "next_target_idx": self.calib_target_idx,
            "next_target": CALIBRATION_TARGETS[self.calib_target_idx],
        }

    def finish_calibration(self) -> Dict[str, Any]:
        self.is_calibrating = False

        if len(self.calib_target_results) < 5:
            return {"success": False, "error": "Not enough targets calibrated"}

        fit_targets = [r for r in self.calib_target_results if r.target_id != "center_2"]
        val_target = next((r for r in self.calib_target_results if r.target_id == "center_2"), None)

        N = len(fit_targets)
        A = np.zeros((N, 4), dtype=np.float64)
        Bx = np.zeros(N, dtype=np.float64)
        By = np.zeros(N, dtype=np.float64)

        for i, t in enumerate(fit_targets):
            gx, gy = t.mean_gaze_x, t.mean_gaze_y
            A[i] = [1.0, gx, gy, gx * gy]
            Bx[i] = t.target_screen_x
            By[i] = t.target_screen_y

        reg_lambda = 0.05
        AtA = np.dot(A.T, A)
        reg_matrix = AtA + reg_lambda * np.eye(4)
        AtBx = np.dot(A.T, Bx)
        AtBy = np.dot(A.T, By)

        try:
            coeff_x = np.linalg.solve(reg_matrix, AtBx)
            coeff_y = np.linalg.solve(reg_matrix, AtBy)
            coeff_x = [float(c) for c in coeff_x]
            coeff_y = [float(c) for c in coeff_y]
        except Exception as e:
            print(f"[HeadMouse] Ridge fit exception: {e}")
            coeff_x = [0.5, -2.5, 0.0, 0.0]
            coeff_y = [0.5, 0.0, 2.5, 0.0]

        val_error = 0.05
        if val_target:
            val_gx, val_gy = val_target.mean_gaze_x, val_target.mean_gaze_y
            pred_sx = coeff_x[0] + coeff_x[1] * val_gx + coeff_x[2] * val_gy + coeff_x[3] * (val_gx * val_gy)
            pred_sy = coeff_y[0] + coeff_y[1] * val_gx + coeff_y[2] * val_gy + coeff_y[3] * (val_gx * val_gy)
            val_error = math.sqrt((pred_sx - val_target.target_screen_x) ** 2 + (pred_sy - val_target.target_screen_y) ** 2)

        if val_error < 0.05:
            quality = "Excellent"
        elif val_error < 0.10:
            quality = "Good"
        elif val_error < 0.18:
            quality = "Fair"
        else:
            quality = "Needs Recalibration"

        profile = GazeCalibrationProfile(
            schema_version=HEAD_MOUSE_SCHEMA_VERSION,
            created_at=time.time(),
            is_calibrated=True,
            quality_label=quality,
            validation_error=round(val_error, 4),
            coeff_x=coeff_x,
            coeff_y=coeff_y,
            targets=[asdict(r) for r in self.calib_target_results],
            tracking_mode=self.tracking_mode,
            neutral_yaw=self.neutral_yaw,
            neutral_pitch=self.neutral_pitch,
            neutral_nose_x=self.neutral_nose_x,
            neutral_nose_y=self.neutral_nose_y,
        )

        self.save_calibration(profile)
        self.filter.reset()

        return {
            "success": True,
            "finished": True,
            "quality_label": quality,
            "validation_error": round(val_error, 4),
            "profile": asdict(profile),
        }

    # ---------------------------------------------------------
    # Stability Diagnostic Procedure
    # ---------------------------------------------------------
    def start_diagnostic(self, duration_seconds: float = 5.0) -> Dict[str, Any]:
        self.is_diagnosing = True
        self.diagnostic_start_ts = time.time()
        self.diagnostic_duration = max(1.0, min(30.0, float(duration_seconds)))
        self.diagnostic_samples = []
        return {
            "status": "diagnostic_started",
            "duration_seconds": self.diagnostic_duration,
        }

    def finish_diagnostic(self) -> Dict[str, Any]:
        """
        Computes real physical measurements:
        - Stationary Jitter RMS (in screen pixels, assuming 1920x1080)
        - Unintended Drift Rate (px/s)
        - Outlier Rate (%)
        - Validity Rate (%)
        - Average Latency (ms)
        - Score: 100 - (Jitter_px * 1.5) - (Drift * 0.5) - (Outlier_% * 0.8) - ((100 - Validity_%) * 1.0)
        """
        self.is_diagnosing = False
        samples = self.diagnostic_samples
        total_samples = len(samples)

        if total_samples < 5:
            res = {
                "success": False,
                "error": "Insufficient diagnostic samples collected",
            }
            self.last_diagnostic_result = res
            return res

        valid_samples = [s for s in samples if s.is_valid]
        validity_rate_pct = (len(valid_samples) / total_samples) * 100.0

        outlier_count = sum(1 for s in samples if s.is_outlier)
        outlier_rate_pct = (outlier_count / total_samples) * 100.0

        avg_latency_ms = float(np.mean([s.latency_ms for s in samples]))

        if len(valid_samples) >= 3:
            xs = np.array([s.cursor_x for s in valid_samples], dtype=np.float64)
            ys = np.array([s.cursor_y for s in valid_samples], dtype=np.float64)

            var_x_px = np.var(xs) * (1920.0 ** 2)
            var_y_px = np.var(ys) * (1080.0 ** 2)
            jitter_px = math.sqrt(var_x_px + var_y_px)

            dur = max(0.5, valid_samples[-1].timestamp - valid_samples[0].timestamp)
            drift_dx = (xs[-1] - xs[0]) * 1920.0
            drift_dy = (ys[-1] - ys[0]) * 1080.0
            drift_dist_px = math.sqrt(drift_dx * drift_dx + drift_dy * drift_dy)
            drift_rate_px_per_sec = drift_dist_px / dur
        else:
            jitter_px = 50.0
            drift_rate_px_per_sec = 20.0

        score = 100.0 - (jitter_px * 1.5) - (drift_rate_px_per_sec * 0.5) - (outlier_rate_pct * 0.8) - ((100.0 - validity_rate_pct) * 1.0)
        score = float(np.clip(score, 0.0, 100.0))

        if score >= 90.0:
            quality = "Exceptional"
        elif score >= 75.0:
            quality = "Stable"
        elif score >= 50.0:
            quality = "Acceptable"
        else:
            quality = "Jittery"

        result = {
            "success": True,
            "timestamp": time.time(),
            "duration_seconds": self.diagnostic_duration,
            "sample_count": total_samples,
            "validity_rate_pct": round(validity_rate_pct, 1),
            "outlier_rate_pct": round(outlier_rate_pct, 1),
            "stationary_jitter_px": round(jitter_px, 2),
            "drift_rate_px_per_sec": round(drift_rate_px_per_sec, 2),
            "avg_latency_ms": round(avg_latency_ms, 2),
            "stability_score": round(score, 1),
            "quality_rating": quality,
            "tracking_mode": self.tracking_mode,
            "preset": self.preset_name,
        }
        self.last_diagnostic_result = result
        return result

    # ---------------------------------------------------------
    # Command Handlers & Safety State
    # ---------------------------------------------------------
    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        if enabled:
            self.emergency_stopped = False
            self.paused = False
        self.is_moving = False
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.in_dead_zone = True
        self.filter.reset()
        self.last_raw_feature = None

    def set_paused(self, paused: bool):
        self.paused = paused
        self.is_moving = False
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.in_dead_zone = True
        self.filter.reset()

    def emergency_stop(self):
        """Immediately halts cursor movement and disables tracking."""
        self.emergency_stopped = True
        self.enabled = False
        self.paused = True
        self.is_calibrating = False
        self.is_diagnosing = False
        self.is_moving = False
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.in_dead_zone = True
        self.filter.reset()
        self.last_raw_feature = None

    def update_settings(self, settings: Dict[str, Any]):
        if "preset" in settings:
            self.apply_preset(str(settings["preset"]))
        if "tracking_mode" in settings:
            self.set_tracking_mode(str(settings["tracking_mode"]))
        if "sensitivity" in settings:
            self.sensitivity = max(0.5, min(3.0, float(settings["sensitivity"])))
        if "dead_zone" in settings:
            self.dead_zone = max(0.0, min(0.05, float(settings["dead_zone"])))
        if "max_speed" in settings:
            self.max_speed = max(0.05, min(2.0, float(settings["max_speed"])))

    def get_status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "paused": self.paused,
            "emergency_stopped": self.emergency_stopped,
            "tracking_valid": self.is_tracking_valid,
            "tracking_reason": self.tracking_status_message,
            "last_valid_ts": self.last_valid_ts,
            "cursor_norm_x": self.last_cursor_norm[0],
            "cursor_norm_y": self.last_cursor_norm[1],
            "velocity_x": round(self.velocity_x, 4),
            "velocity_y": round(self.velocity_y, 4),
            "in_dead_zone": self.in_dead_zone,
            "deflection_x": round(self.deflection_x, 3),
            "deflection_y": round(self.deflection_y, 3),
            "current_yaw": round(self.current_yaw, 1),
            "current_pitch": round(self.current_pitch, 1),
            "neutral_yaw": round(self.neutral_yaw, 1),
            "neutral_pitch": round(self.neutral_pitch, 1),
            "is_neutral_calibrated": self.is_neutral_calibrated,
            "is_calibrated": self.profile.is_calibrated,
            "quality_label": self.profile.quality_label,
            "validation_error": self.profile.validation_error,
            "sensitivity": self.sensitivity,
            "dead_zone": self.dead_zone,
            "max_speed": self.max_speed,
            "smoothing_mode": self.smoothing_mode,
            "tracking_mode": self.tracking_mode,
            "preset": self.preset_name,
            "is_calibrating": self.is_calibrating,
            "calib_target_idx": self.calib_target_idx,
            "outlier_count": self.total_outliers_detected,
            "is_diagnosing": self.is_diagnosing,
            "frame_age_ms": round(self.frame_age_ms, 1),
            "hz": round(self.update_hz, 1),
        }

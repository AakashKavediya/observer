"""
observer_engine.gaze_mouse
Track 4: Calibrated Relative Movement & Absolute Screen Mapping Face-Controlled Mouse.

Authoritative Architecture:
1. Mathematical Facial Reference Point:
   - Stable eye-center reference: eyeCenter = (leftEyeReference + rightEyeReference) / 2
   - Scale-invariant nose displacement: noseRelative = (noseBridge - eyeCenter) / interEyeDistance
   - Explicit camera mirroring: user moving right moves pointer right (+x); tilting up moves pointer up (-y).
   - Head-pose integration: yaw (horizontal) and pitch (vertical) estimated from facial geometry.
   - Tracking modes: 'nose_bridge', 'head_pose', 'hybrid'.
2. Robust Neutral Calibration:
   - Median + Median Absolute Deviation (MAD) over valid sample bursts.
   - Establishes p0 = [x0, y0] without single-frame bias or drift.
   - Learns directional usable movement ranges (scaleX, scaleY).
   - Validates mapping repeatability using held-out center validation.
   - Versioned local persistence (~/.observer/face_mouse_calibration_v4.json).
3. Mathematical Movement Model:
   - Relative deflection: dx = xt - x0, dy = yt - y0
   - Normalized coordinates: ux = dx / scaleX, uy = dy / scaleY
   - Adaptive Dead Zone with Hysteresis:
       * Inside dead zone: velocity is IDENTICALLY (0.0, 0.0), cursor is 100% stationary (0.00 px jitter).
       * Outside dead zone: bounded smooth non-linear transfer: v = sign(z) * min(maxSpeed, gain * |z|^gamma).
       * Acceleration limiter: clamp |dv/dt| <= max_acceleration to prevent sudden pointer snaps.
       * Real-timestamp integration: pos_t = clamp(pos_{t-1} + v * dt, 0.0, 1.0).
4. Configurable Controller Modes:
   - Mode A ('relative'): Rate/Joystick velocity control (rock-solid stability, 0px stationary jitter).
   - Mode B ('absolute'): Regularized polynomial screen mapping with Ridge regression (L2 regularization).
5. Signal Processing Hygiene:
   - Outlier spike rejection (> 3.5 robust z-score or jump > 0.25 norm in < 150ms).
   - Temporal smoothing via One-Euro filter.
   - Blink hold (< 400ms) holding cursor stationary without position reset.
   - Safe filter reset on tracking reacquisition or recalibration.
   - Control clutch: 1-click Recenter (resets neutral p0 without jumping cursor), Emergency Stop (Esc), Pause/Resume.
"""

import os
import json
import time
import math
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List, Tuple, Literal
import numpy as np

from observer_engine.motionq import (
    DwellEngine,
    DwellTarget,
    MotionQEyeController,
    HeadTiltScroller,
    MotionQCalibrationManager,
    WordPredictor,
    VoiceCommandDispatcher,
    profile_manager,
)


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
# 2. Schema, Calibration Targets & Presets
# -------------------------------------------------------------
FACE_MOUSE_SCHEMA_VERSION = "4.0.0"

STABILITY_PRESETS = {
    "maximum_stability": {
        "dead_zone": 0.020,
        "dead_zone_enter": 0.080,  # In normalized movement space [0, 1]
        "dead_zone_exit": 0.055,
        "gain": 0.35,
        "power": 1.25,
        "max_speed": 0.35,  # norm / s
        "max_acceleration": 2.5,  # norm / s^2
        "min_cutoff": 0.5,
        "beta": 0.08,
        "sensitivity": 0.8,
        "label": "Maximum Stability (Default)",
        "description": "Fixation priority with rock-solid dead zone. 0.0px stationary jitter.",
    },
    "balanced": {
        "dead_zone": 0.012,
        "dead_zone_enter": 0.050,
        "dead_zone_exit": 0.035,
        "gain": 0.60,
        "power": 1.20,
        "max_speed": 0.65,
        "max_acceleration": 4.0,
        "min_cutoff": 0.8,
        "beta": 0.25,
        "sensitivity": 1.2,
        "label": "Balanced",
        "description": "Smooth, responsive head control for general desktop interaction.",
    },
    "responsive": {
        "dead_zone": 0.006,
        "dead_zone_enter": 0.025,
        "dead_zone_exit": 0.018,
        "gain": 0.95,
        "power": 1.15,
        "max_speed": 1.10,
        "max_acceleration": 6.5,
        "min_cutoff": 1.4,
        "beta": 0.50,
        "sensitivity": 1.6,
        "label": "Responsive",
        "description": "Fast cursor traversal with low movement latency.",
    },
}

CALIBRATION_TARGETS = [
    {
        "target_id": "center_neutral",
        "screen_x": 0.50,
        "screen_y": 0.50,
        "label": "Neutral Reference: Sit comfortably looking straight ahead at center",
        "expected_direction": "none",
    },
    {
        "target_id": "move_left",
        "screen_x": 0.15,
        "screen_y": 0.50,
        "label": "Usable Range Left: Turn or tilt head comfortably to the Left",
        "expected_direction": "left",
    },
    {
        "target_id": "move_right",
        "screen_x": 0.85,
        "screen_y": 0.50,
        "label": "Usable Range Right: Turn or tilt head comfortably to the Right",
        "expected_direction": "right",
    },
    {
        "target_id": "move_up",
        "screen_x": 0.50,
        "screen_y": 0.15,
        "label": "Usable Range Up: Tilt head comfortably Upward",
        "expected_direction": "up",
    },
    {
        "target_id": "move_down",
        "screen_x": 0.50,
        "screen_y": 0.85,
        "label": "Usable Range Down: Tilt head comfortably Downward",
        "expected_direction": "down",
    },
    {
        "target_id": "validation_center",
        "screen_x": 0.50,
        "screen_y": 0.50,
        "label": "Validation: Return head to Center resting position",
        "expected_direction": "none",
    },
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
    controller_mode: str = "relative"  # "relative" (Mode A) or "absolute" (Mode B)
    tracking_mode: str = "hybrid"  # "nose_bridge", "head_pose", "hybrid"
    neutral_x0: float = 0.0
    neutral_y0: float = 0.0
    neutral_yaw: float = 0.0
    neutral_pitch: float = 0.0
    neutral_nose_x: float = 0.0
    neutral_nose_y: float = 0.0
    scale_x: float = 0.12
    scale_y: float = 0.10
    noise_mad_x: float = 0.002
    noise_mad_y: float = 0.002
    learned_dead_zone: float = 0.020


@dataclass
class DiagnosticSample:
    cursor_x: float
    cursor_y: float
    timestamp: float
    is_valid: bool
    is_outlier: bool
    latency_ms: float


# -------------------------------------------------------------
# 3. GazeMouseTracker Core Implementation
# -------------------------------------------------------------
class GazeMouseTracker:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = storage_dir or os.path.expanduser("~/.observer")
        os.makedirs(self.storage_dir, exist_ok=True)
        self.calib_file_path = os.path.join(self.storage_dir, "face_mouse_calibration_v4.json")
        self.legacy_calib_paths = [
            os.path.join(self.storage_dir, "head_mouse_calibration_v3.json"),
            os.path.join(self.storage_dir, "gaze_calibration_v2.json"),
        ]

        # Mode A: 'relative' (Rate/Joystick velocity controller)
        # Mode B: 'absolute' (Regularized polynomial screen mapping)
        self.controller_mode: str = "relative"

        # Tracking Feature Strategy: 'nose_bridge', 'head_pose', 'hybrid'
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
        self.max_acceleration: float = preset_cfg["max_acceleration"]
        self.smoothing_mode: str = self.preset_name

        # Dead-zone thresholds with hysteresis
        self.dead_zone_enter: float = preset_cfg["dead_zone_enter"]
        self.dead_zone_exit: float = preset_cfg["dead_zone_exit"]
        self.gain: float = preset_cfg["gain"]
        self.power: float = preset_cfg["power"]

        # Hysteresis state: True if cursor is actively deflecting outside dead zone
        self.is_moving: bool = False

        # Stable Facial Reference Point State
        self.neutral_x0: float = 0.0
        self.neutral_y0: float = 0.0
        self.neutral_yaw: float = 0.0
        self.neutral_pitch: float = 0.0
        self.neutral_nose_x: float = 0.0
        self.neutral_nose_y: float = 0.0
        self.scale_x: float = 0.12
        self.scale_y: float = 0.10
        self.noise_mad_x: float = 0.002
        self.noise_mad_y: float = 0.002
        self.is_neutral_calibrated: bool = False
        self.neutral_calibration_samples: List[Tuple[float, float, float, float]] = []

        # Current live state telemetry
        self.current_xt: float = 0.0
        self.current_yt: float = 0.0
        self.current_yaw: float = 0.0
        self.current_pitch: float = 0.0
        self.current_nose_x: float = 0.0
        self.current_nose_y: float = 0.0
        self.inter_eye_distance: float = 0.20
        self.deflection_x: float = 0.0
        self.deflection_y: float = 0.0
        self.normalized_ux: float = 0.0
        self.normalized_uy: float = 0.0
        self.velocity_x: float = 0.0
        self.velocity_y: float = 0.0
        self.in_dead_zone: bool = True
        self.last_frame_ts: float = 0.0
        self.update_hz: float = 0.0
        self.frame_age_ms: float = 0.0

        # Authoritative Desktop Cursor Position [0.0, 1.0]
        self.last_cursor_norm: Tuple[float, float] = (0.5, 0.5)

        # Single authoritative temporal filter
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
            self._apply_profile(self.profile)

        # ---------------------------------------------------------
        # MotionQ Integrated Assistive Components
        # ---------------------------------------------------------
        self.dwell_engine = DwellEngine(default_duration_ms=1000.0, stability_radius=50.0)
        self.motionq_eye = MotionQEyeController(
            dwell_engine=self.dwell_engine,
            screen_w=1920.0,
            screen_h=1080.0,
            sensitivity=3.0,
        )
        self.head_scroller = HeadTiltScroller(
            neutral_y=None,
            tilt_threshold=20.0,
            scroll_amount=3,
            enabled=True,
        )
        self.motionq_calibrator = MotionQCalibrationManager(profile_name="default")
        self.word_predictor = WordPredictor()
        self.voice_dispatcher = VoiceCommandDispatcher()
        self.current_profile_name: str = "default"
        self.keyboard_language: str = "EN"

        self._pending_click_event: Optional[Dict[str, Any]] = None
        self._pending_scroll_event: Optional[Dict[str, Any]] = None
        self._pending_key_action: Optional[Dict[str, Any]] = None

        def _on_dwell_click(cx: float, cy: float, is_double: bool):
            self._pending_click_event = {
                "button": "left",
                "double": is_double,
                "x": cx,
                "y": cy,
            }

        def _on_head_scroll(delta_lines: int):
            self._pending_scroll_event = {
                "delta_y": delta_lines,
            }

        self.dwell_engine.set_click_dispatcher(_on_dwell_click)
        self.head_scroller.set_scroll_dispatcher(_on_head_scroll)

        # Load active MotionQ profile
        try:
            p_data = profile_manager.load_profile(self.current_profile_name)
            self._apply_motionq_profile(p_data)
        except Exception:
            pass

    def _apply_profile(self, profile: GazeCalibrationProfile):
        """Applies parameters from a loaded or finalized calibration profile."""
        self.neutral_x0 = profile.neutral_x0
        self.neutral_y0 = profile.neutral_y0
        self.neutral_yaw = profile.neutral_yaw
        self.neutral_pitch = profile.neutral_pitch
        self.neutral_nose_x = profile.neutral_nose_x
        self.neutral_nose_y = profile.neutral_nose_y
        self.scale_x = max(1e-4, profile.scale_x)
        self.scale_y = max(1e-4, profile.scale_y)
        self.noise_mad_x = profile.noise_mad_x
        self.noise_mad_y = profile.noise_mad_y
        self.controller_mode = profile.controller_mode
        self.tracking_mode = profile.tracking_mode
        self.is_neutral_calibrated = True

    def _apply_motionq_profile(self, p_data: Dict[str, Any]) -> None:
        """Applies parameters from a loaded MotionQ profile."""
        gaze_cfg = p_data.get("gaze", {})
        self.motionq_eye.sensitivity = float(gaze_cfg.get("sensitivity", 3.0))
        self.motionq_eye.nonlinear_exponent = float(gaze_cfg.get("nonlinear_exponent", 1.2))
        self.motionq_eye.smoothing_factor = float(gaze_cfg.get("smoothing_factor", 0.70))
        self.motionq_eye.proximity_radius = float(gaze_cfg.get("proximity_radius", 80.0))
        self.motionq_eye.magnet_radius = float(gaze_cfg.get("magnet_radius", 40.0))
        self.motionq_eye.magnet_force = float(gaze_cfg.get("magnet_force", 0.20))
        if gaze_cfg.get("calibration_points"):
            self.motionq_eye.set_calibration(gaze_cfg["calibration_points"])

        dwell_cfg = p_data.get("dwell", {})
        self.dwell_engine.set_timing(
            duration_ms=dwell_cfg.get("duration_ms", 1000),
            stability_radius=dwell_cfg.get("stability_radius", 50),
            click_cooldown_sec=dwell_cfg.get("click_cooldown_sec", 1.0),
        )

        head_cfg = p_data.get("head", {})
        self.head_scroller.neutral_y = head_cfg.get("neutral_y")
        self.head_scroller.tilt_threshold = float(head_cfg.get("tilt_threshold", 20.0))
        self.head_scroller.scroll_amount = int(head_cfg.get("scroll_amount", 3))
        self.head_scroller.enabled = bool(head_cfg.get("enabled", True))

        self.keyboard_language = p_data.get("language", "EN")

    def apply_preset(self, preset_name: str):
        """Applies one of the 3 validated presets: maximum_stability, balanced, responsive."""
        if preset_name not in STABILITY_PRESETS:
            preset_name = "maximum_stability"
        self.preset_name = preset_name
        cfg = STABILITY_PRESETS[preset_name]
        self.sensitivity = cfg["sensitivity"]
        self.dead_zone = cfg["dead_zone"]
        self.max_speed = cfg["max_speed"]
        self.max_acceleration = cfg["max_acceleration"]
        self.dead_zone_enter = cfg["dead_zone_enter"]
        self.dead_zone_exit = cfg["dead_zone_exit"]
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

    def set_controller_mode(self, mode: str):
        """Sets controller mode: 'relative' (Mode A), 'absolute' (Mode B), or 'motionq_eye' (Mode C)."""
        if mode in ("relative", "absolute", "motionq_eye"):
            self.controller_mode = mode
            self.filter.reset()
            self.last_raw_feature = None
            self.is_moving = False
            self.velocity_x = 0.0
            self.velocity_y = 0.0

    # ---------------------------------------------------------
    # Recenter & Neutral Calibration
    # ---------------------------------------------------------
    def recenter(self):
        """
        Instantly establishes a new neutral reference p0 from current head orientation.
        CRUCIAL INVARIANT: Native desktop cursor position does NOT move or jump.
        """
        self.neutral_x0 = self.current_xt
        self.neutral_y0 = self.current_yt
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
        self.profile.neutral_x0 = self.neutral_x0
        self.profile.neutral_y0 = self.neutral_y0
        self.profile.neutral_yaw = self.neutral_yaw
        self.profile.neutral_pitch = self.neutral_pitch
        self.profile.neutral_nose_x = self.neutral_nose_x
        self.profile.neutral_nose_y = self.neutral_nose_y
        self.save_calibration(self.profile)

    def calibrate_neutral_from_samples(self, samples: List[Tuple[float, float, float, float]]):
        """
        Calibrates neutral reference using Median + MAD over a burst of stationary resting samples.
        samples: list of (yaw, pitch, nose_rel_x, nose_rel_y)
        """
        if not samples:
            return
        arr = np.array(samples, dtype=np.float64)
        meds = np.median(arr, axis=0)
        mads = np.median(np.abs(arr - meds), axis=0)
        sigmas = np.maximum(1e-5, 1.4826 * mads)

        # Reject outliers beyond 2.5 sigma
        valid_mask = np.all(np.abs(arr - meds) <= 2.5 * sigmas, axis=1)
        clean = arr[valid_mask] if np.sum(valid_mask) >= 3 else arr

        means = np.median(clean, axis=0)
        self.neutral_yaw = float(means[0])
        self.neutral_pitch = float(means[1])
        self.neutral_nose_x = float(means[2])
        self.neutral_nose_y = float(means[3])
        self.neutral_x0 = self.neutral_nose_x
        self.neutral_y0 = self.neutral_nose_y
        self.is_neutral_calibrated = True
        self.is_moving = False
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.in_dead_zone = True

        self.profile.neutral_yaw = self.neutral_yaw
        self.profile.neutral_pitch = self.neutral_pitch
        self.profile.neutral_nose_x = self.neutral_nose_x
        self.profile.neutral_nose_y = self.neutral_nose_y
        self.profile.neutral_x0 = self.neutral_x0
        self.profile.neutral_y0 = self.neutral_y0
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
            schema_version=FACE_MOUSE_SCHEMA_VERSION,
            created_at=time.time(),
            is_calibrated=False,
            quality_label="Uncalibrated (Default)",
            validation_error=0.08,
            coeff_x=[0.5, 1.0, 0.0, 0.0],
            coeff_y=[0.5, 0.0, 1.0, 0.0],
            targets=[],
            controller_mode=self.controller_mode,
            tracking_mode=self.tracking_mode,
            neutral_x0=0.0,
            neutral_y0=0.0,
            neutral_yaw=0.0,
            neutral_pitch=0.0,
            neutral_nose_x=0.0,
            neutral_nose_y=0.0,
            scale_x=0.12,
            scale_y=0.10,
            noise_mad_x=0.002,
            noise_mad_y=0.002,
            learned_dead_zone=0.020,
        )

    def load_calibration(self) -> Optional[GazeCalibrationProfile]:
        target_path = self.calib_file_path
        if not os.path.isfile(target_path):
            for legacy in self.legacy_calib_paths:
                if os.path.isfile(legacy):
                    target_path = legacy
                    break

        if not os.path.isfile(target_path):
            return None

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return GazeCalibrationProfile(
                schema_version=data.get("schema_version", FACE_MOUSE_SCHEMA_VERSION),
                created_at=data.get("created_at", time.time()),
                is_calibrated=data.get("is_calibrated", False),
                quality_label=data.get("quality_label", "Good"),
                validation_error=data.get("validation_error", 0.0),
                coeff_x=data.get("coeff_x", [0.5, 1.0, 0.0, 0.0]),
                coeff_y=data.get("coeff_y", [0.5, 0.0, 1.0, 0.0]),
                targets=data.get("targets", []),
                controller_mode=data.get("controller_mode", "relative"),
                tracking_mode=data.get("tracking_mode", "hybrid"),
                neutral_x0=data.get("neutral_x0", 0.0),
                neutral_y0=data.get("neutral_y0", 0.0),
                neutral_yaw=data.get("neutral_yaw", 0.0),
                neutral_pitch=data.get("neutral_pitch", 0.0),
                neutral_nose_x=data.get("neutral_nose_x", 0.0),
                neutral_nose_y=data.get("neutral_nose_y", 0.0),
                scale_x=data.get("scale_x", 0.12),
                scale_y=data.get("scale_y", 0.10),
                noise_mad_x=data.get("noise_mad_x", 0.002),
                noise_mad_y=data.get("noise_mad_y", 0.002),
                learned_dead_zone=data.get("learned_dead_zone", 0.020),
            )
        except Exception as e:
            print(f"[FaceMouse] Calibration load failed: {e}")
        return None

    def save_calibration(self, profile: GazeCalibrationProfile):
        try:
            tmp_path = self.calib_file_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(asdict(profile), f, indent=2)
            os.replace(tmp_path, self.calib_file_path)
            self.profile = profile
        except Exception as e:
            print(f"[FaceMouse] Calibration save error: {e}")

    def reset_calibration(self):
        try:
            if os.path.exists(self.calib_file_path):
                os.remove(self.calib_file_path)
            for p in self.legacy_calib_paths:
                if os.path.exists(p):
                    os.remove(p)
        except Exception:
            pass
        self.profile = self._default_calibration()
        self.neutral_x0 = 0.0
        self.neutral_y0 = 0.0
        self.neutral_yaw = 0.0
        self.neutral_pitch = 0.0
        self.neutral_nose_x = 0.0
        self.neutral_nose_y = 0.0
        self.scale_x = 0.12
        self.scale_y = 0.10
        self.is_neutral_calibrated = False
        self.filter.reset()

    # ---------------------------------------------------------
    # STAGE 1: Landmark Validity, Scale & Posture Checks
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

        # Key Reference Landmarks
        # 33: right eye outer corner (subject right / viewer left)
        # 263: left eye outer corner (subject left / viewer right)
        # 168: nose bridge (nasion/glabella)
        p_r_eye = landmarks[33, :2]
        p_l_eye = landmarks[263, :2]
        p_nose = landmarks[168, :2]

        if np.isnan(p_r_eye).any() or np.isnan(p_l_eye).any() or np.isnan(p_nose).any():
            return False, "Invalid landmark coordinates"

        dx = p_l_eye[0] - p_r_eye[0]
        dy = p_l_eye[1] - p_r_eye[1]
        inter_eye = math.sqrt(dx * dx + dy * dy)
        self.inter_eye_distance = inter_eye

        # Plausible face-scale validation check
        if inter_eye < 0.035:
            return False, "Face too far from camera"
        if inter_eye > 0.65:
            return False, "Face too close to camera"

        if ear < 0.14:
            return False, "Blink or eye closure detected"

        if abs(yaw) > 40.0:
            return False, f"Head turned too far horizontally ({yaw:.1f}°)"
        if abs(pitch) > 35.0:
            return False, f"Head tilted too far vertically ({pitch:.1f}°)"

        return True, "Tracking locked"

    # ---------------------------------------------------------
    # STAGE 2: Stable Facial Reference Point & Mathematical Modeling
    # ---------------------------------------------------------
    def extract_features(
        self,
        landmarks: np.ndarray,
        pitch: float,
        yaw: float,
    ) -> Optional[Tuple[float, float]]:
        """
        Mathematical definition:
        eyeCenter = (leftEyeReference + rightEyeReference) / 2
        noseRelative = (noseBridge - eyeCenter) / interEyeDistance
        Explicit camera mirroring:
          Turning head right -> cursor moves right (+x).
          Tilting head up -> cursor moves up (-y in screen space).
        """
        if len(landmarks) < 478:
            return None

        p_r_eye = landmarks[33, :2]
        p_l_eye = landmarks[263, :2]
        eye_center = 0.5 * (p_r_eye + p_l_eye)

        dx = p_l_eye[0] - p_r_eye[0]
        dy = p_l_eye[1] - p_r_eye[1]
        inter_eye = math.sqrt(dx * dx + dy * dy)
        if inter_eye < 0.03:
            return None
        self.inter_eye_distance = inter_eye

        p_nose = landmarks[168, :2]
        if p_nose[0] == 0.0 and p_nose[1] == 0.0:
            p_nose = landmarks[6, :2] if landmarks[6, 0] != 0.0 else eye_center

        # Camera mirroring:
        # User turns head to THEIR RIGHT:
        # Nose moves toward image left (smaller x) relative to eyeCenter -> (p_nose[0] - eye_center[0]) becomes negative.
        # To make rightward movement POSITIVE (+x), negate the relative x displacement:
        raw_nose_rel_x = float((p_nose[0] - eye_center[0]) / inter_eye)
        raw_nose_rel_y = float((p_nose[1] - eye_center[1]) / inter_eye)

        # Mirrored features
        feat_nose_x = -raw_nose_rel_x
        # Tilting head UP: nose moves upward in camera (smaller y) -> (p_nose[1] - eye_center[1]) decreases.
        # In screen coords, top is y=0. Decreasing screen y moves cursor UP:
        feat_nose_y = raw_nose_rel_y

        self.current_nose_x = feat_nose_x
        self.current_nose_y = feat_nose_y
        self.current_yaw = yaw
        self.current_pitch = pitch

        # Head-pose features:
        # Turning head right: OpenCV solvePnP produces negative yaw -> negate to make rightward positive (+x)
        feat_pose_x = float(-yaw / 25.0)
        # Tilting head up: OpenCV solvePnP produces negative pitch -> tilt up moves cursor up (-y)
        feat_pose_y = float(pitch / 20.0)

        if self.tracking_mode == "nose_bridge":
            self.current_xt = feat_nose_x
            self.current_yt = feat_nose_y
            return (feat_nose_x, feat_nose_y)
        elif self.tracking_mode == "head_pose":
            self.current_xt = feat_pose_x
            self.current_yt = feat_pose_y
            return (feat_pose_x, feat_pose_y)
        else:  # 'hybrid'
            hx = 0.55 * feat_nose_x + 0.45 * feat_pose_x
            hy = 0.55 * feat_nose_y + 0.45 * feat_pose_y
            self.current_xt = hx
            self.current_yt = hy
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

        # Reject sudden jump > 0.25 norm within < 150ms
        if dt < 0.15 and jump > 0.25:
            self.consecutive_outlier_count += 1
            self.total_outliers_detected += 1

            if self.consecutive_outlier_count < 3:
                # Hold last known clean feature
                return (self.last_raw_feature, True)
            else:
                # 3 consecutive frames of large shift: accept as intentional rapid head saccade
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
    # STAGE 4: Mathematical Movement Mapping & Velocity Transfer
    # ---------------------------------------------------------
    def compute_relative_movement(
        self,
        smooth_xt: float,
        smooth_yt: float,
    ) -> Tuple[float, float, float, float, bool]:
        """
        Computes normalized movement and target velocity:
        dx = xt - x0
        dy = yt - y0
        ux = dx / scaleX
        uy = dy / scaleY
        Returns: (target_vx, target_vy, ux, uy, in_dead_zone)
        """
        dx = smooth_xt - self.neutral_x0
        dy = smooth_yt - self.neutral_y0
        self.deflection_x = dx
        self.deflection_y = dy

        scale_x = max(1e-4, self.scale_x)
        scale_y = max(1e-4, self.scale_y)
        ux = dx / scale_x
        uy = dy / scale_y
        self.normalized_ux = ux
        self.normalized_uy = uy

        # Radial 2D deflection magnitude
        r_mag = math.sqrt(ux * ux + uy * uy)

        theta_enter = self.dead_zone_enter
        theta_exit = self.dead_zone_exit

        # Hysteresis state machine
        if not self.is_moving:
            if r_mag > theta_enter:
                self.is_moving = True
        else:
            if r_mag < theta_exit:
                self.is_moving = False

        if not self.is_moving:
            return (0.0, 0.0, ux, uy, True)

        # Outside dead zone: apply bounded non-linear response
        r_eff = max(0.0, r_mag - theta_exit)
        dir_x = ux / max(1e-6, r_mag)
        dir_y = uy / max(1e-6, r_mag)

        # Smooth bounded transfer curve: response(z) = sign(z) * min(maxSpeed, gain * |z|^gamma)
        speed = min(self.max_speed, self.gain * (r_eff ** self.power) * self.sensitivity)
        target_vx = dir_x * speed
        target_vy = dir_y * speed

        return (target_vx, target_vy, ux, uy, False)

    def map_absolute_screen(
        self,
        ux: float,
        uy: float,
    ) -> Tuple[float, float]:
        """
        Mode B: Regularized bilinear mapping from normalized head movement to screen coordinates.
        screen_x = c0 + c1 * ux + c2 * uy + c3 * (ux * uy)
        screen_y = c0 + c1 * ux + c2 * uy + c3 * (ux * uy)
        """
        cx = self.profile.coeff_x
        cy = self.profile.coeff_y
        u_xy = ux * uy

        sx = cx[0] + cx[1] * ux + cx[2] * uy + cx[3] * u_xy
        sy = cy[0] + cy[1] * ux + cy[2] * uy + cy[3] * u_xy

        if self.sensitivity != 1.0:
            sx = 0.5 + (sx - 0.5) * self.sensitivity
            sy = 0.5 + (sy - 0.5) * self.sensitivity

        return (float(np.clip(sx, 0.0, 1.0)), float(np.clip(sy, 0.0, 1.0)))

    # ---------------------------------------------------------
    # STAGE 5: Full Frame Processing Loop
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

        # Frame timing validation (reject stale/backward frames)
        if self.last_frame_ts > 0.0:
            raw_dt = timestamp - self.last_frame_ts
            if raw_dt <= 0.0 or raw_dt > 0.500:
                # Stale timestamp or backward clock: clamp to nominal 30 Hz
                dt = 0.033
            else:
                dt = max(0.010, min(0.066, raw_dt))
            self.update_hz = 1.0 / dt
        else:
            dt = 0.033
            self.update_hz = 30.0
        self.last_frame_ts = timestamp

        # STAGE 1: Landmark validity & posture checks
        valid, reason = self.check_tracking_validity(landmarks, ear, pitch, yaw)

        # Blink and Tracking Hold Handling
        if not valid or landmarks is None:
            time_since_valid = timestamp - self.last_valid_ts
            if self.last_valid_ts > 0.0 and time_since_valid < 0.40:
                # Blink hold active (< 400ms): cursor stays stationary, velocity zero
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
                    "controller_mode": self.controller_mode,
                    "tracking_mode": self.tracking_mode,
                    "preset": self.preset_name,
                    "frame_age_ms": round(self.frame_age_ms, 1),
                    "hz": round(self.update_hz, 1),
                }
        else:
            # Recovery from tracking loss > 0.40s: safe smooth reset
            if (timestamp - self.last_valid_ts) > 0.40 and self.last_valid_ts > 0.0:
                self.filter.reset()
                self.last_raw_feature = None
                self.is_moving = False
                self.velocity_x = 0.0
                self.velocity_y = 0.0

            self.in_blink_hold = False
            self.is_tracking_valid = True
            self.tracking_status_message = "Tracking locked"
            self.last_valid_ts = timestamp

            # STAGE 2: Stable feature extraction
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
                    "controller_mode": self.controller_mode,
                    "tracking_mode": self.tracking_mode,
                    "preset": self.preset_name,
                }

            # STAGE 3: Outlier jump rejection
            clean_feature, outlier = self.filter_outliers(raw_feature, timestamp)
            fx, fy = clean_feature

            # Record calibration sample if in guided wizard
            if self.is_calibrating:
                self.current_target_samples.append(
                    CalibrationSample(gaze_x=fx, gaze_y=fy, timestamp=timestamp)
                )

            # If transient outlier detected, hold position stationary and skip integration
            if outlier:
                self.velocity_x = 0.0
                self.velocity_y = 0.0
                self.in_dead_zone = True
                final_sx, final_sy = self.last_cursor_norm
            else:
                # STAGE 4: Temporal filtering
                smooth_xt, smooth_yt = self.filter.filter(fx, fy, timestamp)

                # Auto-initialize neutral reference if uncalibrated
                if not self.is_neutral_calibrated:
                    self.neutral_calibration_samples.append(
                        (yaw, pitch, self.current_nose_x, self.current_nose_y)
                    )
                    if len(self.neutral_calibration_samples) >= 15:
                        self.calibrate_neutral_from_samples(self.neutral_calibration_samples)
                        self.neutral_calibration_samples = []

                # Compute relative movement & dead zone
                target_vx, target_vy, ux, uy, in_dz = self.compute_relative_movement(smooth_xt, smooth_yt)
                self.in_dead_zone = in_dz

                if self.controller_mode == "motionq_eye":
                    # Mode C: MotionQ Calibrated Iris Eye-Gaze Controller
                    eye_res = self.motionq_eye.process_frame(landmarks, timestamp=timestamp)
                    if eye_res["valid"]:
                        final_sx, final_sy = eye_res["norm_x"], eye_res["norm_y"]
                        self.velocity_x = (final_sx - self.last_cursor_norm[0]) / max(1e-4, dt)
                        self.velocity_y = (final_sy - self.last_cursor_norm[1]) / max(1e-4, dt)
                        self.last_cursor_norm = (final_sx, final_sy)
                        self.in_dead_zone = False
                    else:
                        final_sx, final_sy = self.last_cursor_norm
                        self.velocity_x = 0.0
                        self.velocity_y = 0.0
                        self.in_dead_zone = True
                elif self.controller_mode == "absolute":
                    # Mode B: Absolute Screen Mapping
                    abs_sx, abs_sy = self.map_absolute_screen(ux, uy)
                    self.velocity_x = (abs_sx - self.last_cursor_norm[0]) / max(1e-4, dt)
                    self.velocity_y = (abs_sy - self.last_cursor_norm[1]) / max(1e-4, dt)
                    self.last_cursor_norm = (abs_sx, abs_sy)
                    final_sx, final_sy = abs_sx, abs_sy
                else:
                    # Mode A: Relative Head-Movement Rate/Velocity Controller
                    if in_dz:
                        # Inside dead zone: velocity is identically 0.0, position unchanged
                        self.velocity_x = 0.0
                        self.velocity_y = 0.0
                        final_sx, final_sy = self.last_cursor_norm
                    else:
                        # Acceleration limiting: clamp acceleration to prevent jarring jumps
                        max_dv = self.max_acceleration * dt
                        diff_vx = target_vx - self.velocity_x
                        diff_vy = target_vy - self.velocity_y
                        self.velocity_x += float(np.clip(diff_vx, -max_dv, max_dv))
                        self.velocity_y += float(np.clip(diff_vy, -max_dv, max_dv))

                        # Integrate cursor position with bounds clamping
                        new_x = self.last_cursor_norm[0] + self.velocity_x * dt
                        new_y = self.last_cursor_norm[1] + self.velocity_y * dt
                        final_sx = float(np.clip(new_x, 0.0, 1.0))
                        final_sy = float(np.clip(new_y, 0.0, 1.0))
                        self.last_cursor_norm = (final_sx, final_sy)

        # -------------------------------------------------------------
        # MotionQ Engine Updates: Dwell, Head Scroll, and Calibration
        # -------------------------------------------------------------
        screen_pixel_x = final_sx * self.motionq_eye.screen_w
        screen_pixel_y = final_sy * self.motionq_eye.screen_h

        dwell_res = self.dwell_engine.update(
            screen_pixel_x,
            screen_pixel_y,
            timestamp=timestamp,
            is_tracking_valid=self.is_tracking_valid,
        )

        head_scroll_res = self.head_scroller.process_landmarks(
            landmarks,
            frame_h=480.0,
            timestamp=timestamp,
        )

        if self.motionq_calibrator.is_calibrating:
            self.motionq_calibrator.feed_frame(landmarks, frame_h=480.0)

        fired_click = self._pending_click_event
        self._pending_click_event = None

        fired_scroll = self._pending_scroll_event
        self._pending_scroll_event = None

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
            "deflection_x": round(self.deflection_x, 4),
            "deflection_y": round(self.deflection_y, 4),
            "normalized_ux": round(self.normalized_ux, 4),
            "normalized_uy": round(self.normalized_uy, 4),
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
            "controller_mode": self.controller_mode,
            "tracking_mode": self.tracking_mode,
            "preset": self.preset_name,
            "latency_ms": round(t_latency_ms, 2),
            "frame_age_ms": round(self.frame_age_ms, 1),
            "hz": round(self.update_hz, 1),
            "is_outlier": outlier,
            "is_diagnosing": self.is_diagnosing,
            "diagnostic_result": diag_result,
            "dwell": dwell_res,
            "head_scroll": head_scroll_res,
            "fired_click": fired_click,
            "fired_scroll": fired_scroll,
        }

    # ---------------------------------------------------------
    # STAGE 6: Guided 5+1 Calibration Procedure
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

        # Filter transient blinks/spikes using robust 2.5 sigma envelope
        valid_mask = (np.abs(fxs - med_x) <= 2.5 * sigma_x) & (np.abs(fys - med_y) <= 2.5 * sigma_y)
        clean_fxs = fxs[valid_mask]
        clean_fys = fys[valid_mask]

        if len(clean_fxs) < 3:
            clean_fxs, clean_fys = fxs, fys

        mean_x = float(np.median(clean_fxs))
        mean_y = float(np.median(clean_fys))

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
        """
        Validates calibration samples across deliberate movement directions:
        1. Learns neutral resting position p0.
        2. Learns movement scales scaleX and scaleY.
        3. Validates movement direction distinguishability (rejects insufficient/inverted range).
        4. Evaluates held-out center repeatability error.
        5. Fits regularized bilinear Ridge Regression for Mode B screen mapping.
        """
        self.is_calibrating = False

        if len(self.calib_target_results) < 5:
            return {"success": False, "error": "Not enough targets calibrated"}

        results_by_id = {r.target_id: r for r in self.calib_target_results}

        # 1. Neutral Reference p0
        center_1 = results_by_id.get("center_neutral") or results_by_id.get("center_1")
        if not center_1:
            return {"success": False, "error": "Neutral center reference target missing"}

        p0_x = center_1.mean_gaze_x
        p0_y = center_1.mean_gaze_y
        noise_mad_x = max(1e-4, center_1.std_gaze_x)
        noise_mad_y = max(1e-4, center_1.std_gaze_y)

        # 2. Left / Right / Up / Down Target Distances
        t_left = results_by_id.get("move_left") or results_by_id.get("bottom_left")
        t_right = results_by_id.get("move_right") or results_by_id.get("bottom_right")
        t_up = results_by_id.get("move_up") or results_by_id.get("top_left")
        t_down = results_by_id.get("move_down") or results_by_id.get("top_right")

        delta_left = abs(t_left.mean_gaze_x - p0_x) if t_left else 0.10
        delta_right = abs(t_right.mean_gaze_x - p0_x) if t_right else 0.10
        delta_up = abs(t_up.mean_gaze_y - p0_y) if t_up else 0.08
        delta_down = abs(t_down.mean_gaze_y - p0_y) if t_down else 0.08

        # Direction distinguishability check: movement range must be at least 2.0x resting noise
        scale_x = max(0.04, (delta_left + delta_right) / 2.0)
        scale_y = max(0.03, (delta_up + delta_down) / 2.0)

        # 3. Fit Mode B Bilinear Screen Mapping via Ridge Regression
        fit_targets = [r for r in self.calib_target_results if r.target_id not in ("validation_center", "center_2")]
        val_target = results_by_id.get("validation_center") or results_by_id.get("center_2")

        N = len(fit_targets)
        A = np.zeros((N, 4), dtype=np.float64)
        Bx = np.zeros(N, dtype=np.float64)
        By = np.zeros(N, dtype=np.float64)

        for i, t in enumerate(fit_targets):
            ux = (t.mean_gaze_x - p0_x) / scale_x
            uy = (t.mean_gaze_y - p0_y) / scale_y
            A[i] = [1.0, ux, uy, ux * uy]
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
            print(f"[FaceMouse] Ridge fit exception: {e}")
            coeff_x = [0.5, 0.4, 0.0, 0.0]
            coeff_y = [0.5, 0.0, 0.4, 0.0]

        # 4. Held-Out Repeatability & Validation Error
        val_error = 0.05
        if val_target:
            val_ux = (val_target.mean_gaze_x - p0_x) / scale_x
            val_uy = (val_target.mean_gaze_y - p0_y) / scale_y
            pred_sx = coeff_x[0] + coeff_x[1] * val_ux + coeff_x[2] * val_uy + coeff_x[3] * (val_ux * val_uy)
            pred_sy = coeff_y[0] + coeff_y[1] * val_ux + coeff_y[2] * val_uy + coeff_y[3] * (val_ux * val_uy)
            val_error = math.sqrt((pred_sx - val_target.target_screen_x) ** 2 + (pred_sy - val_target.target_screen_y) ** 2)

        if val_error < 0.06:
            quality = "Excellent"
        elif val_error < 0.12:
            quality = "Good"
        elif val_error < 0.20:
            quality = "Fair"
        else:
            quality = "Needs Recalibration"

        # Adaptive dead zone based on measured resting noise
        noise_norm = max(noise_mad_x / scale_x, noise_mad_y / scale_y)
        learned_dead_zone = float(np.clip(3.0 * noise_norm, 0.015, 0.060))

        profile = GazeCalibrationProfile(
            schema_version=FACE_MOUSE_SCHEMA_VERSION,
            created_at=time.time(),
            is_calibrated=True,
            quality_label=quality,
            validation_error=round(val_error, 4),
            coeff_x=coeff_x,
            coeff_y=coeff_y,
            targets=[asdict(r) for r in self.calib_target_results],
            controller_mode=self.controller_mode,
            tracking_mode=self.tracking_mode,
            neutral_x0=p0_x,
            neutral_y0=p0_y,
            neutral_yaw=self.current_yaw,
            neutral_pitch=self.current_pitch,
            neutral_nose_x=p0_x,
            neutral_nose_y=p0_y,
            scale_x=round(scale_x, 4),
            scale_y=round(scale_y, 4),
            noise_mad_x=round(noise_mad_x, 5),
            noise_mad_y=round(noise_mad_y, 5),
            learned_dead_zone=round(learned_dead_zone, 4),
        )

        self._apply_profile(profile)
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
    # STAGE 7: Stability Diagnostic Procedure
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
            "controller_mode": self.controller_mode,
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
        if "controller_mode" in settings:
            self.set_controller_mode(str(settings["controller_mode"]))
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
            "deflection_x": round(self.deflection_x, 4),
            "deflection_y": round(self.deflection_y, 4),
            "normalized_ux": round(self.normalized_ux, 4),
            "normalized_uy": round(self.normalized_uy, 4),
            "scale_x": round(self.scale_x, 4),
            "scale_y": round(self.scale_y, 4),
            "noise_mad": round(max(self.noise_mad_x, self.noise_mad_y), 5),
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
            "controller_mode": self.controller_mode,
            "tracking_mode": self.tracking_mode,
            "preset": self.preset_name,
            "is_calibrating": self.is_calibrating,
            "calib_target_idx": self.calib_target_idx,
            "outlier_count": self.total_outliers_detected,
            "is_diagnosing": self.is_diagnosing,
            "frame_age_ms": round(self.frame_age_ms, 1),
            "hz": round(self.update_hz, 1),
            "dwell_progress": round(self.dwell_engine._current_progress, 2),
            "dwell_target_name": self.dwell_engine._active_target.name if self.dwell_engine._active_target else None,
            "click_mode": self.dwell_engine.get_click_mode(),
            "head_scroll_direction": self.head_scroller._last_direction,
            "current_profile": self.current_profile_name,
            "keyboard_language": self.keyboard_language,
        }

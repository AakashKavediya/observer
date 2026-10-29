"""
observer_engine.config
Defines all behavioral thresholds, smoothing factors, and window durations.
Every parameter includes detailed commentary on the neurodivergent rationale.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class CameraConfig:
    # Target frame rate for feature extraction. 15 FPS is optimal: provides
    # sub-70ms temporal resolution for blink detection while keeping CPU < 10%.
    target_fps: float = 15.0

    # Frame capture resolution downscaled to 640x480.
    # High enough for accurate iris & blendshape extraction, low enough to avoid thermal throttling.
    frame_width: int = 640
    frame_height: int = 480

    # Device index (0 is typically the primary built-in or USB webcam).
    device_index: int = 0


@dataclass(frozen=True)
class QualityGatingConfig:
    # Minimum average pixel luminance (0-255). Below this, frames are marked invalid.
    # Prevents false positive tension estimations caused by camera noise in darkness.
    min_mean_brightness: float = 38.0

    # Maximum head orientation angles in degrees before gating frame as invalid.
    # If the user is looking away at a second monitor (> 40 deg yaw) or resting their
    # head on a desk, landmark projection errors spike. We suppress classification.
    max_pitch_deg: float = 35.0
    max_yaw_deg: float = 40.0
    max_roll_deg: float = 35.0


@dataclass(frozen=True)
class BlinkConfig:
    # Eye Aspect Ratio (EAR) nominal baseline threshold.
    # Dynamic threshold adapts relative to the user's calibrated open-eye baseline.
    ear_baseline_default: float = 0.28
    ear_closed_ratio: float = 0.70  # < 70% of open EAR indicates eye closure

    # Minimum and maximum duration of a valid physiological blink in seconds.
    # Blinks shorter than 50ms are video flicker noise; closures > 500ms are microsleeps or resting eyes.
    min_blink_duration_s: float = 0.05
    max_blink_duration_s: float = 0.45

    # Window durations (in seconds) for computing rolling blink rate.
    # Neurodivergent hyperfocus and task paralysis frequently depress blink rate below 4/min.
    rate_windows_s: tuple = (30, 60, 180)


@dataclass(frozen=True)
class GazeConfig:
    # I-DT (Identification by Dispersion-Threshold) dispersion sliding windows in seconds.
    # 4s captures momentary fixation; 30s captures persistent stare; 120s captures prolonged freeze.
    dispersion_windows_s: tuple = (4.0, 30.0, 120.0)

    # Threshold for normalized gaze dispersion indicating a frozen stare.
    # If dispersion over 30s is below 0.12, the gaze has remained locked on a tiny screen region.
    fixation_dispersion_threshold: float = 0.12


@dataclass(frozen=True)
class TensionConfig:
    # Blendshape weights combining into a single normalized tension index (0.0 to 1.0).
    # Neurodivergent individuals under task paralysis often exhibit brow furrowing (concentration/freeze),
    # jaw clenching (isometric tension), and lip pressing without realizing it.
    weight_brow_down: float = 0.35
    weight_mouth_press: float = 0.25
    weight_jaw_clench: float = 0.25
    weight_squint: float = 0.15


@dataclass(frozen=True)
class StateEngineConfig:
    # Weights for the frozen evidence formula:
    # frozen_score = 0.30*fixation + 0.25*idle + 0.25*tension + 0.10*blink_anomaly + 0.10*stillness
    weight_fixation: float = 0.30
    weight_idle: float = 0.25
    weight_tension: float = 0.25
    weight_blink_anomaly: float = 0.10
    weight_stillness: float = 0.10

    # Weights for the spinning evidence formula (agitation / rapid task switching):
    # spinning_score = 0.40*switching + 0.30*tension + 0.30*(1 - productive_input)
    weight_switching: float = 0.40
    weight_spinning_tension: float = 0.30
    weight_spinning_unproductive: float = 0.30

    # Hysteresis thresholds to prevent state flickering:
    # Enter paralysis state only if evidence exceeds 0.65.
    # Stay in paralysis state until evidence drops below 0.45.
    enter_threshold: float = 0.65
    exit_threshold: float = 0.45

    # Minimum dwell time in seconds required before confirming task paralysis.
    # Neurodivergent users often pause for 30-60s to think; 90s guarantees sustained freeze
    # before offering support, prioritizing false negatives over annoying interruptions.
    min_dwell_seconds: float = 90.0

    # Exponential Moving Average (EMA) alpha factor (~0.15 for smooth transitions).
    ema_alpha: float = 0.15


@dataclass
class EngineConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    quality: QualityGatingConfig = field(default_factory=QualityGatingConfig)
    blink: BlinkConfig = field(default_factory=BlinkConfig)
    gaze: GazeConfig = field(default_factory=GazeConfig)
    tension: TensionConfig = field(default_factory=TensionConfig)
    state: StateEngineConfig = field(default_factory=StateEngineConfig)


CONFIG = EngineConfig()

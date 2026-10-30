"""
observer_engine.health_tech.schema
Versioned observation data contract, explicit validity states, signal quality metadata,
check-ins, and conservative event records for the Observer Behavioral Observation Platform.

Health-Tech Governance:
Observer is a privacy-first behavioral observation and self-monitoring platform.
It is NOT a diagnostic medical device and does NOT diagnose medical or psychiatric conditions.
Raw video, raw audio, keystrokes, screenshots, and window titles are NEVER stored.
"""

from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Union
import uuid
import time
from datetime import datetime, timezone

SCHEMA_VERSION = "2.0.0"
ALGORITHM_VERSION = "2.0.0"


class ValidityStatus(str, Enum):
    VALID = "valid"
    LOW_QUALITY = "low_quality"
    UNAVAILABLE = "unavailable"
    TRACKING_LOST = "tracking_lost"
    NOT_CALIBRATED = "not_calibrated"
    INSUFFICIENT_SAMPLES = "insufficient_samples"


class Provenance(str, Enum):
    DIRECTLY_MEASURED = "directly_measured"
    DERIVED = "derived"
    INFERRED = "inferred"
    SELF_REPORTED = "self_reported"


@dataclass
class SignalQualityMeta:
    usable_ratio: float = 1.0           # Fraction of valid frames in window [0.0, 1.0]
    mean_brightness: float = 128.0      # Frame brightness [0, 255]
    blur_score: float = 250.0           # Laplacian variance (higher = sharper)
    landmark_stability_mad: float = 0.002 # Median absolute deviation of landmarks
    extreme_angle: bool = False
    face_scale_ratio: float = 0.25      # Inter-ocular distance relative to frame width
    occlusion_detected: bool = False
    fps: float = 30.0
    missing_data_intervals: List[Dict[str, float]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BaselineReference:
    baseline_median: float
    baseline_mad: float
    deviation_score: float              # Robust z-score: (value - median) / (1.4826 * MAD)
    deviation_percent: float            # Percentage change from median
    sample_count: int
    baseline_version: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ObservationRecord:
    observation_id: str                 # Unique UUID
    session_id: str                     # Associated session UUID
    timestamp: float                    # Epoch seconds
    monotonic_time: float               # Monotonic elapsed time
    feature_name: str                   # Canonical feature key
    measured_value: Optional[float]     # None if invalid/missing - NEVER replace with zero
    unit: str                           # e.g., "ratio", "bpm", "degrees", "deg_per_sec", "seconds"
    definition_version: str = SCHEMA_VERSION
    source_stream: str = "webcam_face"  # "webcam_face", "webcam_body", "desktop_input", "user_checkin"
    validity_status: str = ValidityStatus.VALID.value
    missing_data_reason: Optional[str] = None
    signal_quality: Optional[Dict[str, Any]] = None
    baseline_reference: Optional[Dict[str, Any]] = None
    algorithm_version: str = ALGORITHM_VERSION
    provenance: str = Provenance.DIRECTLY_MEASURED.value
    session_context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CheckInRecord:
    checkin_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    energy: Optional[int] = None        # 1 (Exhausted) - 5 (Energized)
    effort: Optional[int] = None        # 1 (Effortless) - 5 (Extreme Effort)
    task_difficulty: Optional[int] = None # 1 (Easy) - 5 (Overwhelming)
    feeling_stuck: Optional[bool] = None # User-reported feeling stuck
    discomfort: Optional[int] = None    # 1 (None) - 5 (Severe)
    stress: Optional[int] = None        # 1 (Calm) - 5 (Very Stressed)
    sleep_quality: Optional[int] = None # 1 (Poor) - 5 (Restful)
    notes: Optional[str] = None         # Short optional text
    task_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["created_at_iso"] = datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat()
        return d


@dataclass
class EventRecord:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    event_type: str = ""                # e.g. "low_head_movement_interval", "elevated_switch_rate"
    start_time: float = 0.0
    end_time: float = 0.0
    duration_seconds: float = 0.0
    supporting_measurements: List[Dict[str, Any]] = field(default_factory=list)
    feature_validity: str = ValidityStatus.VALID.value
    baseline_comparison: str = ""
    rule_version: str = ALGORITHM_VERSION
    explanation: str = ""
    uncertainty: str = "moderate"       # "low", "moderate", "high"
    is_user_reported: bool = False
    created_at_iso: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["created_at_iso"] = self.created_at_iso or datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat()
        return d


@dataclass
class SessionRecord:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_seconds: float = 0.0
    total_frames: int = 0
    valid_frames: int = 0
    coverage_ratio: float = 0.0
    active_streams: List[str] = field(default_factory=list)
    associated_task_id: Optional[str] = None
    associated_task_title: Optional[str] = None
    checkin_count: int = 0
    event_count: int = 0
    status: str = "active"              # "active", "completed", "aborted"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

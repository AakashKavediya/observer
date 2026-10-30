"""
observer_engine.health_tech.baseline
Personal Baseline and Calibration System for Observer Behavioral Platform.

Provides a guided 4-stage personal calibration protocol:
1. Neutral Facial Behavior Capture (relaxed face, closed mouth, resting expression)
2. Eye Behavior & Blink Baseline (natural blinking & gaze)
3. Head-Neutral Calibration (comfortable ergonomic monitor orientation)
4. Natural Behavior Baseline (comfortable ordinary interaction)

Statistical Method:
Uses medians and Median Absolute Deviation (MAD) rather than mean/std, to ensure
robustness against outliers and involuntary twitches.
Health-Tech Governance:
Baselines are strictly individualized references, NEVER clinical norms or universal healthy ranges.
"""

import os
import json
import time
import uuid
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, List
import numpy as np

from observer_engine.health_tech.schema import SCHEMA_VERSION, ALGORITHM_VERSION
from observer_engine.health_tech.feature_extractor import PhysiologicalSnapshot


@dataclass
class RobustMetricBaseline:
    median: float
    mad: float                          # Median Absolute Deviation
    p25: float                          # 25th percentile
    p75: float                          # 75th percentile
    min_val: float
    max_val: float
    sample_count: int

    def compute_deviation_z(self, value: float) -> float:
        """Computes robust z-score: (value - median) / (1.4826 * MAD)."""
        scale = max(1e-4, 1.4826 * self.mad)
        return float((value - self.median) / scale)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PersonalBaselineProfile:
    profile_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    version: str = SCHEMA_VERSION
    algorithm_version: str = ALGORITHM_VERSION
    usable_duration_seconds: float = 0.0
    valid_sample_count: int = 0
    camera_resolution: str = "640x480"
    is_calibrated: bool = False

    # Robust feature baselines
    ear_baseline: Optional[Dict[str, Any]] = None
    blink_rate_baseline: Optional[Dict[str, Any]] = None
    mouth_width_baseline: Optional[Dict[str, Any]] = None
    brow_elevation_baseline: Optional[Dict[str, Any]] = None
    head_pitch_neutral: float = 0.0
    head_yaw_neutral: float = 0.0
    head_roll_neutral: float = 0.0
    head_angular_velocity_baseline: Optional[Dict[str, Any]] = None
    gaze_dispersion_baseline: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BaselineCalibrationManager:
    def __init__(self, storage_dir: Optional[str] = None):
        home = os.path.expanduser("~")
        self.storage_dir = storage_dir or os.path.join(home, ".observer", "baselines")
        os.makedirs(self.storage_dir, exist_ok=True)
        self.file_path = os.path.join(self.storage_dir, "personal_baseline.json")

        self.current_profile: PersonalBaselineProfile = self.load()

        # Calibration accumulator buffers
        self._calibrating: bool = False
        self._calib_stage: str = "idle" # "neutral_face", "eye_blink", "head_neutral", "natural_behavior"
        self._calib_snapshots: List[PhysiologicalSnapshot] = []

    def load(self) -> PersonalBaselineProfile:
        """Loads personal baseline or returns uncalibrated default."""
        if os.path.isfile(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return PersonalBaselineProfile(**data)
            except Exception as e:
                print(f"[BaselineManager] Error loading baseline: {e}. Reverting to default.")
        return PersonalBaselineProfile(is_calibrated=False)

    def save(self) -> bool:
        """Atomically saves the current baseline profile."""
        tmp = f"{self.file_path}.tmp.{uuid.uuid4().hex[:6]}"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.current_profile.to_dict(), f, indent=2)
            os.replace(tmp, self.file_path)
            return True
        except Exception as e:
            print(f"[BaselineManager] Save error: {e}")
            if os.path.isfile(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            return False

    def reset_baseline(self) -> None:
        """Resets to an uncalibrated blank slate and deletes persisted file."""
        self.current_profile = PersonalBaselineProfile(is_calibrated=False)
        if os.path.isfile(self.file_path):
            try:
                os.remove(self.file_path)
            except OSError:
                pass

    def start_calibration(self, stage: str = "neutral_face") -> None:
        """Begins accumulating valid samples for a baseline stage."""
        self._calibrating = True
        self._calib_stage = stage
        self._calib_snapshots.clear()

    def add_calibration_sample(self, snapshot: PhysiologicalSnapshot) -> None:
        """Adds a valid snapshot to the calibration buffer."""
        if self._calibrating and snapshot.valid:
            self._calib_snapshots.append(snapshot)

    def finish_calibration(self) -> PersonalBaselineProfile:
        """Calculates robust medians and MAD across collected samples and saves profile."""
        self._calibrating = False
        valid = [s for s in self._calib_snapshots if s.valid]
        if len(valid) < 30: # Need at least ~2-3 seconds of valid frames
            return self.current_profile

        def compute_robust(values: List[float]) -> Optional[Dict[str, Any]]:
            arr = np.array([v for v in values if v is not None and not np.isnan(v)])
            if len(arr) < 10:
                return None
            med = float(np.median(arr))
            mad = float(np.median(np.abs(arr - med)))
            return RobustMetricBaseline(
                median=round(med, 4),
                mad=round(max(1e-4, mad), 4),
                p25=round(float(np.percentile(arr, 25)), 4),
                p75=round(float(np.percentile(arr, 75)), 4),
                min_val=round(float(np.min(arr)), 4),
                max_val=round(float(np.max(arr)), 4),
                sample_count=len(arr),
            ).to_dict()

        # Compute metrics
        ear_stats = compute_robust([s.ear_avg for s in valid if s.ear_avg is not None])
        mouth_stats = compute_robust([s.mouth_width_ratio for s in valid if s.mouth_width_ratio is not None])
        brow_stats = compute_robust([s.brow_elevation_left for s in valid if s.brow_elevation_left is not None])
        vel_stats = compute_robust([s.angular_velocity for s in valid if s.angular_velocity is not None])
        disp_stats = compute_robust([s.gaze_dispersion_30s for s in valid if s.gaze_dispersion_30s is not None])

        pitches = [s.pitch for s in valid if s.pitch is not None]
        yaws = [s.yaw for s in valid if s.yaw is not None]
        rolls = [s.roll for s in valid if s.roll is not None]

        neutral_p = float(np.median(pitches)) if pitches else 0.0
        neutral_y = float(np.median(yaws)) if yaws else 0.0
        neutral_r = float(np.median(rolls)) if rolls else 0.0

        dur = valid[-1].timestamp - valid[0].timestamp

        self.current_profile = PersonalBaselineProfile(
            profile_id=str(uuid.uuid4()),
            created_at=time.time(),
            updated_at=time.time(),
            usable_duration_seconds=round(dur, 1),
            valid_sample_count=len(valid),
            is_calibrated=True,
            ear_baseline=ear_stats,
            mouth_width_baseline=mouth_stats,
            brow_elevation_baseline=brow_stats,
            head_pitch_neutral=round(neutral_p, 1),
            head_yaw_neutral=round(neutral_y, 1),
            head_roll_neutral=round(neutral_r, 1),
            head_angular_velocity_baseline=vel_stats,
            gaze_dispersion_baseline=disp_stats,
        )
        self.save()
        self._calib_snapshots.clear()
        return self.current_profile

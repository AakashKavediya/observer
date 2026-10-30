"""
observer_engine.health_tech.signal_quality
Signal Quality Assessment Service for Observer Behavioral Platform.

Provides multi-dimensional signal validation before any higher-level behavioral
interpretation. Assesses face presence, landmark confidence, camera frame rate,
lighting changes, motion blur, face distance, extreme angles, and missing-data intervals.
"""

import time
import math
from collections import deque
from typing import Optional, List, Dict, Any, Tuple
import numpy as np
import cv2

from observer_engine.health_tech.schema import SignalQualityMeta, ValidityStatus


class SignalQualityEvaluator:
    def __init__(
        self,
        min_brightness: float = 35.0,
        max_brightness: float = 245.0,
        min_blur_score: float = 40.0,
        min_iod_ratio: float = 0.07,   # Inter-ocular distance relative to frame width
        max_iod_ratio: float = 0.60,
        max_pitch_deg: float = 35.0,
        max_yaw_deg: float = 35.0,
        max_roll_deg: float = 30.0,
        window_seconds: float = 5.0,
    ):
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.min_blur_score = min_blur_score
        self.min_iod_ratio = min_iod_ratio
        self.max_iod_ratio = max_iod_ratio
        self.max_pitch_deg = max_pitch_deg
        self.max_yaw_deg = max_yaw_deg
        self.max_roll_deg = max_roll_deg
        self.window_seconds = window_seconds

        # Frame history buffer
        self._history: deque = deque(maxlen=300)
        
        # Missing data interval tracking
        self._dropout_start: Optional[float] = None
        self._missing_intervals: deque = deque(maxlen=20)
        
        # Landmark stability tracker (last 5 frames)
        self._recent_nose_pts: deque = deque(maxlen=5)

    def evaluate_frame(
        self,
        frame_bgr: Optional[np.ndarray],
        landmarks: Optional[np.ndarray],
        pitch: float,
        yaw: float,
        roll: float,
        timestamp: float,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluates immediate frame signal quality.
        Returns:
            (is_valid, quality_reason, frame_metrics_dict)
        """
        metrics: Dict[str, Any] = {
            "timestamp": timestamp,
            "face_detected": False,
            "brightness": 128.0,
            "blur_score": 150.0,
            "iod_ratio": 0.20,
            "extreme_angle": False,
            "valid": False,
            "reason": "",
        }

        # 1. Face Presence Check
        if landmarks is None or len(landmarks) < 468:
            metrics["reason"] = "face_lost"
            if self._dropout_start is None:
                self._dropout_start = timestamp
            self._history.append((timestamp, False, "face_lost", metrics))
            return False, "face_lost", metrics

        metrics["face_detected"] = True

        # Close dropout interval if face re-appeared
        if self._dropout_start is not None:
            dropout_duration = timestamp - self._dropout_start
            if dropout_duration >= 0.5:
                self._missing_intervals.append({
                    "start": self._dropout_start,
                    "end": timestamp,
                    "duration_seconds": round(dropout_duration, 2),
                    "reason": "face_tracking_loss"
                })
            self._dropout_start = None

        # 2. Lighting & Blur Analysis
        if frame_bgr is not None:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            mean_brightness = float(np.mean(gray))
            metrics["brightness"] = mean_brightness
            
            # Laplacian variance for sharpness/motion blur
            blur_val = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            metrics["blur_score"] = blur_val

            if mean_brightness < self.min_brightness:
                metrics["reason"] = "low_light"
                self._history.append((timestamp, False, "low_light", metrics))
                return False, "low_light", metrics

            if mean_brightness > self.max_brightness:
                metrics["reason"] = "overexposed"
                self._history.append((timestamp, False, "overexposed", metrics))
                return False, "overexposed", metrics

            if blur_val < self.min_blur_score:
                metrics["reason"] = "motion_blur"
                self._history.append((timestamp, False, "motion_blur", metrics))
                return False, "motion_blur", metrics

        # 3. Inter-Ocular Distance (Camera Distance / Scale Check)
        # Landmark 33 (L eye outer) and 263 (R eye outer)
        p_l = landmarks[33, :2]
        p_r = landmarks[263, :2]
        iod = float(np.linalg.norm(p_l - p_r))
        metrics["iod_ratio"] = iod

        if iod < self.min_iod_ratio:
            metrics["reason"] = "face_too_far"
            self._history.append((timestamp, False, "face_too_far", metrics))
            return False, "face_too_far", metrics

        if iod > self.max_iod_ratio:
            metrics["reason"] = "face_too_close"
            self._history.append((timestamp, False, "face_too_close", metrics))
            return False, "face_too_close", metrics

        # 4. Extreme Head Angle Check
        if (
            abs(pitch) > self.max_pitch_deg
            or abs(yaw) > self.max_yaw_deg
            or abs(roll) > self.max_roll_deg
        ):
            metrics["extreme_angle"] = True
            metrics["reason"] = "extreme_head_angle"
            self._history.append((timestamp, False, "extreme_head_angle", metrics))
            return False, "extreme_head_angle", metrics

        # 5. Landmark Stability (MAD)
        nose_pt = landmarks[1, :2]
        self._recent_nose_pts.append(nose_pt)
        if len(self._recent_nose_pts) >= 3:
            pts = np.array(self._recent_nose_pts)
            diffs = np.linalg.norm(np.diff(pts, axis=0), axis=1)
            metrics["landmark_jitter_mad"] = float(np.median(diffs))
        else:
            metrics["landmark_jitter_mad"] = 0.001

        metrics["valid"] = True
        metrics["reason"] = "optimal"
        self._history.append((timestamp, True, "optimal", metrics))
        return True, "optimal", metrics

    def get_window_quality(self, now: float) -> SignalQualityMeta:
        """
        Summarizes windowed signal quality over the last window_seconds.
        """
        recent = [item for item in self._history if now - item[0] <= self.window_seconds]
        if not recent:
            return SignalQualityMeta(
                usable_ratio=0.0,
                extreme_angle=False,
                fps=0.0,
                missing_data_intervals=list(self._missing_intervals),
            )

        total_frames = len(recent)
        valid_frames = sum(1 for item in recent if item[1])
        usable_ratio = float(valid_frames / max(1, total_frames))

        dur = max(0.5, recent[-1][0] - recent[0][0])
        fps = float(total_frames / dur)

        # Average brightness and blur from valid entries
        brightness_vals = [item[3].get("brightness", 128.0) for item in recent if "brightness" in item[3]]
        blur_vals = [item[3].get("blur_score", 150.0) for item in recent if "blur_score" in item[3]]
        iod_vals = [item[3].get("iod_ratio", 0.20) for item in recent if "iod_ratio" in item[3]]
        jitter_vals = [item[3].get("landmark_jitter_mad", 0.002) for item in recent if "landmark_jitter_mad" in item[3]]

        mean_brightness = float(np.mean(brightness_vals)) if brightness_vals else 128.0
        blur_score = float(np.mean(blur_vals)) if blur_vals else 150.0
        face_scale = float(np.mean(iod_vals)) if iod_vals else 0.20
        jitter_mad = float(np.median(jitter_vals)) if jitter_vals else 0.002

        has_extreme_angle = any(item[3].get("extreme_angle", False) for item in recent)

        return SignalQualityMeta(
            usable_ratio=round(usable_ratio, 3),
            mean_brightness=round(mean_brightness, 1),
            blur_score=round(blur_score, 1),
            landmark_stability_mad=round(jitter_mad, 4),
            extreme_angle=has_extreme_angle,
            face_scale_ratio=round(face_scale, 3),
            occlusion_detected=False,
            fps=round(fps, 1),
            missing_data_intervals=list(self._missing_intervals),
        )

    def determine_validity_status(self, is_frame_valid: bool, quality_reason: str, usable_ratio: float) -> str:
        """Determines canonical ValidityStatus enum value."""
        if not is_frame_valid:
            if quality_reason == "face_lost":
                return ValidityStatus.TRACKING_LOST.value
            return ValidityStatus.LOW_QUALITY.value
        if usable_ratio < 0.50:
            return ValidityStatus.INSUFFICIENT_SAMPLES.value
        return ValidityStatus.VALID.value

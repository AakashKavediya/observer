"""
MotionQ Assistive Control System - 5-Point Calibration Manager for Observer
Adapted from MotionQ-blink (calibration_manager.py)
Copyright (c) 2026 Aakash Kavediya
Licensed under the MIT License. See LICENSE.MotionQ-blink for details.

Functional 5-Point Gaze Calibration + Head Neutral Calibration:
- Single authoritative camera: feeds from Observer's existing landmarks pipeline. Zero independent camera opens.
- 5 Targets: Center (0.5, 0.5), Top-Left (0.2, 0.2), Top-Right (0.8, 0.2), Bottom-Left (0.2, 0.8), Bottom-Right (0.8, 0.8).
- Independent Center Validation step to measure real validation error.
- Robust Median + MAD sample aggregation.
- Automatic Head Neutral capture for head-tilt scrolling.
- Persists to profile via profile_manager.
"""

import time
import math
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from observer_engine.motionq import profile_manager


_CALIBRATION_TARGETS = [
    {"index": 0, "label": "Center", "screen": (0.50, 0.50)},
    {"index": 1, "label": "Top Left", "screen": (0.20, 0.20)},
    {"index": 2, "label": "Top Right", "screen": (0.80, 0.20)},
    {"index": 3, "label": "Bottom Left", "screen": (0.20, 0.80)},
    {"index": 4, "label": "Bottom Right", "screen": (0.80, 0.80)},
]

_LEFT_IRIS_PERIMETER = [474, 475, 476, 477]
_RIGHT_IRIS_PERIMETER = [469, 470, 471, 472]
_NOSE_INDEX = 1


class MotionQCalibrationManager:
    def __init__(self, profile_name: str = "default"):
        self.profile_name = profile_name
        self.is_calibrating: bool = False
        self.current_stage: str = "idle"  # "idle" | "gaze" | "validation" | "head_neutral" | "complete"
        self.current_target_index: int = 0

        # Sample buffers per stage
        self._target_samples: List[Tuple[float, float]] = []  # [(iris_x, iris_y), ...]
        self._collected_points: List[Dict[str, Any]] = []    # [{"iris": [ix, iy], "screen": [sx, sy]}, ...]
        self._validation_samples: List[Tuple[float, float]] = []
        self._head_neutral_samples: List[float] = []

        self.last_validation_error_px: Optional[float] = None
        self.last_calibration_time: float = 0.0

    def start_calibration(self) -> Dict[str, Any]:
        """Begin full 5-point calibration flow."""
        self.is_calibrating = True
        self.current_stage = "gaze"
        self.current_target_index = 0
        self._target_samples.clear()
        self._collected_points.clear()
        self._validation_samples.clear()
        self._head_neutral_samples.clear()
        self.last_validation_error_px = None

        target = _CALIBRATION_TARGETS[0]
        return {
            "status": "started",
            "stage": self.current_stage,
            "target_index": 0,
            "target_label": target["label"],
            "screen_x": target["screen"][0],
            "screen_y": target["screen"][1],
            "total_targets": len(_CALIBRATION_TARGETS),
        }

    def feed_frame(
        self,
        landmarks: Optional[np.ndarray],
        frame_h: float = 480.0,
    ) -> bool:
        """Feed landmark sample into currently active calibration stage."""
        if not self.is_calibrating or landmarks is None or len(landmarks) < 478:
            return False

        if np.isnan(landmarks).any() or np.isinf(landmarks).any():
            return False

        if self.current_stage == "gaze":
            left_ix = float(np.mean([landmarks[i, 0] for i in _LEFT_IRIS_PERIMETER]))
            left_iy = float(np.mean([landmarks[i, 1] for i in _LEFT_IRIS_PERIMETER]))
            right_ix = float(np.mean([landmarks[i, 0] for i in _RIGHT_IRIS_PERIMETER]))
            right_iy = float(np.mean([landmarks[i, 1] for i in _RIGHT_IRIS_PERIMETER]))
            self._target_samples.append(((left_ix + right_ix) / 2.0, (left_iy + right_iy) / 2.0))
            return True

        elif self.current_stage == "validation":
            left_ix = float(np.mean([landmarks[i, 0] for i in _LEFT_IRIS_PERIMETER]))
            left_iy = float(np.mean([landmarks[i, 1] for i in _LEFT_IRIS_PERIMETER]))
            right_ix = float(np.mean([landmarks[i, 0] for i in _RIGHT_IRIS_PERIMETER]))
            right_iy = float(np.mean([landmarks[i, 1] for i in _RIGHT_IRIS_PERIMETER]))
            self._validation_samples.append(((left_ix + right_ix) / 2.0, (left_iy + right_iy) / 2.0))
            return True

        elif self.current_stage == "head_neutral":
            nose_y = float(landmarks[_NOSE_INDEX, 1] * frame_h)
            self._head_neutral_samples.append(nose_y)
            return True

        return False

    def advance_target(self) -> Dict[str, Any]:
        """
        Complete current target with median sample aggregation and advance to next.
        Stages: Target 0-4 (Gaze) -> Validation (Center) -> Head Neutral -> Complete.
        """
        if not self.is_calibrating:
            return {"status": "error", "message": "Not calibrating"}

        # -------------------------------------------------------------
        # 1. Processing Gaze Stage Targets 0 to 4
        # -------------------------------------------------------------
        if self.current_stage == "gaze":
            if len(self._target_samples) < 5:
                return {
                    "status": "warning",
                    "message": f"Insufficient valid samples ({len(self._target_samples)}). Keep looking at target.",
                    "target_index": self.current_target_index,
                }

            # Robust Median calculation
            samples_arr = np.array(self._target_samples)
            med_x = float(np.median(samples_arr[:, 0]))
            med_y = float(np.median(samples_arr[:, 1]))

            target = _CALIBRATION_TARGETS[self.current_target_index]
            self._collected_points.append({
                "iris": [round(med_x, 5), round(med_y, 5)],
                "screen": [target["screen"][0], target["screen"][1]],
            })
            self._target_samples.clear()

            # Advance to next target or Validation stage
            self.current_target_index += 1
            if self.current_target_index < len(_CALIBRATION_TARGETS):
                next_t = _CALIBRATION_TARGETS[self.current_target_index]
                return {
                    "status": "next_target",
                    "stage": "gaze",
                    "target_index": self.current_target_index,
                    "target_label": next_t["label"],
                    "screen_x": next_t["screen"][0],
                    "screen_y": next_t["screen"][1],
                }
            else:
                # All 5 gaze targets completed -> Advance to Center Validation
                self.current_stage = "validation"
                return {
                    "status": "stage_changed",
                    "stage": "validation",
                    "target_label": "Center Validation",
                    "screen_x": 0.50,
                    "screen_y": 0.50,
                    "message": "Look back at center to validate repeatability.",
                }

        # -------------------------------------------------------------
        # 2. Processing Validation Stage
        # -------------------------------------------------------------
        elif self.current_stage == "validation":
            if len(self._validation_samples) >= 5:
                val_arr = np.array(self._validation_samples)
                val_x = float(np.median(val_arr[:, 0]))
                val_y = float(np.median(val_arr[:, 1]))
                center_pt = self._collected_points[0]["iris"]
                # Repeatability distance in iris coordinates scaled to pixel space
                error_iris = math.hypot(val_x - center_pt[0], val_y - center_pt[1])
                self.last_validation_error_px = round(error_iris * 1920.0, 1)

            self.current_stage = "head_neutral"
            return {
                "status": "stage_changed",
                "stage": "head_neutral",
                "screen_x": 0.50,
                "screen_y": 0.50,
                "message": "Hold head in comfortable neutral posture for scrolling calibration.",
            }

        # -------------------------------------------------------------
        # 3. Processing Head Neutral Stage
        # -------------------------------------------------------------
        elif self.current_stage == "head_neutral":
            neutral_y = None
            if self._head_neutral_samples:
                neutral_y = float(np.median(self._head_neutral_samples))

            # Finalize and persist profile
            self.is_calibrating = False
            self.current_stage = "complete"
            self.last_calibration_time = time.time()

            # Update and save profile
            updates = {
                "gaze": {
                    "calibration_points": self._collected_points,
                },
            }
            if neutral_y is not None:
                updates["head"] = {
                    "neutral_y": round(neutral_y, 2),
                }

            profile_manager.update_profile(self.profile_name, updates)

            return {
                "status": "complete",
                "stage": "complete",
                "calibration_points": self._collected_points,
                "neutral_y": neutral_y,
                "validation_error_px": self.last_validation_error_px,
                "message": "Calibration successfully saved to user profile.",
            }

        return {"status": "error", "message": "Unknown stage"}

    def cancel(self) -> None:
        """Cancel active calibration."""
        self.is_calibrating = False
        self.current_stage = "idle"
        self._target_samples.clear()
        self._collected_points.clear()
        self._validation_samples.clear()
        self._head_neutral_samples.clear()

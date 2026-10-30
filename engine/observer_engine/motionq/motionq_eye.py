"""
MotionQ Assistive Control System - Eye Gaze Controller for Observer
Adapted from MotionQ-blink (eyefeature.py)
Copyright (c) 2026 Aakash Kavediya
Licensed under the MIT License. See LICENSE.MotionQ-blink for details.

Faithful implementation with verified improvements:
1. MediaPipe iris landmark extraction (indices 474-477 left, 469-472 right).
2. Functional 5-point calibration mapping (coherently maps iris features to screen).
3. Non-linear response curve (power 1.2 exponent for micro-accuracy and macro-range).
4. Proximity slowdown near registered clickable targets.
5. Magnetic attraction toward target centers.
6. Weighted temporal cursor smoothing and screen boundary clamping.
7. Safe position-hold during tracking loss.
"""

import math
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from observer_engine.motionq.dwell_engine import DwellEngine


# MediaPipe Face Mesh iris landmarks
_LEFT_IRIS_PERIMETER = [474, 475, 476, 477]
_RIGHT_IRIS_PERIMETER = [469, 470, 471, 472]
_LEFT_IRIS_CENTER = 473
_RIGHT_IRIS_CENTER = 468


class MotionQEyeController:
    def __init__(
        self,
        dwell_engine: Optional[DwellEngine] = None,
        screen_w: float = 1920.0,
        screen_h: float = 1080.0,
        sensitivity: float = 3.0,
        nonlinear_exponent: float = 1.2,
        smoothing_factor: float = 0.70,
        proximity_radius: float = 80.0,
        magnet_radius: float = 40.0,
        magnet_force: float = 0.20,
    ):
        self.dwell_engine = dwell_engine
        self.screen_w = float(screen_w)
        self.screen_h = float(screen_h)
        self.sensitivity = float(sensitivity)
        self.nonlinear_exponent = float(nonlinear_exponent)
        self.smoothing_factor = float(smoothing_factor)
        self.proximity_radius = float(proximity_radius)
        self.magnet_radius = float(magnet_radius)
        self.magnet_force = float(magnet_force)

        # Calibration affine transformation matrix (2x3 for [ix, iy, 1] -> [sx, sy])
        self._affine_transform: Optional[np.ndarray] = None
        self._calibration_points: List[Dict[str, Any]] = []

        # State tracking
        self._prev_cursor: Optional[Tuple[float, float]] = None
        self._last_raw_iris: Optional[Tuple[float, float]] = None
        self._tracking_lost_count: int = 0
        self._face_detected: bool = False

    def update_screen_dimensions(self, width: float, height: float) -> None:
        if width > 0 and height > 0:
            self.screen_w = float(width)
            self.screen_h = float(height)

    def set_calibration(self, calibration_points: List[Dict[str, Any]]) -> bool:
        """
        Fit regularized affine mapping from calibrated iris positions to screen coordinates.
        calibration_points format: [{"iris": [ix, iy], "screen": [sx, sy]}, ...]
        """
        self._calibration_points = list(calibration_points)
        if len(calibration_points) < 3:
            self._affine_transform = None
            return False

        try:
            # Build matrices: X = [ix, iy, 1], Y = [sx * screen_w, sy * screen_h]
            X_list = []
            Y_list = []
            for pt in calibration_points:
                ix, iy = pt["iris"]
                sx, sy = pt["screen"]
                # Convert normalized screen coords to pixel coords if necessary
                px = sx * self.screen_w if sx <= 1.0 else sx
                py = sy * self.screen_h if sy <= 1.0 else sy
                X_list.append([ix, iy, 1.0])
                Y_list.append([px, py])

            X = np.array(X_list, dtype=np.float64)
            Y = np.array(Y_list, dtype=np.float64)

            # Regularized least squares (Ridge regression: (X^T X + lambda I)^-1 X^T Y)
            lmbda = 1e-4
            reg_matrix = lmbda * np.eye(3)
            reg_matrix[2, 2] = 0.0  # Do not regularize bias
            A = np.linalg.solve(X.T @ X + reg_matrix, X.T @ Y)
            self._affine_transform = A.T  # Shape (2, 3)
            return True
        except Exception as e:
            print(f"[MotionQEye] Calibration fit error: {e}")
            self._affine_transform = None
            return False

    def extract_iris_position(self, landmarks: np.ndarray) -> Optional[Tuple[float, float]]:
        """Extract mean normalized iris position (0-1) from landmarks."""
        if landmarks is None or len(landmarks) < 478:
            return None

        # Check for NaN / Inf
        if np.isnan(landmarks).any() or np.isinf(landmarks).any():
            return None

        # Average left and right iris perimeter landmarks
        left_ix = float(np.mean([landmarks[i, 0] for i in _LEFT_IRIS_PERIMETER]))
        left_iy = float(np.mean([landmarks[i, 1] for i in _LEFT_IRIS_PERIMETER]))

        right_ix = float(np.mean([landmarks[i, 0] for i in _RIGHT_IRIS_PERIMETER]))
        right_iy = float(np.mean([landmarks[i, 1] for i in _RIGHT_IRIS_PERIMETER]))

        iris_x = (left_ix + right_ix) / 2.0
        iris_y = (left_iy + right_iy) / 2.0
        return (iris_x, iris_y)

    def _iris_to_screen(self, iris_x: float, iris_y: float) -> Tuple[float, float]:
        """
        Map normalized iris coordinates to pixel coordinates.
        Uses calibrated transform if available; otherwise uses MotionQ sensitivity offset.
        """
        if self._affine_transform is not None:
            inp = np.array([iris_x, iris_y, 1.0], dtype=np.float64)
            pred = self._affine_transform @ inp
            return float(pred[0]), float(pred[1])

        # Reference formula from eyefeature.py
        center_x, center_y = 0.5, 0.5
        offset_x = (iris_x - center_x) * self.sensitivity
        offset_y = (iris_y - center_y) * self.sensitivity

        # Non-linear acceleration for deliberate gaze shifts
        if abs(offset_x) > 0.1:
            offset_x = math.copysign(abs(offset_x) ** self.nonlinear_exponent, offset_x)
        if abs(offset_y) > 0.1:
            offset_y = math.copysign(abs(offset_y) ** self.nonlinear_exponent, offset_y)

        screen_x = (self.screen_w / 2.0) + (offset_x * self.screen_w)
        screen_y = (self.screen_h / 2.0) + (offset_y * self.screen_h)
        return screen_x, screen_y

    def process_frame(
        self,
        landmarks: Optional[np.ndarray],
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Process frame landmarks through:
        1. Iris extraction
        2. Screen mapping
        3. Proximity slowdown near dwell targets
        4. Magnetic attraction toward target centers
        5. Temporal cursor smoothing
        6. Clamping & Tracking loss hold
        """
        iris = self.extract_iris_position(landmarks) if landmarks is not None else None

        if iris is None:
            self._face_detected = False
            self._tracking_lost_count += 1
            if self._prev_cursor is not None:
                cx, cy = self._prev_cursor
            else:
                cx, cy = (self.screen_w / 2.0, self.screen_h / 2.0)

            return {
                "valid": False,
                "cursor_x": cx,
                "cursor_y": cy,
                "norm_x": cx / max(1.0, self.screen_w),
                "norm_y": cy / max(1.0, self.screen_h),
                "iris_x": None,
                "iris_y": None,
                "face_detected": False,
                "magnet_active": False,
                "proximity_active": False,
            }

        self._face_detected = True
        self._tracking_lost_count = 0
        self._last_raw_iris = iris
        iris_x, iris_y = iris

        # Raw screen coordinate from iris gaze
        new_x, new_y = self._iris_to_screen(iris_x, iris_y)

        # -------------------------------------------------------------
        # Proximity Slowdown & Magnetic Attraction from Dwell Targets
        # -------------------------------------------------------------
        magnet_active = False
        proximity_active = False

        if self.dwell_engine is not None:
            targets = self.dwell_engine.get_targets()
            closest_target = None
            min_dist = float("inf")

            for t in targets:
                tcx = t["x"] + t["width"] / 2.0
                tcy = t["y"] + t["height"] / 2.0
                d = math.hypot(new_x - tcx, new_y - tcy)
                if d < min_dist:
                    min_dist = d
                    closest_target = (t, tcx, tcy, d)

            if closest_target is not None:
                _, tcx, tcy, d = closest_target
                if d <= self.magnet_radius:
                    # Magnetic pull toward center
                    new_x += (tcx - new_x) * self.magnet_force
                    new_y += (tcy - new_y) * self.magnet_force
                    magnet_active = True
                elif d <= self.proximity_radius:
                    # Slowdown near target
                    if self._prev_cursor is not None:
                        dx = new_x - self._prev_cursor[0]
                        dy = new_y - self._prev_cursor[1]
                        new_x = self._prev_cursor[0] + dx * 0.40
                        new_y = self._prev_cursor[1] + dy * 0.40
                    proximity_active = True

        # -------------------------------------------------------------
        # Temporal Smoothing: cursor = (prev * factor) + (new * (1 - factor))
        # -------------------------------------------------------------
        if self._prev_cursor is not None:
            cursor_x = (self._prev_cursor[0] * self.smoothing_factor) + (new_x * (1.0 - self.smoothing_factor))
            cursor_y = (self._prev_cursor[1] * self.smoothing_factor) + (new_y * (1.0 - self.smoothing_factor))
        else:
            cursor_x, cursor_y = new_x, new_y

        # Screen boundary clamping
        cursor_x = max(0.0, min(self.screen_w, cursor_x))
        cursor_y = max(0.0, min(self.screen_h, cursor_y))

        self._prev_cursor = (cursor_x, cursor_y)
        norm_x = cursor_x / max(1.0, self.screen_w)
        norm_y = cursor_y / max(1.0, self.screen_h)

        return {
            "valid": True,
            "cursor_x": cursor_x,
            "cursor_y": cursor_y,
            "norm_x": max(0.0, min(1.0, norm_x)),
            "norm_y": max(0.0, min(1.0, norm_y)),
            "iris_x": iris_x,
            "iris_y": iris_y,
            "face_detected": True,
            "magnet_active": magnet_active,
            "proximity_active": proximity_active,
        }

    def reset(self) -> None:
        """Reset internal cursor filter and tracking state."""
        self._prev_cursor = None
        self._last_raw_iris = None
        self._tracking_lost_count = 0
        self._face_detected = False

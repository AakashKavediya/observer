"""
observer_engine.features
Per-frame feature extraction, temporal window aggregation, and quality gating:
- Eye Aspect Ratio (EAR) + adaptive-threshold blink detection
- Rolling blink rate over 30s / 60s / 180s and inter-blink interval (IBI) irregularity
- Head pose estimation via cv2.solvePnP (pitch, yaw, roll)
- Gaze proxy from iris landmarks with head-pose compensation
- I-DT gaze dispersion (4s, 30s, 120s windows) and gaze shifts per minute
- Facial tension index from MediaPipe blendshapes
- Head stillness variance
- Strict quality gating (face lost, low light, extreme angle)
"""

import time
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any
import numpy as np
import cv2

from observer_engine.config import CONFIG, EngineConfig


@dataclass
class FrameFeatures:
    timestamp: float
    valid: bool
    quality_reason: str = ""

    # Raw metrics
    ear: float = 0.0
    left_ear: float = 0.0
    right_ear: float = 0.0
    is_blink: bool = False

    # Head pose angles in degrees
    pitch: float = 0.0
    yaw: float = 0.0
    roll: float = 0.0

    # Compensated gaze proxy [0.0, 1.0]
    gaze_x: float = 0.5
    gaze_y: float = 0.5

    # Tension index [0.0, 1.0]
    tension_index: float = 0.0
    brow_down: float = 0.0
    mouth_press: float = 0.0
    jaw_clench: float = 0.0
    eye_squint: float = 0.0


@dataclass
class WindowedFeatures:
    timestamp: float
    valid: bool

    # Blink metrics
    blink_count_total: int
    blink_rate_30s: float   # blinks per minute
    blink_rate_60s: float   # blinks per minute
    blink_rate_180s: float  # blinks per minute
    blink_irregularity: float  # standard deviation of inter-blink intervals (seconds)

    # Gaze dispersion (I-DT)
    dispersion_4s: float
    dispersion_30s: float
    dispersion_120s: float
    gaze_shifts_per_min: float

    # Tension
    tension_mean_4s: float
    tension_mean_30s: float

    # Head stillness
    head_pose_var_4s: float
    head_pose_var_30s: float


# Canonical 3D facial model points for solvePnP (matching image coordinate orientation: +Y down, +X right)
_MODEL_POINTS_3D = np.array([
    (0.0, 0.0, 0.0),          # Nose tip (landmark 1)
    (0.0, 110.0, -30.0),      # Chin (landmark 152)
    (-60.0, -45.0, -30.0),    # Image-left eye outer corner (landmark 33)
    (60.0, -45.0, -30.0),     # Image-right eye outer corner (landmark 263)
    (-40.0, 60.0, -30.0),     # Image-left mouth corner (landmark 61)
    (40.0, 60.0, -30.0),      # Image-right mouth corner (landmark 291)
], dtype=np.float64)


def calculate_ear(pts: np.ndarray) -> float:
    """
    Computes Eye Aspect Ratio given 6 2D points [p1, p2, p3, p4, p5, p6].
    p1 = outer corner, p4 = inner corner
    p2, p3 = top lid; p5, p6 = bottom lid
    """
    # Vertical distances
    d_v1 = np.linalg.norm(pts[1] - pts[5])
    d_v2 = np.linalg.norm(pts[2] - pts[4])
    # Horizontal distance
    d_h = np.linalg.norm(pts[0] - pts[3])
    if d_h < 1e-6:
        return 0.0
    return float((d_v1 + d_v2) / (2.0 * d_h))


class FeatureExtractor:
    def __init__(self, config: EngineConfig = CONFIG):
        self.config = config

        # Blink state tracking
        self.blink_count_total = 0
        self._in_blink = False
        self._blink_start_time = 0.0
        self._last_blink_time = 0.0
        self._inter_blink_intervals = deque(maxlen=30)
        self._blink_timestamps = deque()  # stores timestamp of each blink

        # Adaptive open-eye EAR rolling tracker
        self._open_ear_samples = deque(maxlen=150)
        self._adaptive_open_ear = self.config.blink.ear_baseline_default

        # History buffers for sliding window metrics
        # Maximum window duration is 180s; at 15 FPS ~ 2700 samples
        self._history: deque[FrameFeatures] = deque(maxlen=3000)

        # Gaze shift counter
        self._last_stable_gaze = (0.5, 0.5)

    def compute_head_pose(
        self,
        landmarks_norm: np.ndarray,
        frame_w: int = 640,
        frame_h: int = 480,
    ) -> Tuple[float, float, float]:
        """
        Calculates head orientation angles (pitch, yaw, roll in degrees) via solvePnP.
        """
        # Landmark indices: 1 (nose), 152 (chin), 33 (L eye), 263 (R eye), 61 (L mouth), 291 (R mouth)
        image_points = np.array([
            (landmarks_norm[1, 0] * frame_w, landmarks_norm[1, 1] * frame_h),
            (landmarks_norm[152, 0] * frame_w, landmarks_norm[152, 1] * frame_h),
            (landmarks_norm[33, 0] * frame_w, landmarks_norm[33, 1] * frame_h),
            (landmarks_norm[263, 0] * frame_w, landmarks_norm[263, 1] * frame_h),
            (landmarks_norm[61, 0] * frame_w, landmarks_norm[61, 1] * frame_h),
            (landmarks_norm[291, 0] * frame_w, landmarks_norm[291, 1] * frame_h),
        ], dtype=np.float64)

        focal_length = frame_w
        center = (frame_w / 2.0, frame_h / 2.0)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype=np.float64)
        dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        success, rvec, _ = cv2.solvePnP(
            _MODEL_POINTS_3D,
            image_points,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )

        if not success:
            return 0.0, 0.0, 0.0

        rmat, _ = cv2.Rodrigues(rvec)
        # Decompose rotation matrix into Euler angles (Pitch, Yaw, Roll)
        sy = math.sqrt(rmat[0, 0] * rmat[0, 0] + rmat[1, 0] * rmat[1, 0])
        singular = sy < 1e-6

        if not singular:
            pitch = math.atan2(rmat[2, 1], rmat[2, 2])
            yaw = math.atan2(-rmat[2, 0], sy)
            roll = math.atan2(rmat[1, 0], rmat[0, 0])
        else:
            pitch = math.atan2(-rmat[1, 2], rmat[1, 1])
            yaw = math.atan2(-rmat[2, 0], sy)
            roll = 0.0

        return (
            float(math.degrees(pitch)),
            float(math.degrees(yaw)),
            float(math.degrees(roll)),
        )

    def extract_frame_features(
        self,
        frame_bgr: Optional[np.ndarray],
        landmarks: Optional[np.ndarray],
        blendshapes: Optional[Dict[str, float]],
        timestamp: float,
    ) -> FrameFeatures:
        """
        Processes single-frame raw signals into normalized FrameFeatures with quality gating.
        """
        # Quality Gate 1: Face Presence
        if landmarks is None or len(landmarks) < 468:
            return FrameFeatures(
                timestamp=timestamp, valid=False, quality_reason="face_lost"
            )

        # Quality Gate 2: Low Light / Illumination Check
        if frame_bgr is not None:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            mean_brightness = float(np.mean(gray))
            if mean_brightness < self.config.quality.min_mean_brightness:
                return FrameFeatures(
                    timestamp=timestamp, valid=False, quality_reason="low_light"
                )

        # Head Pose Calculation
        pitch, yaw, roll = self.compute_head_pose(landmarks)

        # Quality Gate 3: Extreme Head Angle
        if (
            abs(pitch) > self.config.quality.max_pitch_deg
            or abs(yaw) > self.config.quality.max_yaw_deg
            or abs(roll) > self.config.quality.max_roll_deg
        ):
            return FrameFeatures(
                timestamp=timestamp,
                valid=False,
                quality_reason="extreme_head_angle",
                pitch=pitch,
                yaw=yaw,
                roll=roll,
            )

        # 1. EAR (Eye Aspect Ratio) Calculation
        # Left eye landmarks: 33, 160, 158, 133, 153, 144
        l_pts = landmarks[[33, 160, 158, 133, 153, 144], :2]
        left_ear = calculate_ear(l_pts)

        # Right eye landmarks: 362, 385, 387, 263, 373, 380
        r_pts = landmarks[[362, 385, 387, 263, 373, 380], :2]
        right_ear = calculate_ear(r_pts)

        ear = (left_ear + right_ear) / 2.0

        # Adaptive threshold blink detection
        if not self._in_blink and ear > 0.18:
            self._open_ear_samples.append(ear)
            if len(self._open_ear_samples) >= 10:
                self._adaptive_open_ear = float(np.median(self._open_ear_samples))

        blink_threshold = self._adaptive_open_ear * self.config.blink.ear_closed_ratio
        is_blink_event = False

        if ear < blink_threshold:
            if not self._in_blink:
                self._in_blink = True
                self._blink_start_time = timestamp
        else:
            if self._in_blink:
                blink_duration = timestamp - self._blink_start_time
                self._in_blink = False
                if (
                    self.config.blink.min_blink_duration_s
                    <= blink_duration
                    <= self.config.blink.max_blink_duration_s
                ):
                    is_blink_event = True
                    self.blink_count_total += 1
                    self._blink_timestamps.append(timestamp)
                    if self._last_blink_time > 0:
                        ibi = timestamp - self._last_blink_time
                        self._inter_blink_intervals.append(ibi)
                    self._last_blink_time = timestamp

        # 2. Gaze Proxy with Head Pose Compensation
        # Iris landmarks: Left iris center = 468, Right iris center = 473
        if len(landmarks) >= 478:
            l_iris = landmarks[468, :2]
            r_iris = landmarks[473, :2]

            # Eye corner references:
            # Left eye inner 133, outer 33
            l_inner, l_outer = landmarks[133, :2], landmarks[33, :2]
            # Right eye inner 362, outer 263
            r_inner, r_outer = landmarks[362, :2], landmarks[263, :2]

            # Ratio horizontal: 0 = looking right, 1 = looking left
            l_h_denom = max(1e-5, abs(l_outer[0] - l_inner[0]))
            r_h_denom = max(1e-5, abs(r_outer[0] - r_inner[0]))
            l_h_ratio = (l_iris[0] - min(l_inner[0], l_outer[0])) / l_h_denom
            r_h_ratio = (r_iris[0] - min(r_inner[0], r_outer[0])) / r_h_denom
            raw_gaze_x = float((l_h_ratio + r_h_ratio) / 2.0)

            # Ratio vertical: landmarks 159 (top), 145 (bottom)
            l_v_denom = max(1e-5, abs(landmarks[145, 1] - landmarks[159, 1]))
            r_v_denom = max(1e-5, abs(landmarks[374, 1] - landmarks[386, 1]))
            l_v_ratio = (l_iris[1] - min(landmarks[159, 1], landmarks[145, 1])) / l_v_denom
            r_v_ratio = (r_iris[1] - min(landmarks[386, 1], landmarks[374, 1])) / r_v_denom
            raw_gaze_y = float((l_v_ratio + r_v_ratio) / 2.0)

            # Head pose compensation: offset by normalized pitch and yaw
            # (1 deg yaw ~ 0.008 gaze offset)
            comp_gaze_x = float(np.clip(raw_gaze_x - (yaw * 0.008), 0.0, 1.0))
            comp_gaze_y = float(np.clip(raw_gaze_y - (pitch * 0.008), 0.0, 1.0))
        else:
            comp_gaze_x, comp_gaze_y = 0.5, 0.5

        # 3. Facial Tension Index from Blendshapes
        bs = blendshapes or {}
        brow_down = (bs.get("browDownLeft", 0.0) + bs.get("browDownRight", 0.0)) / 2.0
        mouth_press = (bs.get("mouthPressLeft", 0.0) + bs.get("mouthPressRight", 0.0)) / 2.0
        jaw_clench = max(bs.get("jawForward", 0.0), bs.get("mouthClose", 0.0))
        eye_squint = (bs.get("eyeSquintLeft", 0.0) + bs.get("eyeSquintRight", 0.0)) / 2.0

        tc = self.config.tension
        tension_index = float(
            tc.weight_brow_down * brow_down
            + tc.weight_mouth_press * mouth_press
            + tc.weight_jaw_clench * jaw_clench
            + tc.weight_squint * eye_squint
        )
        tension_index = float(np.clip(tension_index, 0.0, 1.0))

        feat = FrameFeatures(
            timestamp=timestamp,
            valid=True,
            ear=ear,
            left_ear=left_ear,
            right_ear=right_ear,
            is_blink=is_blink_event,
            pitch=pitch,
            yaw=yaw,
            roll=roll,
            gaze_x=comp_gaze_x,
            gaze_y=comp_gaze_y,
            tension_index=tension_index,
            brow_down=brow_down,
            mouth_press=mouth_press,
            jaw_clench=jaw_clench,
            eye_squint=eye_squint,
        )

        self._history.append(feat)
        return feat

    def aggregate_windows(self, now: float) -> WindowedFeatures:
        """
        Computes rolling statistics over 4s, 30s, 60s, 120s, 180s windows.
        """
        # Purge blink timestamps older than 180s
        while self._blink_timestamps and (now - self._blink_timestamps[0] > 180.0):
            self._blink_timestamps.popleft()

        # Count blinks in rolling windows
        blinks_30s = sum(1 for t in self._blink_timestamps if now - t <= 30.0)
        blinks_60s = sum(1 for t in self._blink_timestamps if now - t <= 60.0)
        blinks_180s = len(self._blink_timestamps)

        rate_30s = (blinks_30s / 30.0) * 60.0
        rate_60s = (blinks_60s / 60.0) * 60.0
        rate_180s = (blinks_180s / 180.0) * 60.0

        # Inter-blink interval irregularity (std of IBI)
        if len(self._inter_blink_intervals) >= 3:
            irregularity = float(np.std(self._inter_blink_intervals))
        else:
            irregularity = 0.0

        # Window slices from history for valid frames
        frames_4s = [f for f in self._history if now - f.timestamp <= 4.0 and f.valid]
        frames_30s = [f for f in self._history if now - f.timestamp <= 30.0 and f.valid]
        frames_120s = [f for f in self._history if now - f.timestamp <= 120.0 and f.valid]

        def compute_dispersion(frames: List[FrameFeatures]) -> float:
            if len(frames) < 2:
                return 0.5
            xs = [f.gaze_x for f in frames]
            ys = [f.gaze_y for f in frames]
            return float((max(xs) - min(xs)) + (max(ys) - min(ys)))

        disp_4s = compute_dispersion(frames_4s)
        disp_30s = compute_dispersion(frames_30s)
        disp_120s = compute_dispersion(frames_120s)

        # Gaze shifts per minute (count of sudden transitions |delta| > 0.08 in 60s)
        shifts = 0
        frames_60s = [f for f in self._history if now - f.timestamp <= 60.0 and f.valid]
        for i in range(1, len(frames_60s)):
            dx = frames_60s[i].gaze_x - frames_60s[i - 1].gaze_x
            dy = frames_60s[i].gaze_y - frames_60s[i - 1].gaze_y
            if math.hypot(dx, dy) > 0.08:
                shifts += 1
        gaze_shifts_per_min = float(shifts)

        # Tension averages
        t_4s = float(np.mean([f.tension_index for f in frames_4s])) if frames_4s else 0.0
        t_30s = float(np.mean([f.tension_index for f in frames_30s])) if frames_30s else 0.0

        # Head pose variance (stillness proxy)
        def head_variance(frames: List[FrameFeatures]) -> float:
            if len(frames) < 3:
                return 0.0
            pitches = [f.pitch for f in frames]
            yaws = [f.yaw for f in frames]
            rolls = [f.roll for f in frames]
            return float(np.var(pitches) + np.var(yaws) + np.var(rolls))

        h_var_4s = head_variance(frames_4s)
        h_var_30s = head_variance(frames_30s)

        # Valid overall if at least 50% of frames in the last 4s were valid
        recent_valid = len(frames_4s) >= (self.config.camera.target_fps * 2.0)

        return WindowedFeatures(
            timestamp=now,
            valid=recent_valid,
            blink_count_total=self.blink_count_total,
            blink_rate_30s=rate_30s,
            blink_rate_60s=rate_60s,
            blink_rate_180s=rate_180s,
            blink_irregularity=irregularity,
            dispersion_4s=disp_4s,
            dispersion_30s=disp_30s,
            dispersion_120s=disp_120s,
            gaze_shifts_per_min=gaze_shifts_per_min,
            tension_mean_4s=t_4s,
            tension_mean_30s=t_30s,
            head_pose_var_4s=h_var_4s,
            head_pose_var_30s=h_var_30s,
        )

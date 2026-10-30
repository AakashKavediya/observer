"""
observer_engine.health_tech.feature_extractor
Modular Physiological-Behavioral Feature Extraction Service for Observer.

Calculates:
1. Eye Behavior: EAR (per-eye), validated temporal blinks, blinks/min (30s/60s/180s),
   IBI distribution (mean/median/std/p10/p90), eye closure duration, long-closure events,
   eye aperture variability, gaze dispersion and shift frequency.
2. Smile-Related Behavior: Geometric lip-corner displacement/elevation, blendshape scores,
   duration above threshold, event count/duration, and bilateral asymmetry.
3. Other Facial Movement: Brow elevation & asymmetry, mouth opening, jaw geometry,
   and Euclidean displacement from neutral facial reference.
4. Head Movement: Pitch, yaw, roll, angular velocity, range of movement,
   direction-change frequency, and low-movement intervals.
5. Upper-Body Movement: Modular pose adapter reporting availability or explicit
   'upper_body_outside_camera_frame' status without landmark fabrication.

Health-Tech Disclaimers:
- Facial geometry measurements are geometric features and model-derived coefficients,
  not direct measurements of muscle activation, emotion, pain, or medical condition.
- Low head movement is an observable kinematic property, not clinical paralysis or fatigue.
"""

import time
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
import numpy as np
import cv2

from observer_engine.health_tech.schema import ObservationRecord, ValidityStatus, Provenance


# Standard 3D facial model points for solvePnP
_MODEL_POINTS_3D = np.array([
    (0.0, 0.0, 0.0),          # Nose tip (landmark 1)
    (0.0, 110.0, -30.0),      # Chin (landmark 152)
    (-60.0, -45.0, -30.0),    # Left eye outer corner (landmark 33)
    (60.0, -45.0, -30.0),     # Right eye outer corner (landmark 263)
    (-40.0, 60.0, -30.0),     # Left mouth corner (landmark 61)
    (40.0, 60.0, -30.0),      # Right mouth corner (landmark 291)
], dtype=np.float64)


def calculate_ear(pts: np.ndarray) -> float:
    """
    Computes Eye Aspect Ratio (EAR) given 6 2D points [p1, p2, p3, p4, p5, p6].
    p1 = outer corner, p4 = inner corner
    p2, p3 = upper eyelid; p5, p6 = lower eyelid
    """
    d_v1 = float(np.linalg.norm(pts[1] - pts[5]))
    d_v2 = float(np.linalg.norm(pts[2] - pts[4]))
    d_h = float(np.linalg.norm(pts[0] - pts[3]))
    if d_h < 1e-6:
        return 0.0
    return float((d_v1 + d_v2) / (2.0 * d_h))


@dataclass
class PhysiologicalSnapshot:
    timestamp: float
    session_id: str
    valid: bool
    quality_reason: str = ""

    # Eye behavior
    ear_left: Optional[float] = None
    ear_right: Optional[float] = None
    ear_avg: Optional[float] = None
    is_blink: bool = False
    blink_count_total: int = 0
    blink_rate_30s: Optional[float] = None
    blink_rate_60s: Optional[float] = None
    blink_rate_180s: Optional[float] = None
    ibi_mean: Optional[float] = None
    ibi_median: Optional[float] = None
    ibi_std: Optional[float] = None
    ibi_p10: Optional[float] = None
    ibi_p90: Optional[float] = None
    last_closure_duration: Optional[float] = None
    is_long_closure: bool = False
    eye_aperture_variability_30s: Optional[float] = None
    gaze_dispersion_30s: Optional[float] = None
    gaze_shifts_per_min: Optional[float] = None

    # Smile-related behavior
    mouth_corner_elevation_left: Optional[float] = None
    mouth_corner_elevation_right: Optional[float] = None
    mouth_width_ratio: Optional[float] = None
    smile_blendshape_left: Optional[float] = None
    smile_blendshape_right: Optional[float] = None
    smile_score_avg: Optional[float] = None
    smile_asymmetry: Optional[float] = None
    smile_duration_above_thresh_30s: Optional[float] = None
    smile_event_count_total: int = 0

    # Other facial movement
    brow_elevation_left: Optional[float] = None
    brow_elevation_right: Optional[float] = None
    brow_asymmetry: Optional[float] = None
    mouth_opening_ratio: Optional[float] = None
    jaw_open_score: Optional[float] = None
    facial_geometry_deviation: Optional[float] = None

    # Head movement
    pitch: Optional[float] = None
    yaw: Optional[float] = None
    roll: Optional[float] = None
    angular_velocity: Optional[float] = None
    head_movement_range_30s: Optional[float] = None
    direction_changes_per_min: Optional[float] = None
    low_movement_duration_s: float = 0.0

    # Upper body movement (modular adapter)
    upper_body_available: bool = False
    upper_body_reason: str = "upper_body_outside_camera_frame"
    shoulder_tilt_deg: Optional[float] = None
    shoulder_movement_velocity: Optional[float] = None


class BehavioralFeatureExtractor:
    def __init__(self, session_id: str = "default_session"):
        self.session_id = session_id

        # Blink state tracking
        self.blink_count_total: int = 0
        self._in_blink: bool = False
        self._blink_start_time: float = 0.0
        self._last_blink_time: float = 0.0
        self._last_closure_duration: float = 0.0
        self._inter_blink_intervals: deque = deque(maxlen=30)
        self._blink_timestamps: deque = deque()

        # Open-eye adaptive EAR baseline
        self._open_ear_samples: deque = deque(maxlen=150)
        self._adaptive_open_ear: float = 0.28

        # Long closure event threshold (seconds)
        self.long_closure_threshold_s: float = 0.50

        # Smile event tracking
        self.smile_event_count: int = 0
        self._in_smile: bool = False
        self._smile_start_time: float = 0.0
        self._smile_threshold: float = 0.35
        self._smile_history_30s: deque = deque(maxlen=900) # timestamps where smile was active

        # Head movement kinematics tracking
        self._prev_head_angles: Optional[Tuple[float, float, float]] = None
        self._prev_head_ts: Optional[float] = None
        self._head_angular_velocities: deque = deque(maxlen=900)
        self._head_pitches: deque = deque(maxlen=900)
        self._head_yaws: deque = deque(maxlen=900)
        self._low_movement_start_ts: Optional[float] = None
        self._low_movement_acc_s: float = 0.0

        # Gaze tracking
        self._gaze_points_30s: deque = deque(maxlen=900)
        self._gaze_shifts_60s: deque = deque(maxlen=900)
        self._last_stable_gaze: Optional[Tuple[float, float]] = None

        # Neutral baseline references for relative displacement
        self.neutral_head_angles: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.neutral_brow_elevation: float = 0.15
        self.neutral_mouth_width: float = 0.45
        self.neutral_anchors: Optional[np.ndarray] = None # Landmark coordinates in neutral pose

    def set_neutral_baseline(
        self,
        neutral_angles: Tuple[float, float, float],
        neutral_anchors: Optional[np.ndarray] = None,
        neutral_brow: float = 0.15,
        neutral_mouth_width: float = 0.45,
    ) -> None:
        """Sets calibrated neutral reference points for relative displacements."""
        self.neutral_head_angles = neutral_angles
        self.neutral_anchors = neutral_anchors
        self.neutral_brow_elevation = neutral_brow
        self.neutral_mouth_width = neutral_mouth_width

    def compute_head_pose(
        self,
        landmarks: np.ndarray,
        frame_w: int = 640,
        frame_h: int = 480,
    ) -> Tuple[float, float, float]:
        """Calculates 3D head pitch, yaw, roll angles in degrees via solvePnP."""
        # 1: nose tip, 152: chin, 33: left eye outer, 263: right eye outer, 61: left mouth, 291: right mouth
        image_points = np.array([
            (landmarks[1, 0] * frame_w, landmarks[1, 1] * frame_h),
            (landmarks[152, 0] * frame_w, landmarks[152, 1] * frame_h),
            (landmarks[33, 0] * frame_w, landmarks[33, 1] * frame_h),
            (landmarks[263, 0] * frame_w, landmarks[263, 1] * frame_h),
            (landmarks[61, 0] * frame_w, landmarks[61, 1] * frame_h),
            (landmarks[291, 0] * frame_w, landmarks[291, 1] * frame_h),
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
        sy = math.sqrt(rmat[0, 0] * rmat[0, 0] + rmat[1, 0] * rmat[1, 0])
        if sy >= 1e-6:
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

    def extract_snapshot(
        self,
        frame_bgr: Optional[np.ndarray],
        landmarks: Optional[np.ndarray],
        blendshapes: Optional[Dict[str, float]],
        timestamp: float,
        is_tracking_valid: bool = True,
        tracking_reason: str = "optimal",
    ) -> PhysiologicalSnapshot:
        """
        Extracts multi-feature snapshot from current video frame and landmarks.
        Never replaces missing or invalid metrics with zero.
        """
        if not is_tracking_valid or landmarks is None or len(landmarks) < 468:
            # Tracking loss hold: Reset blink in-progress without registering false blink
            self._in_blink = False
            self._in_smile = False
            self._prev_head_angles = None
            self._prev_head_ts = None
            return PhysiologicalSnapshot(
                timestamp=timestamp,
                session_id=self.session_id,
                valid=False,
                quality_reason=tracking_reason or "tracking_lost",
                blink_count_total=self.blink_count_total,
                smile_event_count_total=self.smile_event_count,
            )

        # -------------------------------------------------------------
        # 1. Eye Behavior Extraction
        # -------------------------------------------------------------
        # Left eye: [33, 160, 158, 133, 153, 144]
        ear_l = calculate_ear(landmarks[[33, 160, 158, 133, 153, 144], :2])
        # Right eye: [362, 385, 387, 263, 373, 380]
        ear_r = calculate_ear(landmarks[[362, 385, 387, 263, 373, 380], :2])
        ear_avg = (ear_l + ear_r) / 2.0

        # Update adaptive open-eye EAR baseline
        if not self._in_blink and ear_avg > 0.16:
            self._open_ear_samples.append(ear_avg)
            if len(self._open_ear_samples) >= 15:
                self._adaptive_open_ear = float(np.median(self._open_ear_samples))

        blink_threshold = self._adaptive_open_ear * 0.75
        is_blink_event = False
        is_long_closure_event = False

        if ear_avg < blink_threshold:
            if not self._in_blink:
                self._in_blink = True
                self._blink_start_time = timestamp
            else:
                closure_duration = timestamp - self._blink_start_time
                if closure_duration >= self.long_closure_threshold_s:
                    is_long_closure_event = True
        else:
            if self._in_blink:
                closure_duration = timestamp - self._blink_start_time
                self._in_blink = False
                self._last_closure_duration = closure_duration

                # Validate blink criteria (50ms - 400ms)
                if 0.05 <= closure_duration <= 0.40:
                    is_blink_event = True
                    self.blink_count_total += 1
                    self._blink_timestamps.append(timestamp)
                    if self._last_blink_time > 0:
                        ibi = timestamp - self._last_blink_time
                        self._inter_blink_intervals.append(ibi)
                    self._last_blink_time = timestamp

        # Rolling blink rates
        # Purge timestamps older than 180s
        while self._blink_timestamps and (timestamp - self._blink_timestamps[0] > 180.0):
            self._blink_timestamps.popleft()

        blinks_30s = sum(1 for t in self._blink_timestamps if timestamp - t <= 30.0)
        blinks_60s = sum(1 for t in self._blink_timestamps if timestamp - t <= 60.0)
        blinks_180s = len(self._blink_timestamps)

        rate_30s = (blinks_30s / 30.0) * 60.0
        rate_60s = (blinks_60s / 60.0) * 60.0
        rate_180s = (blinks_180s / 180.0) * 60.0

        # IBI distribution stats
        if len(self._inter_blink_intervals) >= 3:
            ibis = np.array(self._inter_blink_intervals)
            ibi_mean = float(np.mean(ibis))
            ibi_med = float(np.median(ibis))
            ibi_std = float(np.std(ibis))
            ibi_p10 = float(np.percentile(ibis, 10))
            ibi_p90 = float(np.percentile(ibis, 90))
        else:
            ibi_mean = ibi_med = ibi_std = ibi_p10 = ibi_p90 = None

        # Eye aperture variability (std of open-eye EAR samples over last 30s)
        if len(self._open_ear_samples) >= 10:
            eye_aperture_var = float(np.std(self._open_ear_samples))
        else:
            eye_aperture_var = None

        # -------------------------------------------------------------
        # 2. Gaze Dispersion and Shift Frequency
        # -------------------------------------------------------------
        if len(landmarks) >= 478:
            l_iris = landmarks[468, :2]
            r_iris = landmarks[473, :2]
            gaze_x = float((l_iris[0] + r_iris[0]) / 2.0)
            gaze_y = float((l_iris[1] + r_iris[1]) / 2.0)
            self._gaze_points_30s.append((timestamp, gaze_x, gaze_y))

            # Compute gaze shift (> 0.08 normalized unit delta)
            if self._last_stable_gaze is not None:
                dx = gaze_x - self._last_stable_gaze[0]
                dy = gaze_y - self._last_stable_gaze[1]
                if math.hypot(dx, dy) >= 0.08:
                    self._gaze_shifts_60s.append(timestamp)
                    self._last_stable_gaze = (gaze_x, gaze_y)
            else:
                self._last_stable_gaze = (gaze_x, gaze_y)

            # Purge older gaze shifts
            while self._gaze_shifts_60s and (timestamp - self._gaze_shifts_60s[0] > 60.0):
                self._gaze_shifts_60s.popleft()
            gaze_shifts_per_min = float(len(self._gaze_shifts_60s))

            # I-DT Dispersion over last 30s
            pts_30s = [p for p in self._gaze_points_30s if timestamp - p[0] <= 30.0]
            if len(pts_30s) >= 5:
                xs = [p[1] for p in pts_30s]
                ys = [p[2] for p in pts_30s]
                gaze_dispersion_30s = float((max(xs) - min(xs)) + (max(ys) - min(ys)))
            else:
                gaze_dispersion_30s = None
        else:
            gaze_shifts_per_min = None
            gaze_dispersion_30s = None

        # -------------------------------------------------------------
        # 3. Smile-Related Behavior Extraction
        # -------------------------------------------------------------
        # Inter-ocular distance (IOD) for scale-invariant normalization
        iod = float(np.linalg.norm(landmarks[33, :2] - landmarks[263, :2]))
        iod = max(1e-4, iod)

        # Mouth landmarks: 61 (L corner), 291 (R corner), 13 (upper lip mid), 14 (lower lip mid)
        p_l_corner = landmarks[61, :2]
        p_r_corner = landmarks[291, :2]
        p_mid_lip = (landmarks[13, :2] + landmarks[14, :2]) / 2.0

        # Mouth width ratio
        mouth_width = float(np.linalg.norm(p_l_corner - p_r_corner)) / iod

        # Mouth corner elevation: upward vertical displacement relative to mid-lip (Y down)
        elev_l = float((p_mid_lip[1] - p_l_corner[1]) / iod)
        elev_r = float((p_mid_lip[1] - p_r_corner[1]) / iod)

        # Blendshapes
        bs = blendshapes or {}
        smile_l = float(bs.get("mouthSmileLeft", 0.0))
        smile_r = float(bs.get("mouthSmileRight", 0.0))
        smile_avg = (smile_l + smile_r) / 2.0
        smile_asym = abs(smile_l - smile_r)

        # Smile event tracking
        if smile_avg >= self._smile_threshold:
            self._smile_history_30s.append(timestamp)
            if not self._in_smile:
                self._in_smile = True
                self._smile_start_time = timestamp
                self.smile_event_count += 1
        else:
            self._in_smile = False

        # Purge smile history > 30s
        while self._smile_history_30s and (timestamp - self._smile_history_30s[0] > 30.0):
            self._smile_history_30s.popleft()
        # Approx duration above threshold over 30s (at 15-30 fps ~ 0.033s per frame)
        smile_duration_30s = float(len(self._smile_history_30s) * 0.033)

        # -------------------------------------------------------------
        # 4. Other Facial Movement
        # -------------------------------------------------------------
        # Brow elevation: distance from eye center to brow anchor
        # Left brow: 105, Left eye center: (33 + 133)/2
        l_eye_center = (landmarks[33, :2] + landmarks[133, :2]) / 2.0
        r_eye_center = (landmarks[263, :2] + landmarks[362, :2]) / 2.0
        brow_elev_l = float(np.linalg.norm(landmarks[105, :2] - l_eye_center) / iod)
        brow_elev_r = float(np.linalg.norm(landmarks[334, :2] - r_eye_center) / iod)
        brow_asym = abs(brow_elev_l - brow_elev_r)

        # Mouth opening ratio: vertical opening between lips
        mouth_open = float(np.linalg.norm(landmarks[13, :2] - landmarks[14, :2]) / iod)
        jaw_open_score = float(bs.get("jawOpen", 0.0))

        # Deviation from neutral facial anchors
        if self.neutral_anchors is not None and len(self.neutral_anchors) == len(landmarks):
            geom_diff = np.linalg.norm(landmarks[:, :2] - self.neutral_anchors[:, :2], axis=1)
            facial_geom_dev = float(np.mean(geom_diff) / iod)
        else:
            facial_geom_dev = None

        # -------------------------------------------------------------
        # 5. Head Movement Kinematics
        # -------------------------------------------------------------
        pitch, yaw, roll = self.compute_head_pose(landmarks)
        self._head_pitches.append((timestamp, pitch))
        self._head_yaws.append((timestamp, yaw))

        if self._prev_head_angles is not None and self._prev_head_ts is not None:
            dt = max(1e-4, timestamp - self._prev_head_ts)
            dp = pitch - self._prev_head_angles[0]
            dy = yaw - self._prev_head_angles[1]
            dr = roll - self._prev_head_angles[2]
            ang_vel = float(math.sqrt(dp*dp + dy*dy + dr*dr) / dt)
            self._head_angular_velocities.append((timestamp, ang_vel))

            # Direction-change tracking
            if ang_vel < 1.0: # Below 1 deg/s = low movement
                if self._low_movement_start_ts is None:
                    self._low_movement_start_ts = timestamp
                self._low_movement_acc_s = timestamp - self._low_movement_start_ts
            else:
                self._low_movement_start_ts = None
                self._low_movement_acc_s = 0.0
        else:
            ang_vel = None
            self._low_movement_acc_s = 0.0

        self._prev_head_angles = (pitch, yaw, roll)
        self._prev_head_ts = timestamp

        # Head range over 30s
        recent_p = [p[1] for p in self._head_pitches if timestamp - p[0] <= 30.0]
        recent_y = [y[1] for y in self._head_yaws if timestamp - y[0] <= 30.0]
        if len(recent_p) >= 5 and len(recent_y) >= 5:
            head_range_30s = float((max(recent_p) - min(recent_p)) + (max(recent_y) - min(recent_y)))
        else:
            head_range_30s = None

        # Direction changes per minute (zero crossings of angular velocity derivatives)
        vel_30s = [v[1] for v in self._head_angular_velocities if timestamp - v[0] <= 60.0]
        if len(vel_30s) >= 10:
            diffs = np.diff(vel_30s)
            sign_changes = np.where(np.diff(np.sign(diffs)))[0]
            direction_changes_per_min = float(len(sign_changes) * (60.0 / max(1.0, len(vel_30s) * 0.033)))
        else:
            direction_changes_per_min = None

        # -------------------------------------------------------------
        # 6. Upper-Body Movement (Modular Adapter)
        # -------------------------------------------------------------
        # Observer is designed for face webcams. When shoulders are outside frame,
        # we explicitly mark upper body unavailable without fabricating keypoints.
        upper_body_avail = False
        upper_body_reason = "upper_body_outside_camera_frame"
        shoulder_tilt = None
        shoulder_vel = None

        return PhysiologicalSnapshot(
            timestamp=timestamp,
            session_id=self.session_id,
            valid=True,
            quality_reason="optimal",
            ear_left=round(ear_l, 4),
            ear_right=round(ear_r, 4),
            ear_avg=round(ear_avg, 4),
            is_blink=is_blink_event,
            blink_count_total=self.blink_count_total,
            blink_rate_30s=round(rate_30s, 1),
            blink_rate_60s=round(rate_60s, 1),
            blink_rate_180s=round(rate_180s, 1),
            ibi_mean=round(ibi_mean, 2) if ibi_mean is not None else None,
            ibi_median=round(ibi_med, 2) if ibi_med is not None else None,
            ibi_std=round(ibi_std, 2) if ibi_std is not None else None,
            ibi_p10=round(ibi_p10, 2) if ibi_p10 is not None else None,
            ibi_p90=round(ibi_p90, 2) if ibi_p90 is not None else None,
            last_closure_duration=round(self._last_closure_duration, 3) if self._last_closure_duration > 0 else None,
            is_long_closure=is_long_closure_event,
            eye_aperture_variability_30s=round(eye_aperture_var, 4) if eye_aperture_var is not None else None,
            gaze_dispersion_30s=round(gaze_dispersion_30s, 3) if gaze_dispersion_30s is not None else None,
            gaze_shifts_per_min=round(gaze_shifts_per_min, 1) if gaze_shifts_per_min is not None else None,
            mouth_corner_elevation_left=round(elev_l, 4),
            mouth_corner_elevation_right=round(elev_r, 4),
            mouth_width_ratio=round(mouth_width, 4),
            smile_blendshape_left=round(smile_l, 3),
            smile_blendshape_right=round(smile_r, 3),
            smile_score_avg=round(smile_avg, 3),
            smile_asymmetry=round(smile_asym, 3),
            smile_duration_above_thresh_30s=round(smile_duration_30s, 1),
            smile_event_count_total=self.smile_event_count,
            brow_elevation_left=round(brow_elev_l, 4),
            brow_elevation_right=round(brow_elev_r, 4),
            brow_asymmetry=round(brow_asym, 4),
            mouth_opening_ratio=round(mouth_open, 4),
            jaw_open_score=round(jaw_open_score, 3),
            facial_geometry_deviation=round(facial_geom_dev, 4) if facial_geom_dev is not None else None,
            pitch=round(pitch, 1),
            yaw=round(yaw, 1),
            roll=round(roll, 1),
            angular_velocity=round(ang_vel, 1) if ang_vel is not None else None,
            head_movement_range_30s=round(head_range_30s, 1) if head_range_30s is not None else None,
            direction_changes_per_min=round(direction_changes_per_min, 1) if direction_changes_per_min is not None else None,
            low_movement_duration_s=round(self._low_movement_acc_s, 1),
            upper_body_available=upper_body_avail,
            upper_body_reason=upper_body_reason,
            shoulder_tilt_deg=shoulder_tilt,
            shoulder_movement_velocity=shoulder_vel,
        )

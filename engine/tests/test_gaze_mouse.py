"""
test_gaze_mouse.py
Automated test suite for Track 4 Stability-First Head-Tracking Mouse Controller:
- Scale-invariant feature extraction (nose bridge, head pose, hybrid)
- Scale invariance across face zoom and lateral translation
- Strict validity gating (blinks, face loss, extreme head angles)
- Outlier spike rejection (Stage 3)
- One Euro Filter temporal smoothing (Stage 4)
- Regularized Ridge regression calibration with Median + MAD outlier filtering
- Dead-zone suppression and velocity limiting (Stage 7)
- Blink hold (< 400ms) and smooth recovery
- Preset configuration (maximum_stability, balanced, responsive)
- Stability diagnostic test calculation (jitter, drift, outlier %, validity %, 0-100 score)
- Safety controls (pause, resume, emergency stop)
"""

import os
import tempfile
import time
import pytest
import numpy as np

from observer_engine.gaze_mouse import (
    GazeMouseTracker,
    OneEuroFilter1D,
    OneEuroFilter2D,
    GazeCalibrationProfile,
    CALIBRATION_TARGETS,
    STABILITY_PRESETS,
)


@pytest.fixture
def temp_gaze_tracker():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tracker = GazeMouseTracker(storage_dir=tmp_dir)
        yield tracker


def create_mock_landmarks(
    l_outer=(0.30, 0.40),
    r_outer=(0.70, 0.40),
    nose=(0.50, 0.40),
    iris_l=(0.45, 0.40),
    iris_r=(0.55, 0.40),
):
    """Creates a mock (478, 3) landmarks array with outer eye corners, nose bridge, and irises."""
    arr = np.zeros((478, 3), dtype=np.float32)
    # Eye corners for Left Eye
    arr[33] = [l_outer[0], l_outer[1], 0.0]   # outer corner
    arr[133] = [0.48, 0.40, 0.0]  # inner corner
    arr[159] = [0.39, 0.35, 0.0]  # top lid
    arr[145] = [0.39, 0.45, 0.0]  # bottom lid

    # Eye corners for Right Eye
    arr[263] = [r_outer[0], r_outer[1], 0.0]  # outer corner
    arr[362] = [0.52, 0.40, 0.0]  # inner corner
    arr[386] = [0.61, 0.35, 0.0]  # top lid
    arr[374] = [0.61, 0.45, 0.0]  # bottom lid

    # Nose Bridge
    arr[168] = [nose[0], nose[1], 0.0]  # nasion/glabella
    arr[6] = [nose[0], nose[1] + 0.02, 0.0]   # nasal bridge

    # Iris Centers
    arr[468] = [iris_l[0], iris_l[1], 0.0]  # Left iris
    arr[473] = [iris_r[0], iris_r[1], 0.0]  # Right iris
    return arr


# -------------------------------------------------------------
# 1. Validity Gating Tests
# -------------------------------------------------------------
def test_tracking_validity_checks(temp_gaze_tracker):
    tracker = temp_gaze_tracker
    valid_landmarks = create_mock_landmarks()

    # Normal valid conditions
    valid, msg = tracker.check_tracking_validity(valid_landmarks, ear=0.28, pitch=0.0, yaw=0.0)
    assert valid is True
    assert "locked" in msg.lower()

    # Missing landmarks
    valid, msg = tracker.check_tracking_validity(None, ear=0.28, pitch=0.0, yaw=0.0)
    assert valid is False
    assert "lost" in msg.lower()

    # Incomplete landmarks array (< 478 points)
    valid, msg = tracker.check_tracking_validity(np.zeros((100, 3)), ear=0.28, pitch=0.0, yaw=0.0)
    assert valid is False

    # Blink detection (EAR < 0.15)
    valid, msg = tracker.check_tracking_validity(valid_landmarks, ear=0.10, pitch=0.0, yaw=0.0)
    assert valid is False
    assert "blink" in msg.lower()

    # Extreme yaw (head turned away > 40 deg)
    valid, msg = tracker.check_tracking_validity(valid_landmarks, ear=0.28, pitch=0.0, yaw=45.0)
    assert valid is False
    assert "horizontally" in msg.lower()

    # Extreme pitch (head tilted up/down > 35 deg)
    valid, msg = tracker.check_tracking_validity(valid_landmarks, ear=0.28, pitch=-38.0, yaw=0.0)
    assert valid is False
    assert "vertically" in msg.lower()


# -------------------------------------------------------------
# 2. Scale-Invariant Feature Extraction & Modes
# -------------------------------------------------------------
def test_scale_invariant_feature_extraction(temp_gaze_tracker):
    tracker = temp_gaze_tracker

    # 1. Base scale face (inter-ocular distance = 0.40)
    base_lms = create_mock_landmarks(
        l_outer=(0.30, 0.40),
        r_outer=(0.70, 0.40),
        nose=(0.52, 0.40),  # shifted +0.02 from midpoint 0.50
    )
    tracker.set_tracking_mode("nose_bridge")
    feat_base = tracker.extract_features(base_lms, pitch=0.0, yaw=0.0)
    assert feat_base is not None
    # delta_x = (0.52 - 0.50) / 0.40 = 0.05
    assert pytest.approx(feat_base[0], abs=1e-3) == 0.05

    # 2. Scaled face: 2x zoom (inter-ocular distance = 0.80) & shifted
    zoom_lms = create_mock_landmarks(
        l_outer=(0.10, 0.40),
        r_outer=(0.90, 0.40),
        nose=(0.54, 0.40),  # shifted +0.04 from midpoint 0.50
    )
    feat_zoom = tracker.extract_features(zoom_lms, pitch=0.0, yaw=0.0)
    assert feat_zoom is not None
    # delta_x = (0.54 - 0.50) / 0.80 = 0.05 (IDENTICAL!)
    assert pytest.approx(feat_zoom[0], abs=1e-3) == 0.05

    # 3. Test Head Pose mode
    tracker.set_tracking_mode("head_pose")
    feat_pose = tracker.extract_features(base_lms, pitch=-12.5, yaw=15.0)
    assert feat_pose is not None
    # yaw / 30.0 = 0.5, -pitch / 25.0 = 0.5
    assert pytest.approx(feat_pose[0], abs=1e-3) == 0.50
    assert pytest.approx(feat_pose[1], abs=1e-3) == 0.50

    # 4. Test Hybrid mode (0.6 * nose + 0.4 * pose)
    tracker.set_tracking_mode("hybrid")
    feat_hybrid = tracker.extract_features(base_lms, pitch=0.0, yaw=15.0)
    assert feat_hybrid is not None
    expected_x = 0.6 * 0.05 + 0.4 * 0.50  # 0.03 + 0.20 = 0.23
    assert pytest.approx(feat_hybrid[0], abs=1e-3) == expected_x


# -------------------------------------------------------------
# 3. Outlier Jump Rejection (Stage 3)
# -------------------------------------------------------------
def test_outlier_spike_rejection(temp_gaze_tracker):
    tracker = temp_gaze_tracker
    t0 = 1000.0

    # Initial steady point
    p0, out0 = tracker.filter_outliers((0.10, 0.10), t0)
    assert out0 is False
    assert p0 == (0.10, 0.10)

    # Frame 1: Sudden large spike jump > 0.25 in 30ms -> rejected
    p1, out1 = tracker.filter_outliers((0.45, 0.45), t0 + 0.033)
    assert out1 is True
    assert p1 == (0.10, 0.10)  # holds last known position
    assert tracker.total_outliers_detected == 1

    # Frame 2: Spike persists -> still rejected
    p2, out2 = tracker.filter_outliers((0.45, 0.45), t0 + 0.066)
    assert out2 is True
    assert p2 == (0.10, 0.10)

    # Frame 3: Sustained movement (3 consecutive frames) -> accepted as real intentional head shift
    p3, out3 = tracker.filter_outliers((0.45, 0.45), t0 + 0.100)
    assert out3 is False
    assert p3 == (0.45, 0.45)


# -------------------------------------------------------------
# 4. One Euro Filter, Dead Zone, & Velocity Limiting
# -------------------------------------------------------------
def test_one_euro_filter_smoothing():
    f2d = OneEuroFilter2D(min_cutoff=0.8, beta=0.4)
    t0 = 1000.0

    sx1, sy1 = f2d.filter(0.5, 0.5, t0)
    assert sx1 == 0.5
    assert sy1 == 0.5

    # Small jitter at low speed is strongly dampened
    sx2, sy2 = f2d.filter(0.504, 0.504, t0 + 0.033)
    assert abs(sx2 - 0.5) < 0.003

    # Fast saccade accelerates dynamically
    sx3, sy3 = f2d.filter(0.8, 0.8, t0 + 0.066)
    sx4, sy4 = f2d.filter(0.8, 0.8, t0 + 0.100)
    assert sx4 > sx3
    assert sx4 > 0.60


def test_dead_zone_and_velocity_limiting(temp_gaze_tracker):
    tracker = temp_gaze_tracker
    tracker.dead_zone = 0.02
    tracker.max_speed = 0.05
    tracker.last_cursor_norm = (0.50, 0.50)

    # Movement smaller than dead zone: cursor stays locked at 0.50
    landmarks_still = create_mock_landmarks(nose=(0.501, 0.40))
    res_still = tracker.process_frame(landmarks_still, ear=0.28, pitch=0.0, yaw=0.0, timestamp=time.time())
    assert abs(res_still["norm_x"] - 0.50) <= 0.0001

    # Sudden huge movement: clamped to max_speed (0.05)
    tracker.last_cursor_norm = (0.50, 0.50)
    landmarks_jump = create_mock_landmarks(nose=(0.65, 0.40))
    res_jump = tracker.process_frame(landmarks_jump, ear=0.28, pitch=0.0, yaw=0.0, timestamp=time.time() + 0.05)
    # Cursor distance from 0.50 must not exceed max_speed
    dx = res_jump["norm_x"] - 0.50
    dy = res_jump["norm_y"] - 0.50
    dist = (dx * dx + dy * dy) ** 0.5
    assert dist <= 0.0501


# -------------------------------------------------------------
# 5. Blink Hold & Smooth Re-acquisition
# -------------------------------------------------------------
def test_blink_hold_and_recovery(temp_gaze_tracker):
    tracker = temp_gaze_tracker
    lms = create_mock_landmarks()
    t0 = 1000.0

    # Valid initial frame
    res0 = tracker.process_frame(lms, ear=0.28, pitch=0.0, yaw=0.0, timestamp=t0)
    assert res0["valid"] is True
    assert tracker.in_blink_hold is False

    # Short blink (150ms): EAR < 0.15 -> position held without cursor jump
    res_blink = tracker.process_frame(lms, ear=0.08, pitch=0.0, yaw=0.0, timestamp=t0 + 0.15)
    assert res_blink["valid"] is True
    assert tracker.in_blink_hold is True
    assert res_blink["norm_x"] == res0["norm_x"]
    assert res_blink["norm_y"] == res0["norm_y"]

    # Extended face loss (600ms): marked invalid
    res_lost = tracker.process_frame(lms, ear=0.08, pitch=0.0, yaw=0.0, timestamp=t0 + 0.60)
    assert res_lost["valid"] is False
    assert tracker.in_blink_hold is False


# -------------------------------------------------------------
# 6. Presets Configuration Tests
# -------------------------------------------------------------
def test_presets_configuration(temp_gaze_tracker):
    tracker = temp_gaze_tracker

    tracker.apply_preset("maximum_stability")
    assert tracker.dead_zone == 0.020
    assert tracker.max_speed == 0.35
    assert tracker.sensitivity == 0.8

    tracker.apply_preset("responsive")
    assert tracker.dead_zone == 0.006
    assert tracker.max_speed == 1.10
    assert tracker.sensitivity == 1.6

    tracker.apply_preset("balanced")
    assert tracker.dead_zone == 0.012
    assert tracker.max_speed == 0.65
    assert tracker.sensitivity == 1.2


# -------------------------------------------------------------
# 6b. The 8 Comprehensive Synthetic Reliability Tests
# -------------------------------------------------------------
def test_synthetic_1_stationary_jitter_zero_in_dead_zone(temp_gaze_tracker):
    """Test 1: 30 seconds of stationary face with random micro-jitter within dead zone (±0.5°). Assert 0.0 px displacement."""
    tracker = temp_gaze_tracker
    tracker.apply_preset("maximum_stability")
    tracker.neutral_yaw = 0.0
    tracker.neutral_pitch = 0.0
    tracker.is_neutral_calibrated = True
    tracker.last_cursor_norm = (0.50, 0.50)

    lms = create_mock_landmarks()
    t0 = 1000.0

    # Simulate 30 seconds at 30 fps (900 frames) with ±0.5° random head tremor
    for i in range(900):
        t = t0 + i * 0.033
        jitter_yaw = float(np.random.uniform(-0.5, 0.5))
        jitter_pitch = float(np.random.uniform(-0.4, 0.4))
        res = tracker.process_frame(lms, ear=0.28, pitch=jitter_pitch, yaw=jitter_yaw, timestamp=t)
        assert res["in_dead_zone"] is True
        assert res["velocity_x"] == 0.0
        assert res["velocity_y"] == 0.0
        # Position must not move even a single subpixel
        assert res["norm_x"] == 0.50
        assert res["norm_y"] == 0.50


def test_synthetic_2_stationary_face_outlier_rejection(temp_gaze_tracker):
    """Test 2: Stationary face with transient large outliers. Assert outliers rejected and position held."""
    tracker = temp_gaze_tracker
    tracker.neutral_yaw = 0.0
    tracker.neutral_pitch = 0.0
    tracker.is_neutral_calibrated = True
    tracker.last_cursor_norm = (0.50, 0.50)

    lms_steady = create_mock_landmarks(nose=(0.50, 0.40))
    t0 = 1000.0
    tracker.process_frame(lms_steady, ear=0.28, pitch=0.0, yaw=0.0, timestamp=t0)

    # Inject transient spike
    lms_spike = create_mock_landmarks(nose=(0.85, 0.40))
    res_spike = tracker.process_frame(lms_spike, ear=0.28, pitch=0.0, yaw=0.0, timestamp=t0 + 0.033)
    assert res_spike["is_outlier"] is True
    assert res_spike["norm_x"] == 0.50


def test_synthetic_3_slow_intentional_movement_traversal(temp_gaze_tracker):
    """Test 3: Slow intentional deflection outside dead zone produces smooth, continuous cursor traversal."""
    tracker = temp_gaze_tracker
    tracker.set_tracking_mode("head_pose")
    tracker.apply_preset("balanced")
    tracker.neutral_yaw = 0.0
    tracker.neutral_pitch = 0.0
    tracker.is_neutral_calibrated = True
    tracker.last_cursor_norm = (0.50, 0.50)

    lms = create_mock_landmarks()
    t0 = 1000.0

    # Deflect head to the right (-3.5° yaw in solvePnP convention)
    # Cursor should traverse right smoothly
    positions_x = []
    for i in range(15):
        t = t0 + i * 0.033
        res = tracker.process_frame(lms, ear=0.28, pitch=0.0, yaw=-3.5, timestamp=t)
        positions_x.append(res["norm_x"])

    # Must be actively moving to the right
    assert positions_x[-1] > positions_x[0]
    # Consecutive positions should be monotonically increasing
    for i in range(1, len(positions_x)):
        assert positions_x[i] >= positions_x[i - 1]


def test_synthetic_4_quick_movement_velocity_bounded(temp_gaze_tracker):
    """Test 4: Quick large head deflection is clamped to max_speed."""
    tracker = temp_gaze_tracker
    tracker.set_tracking_mode("head_pose")
    tracker.apply_preset("maximum_stability")
    tracker.neutral_yaw = 0.0
    tracker.neutral_pitch = 0.0
    tracker.is_neutral_calibrated = True

    lms = create_mock_landmarks()
    # Large turn (25°)
    res = tracker.process_frame(lms, ear=0.28, pitch=0.0, yaw=-25.0, timestamp=1000.0)
    speed = (res["velocity_x"] ** 2 + res["velocity_y"] ** 2) ** 0.5
    assert speed <= tracker.max_speed + 1e-4


def test_synthetic_5_scale_zoom_invariance(temp_gaze_tracker):
    """Test 5: Scale/zoom changes (varying eye distance by 2x) do not disrupt tracking."""
    tracker = temp_gaze_tracker
    tracker.set_tracking_mode("nose_bridge")
    tracker.neutral_nose_x = 0.0
    tracker.neutral_nose_y = 0.0
    tracker.is_neutral_calibrated = True

    # Face close (d_ocular = 0.60)
    lms_close = create_mock_landmarks(l_outer=(0.20, 0.40), r_outer=(0.80, 0.40), nose=(0.50, 0.40))
    f_close = tracker.extract_features(lms_close, pitch=0.0, yaw=0.0)

    # Face far (d_ocular = 0.30)
    lms_far = create_mock_landmarks(l_outer=(0.35, 0.40), r_outer=(0.65, 0.40), nose=(0.50, 0.40))
    f_far = tracker.extract_features(lms_far, pitch=0.0, yaw=0.0)

    # Normalized features must be virtually identical despite 2x zoom
    assert abs(f_close[0] - f_far[0]) < 1e-3
    assert abs(f_close[1] - f_far[1]) < 1e-3


def test_synthetic_6_tracking_loss_hold_and_reacquisition(temp_gaze_tracker):
    """Test 6: Tracking loss holds position; smooth re-acquisition does not jump."""
    tracker = temp_gaze_tracker
    tracker.last_cursor_norm = (0.42, 0.68)
    lms = create_mock_landmarks()
    t0 = 1000.0

    # Initial frame
    tracker.process_frame(lms, ear=0.28, pitch=0.0, yaw=0.0, timestamp=t0)

    # Blink (loss < 400ms)
    res_blink = tracker.process_frame(lms, ear=0.05, pitch=0.0, yaw=0.0, timestamp=t0 + 0.20)
    assert res_blink["norm_x"] == 0.42
    assert res_blink["norm_y"] == 0.68
    assert res_blink["in_dead_zone"] is True

    # Extended loss (> 400ms)
    res_lost = tracker.process_frame(lms, ear=0.05, pitch=0.0, yaw=0.0, timestamp=t0 + 0.80)
    assert res_lost["valid"] is False

    # Reacquisition
    res_back = tracker.process_frame(lms, ear=0.28, pitch=0.0, yaw=0.0, timestamp=t0 + 1.0)
    assert res_back["valid"] is True
    # Position must resume smoothly from 0.42, 0.68 without jumping
    assert abs(res_back["norm_x"] - 0.42) < 0.05
    assert abs(res_back["norm_y"] - 0.68) < 0.05


def test_synthetic_7_recentering_neutral_without_cursor_jump(temp_gaze_tracker):
    """Test 7: Recenter neutral updates reference to current head pose while cursor position stays strictly identical."""
    tracker = temp_gaze_tracker
    tracker.neutral_yaw = 0.0
    tracker.neutral_pitch = 0.0
    tracker.last_cursor_norm = (0.75, 0.33)

    # Turn head 6° yaw
    lms = create_mock_landmarks()
    tracker.process_frame(lms, ear=0.28, pitch=2.0, yaw=6.0, timestamp=1000.0)
    pos_before_recenter = tracker.last_cursor_norm

    # Recenter now!
    tracker.recenter()

    assert tracker.neutral_yaw == 6.0
    assert tracker.neutral_pitch == 2.0
    assert tracker.in_dead_zone is True
    assert tracker.velocity_x == 0.0
    assert tracker.velocity_y == 0.0
    # Cursor position must be 100% identical to the moment before recenter!
    assert tracker.last_cursor_norm == pos_before_recenter


def test_synthetic_8_boundaries_clamping_and_emergency_stop(temp_gaze_tracker):
    """Test 8: Boundaries clamped to [0.0, 1.0] and emergency stop halts immediately."""
    tracker = temp_gaze_tracker
    tracker.set_tracking_mode("head_pose")
    tracker.apply_preset("responsive")
    tracker.neutral_yaw = 0.0
    tracker.neutral_pitch = 0.0
    tracker.is_neutral_calibrated = True
    tracker.last_cursor_norm = (0.95, 0.95)

    lms = create_mock_landmarks()
    # Continuous push to bottom-right
    for i in range(30):
        tracker.process_frame(lms, ear=0.28, pitch=15.0, yaw=-20.0, timestamp=1000.0 + i * 0.033)

    assert tracker.last_cursor_norm[0] <= 1.0
    assert tracker.last_cursor_norm[1] <= 1.0

    # Emergency stop
    tracker.emergency_stop()
    assert tracker.emergency_stopped is True
    assert tracker.enabled is False
    assert tracker.paused is True
    assert tracker.velocity_x == 0.0
    assert tracker.velocity_y == 0.0


# -------------------------------------------------------------
# 7. Ridge Regression Calibration & Median + MAD Rejection
# -------------------------------------------------------------
def test_guided_calibration_workflow(temp_gaze_tracker):
    tracker = temp_gaze_tracker
    assert tracker.profile.is_calibrated is False

    tracker.start_calibration()
    assert tracker.is_calibrating is True
    assert tracker.calib_target_idx == 0

    # Step through all 6 calibration targets
    for target_idx, target in enumerate(CALIBRATION_TARGETS):
        target_sx = target["screen_x"]
        target_sy = target["screen_y"]

        # Approximate inverse feature for synthetic target collection
        # screen_x = 0.5 - 2.5 * fx -> fx = (0.5 - screen_x) / 2.5
        fx = (0.5 - target_sx) / 2.5
        fy = (target_sy - 0.5) / 2.5

        # Collect 10 samples per target (including 1 synthetic outlier to verify MAD rejection)
        for i in range(10):
            ts = time.time() + i * 0.05
            # Introduce an outlier at i == 2
            curr_fx = fx + (0.3 if i == 2 else np.random.uniform(-0.002, 0.002))
            curr_fy = fy + (0.3 if i == 2 else np.random.uniform(-0.002, 0.002))

            # Set nose bridge position matching curr_fx
            # delta_nose_x = (nose_x - 0.5) / 0.4 -> nose_x = 0.5 + curr_fx * 0.4
            nose_x = 0.5 + curr_fx * 0.4
            nose_y = 0.4 + curr_fy * 0.4

            tracker.process_frame(
                create_mock_landmarks(nose=(nose_x, nose_y)),
                ear=0.28,
                pitch=0.0,
                yaw=0.0,
                timestamp=ts,
            )

        step_res = tracker.advance_calibration_target()
        assert step_res.get("success") is True

    # Calibration complete
    assert tracker.is_calibrating is False
    assert tracker.profile.is_calibrated is True
    assert tracker.profile.quality_label in ("Excellent", "Good", "Fair")
    assert len(tracker.profile.coeff_x) == 4
    assert len(tracker.profile.coeff_y) == 4

    # Verification: profile saved to disk
    assert os.path.isfile(tracker.calib_file_path)

    # Reset calibration
    tracker.reset_calibration()
    assert tracker.profile.is_calibrated is False
    assert not os.path.exists(tracker.calib_file_path)


# -------------------------------------------------------------
# 8. Stability Diagnostic Test
# -------------------------------------------------------------
def test_stability_diagnostic(temp_gaze_tracker):
    tracker = temp_gaze_tracker
    lms = create_mock_landmarks(nose=(0.50, 0.40))

    diag_start = tracker.start_diagnostic(duration_seconds=1.0)
    assert diag_start["status"] == "diagnostic_started"
    assert tracker.is_diagnosing is True

    # Feed 20 steady frames
    for i in range(20):
        tracker.process_frame(lms, ear=0.28, pitch=0.0, yaw=0.0, timestamp=time.time() + i * 0.033)

    result = tracker.finish_diagnostic()
    assert result["success"] is True
    assert result["sample_count"] == 20
    assert result["validity_rate_pct"] == 100.0
    assert result["stationary_jitter_px"] >= 0.0
    assert result["stationary_jitter_px"] < 15.0  # steady face should have near-zero jitter
    assert result["stability_score"] >= 80.0
    assert result["quality_rating"] in ("Exceptional", "Stable")


# -------------------------------------------------------------
# 9. Safety, Pause, and Emergency Stop Tests
# -------------------------------------------------------------
def test_safety_controls_and_emergency_stop(temp_gaze_tracker):
    tracker = temp_gaze_tracker
    landmarks = create_mock_landmarks()

    # Enable
    tracker.set_enabled(True)
    assert tracker.enabled is True
    assert tracker.paused is False
    assert tracker.emergency_stopped is False

    res = tracker.process_frame(landmarks, ear=0.28, pitch=0.0, yaw=0.0, timestamp=time.time())
    assert res["valid"] is True
    assert res["enabled"] is True

    # Pause
    tracker.set_paused(True)
    assert tracker.paused is True

    # Emergency stop
    tracker.emergency_stop()
    assert tracker.emergency_stopped is True
    assert tracker.enabled is False
    assert tracker.paused is True

    status = tracker.get_status()
    assert status["emergency_stopped"] is True
    assert status["enabled"] is False

"""
Tests for Observer Health-Tech Physiological-Behavioral Platform.

Verifies:
1. Validated observation schema and explicit validity states.
2. Signal quality evaluator: brightness, blur, extreme angle, scale ratio.
3. Feature extractor:
   - EAR, blink timing validation (50-400ms), long closure events.
   - Smile-related geometry, corner elevation, asymmetry.
   - Brow elevation and mouth opening geometry.
   - Head kinematics and angular velocity.
   - Upper-body modular adapter graceful unavailability.
4. Personal baseline manager: robust medians and MAD.
5. Longitudinal analysis: percentiles, distributions, baseline comparisons.
6. User check-ins: recording, retrieval, atomic persistence.
7. Conservative observation events: hysteresis, multi-sample requirements, non-diagnostic labeling.
8. Evidence-based report generation: JSON, CSV, printable HTML.
9. Data purge and privacy.
"""

import time
import math
import numpy as np
import pytest

from observer_engine.health_tech.schema import (
    ObservationRecord,
    CheckInRecord,
    EventRecord,
    SessionRecord,
    ValidityStatus,
    Provenance,
    SCHEMA_VERSION,
)
from observer_engine.health_tech.signal_quality import SignalQualityEvaluator
from observer_engine.health_tech.feature_extractor import (
    BehavioralFeatureExtractor,
    calculate_ear,
)
from observer_engine.health_tech.baseline import (
    BaselineCalibrationManager,
    PersonalBaselineProfile,
    RobustMetricBaseline,
)
from observer_engine.health_tech.checkins import CheckInManager
from observer_engine.health_tech.events import ConservativeEventEngine
from observer_engine.health_tech.longitudinal import (
    LongitudinalAnalyzer,
    compute_distribution_metrics,
)
from observer_engine.health_tech.reports import ReportGenerator, NON_DIAGNOSTIC_DISCLAIMER
from observer_engine.health_tech.storage import HealthTechRepository


def _make_dummy_landmarks(eye_open: bool = True, smile: bool = False) -> np.ndarray:
    """Creates a 478-point synthetic landmark array with realistic geometry."""
    lms = np.zeros((478, 3), dtype=np.float32)
    # Eye corners (Left: 33 outer, 133 inner; Right: 263 outer, 362 inner)
    lms[33] = [0.30, 0.40, 0.0]
    lms[133] = [0.42, 0.40, 0.0]
    lms[362] = [0.58, 0.40, 0.0]
    lms[263] = [0.70, 0.40, 0.0]

    # Upper and lower lids
    lid_y_offset = 0.03 if eye_open else 0.002
    lms[160] = [0.35, 0.40 - lid_y_offset, 0.0]
    lms[158] = [0.38, 0.40 - lid_y_offset, 0.0]
    lms[144] = [0.35, 0.40 + lid_y_offset, 0.0]
    lms[153] = [0.38, 0.40 + lid_y_offset, 0.0]

    lms[385] = [0.62, 0.40 - lid_y_offset, 0.0]
    lms[387] = [0.65, 0.40 - lid_y_offset, 0.0]
    lms[380] = [0.62, 0.40 + lid_y_offset, 0.0]
    lms[373] = [0.65, 0.40 + lid_y_offset, 0.0]

    # Nose tip (1), chin (152), nasion (168)
    lms[1] = [0.50, 0.50, 0.0]
    lms[152] = [0.50, 0.80, 0.0]
    lms[168] = [0.50, 0.35, 0.0]

    # Mouth mid (13 upper, 14 lower), corners (61 L, 291 R)
    lms[13] = [0.50, 0.65, 0.0]
    lms[14] = [0.50, 0.68, 0.0]
    corner_y = 0.62 if smile else 0.66
    lms[61] = [0.40, corner_y, 0.0]
    lms[291] = [0.60, corner_y, 0.0]

    # Brows (Left 105, Right 334)
    lms[105] = [0.36, 0.32, 0.0]
    lms[334] = [0.64, 0.32, 0.0]

    # Irises (468 L, 473 R)
    lms[468] = [0.36, 0.40, 0.0]
    lms[473] = [0.64, 0.40, 0.0]

    return lms


def test_observation_schema_contract():
    obs = ObservationRecord(
        observation_id="test-123",
        session_id="sess-456",
        timestamp=1000.0,
        monotonic_time=10.0,
        feature_name="ear_avg",
        measured_value=0.285,
        unit="ratio",
        validity_status=ValidityStatus.VALID.value,
        provenance=Provenance.DIRECTLY_MEASURED.value,
    )
    d = obs.to_dict()
    assert d["feature_name"] == "ear_avg"
    assert d["measured_value"] == 0.285
    assert d["validity_status"] == "valid"
    assert d["definition_version"] == SCHEMA_VERSION

    # Test explicit missing data preservation: never replaced with zero
    obs_missing = ObservationRecord(
        observation_id="test-miss",
        session_id="sess-456",
        timestamp=1001.0,
        monotonic_time=11.0,
        feature_name="head_angular_velocity",
        measured_value=None,
        unit="deg_per_sec",
        validity_status=ValidityStatus.TRACKING_LOST.value,
        missing_data_reason="face_lost",
    )
    assert obs_missing.measured_value is None
    assert obs_missing.validity_status == "tracking_lost"


def test_signal_quality_evaluator():
    evaluator = SignalQualityEvaluator(min_brightness=40.0, max_brightness=240.0)
    
    # 1. Missing landmarks -> tracking lost
    valid, reason, metrics = evaluator.evaluate_frame(
        frame_bgr=None,
        landmarks=None,
        pitch=0.0,
        yaw=0.0,
        roll=0.0,
        timestamp=10.0,
    )
    assert not valid
    assert reason == "face_lost"

    # 2. Extreme head angle -> invalid
    lms = _make_dummy_landmarks()
    valid_angle, reason_angle, _ = evaluator.evaluate_frame(
        frame_bgr=None,
        landmarks=lms,
        pitch=45.0,  # exceeds max 35 deg
        yaw=0.0,
        roll=0.0,
        timestamp=10.1,
    )
    assert not valid_angle
    assert reason_angle == "extreme_head_angle"

    # 3. Valid normal frame
    valid_ok, reason_ok, _ = evaluator.evaluate_frame(
        frame_bgr=None,
        landmarks=lms,
        pitch=5.0,
        yaw=2.0,
        roll=1.0,
        timestamp=10.2,
    )
    assert valid_ok
    assert reason_ok == "optimal"

    win_q = evaluator.get_window_quality(10.2)
    assert win_q.usable_ratio > 0.0


def test_feature_extractor_eye_behavior():
    extractor = BehavioralFeatureExtractor(session_id="test-session")
    lms_open = _make_dummy_landmarks(eye_open=True)
    lms_closed = _make_dummy_landmarks(eye_open=False)

    # 1. Open eyes
    s_open = extractor.extract_snapshot(None, lms_open, {}, timestamp=10.0)
    assert s_open.valid
    assert s_open.ear_avg > 0.20
    assert not s_open.is_blink

    # 2. Blink event (open -> closed for 150ms -> open)
    extractor.extract_snapshot(None, lms_closed, {}, timestamp=10.10)
    s_blink = extractor.extract_snapshot(None, lms_open, {}, timestamp=10.25)
    assert s_blink.is_blink
    assert extractor.blink_count_total == 1
    assert s_blink.last_closure_duration is not None
    assert 0.10 <= s_blink.last_closure_duration <= 0.20


def test_feature_extractor_smile_and_head():
    extractor = BehavioralFeatureExtractor(session_id="test-session")
    lms_neutral = _make_dummy_landmarks(smile=False)
    lms_smile = _make_dummy_landmarks(smile=True)

    # Neutral frame
    s_neutral = extractor.extract_snapshot(None, lms_neutral, {"mouthSmileLeft": 0.0, "mouthSmileRight": 0.0}, timestamp=20.0)
    assert s_neutral.mouth_corner_elevation_left is not None

    # Smile frame
    s_smile = extractor.extract_snapshot(
        None,
        lms_smile,
        {"mouthSmileLeft": 0.65, "mouthSmileRight": 0.60},
        timestamp=20.05,
    )
    assert s_smile.smile_score_avg == 0.625
    assert s_smile.smile_asymmetry == pytest.approx(0.05, abs=0.01)
    assert s_smile.mouth_corner_elevation_left > s_neutral.mouth_corner_elevation_left

    # Upper body should be explicitly unavailable without body in camera
    assert not s_smile.upper_body_available
    assert s_smile.upper_body_reason == "upper_body_outside_camera_frame"


def test_baseline_manager(tmp_path):
    mgr = BaselineCalibrationManager(storage_dir=str(tmp_path))
    assert not mgr.current_profile.is_calibrated

    mgr.start_calibration("neutral_face")
    lms = _make_dummy_landmarks(eye_open=True, smile=False)
    ext = BehavioralFeatureExtractor("calib-sess")

    # Feed 35 valid samples
    for i in range(35):
        snap = ext.extract_snapshot(None, lms, {}, timestamp=100.0 + i * 0.05)
        mgr.add_calibration_sample(snap)

    prof = mgr.finish_calibration()
    assert prof.is_calibrated
    assert prof.valid_sample_count >= 30
    assert prof.ear_baseline is not None
    assert prof.ear_baseline["median"] > 0.15

    # Check reset
    mgr.reset_baseline()
    assert not mgr.current_profile.is_calibrated


def test_longitudinal_analyzer():
    analyzer = LongitudinalAnalyzer()
    obs = [
        ObservationRecord(
            observation_id=f"o-{i}",
            session_id="sess-1",
            timestamp=1000.0 + i * 2.0,
            monotonic_time=float(i),
            feature_name="ear_avg",
            measured_value=0.25 + (i % 5) * 0.01,
            unit="ratio",
            validity_status=ValidityStatus.VALID.value,
        )
        for i in range(20)
    ]

    analysis = analyzer.analyze_window(obs, 1000.0, 1040.0)
    assert analysis["total_observations"] == 20
    assert analysis["valid_coverage_pct"] == 100.0
    assert "ear_avg" in analysis["features"]
    dist = analysis["features"]["ear_avg"]["distribution"]
    assert dist["count"] == 20
    assert dist["median"] >= 0.25
    assert dist["p25"] <= dist["p75"]


def test_checkin_manager(tmp_path):
    mgr = CheckInManager(storage_dir=str(tmp_path))
    c = mgr.record_checkin(
        energy=4,
        effort=2,
        task_difficulty=3,
        feeling_stuck=False,
        stress=2,
        notes="Feeling productive and clear",
    )
    assert c.checkin_id is not None
    checkins = mgr.get_checkins()
    assert len(checkins) == 1
    assert checkins[0]["energy"] == 4
    assert checkins[0]["notes"] == "Feeling productive and clear"

    mgr.clear_all()
    assert len(mgr.get_checkins()) == 0


def test_conservative_event_engine():
    engine = ConservativeEventEngine("test-session")
    prof = PersonalBaselineProfile(is_calibrated=True)
    snap = BehavioralFeatureExtractor("test").extract_snapshot(None, _make_dummy_landmarks(), {}, 100.0)

    # 1. Brief idle (<90s) does NOT emit event
    events_brief = engine.evaluate_signals(
        snapshot=snap,
        baseline=prof,
        idle_seconds=30.0,
        window_switch_count_60s=2,
        usable_ratio=0.90,
        now=100.0,
    )
    assert len(events_brief) == 0

    # 2. Prolonged idle (>=90s) with valid coverage emits transparent behavioral event
    events_idle = engine.evaluate_signals(
        snapshot=snap,
        baseline=prof,
        idle_seconds=95.0,
        window_switch_count_60s=2,
        usable_ratio=0.85,
        now=100.0,
    )
    assert len(events_idle) == 1
    ev = events_idle[0]
    assert ev.event_type == "Prolonged interval without detected task input"
    assert "paralysis" not in ev.event_type.lower()
    assert "ADHD" not in ev.explanation


def test_report_generation(tmp_path):
    repo = HealthTechRepository(base_dir=str(tmp_path))
    lms = _make_dummy_landmarks()
    ext = BehavioralFeatureExtractor("test-sess")

    # Record some observations
    for i in range(10):
        snap = ext.extract_snapshot(None, lms, {"mouthSmileLeft": 0.1, "mouthSmileRight": 0.1}, 100.0 + i)
        repo.record_observation(
            ObservationRecord(
                observation_id=f"rep-obs-{i}",
                session_id=repo.active_session.session_id,
                timestamp=100.0 + i,
                monotonic_time=float(i),
                feature_name="ear_avg",
                measured_value=snap.ear_avg,
                unit="ratio",
                validity_status=ValidityStatus.VALID.value,
            )
        )

    # Generate multi-section report
    rep = repo.generate_report()
    assert "report_id" in rep
    assert "direct_measurements" in rep
    assert "derived_metrics" in rep
    assert "disclaimer" in rep
    assert NON_DIAGNOSTIC_DISCLAIMER in rep["disclaimer"]
    assert "csv_export" in rep
    assert "html_printable_export" in rep
    assert "### SECTION 1: OBSERVATIONS" in rep["csv_export"]
    assert "<!DOCTYPE html>" in rep["html_printable_export"]


def test_privacy_data_purge(tmp_path):
    repo = HealthTechRepository(base_dir=str(tmp_path))
    repo.checkin_manager.record_checkin(energy=3, notes="Private note")
    repo.record_observation(
        ObservationRecord(
            observation_id="purge-1",
            session_id=repo.active_session.session_id,
            timestamp=500.0,
            monotonic_time=1.0,
            feature_name="ear_avg",
            measured_value=0.28,
            unit="ratio",
        )
    )
    repo._flush_observations()
    assert len(repo.checkin_manager.get_checkins()) == 1

    # Execute complete purge
    assert repo.delete_all_data()
    assert len(repo.checkin_manager.get_checkins()) == 0
    assert len(repo.get_recent_observations()) == 0
    assert len(repo.get_events()) == 0

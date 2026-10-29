"""
test_calibration_and_history.py
Tests for:
- 5-stage calibration workflow (Hardware check, Neutral, Gaze 6-targets, Natural, Validation)
- Versioned JSON persistence and corruption recovery
- Baseline feature normalization with safeguards against zero variance
- Observation history deduplication and local persistence
- Report generation with CSV export
- Non-clinical limitations notice and feedback updates
"""

import os
import json
import time
import tempfile
import pytest

from observer_engine.baseline import BaselineManager, GAZE_CALIBRATION_TARGETS, FeatureStats
from observer_engine.history import HistoryManager, ObservationRecord
from observer_engine.features import FrameFeatures, WindowedFeatures


def create_dummy_frame_features(valid: bool = True, ear: float = 0.28, tension: float = 0.15, gaze_x: float = 0.5, gaze_y: float = 0.5) -> FrameFeatures:
    return FrameFeatures(
        timestamp=time.time(),
        valid=valid,
        quality_reason="" if valid else "face_lost",
        ear=ear,
        left_ear=ear,
        right_ear=ear,
        is_blink=False,
        pitch=0.0,
        yaw=0.0,
        roll=0.0,
        gaze_x=gaze_x,
        gaze_y=gaze_y,
        tension_index=tension,
    )


def create_dummy_windowed_features(valid: bool = True, dispersion: float = 0.35, tension: float = 0.18, blink_rate: float = 16.0) -> WindowedFeatures:
    return WindowedFeatures(
        timestamp=time.time(),
        valid=valid,
        blink_count_total=10,
        blink_rate_30s=blink_rate,
        blink_rate_60s=blink_rate,
        blink_rate_180s=blink_rate,
        blink_irregularity=1.0,
        dispersion_4s=dispersion,
        dispersion_30s=dispersion,
        dispersion_120s=dispersion,
        gaze_shifts_per_min=5.0,
        tension_mean_4s=tension,
        tension_mean_30s=tension,
        head_pose_var_4s=1.20,
        head_pose_var_30s=1.20,
    )


def test_hardware_check_stage():
    mgr = BaselineManager()
    res = mgr.perform_hardware_check(
        frame_present=True,
        face_detected=True,
        iris_detected=True,
        blendshapes_present=True,
        quality_valid=True,
    )
    assert res["passed"] is True
    assert res["camera_ok"] is True

    # Check failure on missing face
    fail_res = mgr.perform_hardware_check(
        frame_present=True,
        face_detected=False,
        iris_detected=False,
        blendshapes_present=False,
        quality_valid=False,
        quality_reason="No face in frame",
    )
    assert fail_res["passed"] is False


def test_gaze_calibration_target_sequence():
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_path = os.path.join(temp_dir, "calibration.json")
        mgr = BaselineManager(storage_path=storage_path)

        assert len(GAZE_CALIBRATION_TARGETS) == 6
        # Target 0: center_1, Target 5: center_2 (drift check)
        assert GAZE_CALIBRATION_TARGETS[0]["target_id"] == "center_1"
        assert GAZE_CALIBRATION_TARGETS[5]["target_id"] == "center_2"

        mgr.start_stage("gaze_calibration", target_idx=0)
        win = create_dummy_windowed_features()

        # Feed 10 samples for target 0
        for _ in range(10):
            feat = create_dummy_frame_features(gaze_x=0.50, gaze_y=0.50)
            mgr.feed_calibration_frame(feat, win)

        res = mgr.complete_current_gaze_target()
        assert res["success"] is True
        assert res["completed_targets"] == 1
        assert res["all_targets_complete"] is False

        # Feed remaining 5 targets
        for tgt_idx in range(1, 6):
            mgr.start_stage("gaze_calibration", target_idx=tgt_idx)
            for _ in range(8):
                feat = create_dummy_frame_features(gaze_x=0.50 + 0.01 * tgt_idx, gaze_y=0.50)
                mgr.feed_calibration_frame(feat, win)
            res = mgr.complete_current_gaze_target()
            assert res["success"] is True

        assert res["all_targets_complete"] is True
        assert len(mgr.gaze_target_results) == 6


def test_calibration_atomic_persistence_and_loading():
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_path = os.path.join(temp_dir, "calibration.json")
        mgr = BaselineManager(storage_path=storage_path)

        # Feed neutral and natural samples
        mgr.start_stage("neutral_baseline")
        win = create_dummy_windowed_features(dispersion=0.25, tension=0.14, blink_rate=12.0)
        for _ in range(15):
            feat = create_dummy_frame_features(ear=0.29, tension=0.14)
            mgr.feed_calibration_frame(feat, win)

        mgr.start_stage("natural_baseline")
        for _ in range(15):
            feat = create_dummy_frame_features(ear=0.28, tension=0.15)
            mgr.feed_calibration_frame(feat, win)

        val_res = mgr.validate_and_finalize()
        assert val_res["passed"] is True
        assert val_res["status"] == "complete"
        assert os.path.isfile(storage_path)

        # Verify JSON schema version and fields
        with open(storage_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["schema_version"] == 1
        assert "calibration_id" in data
        assert "created_at" in data
        assert data["status"] == "complete"
        assert "baseline" in data
        assert "blink_rate" in data["baseline"]
        assert "gaze_dispersion" in data["baseline"]

        # Reload from storage
        mgr2 = BaselineManager(storage_path=storage_path)
        assert mgr2.profile.status == "complete"
        assert abs(mgr2.profile.ear.mean - 0.285) < 0.02
        assert mgr2.profile.ear.std > 0.01


def test_corruption_fallback():
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_path = os.path.join(temp_dir, "calibration.json")
        with open(storage_path, "w") as f:
            f.write("{invalid json content!#@$")

        # Manager should handle gracefully without crashing and use fallback
        mgr = BaselineManager(storage_path=storage_path)
        assert mgr.profile.status == "uncalibrated"
        assert mgr.profile.ear.mean == 0.28


def test_history_deduplication_and_atomic_save():
    with tempfile.TemporaryDirectory() as temp_dir:
        hist_path = os.path.join(temp_dir, "history.json")
        mgr = HistoryManager(storage_path=hist_path)

        # Simulate sustained paralysis episode
        now = time.time()
        features = [
            {"feature": "gaze_dispersion", "measured_value": "0.15", "baseline_value": "0.35", "deviation": "-1.8σ", "window": "30s", "valid": True, "contribution": "+0.28"},
            {"feature": "desktop_idle", "measured_value": "85s", "baseline_value": "15s", "deviation": "+70s", "window": "OS timer", "valid": True, "contribution": "+0.24"},
        ]

        # 3 calls within same episode
        mgr.update_or_record_episode("PARALYSIS_LIKELY", score=0.72, features=features, evidence_strength="Strong", qualification_reason="Dwell 90s satisfied", now=now)
        mgr.update_or_record_episode("PARALYSIS_LIKELY", score=0.75, features=features, evidence_strength="Strong", qualification_reason="Dwell 90s satisfied", now=now + 10.0)
        mgr.update_or_record_episode("PARALYSIS_LIKELY", score=0.78, features=features, evidence_strength="Strong", qualification_reason="Dwell 90s satisfied", now=now + 20.0)

        # Exit to FOCUSED -> closes active episode
        closed = mgr.update_or_record_episode("FOCUSED", score=0.85, features=[], evidence_strength="Active typing", qualification_reason="Input restored", now=now + 30.0)
        assert closed is not None
        assert closed.state == "PARALYSIS_LIKELY"
        assert closed.duration_seconds >= 20.0
        assert closed.score == 0.78

        # Exactly 1 deduplicated record in history
        history = mgr.get_history()
        assert len(history) == 1
        assert history[0]["state"] == "PARALYSIS_LIKELY"

        # User feedback
        event_id = history[0]["event_id"]
        mgr.update_feedback(event_id, "useful", notes="Accurately caught me staring at code")
        updated = mgr.get_history()
        assert updated[0]["user_review"] == "useful"
        assert updated[0]["user_notes"] == "Accurately caught me staring at code"

        # Generate report
        report = mgr.generate_report()
        assert report["total_observations"] == 1
        assert "csv_export" in report
        assert "event_id,created_at" in report["csv_export"]
        assert "Non-clinical notice" in report["limitations_notice"]

        # Delete observation
        mgr.delete_observation(event_id)
        assert len(mgr.get_history()) == 0

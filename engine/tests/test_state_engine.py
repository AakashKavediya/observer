"""
test_state_engine.py
Pytest suite for Milestone 3:
- Baseline calibration z-scoring and persistence
- State engine evidence formulas
- CRITICAL TEST: 'Fixation alone NEVER triggers paralysis'
- Hysteresis and dwell time enforcement
- Feedback sensitivity adaptation
"""

import os
import tempfile
import time
import pytest

from observer_engine.baseline import BaselineManager, FeatureStats, BaselineProfile
from observer_engine.features import WindowedFeatures, FrameFeatures
from observer_engine.state_engine import StateEngine
from observer_engine.config import StateEngineConfig


def create_dummy_windowed(
    dispersion: float = 0.35,
    tension: float = 0.15,
    blink_rate: float = 16.0,
    head_var: float = 1.0,
    valid: bool = True,
) -> WindowedFeatures:
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
        head_pose_var_4s=head_var,
        head_pose_var_30s=head_var,
    )


def create_dummy_frame(valid: bool = True) -> FrameFeatures:
    return FrameFeatures(
        timestamp=time.time(),
        valid=valid,
        ear=0.28,
        left_ear=0.28,
        right_ear=0.28,
        gaze_x=0.5,
        gaze_y=0.5,
    )


def test_baseline_zscoring_and_reset():
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_path = os.path.join(temp_dir, "baseline.json")
        mgr = BaselineManager(storage_path=storage_path)

        # Baseline initially defaults
        assert mgr.profile.ear.mean == 0.28
        assert mgr.profile.ear.z_score(0.28) == 0.0

        # Feed calibration samples
        mgr.start_calibration(duration_seconds=0.5)
        win = create_dummy_windowed(dispersion=0.25, tension=0.12, blink_rate=14.0)

        last_pct = 0.0
        for i in range(15):
            p = mgr.update_calibration(win, ear=0.28)
            if p is not None:
                last_pct = p
            time.sleep(0.05)

        assert last_pct == 100.0
        assert os.path.isfile(storage_path)

        # Test reset
        mgr.reset()
        assert not os.path.isfile(storage_path)


def test_fixation_alone_never_triggers_paralysis():
    """
    CRITICAL ETHICAL RULE:
    Staring at a single spot (e.g. reading or casually watching a video)
    must NEVER trigger paralysis if tension is low or user is typing.
    """
    engine = StateEngine()
    baseline = BaselineProfile(
        created_at=0.0,
        updated_at=0.0,
        samples_count=100,
        ear=FeatureStats(mean=0.28, std=0.04),
        blink_rate=FeatureStats(mean=16.0, std=5.0),
        dispersion=FeatureStats(mean=0.35, std=0.08),
        tension=FeatureStats(mean=0.18, std=0.05),
        head_variance=FeatureStats(mean=1.20, std=0.50),
    )

    frame = create_dummy_frame()

    # Extreme gaze fixation: dispersion near 0.0 (user stares at cursor)
    # BUT tension is low (relaxed musculature)
    win_relaxed_stare = create_dummy_windowed(
        dispersion=0.01,   # 100% fixated!
        tension=0.12,      # Relaxed brow and jaw
        blink_rate=14.0,   # Normal breathing/blinking
        head_var=0.5,
    )

    # Even after 120 seconds of staring at one spot:
    now = 1000.0
    for i in range(120):
        t = now + i
        res = engine.compute_state(
            features=win_relaxed_stare,
            frame_feat=frame,
            baseline=baseline,
            idle_seconds=20.0,
            window_switch_count=0,
            now=t,
        )

    # Must NOT be paralysis!
    assert res.state != "PARALYSIS_LIKELY"
    assert res.state in ("FOCUSED", "RELAXED")
    assert res.probabilities.paralysis < 0.60


def test_paralysis_requires_sustained_dwell_and_tension():
    """
    Paralysis requires fixation + elevated facial tension + input idle,
    and MUST sustain for at least 90s (min_dwell_seconds).
    """
    cfg = StateEngineConfig(min_dwell_seconds=90.0, enter_threshold=0.65)
    engine = StateEngine(config=cfg)
    baseline = BaselineProfile(
        created_at=0.0,
        updated_at=0.0,
        samples_count=100,
        ear=FeatureStats(mean=0.28, std=0.04),
        blink_rate=FeatureStats(mean=16.0, std=5.0),
        dispersion=FeatureStats(mean=0.35, std=0.08),
        tension=FeatureStats(mean=0.15, std=0.05),
        head_variance=FeatureStats(mean=1.20, std=0.50),
    )

    frame = create_dummy_frame()
    # High freeze evidence: fixation + high tension + depressed blinking + frozen posture
    win_freeze = create_dummy_windowed(
        dispersion=0.05,  # Gaze lock
        tension=0.55,     # Tense brow furrow and jaw
        blink_rate=3.0,   # Depressed blink rate
        head_var=0.02,    # Rigid posture
    )

    # Dwell second 0 to 60 (sustained for ~50s after crossing 0.65 threshold - below 90s dwell threshold):
    now = 1000.0
    for i in range(60):
        t = now + i
        res = engine.compute_state(
            features=win_freeze,
            frame_feat=frame,
            baseline=baseline,
            idle_seconds=45.0,
            window_switch_count=0,
            now=t,
        )

    # At 60s, paralysis should NOT yet be declared (dwell gate protecting false positive)
    assert res.state != "PARALYSIS_LIKELY"

    # Sustain past 105 seconds (dwell duration exceeds 90s):
    for i in range(60, 110):
        t = now + i
        res = engine.compute_state(
            features=win_freeze,
            frame_feat=frame,
            baseline=baseline,
            idle_seconds=45.0,
            window_switch_count=0,
            now=t,
        )

    # Now dwell time (>= 90s) is satisfied and state transitions to PARALYSIS_LIKELY!
    assert res.state == "PARALYSIS_LIKELY"


def test_hysteresis_exit():
    """
    Once in paralysis, easing evidence slightly (e.g. to 0.55) maintains state,
    while dropping below exit_threshold (0.45) exits cleanly.
    """
    cfg = StateEngineConfig(min_dwell_seconds=10.0, enter_threshold=0.65, exit_threshold=0.45)
    engine = StateEngine(config=cfg)
    baseline = BaselineProfile(
        created_at=0.0,
        updated_at=0.0,
        samples_count=100,
        ear=FeatureStats(mean=0.28, std=0.04),
        blink_rate=FeatureStats(mean=16.0, std=5.0),
        dispersion=FeatureStats(mean=0.35, std=0.08),
        tension=FeatureStats(mean=0.15, std=0.05),
        head_variance=FeatureStats(mean=1.20, std=0.50),
    )

    frame = create_dummy_frame()
    win_freeze = create_dummy_windowed(dispersion=0.05, tension=0.55, blink_rate=3.0, head_var=0.02)

    # Enter paralysis
    now = 100.0
    for i in range(20):
        res = engine.compute_state(win_freeze, frame, baseline, idle_seconds=45.0, window_switch_count=0, now=now + i)

    assert res.state == "PARALYSIS_LIKELY"

    # Moderate easing: tension drops to moderate, input pauses drop slightly (evidence ~ 0.55 > 0.45)
    win_mid = create_dummy_windowed(dispersion=0.20, tension=0.30, blink_rate=10.0, head_var=0.5)
    res_mid = engine.compute_state(win_mid, frame, baseline, idle_seconds=18.0, window_switch_count=0, now=now + 25)
    assert res_mid.state == "PARALYSIS_LIKELY"  # Hysteresis prevents flickering

    # Full release: user types (idle = 1.0s, low tension)
    win_relaxed = create_dummy_windowed(dispersion=0.35, tension=0.10, blink_rate=16.0, head_var=1.2)
    for i in range(15):
        res_exit = engine.compute_state(win_relaxed, frame, baseline, idle_seconds=1.0, window_switch_count=1, now=now + 30 + i)

    assert res_exit.state in ("FOCUSED", "RELAXED")

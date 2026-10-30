"""
Tests for MotionQ Assistive Control System Integration in Observer
Tests all components: DwellEngine, MotionQEyeController, HeadTiltScroller,
ProfileManager, WordPredictor, VoiceCommandDispatcher, and end-to-end integration.
"""

import os
import json
import time
import math
import tempfile
import pytest
import numpy as np

from observer_engine.motionq.dwell_engine import DwellEngine, DwellTarget
from observer_engine.motionq.motionq_eye import MotionQEyeController
from observer_engine.motionq.head_scroll import HeadTiltScroller
from observer_engine.motionq.word_prediction import WordPredictor
from observer_engine.motionq.voice_commands import VoiceCommandDispatcher
from observer_engine.motionq import profile_manager
from observer_engine.gaze_mouse import GazeMouseTracker


# Helper to create synthetic 478 MediaPipe landmarks
def create_synthetic_landmarks(
    iris_x: float = 0.50,
    iris_y: float = 0.50,
    nose_y: float = 0.50,
    inter_eye_dist: float = 0.20,
) -> np.ndarray:
    lm = np.zeros((478, 3), dtype=np.float32)

    # Eyes: landmark 33 (right) and 263 (left)
    lm[33, 0] = 0.50 - inter_eye_dist / 2.0
    lm[33, 1] = 0.40
    lm[263, 0] = 0.50 + inter_eye_dist / 2.0
    lm[263, 1] = 0.40

    # Nose: 1 and 168
    lm[1, 0] = 0.50
    lm[1, 1] = nose_y
    lm[168, 0] = 0.50
    lm[168, 1] = 0.40

    # Iris perimeter landmarks
    # Left: 474, 475, 476, 477
    for idx in [474, 475, 476, 477]:
        lm[idx, 0] = iris_x
        lm[idx, 1] = iris_y

    # Right: 469, 470, 471, 472
    for idx in [469, 470, 471, 472]:
        lm[idx, 0] = iris_x
        lm[idx, 1] = iris_y

    return lm


# =====================================================================
# 1. Dwell Engine Tests
# =====================================================================

def test_dwell_target_geometry_and_priority():
    engine = DwellEngine()
    t1 = engine.register_target(100, 100, 200, 100, target_id="t1", name="Target 1")
    t2 = engine.register_target(150, 120, 200, 100, target_id="t2", name="Target 2")

    assert t1.contains(120, 150)
    assert not t1.contains(50, 50)
    assert t1.center() == (200.0, 150.0)

    # Overlapping point: (180, 140) is in both t1 and t2
    # Last registered target (t2) MUST have highest priority
    resolved = engine.get_target_at(180, 140)
    assert resolved is not None
    assert resolved.target_id == "t2"


def test_dwell_progress_and_single_activation():
    engine = DwellEngine(default_duration_ms=500, stability_radius=30)
    fired_count = 0

    def on_click():
        nonlocal fired_count
        fired_count += 1

    engine.register_target(100, 100, 100, 100, target_id="btn", callback=on_click)

    # Frame 1: Enter target
    res1 = engine.update(150, 150, timestamp=10.0)
    assert res1["progress"] == 0.0
    assert not res1["fired"]
    assert fired_count == 0

    # Frame 2: Mid-dwell (250ms elapsed)
    res2 = engine.update(152, 151, timestamp=10.25)
    assert 0.45 <= res2["progress"] <= 0.55
    assert not res2["fired"]
    assert fired_count == 0

    # Frame 3: Completion (500ms elapsed)
    res3 = engine.update(151, 150, timestamp=10.50)
    assert res3["progress"] == 1.0
    assert res3["fired"]
    assert fired_count == 1

    # Frame 4: Staying inside target MUST NOT re-fire (single activation guarantee)
    res4 = engine.update(150, 150, timestamp=10.75)
    assert res4["progress"] == 1.0
    assert not res4["fired"]
    assert fired_count == 1

    # Frame 5: Leaving target resets dwell
    res5 = engine.update(500, 500, timestamp=11.0)
    assert res5["progress"] == 0.0
    assert res5["active_target"] is None

    # Frame 6: Re-entering target starts new dwell
    res6 = engine.update(150, 150, timestamp=11.10)
    assert res6["progress"] == 0.0


def test_dwell_stability_radius_reset():
    engine = DwellEngine(default_duration_ms=1000, stability_radius=20)
    engine.register_target(0, 0, 500, 500, target_id="big_btn")

    # Start dwell at (100, 100)
    engine.update(100, 100, timestamp=1.0)
    res = engine.update(105, 105, timestamp=1.5)
    assert res["progress"] > 0.0

    # Sudden jump > 20px (within target, but moving too fast)
    res_jump = engine.update(160, 160, timestamp=1.6)
    # Dwell timer must restart
    assert res_jump["progress"] == 0.0


def test_dwell_click_mode_general_screen():
    engine = DwellEngine(default_duration_ms=400, stability_radius=30, click_cooldown_sec=0.5)
    clicks = []

    def on_click(x, y, is_double):
        clicks.append((x, y, is_double))

    engine.set_click_dispatcher(on_click)

    # Click mode OFF: no dwell on empty screen
    res = engine.update(400, 300, timestamp=1.0)
    assert res["click_mode"] is None
    assert res["progress"] == 0.0

    # Arm Single Click mode
    engine.set_click_mode("single")
    assert engine.get_click_mode() == "single"

    # Start dwelling at (400, 300)
    engine.update(400, 300, timestamp=2.0)
    res_mid = engine.update(402, 301, timestamp=2.2)
    assert 0.45 <= res_mid["progress"] <= 0.55

    # Complete dwell
    res_done = engine.update(401, 300, timestamp=2.4)
    assert res_done["fired"]
    assert res_done["action"] == "single_click"
    assert len(clicks) == 1
    assert clicks[0] == (401, 300, False)

    # Cooldown enforcement: subsequent frame immediately after must not fire
    res_cooldown = engine.update(401, 300, timestamp=2.5)
    assert res_cooldown["progress"] == 0.0
    assert len(clicks) == 1


# =====================================================================
# 2. MotionQ Eye Controller Tests
# =====================================================================

def test_eye_controller_iris_extraction_and_mapping():
    controller = MotionQEyeController(screen_w=1920, screen_h=1080, sensitivity=3.0)

    # Missing landmarks -> invalid, holds position
    res_none = controller.process_frame(None)
    assert not res_none["valid"]
    assert res_none["cursor_x"] == 960.0
    assert res_none["cursor_y"] == 540.0

    # Looking dead center (0.50, 0.50)
    lm_center = create_synthetic_landmarks(0.50, 0.50)
    res_center = controller.process_frame(lm_center)
    assert res_center["valid"]
    assert math.isclose(res_center["norm_x"], 0.50, abs_tol=0.05)
    assert math.isclose(res_center["norm_y"], 0.50, abs_tol=0.05)

    # Looking right (iris_x = 0.55 -> offset_x > 0 -> screen_x > 960)
    lm_right = create_synthetic_landmarks(0.55, 0.50)
    res_right = controller.process_frame(lm_right)
    assert res_right["cursor_x"] > 960.0


def test_eye_controller_5point_calibration_fit():
    controller = MotionQEyeController(screen_w=1920, screen_h=1080)

    calibration_points = [
        {"iris": [0.50, 0.50], "screen": [0.50, 0.50]},
        {"iris": [0.45, 0.45], "screen": [0.20, 0.20]},
        {"iris": [0.55, 0.45], "screen": [0.80, 0.20]},
        {"iris": [0.45, 0.55], "screen": [0.20, 0.80]},
        {"iris": [0.55, 0.55], "screen": [0.80, 0.80]},
    ]

    fit_ok = controller.set_calibration(calibration_points)
    assert fit_ok
    assert controller._affine_transform is not None

    # Predict center
    cx, cy = controller._iris_to_screen(0.50, 0.50)
    assert math.isclose(cx, 960.0, abs_tol=20.0)
    assert math.isclose(cy, 540.0, abs_tol=20.0)


def test_eye_controller_magnet_and_proximity():
    dwell = DwellEngine()
    # Register target centered at (1000, 500) with size 100x100
    dwell.register_target(950, 450, 100, 100, target_id="target_magnet")

    controller = MotionQEyeController(
        dwell_engine=dwell,
        screen_w=1920,
        screen_h=1080,
        magnet_radius=40.0,
        proximity_radius=80.0,
        magnet_force=0.50,
        smoothing_factor=0.0,  # 0.0 factor to test instantaneous magnet deflection
    )

    # Put cursor at (1020, 510) - distance to center (1000, 500) is ~22.3px (< magnet_radius 40px)
    # Without magnet, iris would map to ~1020, 510
    # Center target is at (1000, 500)
    target_center = (1000.0, 500.0)

    # Mock _iris_to_screen to return (1020, 510)
    controller._iris_to_screen = lambda ix, iy: (1020.0, 510.0)

    lm = create_synthetic_landmarks(0.50, 0.50)
    res = controller.process_frame(lm)

    assert res["magnet_active"]
    # Cursor should be pulled 50% toward (1000, 500): 1020 + (1000 - 1020)*0.5 = 1010
    assert math.isclose(res["cursor_x"], 1010.0, abs_tol=1.0)
    assert math.isclose(res["cursor_y"], 505.0, abs_tol=1.0)


# =====================================================================
# 3. Head Tilt Scroller Tests
# =====================================================================

def test_head_tilt_scroller_consecutive_frames_and_neutral():
    scrolls = []
    scroller = HeadTiltScroller(
        neutral_y=240.0,
        tilt_threshold=20.0,
        scroll_amount=3,
        tilt_frame_threshold=3,
        enabled=True,
    )
    scroller.set_scroll_dispatcher(lambda delta: scrolls.append(delta))

    # Neutral position (nose_y = 240 / 480 = 0.50)
    lm_neutral = create_synthetic_landmarks(nose_y=0.50)
    res_neut = scroller.process_landmarks(lm_neutral, frame_h=480.0)
    assert not res_neut["active"]
    assert res_neut["direction"] == "neutral"

    # Tilt DOWN: nose_y = 300 / 480 = 0.625 (dy = 300 - 240 = +60 > 20)
    lm_down = create_synthetic_landmarks(nose_y=0.625)

    # Frame 1: accumulator = 1, no scroll yet
    r1 = scroller.process_landmarks(lm_down, frame_h=480.0)
    assert r1["frames_accumulated"] == 1
    assert not r1["scrolled"]
    assert len(scrolls) == 0

    # Frame 2: accumulator = 2, no scroll yet
    r2 = scroller.process_landmarks(lm_down, frame_h=480.0)
    assert r2["frames_accumulated"] == 2
    assert not r2["scrolled"]

    # Frame 3: threshold 3 reached -> scroll down (-3 lines)
    r3 = scroller.process_landmarks(lm_down, frame_h=480.0)
    assert r3["scrolled"]
    assert r3["delta_lines"] == -3
    assert len(scrolls) == 1
    assert scrolls[0] == -3
    # Counter must reset to prevent continuous runaway scrolling
    assert r3["frames_accumulated"] == 0

    # Returning to neutral clears accumulator immediately
    scroller.process_landmarks(lm_neutral, frame_h=480.0)
    assert scroller._tilt_frame_count == 0
    assert scroller._last_direction is None


# =====================================================================
# 4. Profile Manager Tests
# =====================================================================

def test_profile_manager_crud_and_healing():
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_manager.set_profiles_dir(tmpdir)

        # 1. Default profile auto-created
        default_prof = profile_manager.load_profile("default")
        assert default_prof["name"] == "default"
        assert default_prof["dwell"]["duration_ms"] == 1000
        assert default_prof["head"]["tilt_threshold"] == 20.0

        # 2. Create and list profiles
        ok = profile_manager.create_profile("user_alex")
        assert ok
        profs = profile_manager.list_profiles()
        assert "default" in profs
        assert "user_alex" in profs

        # 3. Update profile
        updated = profile_manager.update_profile("user_alex", {
            "language": "HI",
            "dwell": {"duration_ms": 750},
        })
        assert updated["language"] == "HI"
        assert updated["dwell"]["duration_ms"] == 750

        # 4. Corrupted file auto-healed
        alex_path = os.path.join(tmpdir, "user_alex.json")
        with open(alex_path, "w", encoding="utf-8") as f:
            f.write("corrupted json merge conflict <<<< === >>>>")

        healed = profile_manager.load_profile("user_alex")
        assert healed["name"] == "user_alex"
        assert healed["dwell"]["duration_ms"] == 1000

        # 5. Delete profile
        del_ok = profile_manager.delete_profile("user_alex")
        assert del_ok
        assert "user_alex" not in profile_manager.list_profiles()


# =====================================================================
# 5. Word Predictor Tests
# =====================================================================

def test_word_predictor_multilingual():
    predictor = WordPredictor()

    # English predictions
    preds_en = predictor.predict("th", language="EN", limit=3)
    assert len(preds_en) > 0
    for w in preds_en:
        assert w.startswith("th")

    # Hindi prediction for 'क' (e.g. कर, करना, क्या)
    preds_hi = predictor.predict("क", language="HI", limit=3)
    assert len(preds_hi) > 0

    # Marathi prediction for 'म' (e.g. मी, माझे, मला)
    preds_mr = predictor.predict("म", language="MR", limit=3)
    assert len(preds_mr) > 0


# =====================================================================
# 6. Voice Commands Dispatcher Tests
# =====================================================================

def test_voice_command_matching_and_deduplication():
    dispatcher = VoiceCommandDispatcher(cooldown_seconds=1.0)
    executed = []

    dispatcher.register_handler("click", lambda: executed.append("click"))
    dispatcher.register_handler("emergency stop", lambda: executed.append("stop"))

    # 1. Match canonical and alias
    res_click = dispatcher.process_transcript("please click now", timestamp=10.0)
    # The utterance "please click now" doesn't start/end with click token, test exact alias
    res_click_direct = dispatcher.process_transcript("click", timestamp=10.0)
    assert res_click_direct is not None
    assert res_click_direct["command"] == "click"
    assert "click" in executed

    # 2. Cooldown deduplication (same command within 1s is suppressed)
    res_dup = dispatcher.process_transcript("click", timestamp=10.5)
    assert res_dup is None
    assert len(executed) == 1

    # 3. Emergency stop (different command, allowed immediately)
    res_stop = dispatcher.process_transcript("emergency stop", timestamp=10.6)
    assert res_stop is not None
    assert "stop" in executed

    # 4. Non-command rejected
    res_chat = dispatcher.process_transcript("what is the weather today", timestamp=12.0)
    assert res_chat is None


# =====================================================================
# 7. End-to-End GazeMouseTracker MotionQ Integration Tests
# =====================================================================

def test_gaze_mouse_tracker_motionq_integration():
    with tempfile.TemporaryDirectory() as tmpdir:
        tracker = GazeMouseTracker(storage_dir=tmpdir)

        # Switch to MotionQ Eye mode
        tracker.set_controller_mode("motionq_eye")
        assert tracker.controller_mode == "motionq_eye"

        # Register dwell targets
        t_click = tracker.dwell_engine.register_target(
            x=800, y=400, width=100, height=100,
            target_id="test_btn", action="test_action", duration_ms=200
        )
        assert len(tracker.dwell_engine.get_targets()) == 1

        # Feed frame looking directly at target center (850, 450)
        # Mock iris mapping to target
        tracker.motionq_eye._iris_to_screen = lambda ix, iy: (850.0, 450.0)
        lm = create_synthetic_landmarks(0.50, 0.50)

        # Frame 1: start dwell
        res1 = tracker.process_frame(lm, ear=0.30, pitch=0.0, yaw=0.0, timestamp=1.0)
        assert res1["valid"]
        assert "dwell" in res1
        assert res1["dwell"]["progress"] == 0.0

        # Frame 2: complete dwell (250ms later)
        res2 = tracker.process_frame(lm, ear=0.30, pitch=0.0, yaw=0.0, timestamp=1.25)
        assert res2["dwell"]["progress"] == 1.0
        assert res2["dwell"]["fired"]
        assert res2["dwell"]["action"] == "test_action"

        # Status inspection
        st = tracker.get_status()
        assert st["controller_mode"] == "motionq_eye"
        assert st["dwell_progress"] == 1.0
        assert st["current_profile"] == "default"

"""
test_features.py
Pytest suite for Milestone 2:
- EAR calculation and adaptive blink detection on synthetic landmark sequences
- I-DT gaze dispersion
- Quality gating (low light, extreme head angles)
- Privacy assertions: zero disk file persistence, zero open network sockets
"""

import os
import tempfile
import numpy as np
import pytest

from observer_engine.features import calculate_ear, FeatureExtractor, FrameFeatures
from observer_engine.privacy import PrivacyGuard


def test_ear_open_vs_closed():
    # Synthetic eye: 6 points [p1, p2, p3, p4, p5, p6]
    # Wide open eye: outer=(0, 0), inner=(10, 0), top lids=(3, 3), (7, 3), bottom lids=(3, -3), (7, -3)
    open_eye = np.array([
        [0.0, 0.0],
        [3.0, 3.0],
        [7.0, 3.0],
        [10.0, 0.0],
        [7.0, -3.0],
        [3.0, -3.0],
    ])
    ear_open = calculate_ear(open_eye)
    assert ear_open > 0.5

    # Fully closed eye (vertical distance near 0)
    closed_eye = np.array([
        [0.0, 0.0],
        [3.0, 0.1],
        [7.0, 0.1],
        [10.0, 0.0],
        [7.0, -0.1],
        [3.0, -0.1],
    ])
    ear_closed = calculate_ear(closed_eye)
    assert ear_closed < 0.05
    assert ear_closed < ear_open * 0.2


def test_blink_detection_synthetic_timeline():
    extractor = FeatureExtractor()

    # Generate synthetic 478 landmarks
    base_landmarks = np.zeros((478, 3), dtype=np.float32)
    # Nose
    base_landmarks[1] = [0.5, 0.5, 0.0]
    # Chin
    base_landmarks[152] = [0.5, 0.72, 0.0]
    # Mouth
    base_landmarks[61] = [0.42, 0.62, 0.0]
    base_landmarks[291] = [0.58, 0.62, 0.0]

    # Function to set eye landmarks for open vs closed
    def set_eyes(lm, is_open: bool):
        delta = 0.035 if is_open else 0.005
        # Left eye: 33 (outer), 133 (inner), 160/158 (top), 153/144 (bottom)
        lm[33] = [0.38, 0.40, 0.0]
        lm[133] = [0.46, 0.40, 0.0]
        lm[160] = [0.41, 0.40 - delta, 0.0]
        lm[158] = [0.43, 0.40 - delta, 0.0]
        lm[144] = [0.41, 0.40 + delta, 0.0]
        lm[153] = [0.43, 0.40 + delta, 0.0]

        # Right eye: 263 (outer), 362 (inner), 385/387 (top), 373/380 (bottom)
        lm[263] = [0.62, 0.40, 0.0]
        lm[362] = [0.54, 0.40, 0.0]
        lm[385] = [0.57, 0.40 - delta, 0.0]
        lm[387] = [0.59, 0.40 - delta, 0.0]
        lm[380] = [0.57, 0.40 + delta, 0.0]
        lm[373] = [0.59, 0.40 + delta, 0.0]

    # Phase 1: Open eyes baseline for 1.0 second (15 frames)
    t = 100.0
    for _ in range(15):
        lm = base_landmarks.copy()
        set_eyes(lm, is_open=True)
        extractor.extract_frame_features(frame_bgr=None, landmarks=lm, blendshapes={}, timestamp=t)
        t += 0.066

    assert extractor.blink_count_total == 0

    # Phase 2: Blink occurs (closed for 150ms ~ 3 frames)
    for _ in range(3):
        lm = base_landmarks.copy()
        set_eyes(lm, is_open=False)
        extractor.extract_frame_features(frame_bgr=None, landmarks=lm, blendshapes={}, timestamp=t)
        t += 0.05

    # Phase 3: Eyes reopen
    for _ in range(5):
        lm = base_landmarks.copy()
        set_eyes(lm, is_open=True)
        extractor.extract_frame_features(frame_bgr=None, landmarks=lm, blendshapes={}, timestamp=t)
        t += 0.066

    # Verify blink was registered
    assert extractor.blink_count_total == 1


def test_idt_dispersion_calculation():
    extractor = FeatureExtractor()

    # Case A: Tightly clustered gaze coordinates (Fixation / Stare)
    # User stares at cursor at (0.50, 0.50) with tiny jitter
    now = 1000.0
    for i in range(30):
        t = now - (30 - i)
        f = FrameFeatures(
            timestamp=t,
            valid=True,
            gaze_x=0.50 + np.random.uniform(-0.01, 0.01),
            gaze_y=0.50 + np.random.uniform(-0.01, 0.01),
        )
        extractor._history.append(f)

    win = extractor.aggregate_windows(now)
    assert win.dispersion_30s < 0.10  # Low dispersion indicates fixation

    # Case B: Dispersed gaze coordinates (Casual video watching)
    extractor._history.clear()
    for i in range(30):
        t = now - (30 - i)
        f = FrameFeatures(
            timestamp=t,
            valid=True,
            gaze_x=0.20 + (i % 5) * 0.15,
            gaze_y=0.20 + (i % 4) * 0.15,
        )
        extractor._history.append(f)

    win_dispersed = extractor.aggregate_windows(now)
    assert win_dispersed.dispersion_30s > 0.40  # Broad exploration


def test_quality_gating_low_light():
    extractor = FeatureExtractor()
    dark_frame = np.full((480, 640, 3), 10, dtype=np.uint8)  # Brightness ~10 < 38 threshold
    dummy_lm = np.zeros((478, 3), dtype=np.float32)

    feat = extractor.extract_frame_features(
        frame_bgr=dark_frame, landmarks=dummy_lm, blendshapes={}, timestamp=1.0
    )
    assert feat.valid is False
    assert feat.quality_reason == "low_light"


def test_quality_gating_face_lost():
    extractor = FeatureExtractor()
    feat = extractor.extract_frame_features(
        frame_bgr=None, landmarks=None, blendshapes={}, timestamp=1.0
    )
    assert feat.valid is False
    assert feat.quality_reason == "face_lost"


def test_privacy_no_disk_writes():
    with tempfile.TemporaryDirectory() as temp_dir:
        violations = PrivacyGuard.check_file_safety(temp_dir)
        assert len(violations) == 0

        # Simulate creating an unauthorized frame dump
        test_file = os.path.join(temp_dir, "frame_dump.png")
        with open(test_file, "w") as f:
            f.write("fake image")

        violations_after = PrivacyGuard.check_file_safety(temp_dir)
        assert len(violations_after) == 1
        assert "frame_dump.png" in violations_after[0]


def test_privacy_no_open_sockets():
    assert PrivacyGuard.assert_no_open_sockets() is True

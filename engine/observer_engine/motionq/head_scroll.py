"""
MotionQ Assistive Control System - Head-Tilt Scrolling for Observer
Adapted from MotionQ-blink (head.py)
Copyright (c) 2026 Aakash Kavediya
Licensed under the MIT License. See LICENSE.MotionQ-blink for details.

Head-tilt scrolling:
- Evaluates vertical nose displacement relative to calibrated neutral_y.
- Consecutive frame threshold (default 3 frames) rejects micro-tremors and natural shifts.
- Neutral zone resets counter cleanly.
- Tracking loss clears directional accumulator.
- Resets frame counter immediately after scroll event to prevent runaway continuous scrolling.
- Compatible with macOS and Windows input layers.
"""

import math
from typing import Optional, Dict, Any, Tuple, Callable
import numpy as np


_NOSE_INDEX = 1  # MediaPipe face mesh nose landmark


class HeadTiltScroller:
    def __init__(
        self,
        neutral_y: Optional[float] = None,
        tilt_threshold: float = 20.0,
        scroll_amount: int = 3,  # Lines per scroll tick on macOS
        tilt_frame_threshold: int = 3,
        enabled: bool = True,
    ):
        self.neutral_y = neutral_y
        self.tilt_threshold = float(tilt_threshold)
        self.scroll_amount = int(scroll_amount)
        self.tilt_frame_threshold = int(tilt_frame_threshold)
        self.enabled = bool(enabled)

        self._tilt_frame_count: int = 0
        self._last_direction: Optional[str] = None  # "up" | "down" | None
        self._scroll_dispatcher: Optional[Callable[[int], None]] = None

    def set_scroll_dispatcher(self, dispatcher: Callable[[int], None]) -> None:
        """Register native scroll handler: (delta_y: int) -> None."""
        self._scroll_dispatcher = dispatcher

    def set_neutral_y(self, neutral_y: Optional[float]) -> None:
        self.neutral_y = float(neutral_y) if neutral_y is not None else None

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        if not self.enabled:
            self.reset()

    def reset(self) -> None:
        self._tilt_frame_count = 0
        self._last_direction = None

    def process_landmarks(
        self,
        landmarks: Optional[np.ndarray],
        frame_h: float = 480.0,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Process nose landmark against neutral_y:
        - Down tilt (nose moves down, dy > threshold) -> scroll down (-scroll_amount).
        - Up tilt (nose moves up, dy < -threshold) -> scroll up (+scroll_amount).
        """
        if not self.enabled or self.neutral_y is None:
            self.reset()
            return {
                "active": False,
                "direction": None,
                "frames_accumulated": 0,
                "scrolled": False,
                "dy": 0.0,
            }

        if landmarks is None or len(landmarks) <= _NOSE_INDEX:
            self.reset()
            return {
                "active": False,
                "direction": None,
                "frames_accumulated": 0,
                "scrolled": False,
                "dy": 0.0,
            }

        # Check for NaN / Inf
        if np.isnan(landmarks[_NOSE_INDEX]).any():
            self.reset()
            return {
                "active": False,
                "direction": None,
                "frames_accumulated": 0,
                "scrolled": False,
                "dy": 0.0,
            }

        # Nose Y position in pixel space (matching calibration_manager)
        nose_y = float(landmarks[_NOSE_INDEX, 1] * frame_h)
        dy = nose_y - self.neutral_y

        # Determine tilt direction
        if dy > self.tilt_threshold:
            current_direction = "down"
        elif dy < -self.tilt_threshold:
            current_direction = "up"
        else:
            # Within neutral dead zone: reset accumulator
            self.reset()
            return {
                "active": False,
                "direction": "neutral",
                "frames_accumulated": 0,
                "scrolled": False,
                "dy": dy,
            }

        # Check consecutive frames in same direction
        if current_direction == self._last_direction:
            self._tilt_frame_count += 1
        else:
            self._tilt_frame_count = 1
            self._last_direction = current_direction

        scrolled = False
        delta_lines = 0

        # Trigger scroll once threshold is reached
        if self._tilt_frame_count >= self.tilt_frame_threshold:
            # On macOS / native: positive = scroll up, negative = scroll down
            delta_lines = self.scroll_amount if current_direction == "up" else -self.scroll_amount
            scrolled = True

            # Reset counter so it requires subsequent frame accumulation to fire again
            self._tilt_frame_count = 0

            if self._scroll_dispatcher is not None:
                try:
                    self._scroll_dispatcher(delta_lines)
                except Exception as e:
                    print(f"[HeadTiltScroller] Scroll dispatch error: {e}")

        return {
            "active": True,
            "direction": current_direction,
            "frames_accumulated": self._tilt_frame_count,
            "scrolled": scrolled,
            "delta_lines": delta_lines,
            "dy": dy,
        }

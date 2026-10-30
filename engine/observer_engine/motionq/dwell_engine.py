"""
MotionQ Assistive Control System - Dwell Engine for Observer
Adapted from MotionQ-blink (dwell_engine.py)
Copyright (c) 2026 Aakash Kavediya
Licensed under the MIT License. See LICENSE.MotionQ-blink for details.

Deterministic Dwell Engine:
- Screen-space rectangular target registration with name, priority, stability radius, duration override.
- Overlapping target resolution: last registered target has highest priority.
- Dwell progress tracking [0.0, 1.0] with stability radius check.
- Single activation per dwell: target callback fires once; does not re-fire until cursor leaves.
- Click modes: None, 'single', 'double' (mutually exclusive).
- General screen dwell: when click-mode is armed and not over UI targets, dwelling still triggers native click.
- Click cooldown to prevent accidental rapid double-firing.
"""

import time
import math
from typing import Optional, Dict, Any, List, Callable, Tuple, Literal

ClickMode = Literal["single", "double", None]


class DwellTarget:
    def __init__(
        self,
        target_id: str,
        x: float,
        y: float,
        width: float,
        height: float,
        callback: Optional[Callable[[], None]] = None,
        action: Optional[str] = None,
        name: Optional[str] = None,
        duration_ms: Optional[float] = None,
        stability_radius: Optional[float] = None,
    ):
        self.target_id = target_id
        self.x = float(x)
        self.y = float(y)
        self.width = float(width)
        self.height = float(height)
        self.callback = callback
        self.action = action
        self.name = name or target_id
        self.duration_ms = duration_ms
        self.stability_radius = stability_radius

    def contains(self, px: float, py: float) -> bool:
        return (
            self.x <= px <= (self.x + self.width)
            and self.y <= py <= (self.y + self.height)
        )

    def center(self) -> Tuple[float, float]:
        return (self.x + self.width / 2.0, self.y + self.height / 2.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "action": self.action,
            "duration_ms": self.duration_ms,
            "stability_radius": self.stability_radius,
        }


class DwellEngine:
    def __init__(
        self,
        default_duration_ms: float = 1000.0,
        stability_radius: float = 50.0,
        click_cooldown_sec: float = 1.0,
    ):
        self.default_duration_ms = default_duration_ms
        self.stability_radius = stability_radius
        self.click_cooldown_sec = click_cooldown_sec

        self._targets: List[DwellTarget] = []
        self._click_mode: Optional[str] = None  # None | "single" | "double"

        # State tracking for UI target dwell
        self._active_target: Optional[DwellTarget] = None
        self._target_dwell_start_time: float = 0.0
        self._target_dwell_origin: Tuple[float, float] = (0.0, 0.0)
        self._target_activated: bool = False

        # State tracking for general screen click dwell
        self._click_dwell_start_time: float = 0.0
        self._click_dwell_origin: Tuple[float, float] = (0.0, 0.0)
        self._click_dwell_active: bool = False
        self._last_click_time: float = 0.0

        # State output
        self._current_progress: float = 0.0
        self._dwell_center: Tuple[float, float] = (0.0, 0.0)
        self._last_fired_event: Optional[Dict[str, Any]] = None

        # External click dispatch handler
        self._click_dispatcher: Optional[Callable[[float, float, bool], None]] = None

    def set_click_dispatcher(self, dispatcher: Callable[[float, float, bool], None]) -> None:
        """Register callback for native clicking: (x, y, is_double) -> None."""
        self._click_dispatcher = dispatcher

    def set_timing(
        self,
        duration_ms: Optional[float] = None,
        stability_radius: Optional[float] = None,
        click_cooldown_sec: Optional[float] = None,
    ) -> None:
        if duration_ms is not None and duration_ms > 0:
            self.default_duration_ms = float(duration_ms)
        if stability_radius is not None and stability_radius > 0:
            self.stability_radius = float(stability_radius)
        if click_cooldown_sec is not None and click_cooldown_sec >= 0:
            self.click_cooldown_sec = float(click_cooldown_sec)

    def register_target(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        target_id: Optional[str] = None,
        callback: Optional[Callable[[], None]] = None,
        action: Optional[str] = None,
        name: Optional[str] = None,
        duration_ms: Optional[float] = None,
        stability_radius: Optional[float] = None,
    ) -> DwellTarget:
        """
        Register a rectangular dwell target.
        Last registered target has highest priority when overlapping.
        """
        tid = target_id or f"target_{len(self._targets) + 1}_{int(time.time() * 1000)}"
        target = DwellTarget(
            target_id=tid,
            x=x,
            y=y,
            width=width,
            height=height,
            callback=callback,
            action=action,
            name=name or tid,
            duration_ms=duration_ms,
            stability_radius=stability_radius,
        )
        self._targets.append(target)
        return target

    def get_targets(self) -> List[Dict[str, Any]]:
        """Return list of registered target dicts (for magnet/proximity queries)."""
        return [t.to_dict() for t in self._targets]

    def clear_targets(self) -> None:
        """Clear all registered targets and reset dwell state."""
        self._targets.clear()
        self.reset_dwell()

    def reset_dwell(self) -> None:
        """Reset active dwell progress and state."""
        self._active_target = None
        self._target_dwell_start_time = 0.0
        self._target_dwell_origin = (0.0, 0.0)
        self._target_activated = False

        self._click_dwell_active = False
        self._click_dwell_start_time = 0.0
        self._click_dwell_origin = (0.0, 0.0)

        self._current_progress = 0.0
        self._dwell_center = (0.0, 0.0)

    def set_click_mode(self, mode: Optional[str]) -> None:
        """Set click mode: None, 'single', or 'double'. Mutually exclusive."""
        if mode not in ("single", "double"):
            self._click_mode = None
        else:
            self._click_mode = mode
        self.reset_dwell()

    def get_click_mode(self) -> Optional[str]:
        return self._click_mode

    def toggle_click_mode(self, mode: str) -> Optional[str]:
        """Toggles specified mode. If active, turns off; if off, switches to it."""
        if self._click_mode == mode:
            self._click_mode = None
        else:
            self._click_mode = mode if mode in ("single", "double") else None
        self.reset_dwell()
        return self._click_mode

    def get_target_at(self, px: float, py: float) -> Optional[DwellTarget]:
        """Find last registered target that contains (px, py)."""
        for t in reversed(self._targets):
            if t.contains(px, py):
                return t
        return None

    def update(
        self,
        cursor_x: float,
        cursor_y: float,
        timestamp: Optional[float] = None,
        is_tracking_valid: bool = True,
    ) -> Dict[str, Any]:
        """
        Update dwell engine with current cursor position.
        Returns dwell status including:
        - progress: float [0.0, 1.0]
        - active_target: target dict or None
        - click_mode: None | 'single' | 'double'
        - fired: bool
        - action: action string or None
        """
        now = timestamp if timestamp is not None else time.time()

        if not is_tracking_valid:
            self.reset_dwell()
            return {
                "progress": 0.0,
                "center": (cursor_x, cursor_y),
                "active_target": None,
                "click_mode": self._click_mode,
                "fired": False,
                "action": None,
            }

        target = self.get_target_at(cursor_x, cursor_y)

        # -------------------------------------------------------------
        # Path A: Cursor is hovering over a registered UI target
        # -------------------------------------------------------------
        if target is not None:
            # Clear general screen click dwell
            self._click_dwell_active = False

            cx, cy = target.center()
            self._dwell_center = (cx, cy)
            req_radius = target.stability_radius or self.stability_radius
            req_duration_sec = (
                (target.duration_ms / 1000.0)
                if target.duration_ms
                else (self.default_duration_ms / 1000.0)
            )

            # Case A1: New target entered
            if self._active_target is not target:
                self._active_target = target
                self._target_dwell_start_time = now
                self._target_dwell_origin = (cursor_x, cursor_y)
                self._target_activated = False
                self._current_progress = 0.0
                return {
                    "progress": 0.0,
                    "center": (cx, cy),
                    "active_target": target.to_dict(),
                    "click_mode": self._click_mode,
                    "fired": False,
                    "action": None,
                }

            # Case A2: Already activated during this dwell session (do not re-fire)
            if self._target_activated:
                return {
                    "progress": 1.0,
                    "center": (cx, cy),
                    "active_target": target.to_dict(),
                    "click_mode": self._click_mode,
                    "fired": False,
                    "action": None,
                }

            # Case A3: Check stability
            dist = math.hypot(
                cursor_x - self._target_dwell_origin[0],
                cursor_y - self._target_dwell_origin[1],
            )
            if dist > req_radius:
                # Tremor / head moved too far: restart dwell
                self._target_dwell_start_time = now
                self._target_dwell_origin = (cursor_x, cursor_y)
                self._current_progress = 0.0
                return {
                    "progress": 0.0,
                    "center": (cx, cy),
                    "active_target": target.to_dict(),
                    "click_mode": self._click_mode,
                    "fired": False,
                    "action": None,
                }

            # Case A4: Accumulate progress
            elapsed = now - self._target_dwell_start_time
            progress = min(1.0, max(0.0, elapsed / max(1e-3, req_duration_sec)))
            self._current_progress = progress

            if progress >= 1.0 or elapsed >= (req_duration_sec - 1e-4):
                # Fire target callback and action
                self._target_activated = True
                self._last_fired_event = {
                    "target_id": target.target_id,
                    "action": target.action,
                    "timestamp": now,
                }
                if target.callback is not None:
                    try:
                        target.callback()
                    except Exception as e:
                        print(f"[DwellEngine] Callback error on {target.name}: {e}")

                return {
                    "progress": 1.0,
                    "center": (cx, cy),
                    "active_target": target.to_dict(),
                    "click_mode": self._click_mode,
                    "fired": True,
                    "action": target.action or target.target_id,
                }

            return {
                "progress": progress,
                "center": (cx, cy),
                "active_target": target.to_dict(),
                "click_mode": self._click_mode,
                "fired": False,
                "action": None,
            }

        # -------------------------------------------------------------
        # Path B: Cursor is NOT over any registered target
        # -------------------------------------------------------------
        self._active_target = None
        self._target_activated = False

        # If click mode is OFF, reset dwell and hide
        if self._click_mode is None:
            self._click_dwell_active = False
            self._current_progress = 0.0
            return {
                "progress": 0.0,
                "center": (cursor_x, cursor_y),
                "active_target": None,
                "click_mode": None,
                "fired": False,
                "action": None,
            }

        # Click mode is ARMED ('single' or 'double'): general screen dwell
        self._dwell_center = (cursor_x, cursor_y)
        req_duration_sec = self.default_duration_ms / 1000.0

        if not self._click_dwell_active:
            self._click_dwell_active = True
            self._click_dwell_start_time = now
            self._click_dwell_origin = (cursor_x, cursor_y)
            self._current_progress = 0.0
            return {
                "progress": 0.0,
                "center": (cursor_x, cursor_y),
                "active_target": None,
                "click_mode": self._click_mode,
                "fired": False,
                "action": None,
            }

        # Check stability
        dist = math.hypot(
            cursor_x - self._click_dwell_origin[0],
            cursor_y - self._click_dwell_origin[1],
        )
        if dist > self.stability_radius:
            # Moved outside stability radius: restart dwell at new position
            self._click_dwell_start_time = now
            self._click_dwell_origin = (cursor_x, cursor_y)
            self._current_progress = 0.0
            return {
                "progress": 0.0,
                "center": (cursor_x, cursor_y),
                "active_target": None,
                "click_mode": self._click_mode,
                "fired": False,
                "action": None,
            }

        # Check cooldown
        time_since_click = now - self._last_click_time
        if time_since_click < self.click_cooldown_sec:
            return {
                "progress": 0.0,
                "center": (cursor_x, cursor_y),
                "active_target": None,
                "click_mode": self._click_mode,
                "fired": False,
                "action": None,
            }

        elapsed = now - self._click_dwell_start_time
        progress = min(1.0, max(0.0, elapsed / max(1e-3, req_duration_sec)))
        self._current_progress = progress

        if progress >= 1.0 or elapsed >= (req_duration_sec - 1e-4):
            is_double = (self._click_mode == "double")
            self._last_click_time = now
            self._click_dwell_active = False
            self._current_progress = 0.0

            if self._click_dispatcher is not None:
                try:
                    self._click_dispatcher(cursor_x, cursor_y, is_double)
                except Exception as e:
                    print(f"[DwellEngine] Click dispatch error: {e}")

            return {
                "progress": 1.0,
                "center": (cursor_x, cursor_y),
                "active_target": None,
                "click_mode": self._click_mode,
                "fired": True,
                "action": "double_click" if is_double else "single_click",
                "click_x": cursor_x,
                "click_y": cursor_y,
                "is_double": is_double,
            }

        return {
            "progress": progress,
            "center": (cursor_x, cursor_y),
            "active_target": None,
            "click_mode": self._click_mode,
            "fired": False,
            "action": None,
        }

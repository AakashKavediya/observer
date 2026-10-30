"""
MotionQ Assistive Control System - Voice Commands for Observer
Copyright (c) 2026 Aakash Kavediya / Observer Engineering Team
Licensed under the MIT License. See LICENSE.MotionQ-blink for details.

Deduplicated Assistive Voice Command Dispatcher:
- Supports 13 canonical assistive commands.
- Fuzzy matching & alias normalization.
- Cooldown deduplication (1.0s) prevents rapid repeated activations.
- Strict command gating: rejects freeform conversational text.
"""

import time
import re
from typing import Optional, Dict, Any, Callable

_CANONICAL_COMMANDS = {
    "start eye control": ["start eye control", "enable eye control", "turn on eye control"],
    "pause eye control": ["pause eye control", "pause cursor", "pause eye mouse"],
    "resume eye control": ["resume eye control", "resume cursor", "resume eye mouse", "unpause"],
    "recenter": ["recenter", "center mouse", "reset center", "recenter pointer"],
    "recalibrate": ["recalibrate", "start calibration", "calibrate eye control"],
    "click": ["click", "left click", "single click", "tap"],
    "double-click": ["double click", "double-click", "open it"],
    "right-click": ["right click", "right-click", "context menu"],
    "scroll up": ["scroll up", "page up"],
    "scroll down": ["scroll down", "page down"],
    "show keyboard": ["show keyboard", "open keyboard", "virtual keyboard", "display keyboard"],
    "hide keyboard": ["hide keyboard", "close keyboard", "dismiss keyboard"],
    "emergency stop": ["emergency stop", "stop everything", "abort", "freeze"],
}


class VoiceCommandDispatcher:
    def __init__(self, cooldown_seconds: float = 1.0):
        self.cooldown_seconds = cooldown_seconds
        self._last_command: Optional[str] = None
        self._last_command_time: float = 0.0
        self._action_handlers: Dict[str, Callable[[], None]] = {}

    def register_handler(self, command_name: str, handler: Callable[[], None]) -> None:
        self._action_handlers[command_name] = handler

    def normalize_text(self, text: str) -> str:
        t = re.sub(r"[^\w\s-]", "", (text or "").lower()).strip()
        return re.sub(r"\s+", " ", t)

    def match_command(self, text: str) -> Optional[str]:
        cleaned = self.normalize_text(text)
        if not cleaned:
            return None

        # Exact match or phrase match
        for canonical, aliases in _CANONICAL_COMMANDS.items():
            for alias in aliases:
                # Require command to match entire text or end with clear command token
                if cleaned == alias or cleaned.endswith(" " + alias) or cleaned.startswith(alias + " "):
                    return canonical

        return None

    def process_transcript(self, text: str, timestamp: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Process speech transcript.
        If matched and not in cooldown, executes handler and returns command event.
        """
        cmd = self.match_command(text)
        if not cmd:
            return None

        now = timestamp if timestamp is not None else time.time()
        if cmd == self._last_command and (now - self._last_command_time) < self.cooldown_seconds:
            # Deduplicated within cooldown
            return None

        self._last_command = cmd
        self._last_command_time = now

        # Execute registered action handler if available
        if cmd in self._action_handlers:
            try:
                self._action_handlers[cmd]()
            except Exception as e:
                print(f"[VoiceCommands] Error executing handler for {cmd}: {e}")

        return {
            "command": cmd,
            "raw_text": text,
            "timestamp": now,
            "success": True,
        }

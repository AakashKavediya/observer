"""
observer_engine.intervention
Manages gentle, optional, non-intrusive cognitive interventions:
- Tiers 0 to 3 (0=Off, 1=Ambient Cue, 2=Gentle Offer, 3=Micro-steps).
- Configurable cooldown (default 20 min) with exponential back-off when ignored.
- Hourly frequency caps to prevent overwhelming the user.
- Quiet hours support with 24h clock comparison.
- Short, reassuring copy pool (strictly under 12 words, zero shaming).
- Never repeats consecutive phrases.
- Suppressed while RELAXED, FOCUSED, or UNKNOWN.
- Responds to feedback: 'helped', 'not_now', 'wrong_guess'.
"""

import time
import random
from typing import List, Optional, Tuple
from datetime import datetime

from observer_engine.config import CONFIG
from observer_engine.ipc import (
    InterventionEvent,
    InterventionAction,
    InterventionStatusTelemetry,
    SettingsPayload,
)

# Curated pool of gentle, compassionate prompts (< 12 words, no judgment)
PARALYSIS_PROMPTS = [
    "Need a hand picking the next tiny step?",
    "Would pausing for a quick stretch help right now?",
    "Everything can wait. Would a minute to breathe help?",
    "Want to break this task into one small step?",
    "It is okay to pause. Would a gentle reset help?",
    "Would looking away from the screen for 20 seconds help?",
    "Feeling stuck? We can break this into smaller pieces.",
]

OVERLOAD_PROMPTS = [
    "Lots going on right now. Want to pause together?",
    "Deep breath. Would closing extra windows feel lighter?",
    "Take your time. Would a quick 60-second breather help?",
    "No rush at all. Want to focus on just one thing?",
    "Overload is real. Would stepping away for tea help?",
]


class InterventionManager:
    def __init__(self, default_cooldown_mins: int = 20, max_per_hour: int = 3):
        self.cooldown_base_seconds: float = default_cooldown_mins * 60.0
        self.max_per_hour: int = max_per_hour
        self.current_tier: int = 2  # Default Tier 2 (Gentle offer)

        # Settings
        self.quiet_hours_enabled: bool = False
        self.quiet_hours_start: str = "22:00"
        self.quiet_hours_end: str = "08:00"

        # State tracking
        self.last_intervention_ts: float = 0.0
        self.snooze_until_ts: float = 0.0
        self.backoff_multiplier: float = 1.0
        self.last_prompt_text: Optional[str] = None
        self.recent_intervention_timestamps: List[float] = []

        # Current active intervention pending user action
        self.active_intervention_id: Optional[str] = None
        self.active_intervention_ts: float = 0.0

    def update_settings(self, settings: SettingsPayload) -> None:
        """Applies updated user settings."""
        if settings.cooldown_mins is not None:
            self.cooldown_base_seconds = max(60.0, float(settings.cooldown_mins * 60.0))
        if settings.intervention_tier is not None:
            self.current_tier = max(0, min(3, settings.intervention_tier))
        if settings.quiet_hours_enabled is not None:
            self.quiet_hours_enabled = settings.quiet_hours_enabled
        if settings.quiet_hours_start is not None:
            self.quiet_hours_start = settings.quiet_hours_start
        if settings.quiet_hours_end is not None:
            self.quiet_hours_end = settings.quiet_hours_end

    def snooze(self, duration_minutes: int) -> None:
        """Snoozes all interventions for a set duration."""
        self.snooze_until_ts = time.time() + (duration_minutes * 60.0)

    def record_feedback(self, kind: str) -> None:
        """
        Processes feedback on an intervention:
        - helped: resets backoff to 1.0, normal cooldown.
        - not_now: user dismissed; increases backoff by 1.5x (up to 3x).
        - wrong_guess: state engine was wrong; increases backoff to 2.5x and snoozes 30m.
        """
        now = time.time()
        self.active_intervention_id = None

        if kind == "helped":
            self.backoff_multiplier = 1.0
            self.last_intervention_ts = now
        elif kind == "not_now":
            self.backoff_multiplier = min(3.0, self.backoff_multiplier * 1.5)
            self.last_intervention_ts = now
        elif kind == "wrong_guess":
            self.backoff_multiplier = min(4.0, self.backoff_multiplier * 2.0)
            self.snooze_until_ts = now + (30.0 * 60.0)
            self.last_intervention_ts = now

    def _is_in_quiet_hours(self, now_dt: Optional[datetime] = None) -> bool:
        """Checks if current local time falls in configured quiet hours."""
        if not self.quiet_hours_enabled:
            return False

        try:
            now_dt = now_dt or datetime.now()
            current_time = now_dt.strftime("%H:%M")

            start = self.quiet_hours_start
            end = self.quiet_hours_end

            if start <= end:
                return start <= current_time <= end
            else:
                # Wraps past midnight (e.g. 22:00 to 08:00)
                return current_time >= start or current_time <= end
        except Exception:
            return False

    def evaluate_eligibility(
        self, state: str, now: Optional[float] = None
    ) -> Tuple[bool, str, float]:
        """
        Evaluates whether an intervention can be offered.
        Returns: (eligible, reason, cooldown_remaining_seconds)
        """
        now = now or time.time()

        # 1. Tier 0 disabled
        if self.current_tier == 0:
            return False, "Interventions disabled (Tier 0)", 0.0

        # 2. State restriction: must be PARALYSIS_LIKELY or OVERLOAD_LIKELY
        if state not in ("PARALYSIS_LIKELY", "OVERLOAD_LIKELY"):
            return False, f"State is {state} (no check-in needed)", 0.0

        # 3. Snooze check
        if now < self.snooze_until_ts:
            rem = self.snooze_until_ts - now
            return False, f"Snoozed ({int(rem // 60)}m remaining)", rem

        # 4. Quiet hours check
        if self._is_in_quiet_hours():
            return False, "Quiet hours active", 0.0

        # 5. Cooldown with exponential backoff
        effective_cooldown = self.cooldown_base_seconds * self.backoff_multiplier
        elapsed = now - self.last_intervention_ts
        if elapsed < effective_cooldown:
            rem = effective_cooldown - elapsed
            return False, f"In cooldown ({int(rem // 60)}m remaining)", rem

        # 6. Hourly frequency cap
        cutoff = now - 3600.0
        self.recent_intervention_timestamps = [
            ts for ts in self.recent_intervention_timestamps if ts > cutoff
        ]
        if len(self.recent_intervention_timestamps) >= self.max_per_hour:
            return False, "Hourly limit reached", 3600.0 - (now - self.recent_intervention_timestamps[0])

        return True, "Eligible for gentle check-in", 0.0

    def get_status_telemetry(self, state: str, now: Optional[float] = None) -> InterventionStatusTelemetry:
        """Returns structured telemetry for transparency UI."""
        eligible, reason, rem = self.evaluate_eligibility(state, now)
        return InterventionStatusTelemetry(
            eligible=eligible,
            reason=reason,
            cooldown_remaining_s=round(rem, 1),
        )

    def maybe_create_intervention(
        self, state: str, now: Optional[float] = None
    ) -> Optional[InterventionEvent]:
        """
        Generates a non-intrusive intervention event if eligible.
        Guarantees:
        - Text is < 12 words.
        - Text is not identical to the last one shown.
        - Tier matches user preference.
        """
        now = now or time.time()
        eligible, _, _ = self.evaluate_eligibility(state, now)
        if not eligible:
            return None

        # Select prompt pool
        pool = OVERLOAD_PROMPTS if state == "OVERLOAD_LIKELY" else PARALYSIS_PROMPTS
        available_prompts = [p for p in pool if p != self.last_prompt_text]
        if not available_prompts:
            available_prompts = pool

        selected_text = random.choice(available_prompts)
        self.last_prompt_text = selected_text

        # Record timestamps
        self.last_intervention_ts = now
        self.recent_intervention_timestamps.append(now)

        intervention_id = f"intv_{int(now)}_{random.randint(1000, 9999)}"
        self.active_intervention_id = intervention_id
        self.active_intervention_ts = now

        # Tier-specific actions
        if self.current_tier == 1:
            actions = [
                InterventionAction(id="dismiss", label="I'm okay"),
            ]
        elif self.current_tier == 2:
            actions = [
                InterventionAction(id="tiny_step", label="Break down next step"),
                InterventionAction(id="breathe", label="60s reset"),
                InterventionAction(id="snooze_15", label="Not now (15m)"),
            ]
        else:  # Tier 3
            actions = [
                InterventionAction(id="tiny_step", label="Step 1: Write down 1 word"),
                InterventionAction(id="stretch", label="Stretch arms & neck"),
                InterventionAction(id="snooze_30", label="Check back in 30m"),
            ]

        return InterventionEvent(
            tier=self.current_tier,
            id=intervention_id,
            text=selected_text,
            actions=actions,
        )

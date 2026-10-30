"""
observer_engine.health_tech.events
Conservative Observation and Event Engine for Observer Behavioral Platform.

Replaces simplistic single-state cognitive classifications with transparent,
feature-specific behavioral observation events.

Acceptable Events:
- "Prolonged interval without detected task input"
- "Head movement lower than personal baseline"
- "Increased application-switch frequency"
- "Smile-related facial features above calibrated threshold"
- "Eye-tracking quality insufficient"
- "User-reported difficulty starting a task"

Health-Tech Governance:
- Events are purely descriptive behavioral observations.
- NEVER automatically labeled as paralysis, anxiety, stress, or medical pathology.
- Requires sustained conditions (multi-sample hysteresis) and >= 60% valid observation coverage.
"""

import time
import uuid
from typing import Optional, List, Dict, Any
from observer_engine.health_tech.schema import EventRecord, ValidityStatus, ALGORITHM_VERSION
from observer_engine.health_tech.feature_extractor import PhysiologicalSnapshot
from observer_engine.health_tech.baseline import PersonalBaselineProfile


class ConservativeEventEngine:
    def __init__(self, session_id: str = "default_session"):
        self.session_id = session_id
        self.recorded_events: List[EventRecord] = []

        # Sustained condition tracking timers
        self._low_head_move_start: Optional[float] = None
        self._prolonged_idle_start: Optional[float] = None
        self._smile_sustained_start: Optional[float] = None
        self._tracking_lost_start: Optional[float] = None

        # Cooldowns to prevent event spam (min 120s between identical events)
        self._last_event_times: Dict[str, float] = {}

    def evaluate_signals(
        self,
        snapshot: PhysiologicalSnapshot,
        baseline: PersonalBaselineProfile,
        idle_seconds: float,
        window_switch_count_60s: int,
        usable_ratio: float,
        now: Optional[float] = None,
    ) -> List[EventRecord]:
        """
        Evaluates current signals against transparent rule thresholds.
        Returns newly generated events, if any.
        """
        now = now or time.time()
        new_events: List[EventRecord] = []

        # 1. Tracking Quality Event
        if not snapshot.valid or usable_ratio < 0.40:
            if self._tracking_lost_start is None:
                self._tracking_lost_start = now
            elif (now - self._tracking_lost_start >= 45.0) and self._can_emit("tracking_insufficient", now):
                ev = EventRecord(
                    event_id=str(uuid.uuid4()),
                    session_id=self.session_id,
                    event_type="Eye-tracking quality insufficient",
                    start_time=self._tracking_lost_start,
                    end_time=now,
                    duration_seconds=round(now - self._tracking_lost_start, 1),
                    supporting_measurements=[
                        {"name": "usable_frame_ratio", "value": round(usable_ratio, 2), "threshold": "< 0.40"},
                        {"name": "quality_reason", "value": snapshot.quality_reason},
                    ],
                    feature_validity=ValidityStatus.LOW_QUALITY.value,
                    baseline_comparison="N/A",
                    explanation="Camera tracking was disrupted or lost for over 45 seconds due to occlusion, lighting, or face angle.",
                    uncertainty="low",
                    is_user_reported=False,
                )
                new_events.append(ev)
                self.recorded_events.append(ev)
                self._last_event_times["tracking_insufficient"] = now
            return new_events
        else:
            self._tracking_lost_start = None

        # Guard: Require >= 60% valid coverage for behavioral events
        if usable_ratio < 0.60:
            return new_events

        # 2. Prolonged Inactivity Interval (> 90 seconds without keyboard/mouse)
        if idle_seconds >= 90.0:
            if self._prolonged_idle_start is None:
                self._prolonged_idle_start = now - idle_seconds
            if self._can_emit("prolonged_idle", now):
                dur = now - self._prolonged_idle_start
                ev = EventRecord(
                    event_id=str(uuid.uuid4()),
                    session_id=self.session_id,
                    event_type="Prolonged interval without detected task input",
                    start_time=self._prolonged_idle_start,
                    end_time=now,
                    duration_seconds=round(dur, 1),
                    supporting_measurements=[
                        {"name": "input_idle_seconds", "value": round(idle_seconds, 1), "threshold": ">= 90.0s"},
                    ],
                    feature_validity=ValidityStatus.VALID.value,
                    baseline_comparison="N/A",
                    explanation="No local mouse or keyboard input interactions were detected during this interval.",
                    uncertainty="low",
                    is_user_reported=False,
                )
                new_events.append(ev)
                self.recorded_events.append(ev)
                self._last_event_times["prolonged_idle"] = now
        else:
            self._prolonged_idle_start = None

        # 3. Low Head Movement Below Baseline (angular velocity < 1.0 deg/s sustained for >= 60s)
        if snapshot.angular_velocity is not None and snapshot.angular_velocity < 1.0:
            if self._low_head_move_start is None:
                self._low_head_move_start = now
            elif (now - self._low_head_move_start >= 60.0) and self._can_emit("low_head_movement", now):
                dur = now - self._low_head_move_start
                base_vel = baseline.head_angular_velocity_baseline.get("median", 3.5) if baseline.head_angular_velocity_baseline else 3.5
                ev = EventRecord(
                    event_id=str(uuid.uuid4()),
                    session_id=self.session_id,
                    event_type="Head movement lower than personal baseline",
                    start_time=self._low_head_move_start,
                    end_time=now,
                    duration_seconds=round(dur, 1),
                    supporting_measurements=[
                        {"name": "angular_velocity_deg_s", "value": round(snapshot.angular_velocity, 2), "threshold": "< 1.0 deg/s"},
                        {"name": "baseline_median_velocity", "value": round(base_vel, 2)},
                    ],
                    feature_validity=ValidityStatus.VALID.value,
                    baseline_comparison=f"{round(snapshot.angular_velocity, 2)} deg/s vs baseline {round(base_vel, 2)} deg/s",
                    explanation="Head kinematic movement remained below 1.0 deg/s continuously for over 60 seconds.",
                    uncertainty="moderate",
                    is_user_reported=False,
                )
                new_events.append(ev)
                self.recorded_events.append(ev)
                self._last_event_times["low_head_movement"] = now
        else:
            self._low_head_move_start = None

        # 4. Elevated Application-Switch Frequency (>= 12 switches in 60s)
        if window_switch_count_60s >= 12 and self._can_emit("elevated_switching", now):
            ev = EventRecord(
                event_id=str(uuid.uuid4()),
                session_id=self.session_id,
                event_type="Increased application-switch frequency",
                start_time=now - 60.0,
                end_time=now,
                duration_seconds=60.0,
                supporting_measurements=[
                    {"name": "window_switch_count_60s", "value": window_switch_count_60s, "threshold": ">= 12"},
                ],
                feature_validity=ValidityStatus.VALID.value,
                baseline_comparison="N/A",
                explanation="Frequent application focus transitions were recorded in the aggregate OS signal counter.",
                uncertainty="low",
                is_user_reported=False,
            )
            new_events.append(ev)
            self.recorded_events.append(ev)
            self._last_event_times["elevated_switching"] = now

        # 5. Sustained Smile-Related Features Above Threshold (>= 15s)
        if snapshot.smile_score_avg is not None and snapshot.smile_score_avg >= 0.40:
            if self._smile_sustained_start is None:
                self._smile_sustained_start = now
            elif (now - self._smile_sustained_start >= 15.0) and self._can_emit("sustained_smile", now):
                dur = now - self._smile_sustained_start
                ev = EventRecord(
                    event_id=str(uuid.uuid4()),
                    session_id=self.session_id,
                    event_type="Smile-related facial features above calibrated threshold",
                    start_time=self._smile_sustained_start,
                    end_time=now,
                    duration_seconds=round(dur, 1),
                    supporting_measurements=[
                        {"name": "smile_score_avg", "value": round(snapshot.smile_score_avg, 2), "threshold": ">= 0.40"},
                        {"name": "mouth_corner_elevation_avg", "value": round(((snapshot.mouth_corner_elevation_left or 0.0) + (snapshot.mouth_corner_elevation_right or 0.0)) / 2.0, 3)},
                    ],
                    feature_validity=ValidityStatus.VALID.value,
                    baseline_comparison="N/A",
                    explanation="Elevated mouth corner geometry and smile blendshape coefficients were detected continuously for over 15 seconds.",
                    uncertainty="moderate",
                    is_user_reported=False,
                )
                new_events.append(ev)
                self.recorded_events.append(ev)
                self._last_event_times["sustained_smile"] = now
        else:
            self._smile_sustained_start = None

        return new_events

    def _can_emit(self, event_key: str, now: float) -> bool:
        if event_key not in self._last_event_times:
            return True
        last_t = self._last_event_times[event_key]
        return (now - last_t) >= 120.0  # 2 minute minimum cooldown per event type

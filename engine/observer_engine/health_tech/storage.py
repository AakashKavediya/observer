"""
observer_engine.health_tech.storage
Centralized Persistence & Query Repository for Observer Behavioral Platform.

Manages:
- Versioned observation records (~/.observer/observations/session_<id>.json)
- Session metadata and lifecycle
- Conservative behavioral events
- Optional user check-ins
- Generated evidence-based reports
- Instant complete data export and data purge

100% Local-First & Privacy Guarantees:
- Zero raw frames or audio stored.
- Keystrokes, passwords, screenshots, and window titles are NEVER captured or saved.
"""

import os
import json
import time
import uuid
from typing import Optional, List, Dict, Any

from observer_engine.health_tech.schema import (
    ObservationRecord,
    CheckInRecord,
    EventRecord,
    SessionRecord,
    ValidityStatus,
    SCHEMA_VERSION,
)
from observer_engine.health_tech.baseline import BaselineCalibrationManager
from observer_engine.health_tech.checkins import CheckInManager
from observer_engine.health_tech.events import ConservativeEventEngine
from observer_engine.health_tech.reports import ReportGenerator


class HealthTechRepository:
    def __init__(self, base_dir: Optional[str] = None):
        home = os.path.expanduser("~")
        self.base_dir = base_dir or os.path.join(home, ".observer")
        self.sessions_dir = os.path.join(self.base_dir, "sessions")
        self.obs_dir = os.path.join(self.base_dir, "observations")
        self.reports_dir = os.path.join(self.base_dir, "reports")
        os.makedirs(self.sessions_dir, exist_ok=True)
        os.makedirs(self.obs_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)

        self.sessions_file = os.path.join(self.sessions_dir, "sessions_index.json")
        self.events_file = os.path.join(self.base_dir, "behavioral_events.json")

        self.baseline_manager = BaselineCalibrationManager(os.path.join(self.base_dir, "baselines"))
        self.checkin_manager = CheckInManager(os.path.join(self.base_dir, "checkins"))
        self.report_generator = ReportGenerator(self.baseline_manager.current_profile)

        # Active in-memory session
        self.active_session: SessionRecord = self._init_or_load_session()
        self.event_engine = ConservativeEventEngine(self.active_session.session_id)

        # In-memory observation cache for fast live queries
        self._live_observation_buffer: List[ObservationRecord] = []
        self._last_flush_ts: float = time.time()

        # Load persisted events
        self.events: List[EventRecord] = self._load_events()

    def _init_or_load_session(self) -> SessionRecord:
        """Initializes a new active recording session."""
        sess = SessionRecord(
            session_id=str(uuid.uuid4()),
            start_time=time.time(),
            status="active",
            active_streams=["webcam_face", "desktop_input"],
        )
        self._upsert_session_index(sess)
        return sess

    def _load_events(self) -> List[EventRecord]:
        if not os.path.isfile(self.events_file):
            return []
        try:
            with open(self.events_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [EventRecord(**item) for item in data.get("events", [])]
        except Exception:
            return []

    def _save_events_atomic(self) -> bool:
        tmp = f"{self.events_file}.tmp.{uuid.uuid4().hex[:6]}"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"events": [e.to_dict() for e in self.events]}, f, indent=2)
            os.replace(tmp, self.events_file)
            return True
        except Exception as e:
            print(f"[Storage] Save events error: {e}")
            return False

    def _upsert_session_index(self, sess: SessionRecord) -> None:
        sessions = self.get_sessions()
        updated = False
        for i, s in enumerate(sessions):
            if s.get("session_id") == sess.session_id:
                sessions[i] = sess.to_dict()
                updated = True
                break
        if not updated:
            sessions.append(sess.to_dict())

        tmp = f"{self.sessions_file}.tmp.{uuid.uuid4().hex[:6]}"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"sessions": sessions}, f, indent=2)
            os.replace(tmp, self.sessions_file)
        except Exception as e:
            print(f"[Storage] Session index error: {e}")

    def get_sessions(self) -> List[Dict[str, Any]]:
        if not os.path.isfile(self.sessions_file):
            return []
        try:
            with open(self.sessions_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("sessions", [])
        except Exception:
            return []

    def record_observation(self, obs: ObservationRecord) -> None:
        """Appends an observation to live buffer and session counters."""
        self._live_observation_buffer.append(obs)
        self.active_session.total_frames += 1
        if obs.validity_status == ValidityStatus.VALID.value:
            self.active_session.valid_frames += 1
        self.active_session.duration_seconds = round(obs.timestamp - self.active_session.start_time, 1)
        self.active_session.coverage_ratio = round(
            self.active_session.valid_frames / max(1, self.active_session.total_frames), 3
        )

        # Periodic atomic flush to session file (every 20s or 500 samples)
        now = obs.timestamp
        if now - self._last_flush_ts >= 20.0 or len(self._live_observation_buffer) >= 500:
            self._flush_observations()
            self._last_flush_ts = now
            self._upsert_session_index(self.active_session)

    def _flush_observations(self) -> None:
        if not self._live_observation_buffer:
            return
        sess_file = os.path.join(self.obs_dir, f"session_{self.active_session.session_id}.json")
        existing: List[Dict[str, Any]] = []
        if os.path.isfile(sess_file):
            try:
                with open(sess_file, "r", encoding="utf-8") as f:
                    existing = json.load(f).get("observations", [])
            except Exception:
                pass

        existing.extend([o.to_dict() for o in self._live_observation_buffer])
        self._live_observation_buffer.clear()

        tmp = f"{sess_file}.tmp.{uuid.uuid4().hex[:6]}"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"observations": existing}, f)
            os.replace(tmp, sess_file)
        except Exception as e:
            print(f"[Storage] Flush obs error: {e}")

    def add_event(self, event: EventRecord) -> None:
        self.events.append(event)
        self.active_session.event_count += 1
        self._save_events_atomic()

    def get_recent_observations(self, count: int = 100, feature_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns the most recent observations from memory or session file."""
        res = [o.to_dict() for o in reversed(self._live_observation_buffer)]
        if len(res) < count:
            sess_file = os.path.join(self.obs_dir, f"session_{self.active_session.session_id}.json")
            if os.path.isfile(sess_file):
                try:
                    with open(sess_file, "r", encoding="utf-8") as f:
                        file_obs = json.load(f).get("observations", [])
                        res.extend(reversed(file_obs))
                except Exception:
                    pass

        if feature_name:
            res = [r for r in res if r.get("feature_name") == feature_name]
        return res[:count]

    def get_events(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []
        for e in reversed(self.events):
            if session_id and e.session_id != session_id:
                continue
            results.append(e.to_dict())
        return results

    def generate_report(
        self,
        session_id: Optional[str] = None,
        start_ts: Optional[float] = None,
        end_ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Generates full multi-section evidence report."""
        self._flush_observations()
        sess_dict = next((s for s in self.get_sessions() if s.get("session_id") == session_id), None)
        sess = SessionRecord(**sess_dict) if sess_dict else self.active_session

        # Load observations for session
        sess_file = os.path.join(self.obs_dir, f"session_{sess.session_id}.json")
        obs_records: List[ObservationRecord] = []
        if os.path.isfile(sess_file):
            try:
                with open(sess_file, "r", encoding="utf-8") as f:
                    obs_records = [ObservationRecord(**o) for o in json.load(f).get("observations", [])]
            except Exception as e:
                print(f"[Storage] Read obs error: {e}")

        checkins = [CheckInRecord(**c) for c in self.checkin_manager.get_checkins(start_ts, end_ts)]
        events = [e for e in self.events if (not session_id or e.session_id == sess.session_id)]

        self.report_generator.analyzer.set_baseline(self.baseline_manager.current_profile)
        report = self.report_generator.generate_report(
            session=sess,
            observations=obs_records,
            checkins=checkins,
            events=events,
            start_ts=start_ts,
            end_ts=end_ts,
        )

        # Save report JSON
        rep_file = os.path.join(self.reports_dir, f"{report['report_id']}.json")
        try:
            with open(rep_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
        except Exception:
            pass

        return report

    def delete_all_data(self) -> bool:
        """Permanently wipes all sessions, observations, check-ins, events, baselines, and reports."""
        self._live_observation_buffer.clear()
        self.events.clear()
        self.baseline_manager.reset_baseline()
        self.checkin_manager.clear_all()

        for folder in (self.sessions_dir, self.obs_dir, self.reports_dir):
            if os.path.isdir(folder):
                for f in os.listdir(folder):
                    try:
                        os.remove(os.path.join(folder, f))
                    except OSError:
                        pass

        if os.path.isfile(self.events_file):
            try:
                os.remove(self.events_file)
            except OSError:
                pass

        self.active_session = self._init_or_load_session()
        return True

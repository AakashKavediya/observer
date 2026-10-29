"""
observer_engine.history
Manages persistent local observation history without intrusive alerts or popups:
- Deduplicates continuous episodes of task paralysis / overload.
- Persists structured observation records atomically as JSON.
- Provides filtering by date range, state, and user review status.
- Supports user correction / feedback: 'useful', 'incorrect', 'uncertain'.
- Generates transparent, evidence-backed reports with CSV export.
- 100% local, privacy-first: zero video frames, screenshots, or raw keystrokes are ever stored.
"""

import os
import json
import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional


@dataclass
class ObservationContributingFeature:
    feature: str
    measured_value: str
    baseline_value: str
    deviation: str
    window: str
    valid: bool
    contribution: str


@dataclass
class ObservationRecord:
    event_id: str
    start_ts: float
    end_ts: float
    duration_seconds: float
    state: str
    score: float
    scoring_method: str
    contributing_features: List[ObservationContributingFeature]
    evidence_strength: str
    data_quality_status: str
    qualification_reason: str
    user_review: Optional[str] = None  # "useful" | "incorrect" | "uncertain"
    user_notes: Optional[str] = None
    created_at_iso: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["created_at_iso"] = self.created_at_iso or datetime.fromtimestamp(self.start_ts, tz=timezone.utc).isoformat()
        return d


class HistoryManager:
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or self._resolve_storage_path()
        self.records: List[ObservationRecord] = self._load()

        # Active episode tracking for deduplication
        self.active_episode: Optional[ObservationRecord] = None
        self.last_flush_ts: float = 0.0

    @staticmethod
    def _resolve_storage_path() -> str:
        home = os.path.expanduser("~")
        if os.name == "nt":
            base = os.environ.get("LOCALAPPDATA", os.path.join(home, "AppData", "Local"))
        elif sys_platform := getattr(os, "uname", None):
            base = os.path.join(home, "Library", "Application Support") if sys_platform().sysname == "Darwin" else os.path.join(home, ".local", "share")
        else:
            base = os.path.join(home, ".observer")

        app_dir = os.path.join(base, "Observer")
        return os.path.join(app_dir, "observations_history.json")

    def _load(self) -> List[ObservationRecord]:
        if not os.path.isfile(self.storage_path):
            return []
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            records = []
            for item in data.get("records", []):
                feats = [
                    ObservationContributingFeature(**f)
                    for f in item.get("contributing_features", [])
                ]
                rec = ObservationRecord(
                    event_id=item["event_id"],
                    start_ts=float(item["start_ts"]),
                    end_ts=float(item["end_ts"]),
                    duration_seconds=float(item.get("duration_seconds", item["end_ts"] - item["start_ts"])),
                    state=item["state"],
                    score=float(item.get("score", 0.0)),
                    scoring_method=item.get("scoring_method", ""),
                    contributing_features=feats,
                    evidence_strength=item.get("evidence_strength", ""),
                    data_quality_status=item.get("data_quality_status", "valid"),
                    qualification_reason=item.get("qualification_reason", ""),
                    user_review=item.get("user_review"),
                    user_notes=item.get("user_notes"),
                    created_at_iso=item.get("created_at_iso", ""),
                )
                records.append(rec)
            return records
        except Exception as e:
            print(f"[History Warning] Could not load observation history: {e}")
            return []

    def save_atomic(self) -> bool:
        try:
            dir_name = os.path.dirname(self.storage_path)
            os.makedirs(dir_name, exist_ok=True)
            tmp_path = f"{self.storage_path}.tmp_{uuid.uuid4().hex[:8]}"

            data = {
                "schema_version": 1,
                "updated_at_iso": datetime.now(timezone.utc).isoformat(),
                "total_records": len(self.records),
                "records": [r.to_dict() for r in self.records],
            }

            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, self.storage_path)
            return True
        except Exception as e:
            print(f"[History Error] Failed atomic write to {self.storage_path}: {e}")
            if os.path.isfile(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            return False

    def update_or_record_episode(
        self,
        state: str,
        score: float,
        features: List[Dict[str, Any]],
        evidence_strength: str,
        qualification_reason: str,
        data_quality: str = "valid",
        now: Optional[float] = None,
    ) -> Optional[ObservationRecord]:
        """
        Deduplicates continuous periods of the same state into a single cohesive episode.
        Only records states of interest (PARALYSIS_LIKELY, OVERLOAD_LIKELY, or significant shifts).
        """
        now = now or time.time()

        # Only qualify notable episodes for permanent evidence history
        if state not in ("PARALYSIS_LIKELY", "OVERLOAD_LIKELY"):
            # If an active episode was underway, finalize and close it
            if self.active_episode is not None:
                closed = self._finalize_active_episode(now)
                return closed
            return None

        conv_features = [
            ObservationContributingFeature(
                feature=f.get("feature", "unknown"),
                measured_value=str(f.get("measured_value", "")),
                baseline_value=str(f.get("baseline_value", "")),
                deviation=str(f.get("deviation", "")),
                window=str(f.get("window", "")),
                valid=bool(f.get("valid", True)),
                contribution=str(f.get("contribution", "")),
            )
            for f in features
        ]

        if self.active_episode is None:
            # Start new episode
            event_id = f"obs_{int(now)}_{uuid.uuid4().hex[:6]}"
            self.active_episode = ObservationRecord(
                event_id=event_id,
                start_ts=now,
                end_ts=now,
                duration_seconds=0.0,
                state=state,
                score=score,
                scoring_method="Weighted evidence formula (EMA smoothed + dwell gate)",
                contributing_features=conv_features,
                evidence_strength=evidence_strength,
                data_quality_status=data_quality,
                qualification_reason=qualification_reason,
                created_at_iso=datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            )
            self.last_flush_ts = now
            return None
        else:
            # Check if active episode matches current state
            if self.active_episode.state == state:
                # Update continuous duration
                self.active_episode.end_ts = now
                self.active_episode.duration_seconds = max(0.0, now - self.active_episode.start_ts)
                self.active_episode.score = max(self.active_episode.score, score)
                # Keep latest features
                self.active_episode.contributing_features = conv_features

                # Periodic save during sustained episode (every 30s)
                if now - self.last_flush_ts >= 30.0:
                    self.last_flush_ts = now
                    # Update in records or append
                    self._upsert_active_record()
                    self.save_atomic()
                return None
            else:
                # State changed from one notable state to another
                closed = self._finalize_active_episode(now)
                # Start new one for the new state
                self.update_or_record_episode(state, score, features, evidence_strength, qualification_reason, data_quality, now)
                return closed

    def _upsert_active_record(self) -> None:
        if not self.active_episode:
            return
        found = False
        for i, rec in enumerate(self.records):
            if rec.event_id == self.active_episode.event_id:
                self.records[i] = self.active_episode
                found = True
                break
        if not found:
            self.records.append(self.active_episode)

    def _finalize_active_episode(self, now: float) -> Optional[ObservationRecord]:
        if not self.active_episode:
            return None
        self.active_episode.end_ts = now
        self.active_episode.duration_seconds = max(1.0, now - self.active_episode.start_ts)
        completed = self.active_episode
        self._upsert_active_record()
        self.active_episode = None
        self.save_atomic()
        return completed

    def get_history(
        self,
        filter_state: Optional[str] = None,
        start_ts: Optional[float] = None,
        end_ts: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Returns filtered list of observation records sorted newest first."""
        results = []
        for r in reversed(self.records):
            if filter_state and filter_state.upper() != "ALL" and r.state != filter_state:
                continue
            if start_ts and r.start_ts < start_ts:
                continue
            if end_ts and r.end_ts > end_ts:
                continue
            results.append(r.to_dict())
        return results

    def update_feedback(self, event_id: str, feedback: str, notes: Optional[str] = None) -> bool:
        """Sets user review status: 'useful', 'incorrect', or 'uncertain'."""
        for r in self.records:
            if r.event_id == event_id:
                r.user_review = feedback
                if notes is not None:
                    r.user_notes = notes
                self.save_atomic()
                return True
        return False

    def delete_observation(self, event_id: str) -> bool:
        """Deletes a single observation record."""
        orig_len = len(self.records)
        self.records = [r for r in self.records if r.event_id != event_id]
        if len(self.records) < orig_len:
            self.save_atomic()
            return True
        return False

    def clear_all(self) -> bool:
        """Wipes all observation history."""
        self.records.clear()
        self.active_episode = None
        return self.save_atomic()

    def generate_report(
        self, start_ts: Optional[float] = None, end_ts: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Compiles an evidence-backed report derived exclusively from real stored records.
        Includes summary metrics, state distribution, feature trends, and CSV export text.
        """
        filtered = [
            r for r in self.records
            if (not start_ts or r.start_ts >= start_ts) and (not end_ts or r.end_ts <= end_ts)
        ]

        total_obs = len(filtered)
        if total_obs == 0:
            return {
                "total_observations": 0,
                "message": "No observation records found for the selected period.",
                "state_distribution": {},
                "records": [],
                "csv_export": "event_id,created_at,state,duration_seconds,score,evidence_strength,user_review\n",
            }

        state_dist: Dict[str, int] = {}
        total_duration = 0.0
        review_dist: Dict[str, int] = {"useful": 0, "incorrect": 0, "uncertain": 0, "unreviewed": 0}

        csv_lines = [
            "event_id,created_at,state,duration_seconds,score,evidence_strength,user_review,qualification_reason"
        ]

        for r in filtered:
            state_dist[r.state] = state_dist.get(r.state, 0) + 1
            total_duration += r.duration_seconds

            rev = r.user_review or "unreviewed"
            review_dist[rev] = review_dist.get(rev, 0) + 1

            csv_lines.append(
                f'"{r.event_id}","{r.created_at_iso}","{r.state}",{r.duration_seconds:.1f},'
                f'{r.score:.3f},"{r.evidence_strength}","{rev}","{r.qualification_reason}"'
            )

        start_date_str = datetime.fromtimestamp(filtered[0].start_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        end_date_str = datetime.fromtimestamp(filtered[-1].end_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        report = {
            "reporting_period": f"{start_date_str} to {end_date_str}",
            "total_observations": total_obs,
            "total_episode_duration_seconds": round(total_duration, 1),
            "state_distribution": state_dist,
            "user_feedback_summary": review_dist,
            "records": [r.to_dict() for r in filtered],
            "csv_export": "\n".join(csv_lines),
            "limitations_notice": (
                "Non-clinical notice: This report summarizes computational estimates derived from webcam "
                "landmark tracking and input idle duration relative to your personalized baseline. "
                "These metrics do not constitute a medical, psychiatric, or psychological diagnosis."
            ),
        }
        return report

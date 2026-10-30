"""
observer_engine.health_tech.checkins
Manages optional, non-intrusive user check-ins.

Records:
- Perceived Energy (1-5)
- Perceived Effort (1-5)
- Task Difficulty (1-5)
- Feeling Stuck (Boolean)
- Discomfort (1-5)
- Self-Reported Stress (1-5)
- Sleep Quality (1-5)
- Optional brief context note

Health-Tech Governance:
Check-ins are subjective self-reports, clearly differentiated from objective camera
measurements. They are never interpreted as clinical symptoms or medical diagnoses.
"""

import os
import json
import time
import uuid
from typing import Optional, List, Dict, Any
from observer_engine.health_tech.schema import CheckInRecord


class CheckInManager:
    def __init__(self, storage_dir: Optional[str] = None):
        home = os.path.expanduser("~")
        self.storage_dir = storage_dir or os.path.join(home, ".observer", "checkins")
        os.makedirs(self.storage_dir, exist_ok=True)
        self.file_path = os.path.join(self.storage_dir, "user_checkins.json")
        self.checkins: List[CheckInRecord] = self._load()

    def _load(self) -> List[CheckInRecord]:
        if not os.path.isfile(self.file_path):
            return []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [CheckInRecord(**item) for item in data.get("checkins", [])]
        except Exception as e:
            print(f"[CheckInManager] Load error: {e}")
            return []

    def save_atomic(self) -> bool:
        tmp = f"{self.file_path}.tmp.{uuid.uuid4().hex[:6]}"
        try:
            data = {"version": "2.0.0", "checkins": [c.to_dict() for c in self.checkins]}
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self.file_path)
            return True
        except Exception as e:
            print(f"[CheckInManager] Save error: {e}")
            if os.path.isfile(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            return False

    def record_checkin(
        self,
        energy: Optional[int] = None,
        effort: Optional[int] = None,
        task_difficulty: Optional[int] = None,
        feeling_stuck: Optional[bool] = None,
        discomfort: Optional[int] = None,
        stress: Optional[int] = None,
        sleep_quality: Optional[int] = None,
        notes: Optional[str] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> CheckInRecord:
        """Records a new optional self-report checkin."""
        rec = CheckInRecord(
            checkin_id=str(uuid.uuid4()),
            session_id=session_id,
            timestamp=time.time(),
            energy=energy,
            effort=effort,
            task_difficulty=task_difficulty,
            feeling_stuck=feeling_stuck,
            discomfort=discomfort,
            stress=stress,
            sleep_quality=sleep_quality,
            notes=notes.strip() if notes else None,
            task_id=task_id,
        )
        self.checkins.append(rec)
        self.save_atomic()
        return rec

    def get_checkins(
        self,
        start_ts: Optional[float] = None,
        end_ts: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Returns chronological list of checkins."""
        res = []
        for c in reversed(self.checkins):
            if start_ts and c.timestamp < start_ts:
                continue
            if end_ts and c.timestamp > end_ts:
                continue
            res.append(c.to_dict())
        return res

    def clear_all(self) -> bool:
        self.checkins.clear()
        return self.save_atomic()

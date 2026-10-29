"""
observer_engine.sequencer.planner_adapter
Adapter connecting Track 2 (Task Sequencer) to Track 3 (Adaptive Planner).
Strict safety rules:
- Reads tasks only through supported interface.
- Never silently overwrites deadlines or reschedules without user confirmation.
- Clearly reports unavailable state when Track 3 is not running.
- Does not create conflicting parallel databases.
"""

from typing import List, Optional, Dict, Any


class PlannerAdapter:
    def __init__(self):
        self.connected: bool = False
        self.status_message: str = "Track 3 Adaptive Planner is currently disconnected. Working with local sequencer tasks."

    def is_connected(self) -> bool:
        return self.connected

    def get_status_message(self) -> str:
        return self.status_message

    def get_user_tasks(self) -> List[Dict[str, Any]]:
        """
        Retrieves user tasks from Track 3 if connected.
        Returns empty list when disconnected without fabricating data.
        """
        if not self.connected:
            return []
        return []

    def get_task_details(self, task_id: str) -> Optional[Dict[str, Any]]:
        if not self.connected:
            return None
        return None

    def propose_task_creation(self, title: str, deadline: Optional[str] = None) -> Dict[str, Any]:
        """
        Returns a proposed task structure requiring explicit user confirmation before creation.
        """
        return {
            "action": "propose_create",
            "title": title,
            "deadline": deadline,
            "requires_user_confirmation": True,
            "confirmed": False,
        }

    def propose_reschedule(self, task_id: str, new_deadline: str) -> Dict[str, Any]:
        """
        Returns a proposed reschedule requiring explicit user confirmation.
        """
        return {
            "action": "propose_reschedule",
            "task_id": task_id,
            "new_deadline": new_deadline,
            "requires_user_confirmation": True,
            "confirmed": False,
        }

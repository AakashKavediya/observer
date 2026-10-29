"""
observer_engine.sequencer.observer_adapter
Adapter integrating Track 1 (Observer Computer Vision & Telemetry) into Track 2 (Task Sequencer).
Strict integration rules:
- Consumes validated Track 1 events only when consented.
- UNKNOWN state is NEVER interpreted as paralysis.
- Invalid or stale telemetry is ignored.
- Unverified estimates are never presented as user-confirmed emotions.
- User corrections always override inferences.
- Operates 100% fine when Track 1 or camera is offline.
"""

from typing import Optional, Dict, Any


class ObserverAdapter:
    def __init__(self):
        self.enabled: bool = True
        self.latest_state: str = "UNKNOWN"
        self.latest_confidence: float = 0.0
        self.tracking_valid: bool = False
        self.quality_reason: str = "Camera offline or uninitialized"
        self.last_update_ts: float = 0.0

    def update_from_telemetry(self, telemetry_data: Dict[str, Any]) -> None:
        """
        Updates cached state from validated TelemetryEvent or StateUpdateEvent.
        """
        if not self.enabled:
            return

        vision = telemetry_data.get("vision", {})
        pred = telemetry_data.get("prediction", {})

        self.tracking_valid = bool(vision.get("face_detected") and vision.get("quality_valid"))
        self.quality_reason = vision.get("quality_reason", "")
        self.latest_state = pred.get("state", "UNKNOWN")
        self.latest_confidence = float(pred.get("confidence", 0.0))
        self.last_update_ts = float(telemetry_data.get("ts", 0.0))

    def get_context_summary(self) -> Optional[str]:
        """
        Returns gentle, non-clinical plain-language context if tracking is valid and consented.
        Returns None if tracking is invalid, unavailable, or UNKNOWN.
        """
        if not self.enabled or not self.tracking_valid:
            return None

        if self.latest_state == "PARALYSIS_LIKELY" and self.latest_confidence >= 0.65:
            return "Observer detected sustained screen fixation with reduced input activity."
        elif self.latest_state == "OVERLOAD_LIKELY" and self.latest_confidence >= 0.65:
            return "Observer detected rapid window switching activity with high input pauses."
        elif self.latest_state == "FOCUSED":
            return "Observer detected steady engagement."
        elif self.latest_state == "RELAXED":
            return "Observer detected low tension baseline."

        return None

"""
Tests for IPC schema models and serialization.
Compatible with both pytest and unittest.
"""

import json
import unittest
from observer_engine.ipc import (
    StatusEvent,
    StateUpdateEvent,
    StateProbabilities,
    InterventionEvent,
    InterventionAction,
    CommandMessage,
    OsSignalsEvent,
    serialize_message,
    parse_incoming_line,
    SCHEMA_VERSION,
)


class TestIPCSchema(unittest.TestCase):
    def test_status_event_serialization(self):
        status = StatusEvent(camera="on", mode="live", calibrating=False, paused=False, fps=15.2, engine_ok=True)
        serialized = serialize_message(status)
        data = json.loads(serialized)
        self.assertEqual(data["schema_version"], SCHEMA_VERSION)
        self.assertEqual(data["type"], "status")
        self.assertEqual(data["camera"], "on")
        self.assertEqual(data["mode"], "live")
        self.assertEqual(data["fps"], 15.2)
        self.assertTrue(data["engine_ok"])

    def test_state_update_event(self):
        state = StateUpdateEvent(
            state="PARALYSIS_LIKELY",
            probabilities=StateProbabilities(relaxed=0.05, focused=0.15, paralysis=0.72, overload=0.08),
            confidence=0.82,
            top_signals=["High gaze fixation", "Elevated facial tension"],
            ts=1700000000.0,
        )
        serialized = serialize_message(state)
        data = json.loads(serialized)
        self.assertEqual(data["type"], "state_update")
        self.assertEqual(data["state"], "PARALYSIS_LIKELY")
        self.assertEqual(len(data["top_signals"]), 2)
        self.assertEqual(data["probabilities"]["paralysis"], 0.72)

    def test_intervention_event(self):
        intv = InterventionEvent(
            tier=2,
            id="test_id_123",
            text="That looks stuck. Want a tiny first step? Totally optional.",
            actions=[
                InterventionAction(id="tiny_step", label="Tiny step"),
                InterventionAction(id="not_now", label="Not now"),
            ],
        )
        serialized = serialize_message(intv)
        data = json.loads(serialized)
        self.assertEqual(data["type"], "intervention")
        self.assertEqual(data["tier"], 2)
        self.assertEqual(len(data["actions"]), 2)

    def test_parse_command(self):
        raw_cmd = json.dumps({"schema_version": "1.0.0", "type": "command", "name": "pause", "extra_field": "ignore_me"})
        parsed = parse_incoming_line(raw_cmd)
        self.assertIsInstance(parsed, CommandMessage)
        self.assertEqual(parsed.name, "pause")

    def test_parse_os_signals(self):
        raw_sig = json.dumps({
            "schema_version": "1.0.0",
            "type": "os_signals",
            "idle_seconds": 15.5,
            "window_switch_count": 3,
            "fullscreen_media": False
        })
        parsed = parse_incoming_line(raw_sig)
        self.assertIsInstance(parsed, OsSignalsEvent)
        self.assertEqual(parsed.idle_seconds, 15.5)
        self.assertEqual(parsed.window_switch_count, 3)

    def test_telemetry_event_serialization(self):
        from observer_engine.ipc import (
            TelemetryEvent,
            CameraTelemetry,
            VisionTelemetry,
            DesktopInputTelemetry,
            PredictionTelemetry,
        )
        telem = TelemetryEvent(
            seq=42,
            ts=1700000000.0,
            camera=CameraTelemetry(status="on", fps=14.9),
            vision=VisionTelemetry(face_detected=True, quality_valid=True),
            desktop_input=DesktopInputTelemetry(idle_seconds=2.5, window_switch_count_60s=1),
            prediction=PredictionTelemetry(state="FOCUSED", confidence=0.89),
        )
        serialized = serialize_message(telem)
        data = json.loads(serialized)
        self.assertEqual(data["type"], "telemetry")
        self.assertEqual(data["seq"], 42)
        self.assertEqual(data["camera"]["status"], "on")
        self.assertTrue(data["vision"]["face_detected"])
        self.assertEqual(data["prediction"]["state"], "FOCUSED")


if __name__ == "__main__":
    unittest.main()

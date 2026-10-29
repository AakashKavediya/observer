"""
observer_engine.fake_engine
A realistic mock engine for testing IPC, UI rendering, demo walkthroughs,
and end-to-end integration without requiring a live webcam.
"""

import sys
import time
import threading
from typing import Optional
from observer_engine.ipc import (
    StatusEvent,
    CalibrationProgressEvent,
    StateUpdateEvent,
    StateProbabilities,
    InterventionEvent,
    InterventionAction,
    CommandMessage,
    OsSignalsEvent,
    serialize_message,
    parse_incoming_line,
)


class FakeEngine:
    def __init__(self):
        self.running = True
        self.paused = False
        self.calibrating = False
        self.demo_mode = True
        self.demo_tick = 0
        self.last_intervention_id: Optional[str] = None
        self.os_idle_seconds: float = 0.0
        self.os_window_switches: int = 0

    def emit(self, event) -> None:
        """Prints serialized NDJSON line to stdout and flushes immediately."""
        line = serialize_message(event)
        try:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
        except IOError:
            self.running = False

    def handle_command(self, cmd: CommandMessage) -> None:
        if cmd.name == "pause":
            self.paused = True
            self.emit(StatusEvent(camera="off", mode="demo", calibrating=self.calibrating, paused=True, fps=0.0))
        elif cmd.name == "resume":
            self.paused = False
            self.emit(StatusEvent(camera="off", mode="demo", calibrating=self.calibrating, paused=False, fps=15.0))
        elif cmd.name == "start_calibration":
            self.start_simulated_calibration()
        elif cmd.name == "cancel_calibration":
            self.calibrating = False
            self.emit(StatusEvent(camera="off", mode="demo", calibrating=False, paused=self.paused, fps=15.0))
        elif cmd.name == "start_demo":
            self.demo_mode = True
            self.demo_tick = 0
            self.emit(StatusEvent(camera="off", mode="demo", calibrating=False, paused=False, fps=15.0))
        elif cmd.name == "stop_demo":
            self.demo_mode = False
            self.emit(StatusEvent(camera="off", mode="demo", calibrating=False, paused=False, fps=0.0))
        elif cmd.name == "shutdown":
            self.running = False
        elif cmd.name == "feedback":
            pass  # Feedback acknowledged
        elif cmd.name == "delete_all_data":
            pass

    def handle_os_signals(self, signals: OsSignalsEvent) -> None:
        self.os_idle_seconds = signals.idle_seconds
        self.os_window_switches = signals.window_switch_count

    def start_simulated_calibration(self) -> None:
        self.calibrating = True

        def run_calib():
            for pct in range(0, 51, 10):
                if not self.calibrating or not self.running:
                    return
                self.emit(CalibrationProgressEvent(phase="relaxed_baseline", percent=float(pct * 2)))
                time.sleep(0.4)
            for pct in range(50, 101, 10):
                if not self.calibrating or not self.running:
                    return
                self.emit(CalibrationProgressEvent(phase="normal_work", percent=float(pct)))
                time.sleep(0.4)
            self.calibrating = False
            self.emit(CalibrationProgressEvent(phase="complete", percent=100.0))
            self.emit(StatusEvent(camera="off", mode="demo", calibrating=False, paused=self.paused, fps=15.0))

        threading.Thread(target=run_calib, daemon=True).start()

    def run_stdin_listener(self) -> None:
        while self.running:
            try:
                line = sys.stdin.readline()
                if not line:
                    self.running = False
                    break
                parsed = parse_incoming_line(line)
                if isinstance(parsed, CommandMessage):
                    self.handle_command(parsed)
                elif isinstance(parsed, OsSignalsEvent):
                    self.handle_os_signals(parsed)
            except Exception:
                break

    def run(self) -> None:
        # Start background stdin listener
        t = threading.Thread(target=self.run_stdin_listener, daemon=True)
        t.start()

        # Emit initial startup status (Demo mode)
        self.emit(StatusEvent(camera="off", mode="demo", calibrating=False, paused=False, fps=15.0, engine_ok=True))

        while self.running:
            time.sleep(1.0)
            if self.paused or self.calibrating:
                continue

            now = time.time()
            if self.demo_mode:
                self.demo_tick = (self.demo_tick + 1) % 32
                t = self.demo_tick

                if t <= 6:
                    # Stage 1: Relaxed
                    self.emit(StateUpdateEvent(
                        state="RELAXED",
                        probabilities=StateProbabilities(relaxed=0.88, focused=0.08, paralysis=0.02, overload=0.02),
                        confidence=0.85,
                        top_signals=["Regular blink pattern", "Relaxed facial musculature", "Smooth gaze shifts"],
                        ts=now
                    ))
                elif t <= 14:
                    # Stage 2: Focused work
                    self.emit(StateUpdateEvent(
                        state="FOCUSED",
                        probabilities=StateProbabilities(relaxed=0.10, focused=0.82, paralysis=0.05, overload=0.03),
                        confidence=0.89,
                        top_signals=["Active input activity", "Engaged gaze distribution", "Normal tension levels"],
                        ts=now
                    ))
                elif t <= 21:
                    # Stage 3: Paralysis signs emerging
                    self.emit(StateUpdateEvent(
                        state="PARALYSIS_LIKELY",
                        probabilities=StateProbabilities(relaxed=0.04, focused=0.12, paralysis=0.76, overload=0.08),
                        confidence=0.78,
                        top_signals=["Prolonged gaze fixation on cursor", "Elevated brow furrow tension", "Unbroken 42s input pause"],
                        ts=now
                    ))
                elif t == 22:
                    # Stage 4: Gentle intervention triggered
                    intv_id = f"demo_intv_{int(now)}"
                    self.last_intervention_id = intv_id
                    self.emit(InterventionEvent(
                        tier=2,
                        id=intv_id,
                        text="That looks stuck. Want a tiny first step? Totally optional.",
                        actions=[
                            InterventionAction(id="tiny_step", label="Tiny step"),
                            InterventionAction(id="rest_bit", label="Rest a bit"),
                            InterventionAction(id="not_now", label="Not now")
                        ]
                    ))
                else:
                    # Stage 5: Recovery
                    self.emit(StateUpdateEvent(
                        state="RELAXED",
                        probabilities=StateProbabilities(relaxed=0.78, focused=0.15, paralysis=0.05, overload=0.02),
                        confidence=0.84,
                        top_signals=["Gentle breathing rhythm", "Facial tension released", "Disengaged from freeze"],
                        ts=now
                    ))
            else:
                # Default steady state
                self.emit(StateUpdateEvent(
                    state="FOCUSED",
                    probabilities=StateProbabilities(relaxed=0.15, focused=0.78, paralysis=0.04, overload=0.03),
                    confidence=0.91,
                    top_signals=["Active work rhythm", "Balanced blink cadence"],
                    ts=now
                ))

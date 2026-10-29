"""
observer_engine.main
Core entry point for the Python sidecar.
CLI Arguments:
  --live            Run live pipeline with real camera (DEFAULT)
  --demo            Run synthetic timeline for testing UI without webcam
  --selftest        Run 5-second camera diagnostic and exit
  --debug-overlay   Dev only: displays live OpenCV visual debug window
  --simulate PATH   Replay video file through the real pipeline
  --model PATH      Explicit path to face_landmarker.task
"""

import os
import sys

# Ensure package root is in sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

import time
import base64
import argparse
import threading
from typing import Optional, List
import cv2
import numpy as np

from observer_engine.config import CONFIG
from observer_engine.camera import CameraCapture
from observer_engine.landmarks import FaceLandmarkerWrapper
from observer_engine.features import FeatureExtractor, FrameFeatures, WindowedFeatures
from observer_engine.baseline import BaselineManager
from observer_engine.state_engine import StateEngine
from observer_engine.intervention import InterventionManager
from observer_engine.history import HistoryManager
from observer_engine.fake_engine import FakeEngine
from observer_engine.sequencer.service import TaskSequencerService
from observer_engine.sequencer.models import UserPreferences
from observer_engine.gaze_mouse import GazeMouseTracker
from observer_engine.ipc import (
    StatusEvent,
    GazeStatusEvent,
    GazeCalibrationEvent,
    GazeDiagnosticEvent,
    GazeCursorMoveEvent,
    StateUpdateEvent,
    StateProbabilities,
    CalibrationProgressEvent,
    ErrorEvent,
    CommandMessage,
    OsSignalsEvent,
    TelemetryEvent,
    PipelineDiagnostics,
    CameraTelemetry,
    VisionTelemetry,
    EarTelemetry,
    BlinkTelemetry,
    GazeTelemetry,
    TensionTelemetry,
    HeadPoseTelemetry,
    DesktopInputTelemetry,
    PredictionTelemetry,
    ObservationItemEvent,
    HistoryListEvent,
    ReportGeneratedEvent,
    SequencerStatusEvent,
    SequencerResponseEvent,
    SequencerDiagnosticsEvent,
    SequencerConversationsListEvent,
    SequencerConversationLoadedEvent,
    serialize_message,
    parse_incoming_line,
)


def emit_ipc(event) -> None:
    """Emits serialized NDJSON line to stdout."""
    line = serialize_message(event)
    try:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except IOError:
        pass


def run_selftest(device_index: int = 0) -> int:
    """
    Self-test harness: runs camera for 5.0 seconds.
    Measures FPS, face detection %, blink count.
    Prints a clean, honest PASS/FAIL summary and exits.
    """
    print("========================================")
    print("Observer Real Camera Diagnostic (5s)")
    print("========================================")

    # 1. Check Model
    model_path = FaceLandmarkerWrapper._resolve_model_path()
    if not os.path.isfile(model_path):
        print(f"Model File:        FAIL (Not found at {model_path})")
        print("RESULT: FAIL")
        return 1
    print(f"Model File:        PASS ({os.path.basename(model_path)})")

    # 2. Check Camera
    backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
    cap = cv2.VideoCapture(device_index, backend)
    if not cap.isOpened():
        cap = cv2.VideoCapture(device_index)

    if not cap.isOpened():
        print("Camera Open:       FAIL (Device not detected or blocked by OS)")
        print("RESULT: FAIL (No Camera)")
        return 1

    print("Camera Open:       PASS")

    try:
        landmarker = FaceLandmarkerWrapper(model_path=model_path)
        feature_extractor = FeatureExtractor()
    except Exception as e:
        print(f"Pipeline Init:     FAIL ({e})")
        cap.release()
        return 1

    frames_captured = 0
    faces_detected = 0
    start_time = time.time()
    test_duration = 5.0

    print("Running diagnostic capture for 5 seconds... (please look at camera)")

    while time.time() - start_time < test_duration:
        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(0.05)
            continue

        frames_captured += 1
        now = time.time()

        res = landmarker.process_frame(frame)
        if res is not None:
            faces_detected += 1
            feature_extractor.extract_frame_features(
                frame_bgr=frame,
                landmarks=res.landmarks,
                blendshapes=res.blendshapes,
                timestamp=now,
            )
        else:
            feature_extractor.extract_frame_features(
                frame_bgr=frame,
                landmarks=None,
                blendshapes=None,
                timestamp=now,
            )

        time.sleep(0.04)  # ~20 FPS

    elapsed = time.time() - start_time
    cap.release()
    landmarker.close()

    fps = frames_captured / elapsed if elapsed > 0 else 0.0
    face_pct = (faces_detected / frames_captured * 100.0) if frames_captured > 0 else 0.0
    blinks = feature_extractor.blink_count_total

    print("----------------------------------------")
    print(f"Frames Captured:   {frames_captured} ({fps:.1f} FPS)")
    print(f"Face Detected:     {faces_detected}/{frames_captured} ({face_pct:.1f}%)")
    print(f"Blinks Counted:    {blinks}")
    print("========================================")

    if frames_captured > 10:
        print("RESULT: PASS")
        return 0
    else:
        print("RESULT: FAIL (Insufficient frames captured)")
        return 1


def run_simulation(video_path: str, model_path: Optional[str] = None) -> int:
    """
    Offline video simulation harness:
    Processes an input video file through the real landmark & feature pipeline.
    Writes ONLY a CSV of numeric features for validation analysis.
    Zero image frames or video buffers are persisted.
    """
    if not os.path.isfile(video_path):
        print(f"[Error] Simulation video not found: {video_path}", file=sys.stderr)
        return 1

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[Error] Failed to open video file: {video_path}", file=sys.stderr)
        return 1

    output_csv = video_path + ".features.csv"
    print(f"=== Replaying Video Through Real Pipeline: {video_path} ===")
    print(f"Output numeric features: {output_csv}")

    landmarker = FaceLandmarkerWrapper(model_path=model_path)
    extractor = FeatureExtractor()

    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    frame_interval = 1.0 / fps

    total_frames = 0
    valid_frames = 0
    t = 0.0

    import csv
    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp_s", "valid", "ear", "is_blink",
            "pitch_deg", "yaw_deg", "roll_deg",
            "gaze_x", "gaze_y", "tension_index",
            "dispersion_4s", "dispersion_30s", "blink_rate_60s"
        ])

        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            total_frames += 1
            t += frame_interval

            res = landmarker.process_frame(frame)
            if res is not None:
                valid_frames += 1
                feat = extractor.extract_frame_features(
                    frame_bgr=frame,
                    landmarks=res.landmarks,
                    blendshapes=res.blendshapes,
                    timestamp=t,
                )
            else:
                feat = extractor.extract_frame_features(
                    frame_bgr=frame,
                    landmarks=None,
                    blendshapes=None,
                    timestamp=t,
                )

            win = extractor.aggregate_windows(t)

            writer.writerow([
                f"{t:.3f}", int(feat.valid), f"{feat.ear:.4f}", int(feat.is_blink),
                f"{feat.pitch:.2f}", f"{feat.yaw:.2f}", f"{feat.roll:.2f}",
                f"{feat.gaze_x:.4f}", f"{feat.gaze_y:.4f}", f"{feat.tension_index:.4f}",
                f"{win.dispersion_4s:.4f}", f"{win.dispersion_30s:.4f}", f"{win.blink_rate_60s:.2f}"
            ])

            del frame

    cap.release()
    landmarker.close()

    pct = (valid_frames / total_frames * 100.0) if total_frames > 0 else 0.0
    print(f"Processed {total_frames} frames. Face tracking: {valid_frames}/{total_frames} ({pct:.1f}%).")
    print(f"Total blinks detected: {extractor.blink_count_total}.")
    print(f"Feature CSV saved to: {output_csv}")
    return 0


# Key landmark indices for the lightweight visual wireframe
_WIREFRAME_INDICES = [
    # Face contour
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378,
    400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21,
    54, 103, 67, 109,
    # Left eye outline
    33, 160, 158, 133, 153, 144,
    # Right eye outline
    362, 385, 387, 263, 373, 380,
    # Irises
    468, 473,
    # Lips
    61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291,
    # Nose bridge & tip
    168, 6, 197, 195, 5, 4, 1, 19, 94, 2
]


class LiveEngineRunner:
    def __init__(self, debug_overlay: bool = False, model_path: Optional[str] = None):
        self.debug_overlay = debug_overlay
        self.running = True
        self.paused = False
        self.calibrating = False

        # Status tracking
        self.camera_status = "starting"
        self.measured_fps = 0.0
        self.first_frame_received = False
        self.seq = 0

        # Inspector controls - active by default to guarantee continuous vision telemetry
        self.inspector_active = True
        self.show_camera_preview = True

        # Host OS signals telemetry
        self.desktop_input = DesktopInputTelemetry()

        # Components
        self.camera = CameraCapture(
            status_callback=self._handle_camera_status
        )
        self.landmarker = FaceLandmarkerWrapper(model_path=model_path)
        self.feature_extractor = FeatureExtractor()
        self.baseline_mgr = BaselineManager()
        self.state_engine = StateEngine()
        self.intervention_mgr = InterventionManager()
        self.history_mgr = HistoryManager()
        self.sequencer_service = TaskSequencerService()
        self.gaze_tracker = GazeMouseTracker()

    def _handle_camera_status(self, status: str, fps: float) -> None:
        self.camera_status = status
        self.measured_fps = fps
        emit_ipc(
            StatusEvent(
                camera=self.camera_status,
                mode="live",
                calibrating=self.calibrating,
                paused=self.paused,
                fps=self.measured_fps if self.camera_status == "on" else 0.0,
                engine_ok=(status not in ("blocked", "unplugged")),
            )
        )

    def handle_command(self, cmd: CommandMessage) -> None:
        if cmd.name == "pause":
            self.paused = True
            self.camera.pause()
        elif cmd.name == "resume":
            self.paused = False
            self.camera.resume()
        elif cmd.name == "shutdown":
            self.running = False
        elif cmd.name == "start_calibration":
            self.calibrating = True
            self.baseline_mgr.start_calibration()
            emit_ipc(
                CalibrationProgressEvent(
                    phase=self.baseline_mgr.calibration_phase,
                    percent=0.0,
                    step_index=self.baseline_mgr.current_step_index,
                    total_steps=5,
                    message="Calibration started",
                )
            )
        elif cmd.name == "cancel_calibration":
            self.calibrating = False
            self.baseline_mgr.cancel_calibration()
            emit_ipc(
                CalibrationProgressEvent(
                    phase="idle",
                    percent=0.0,
                    step_index=0,
                    total_steps=5,
                    message="Calibration cancelled",
                )
            )
        elif cmd.name == "start_calibration_stage":
            self.calibrating = True
            res = self.baseline_mgr.start_stage(cmd.stage or "hardware_check", cmd.target_idx or 0)
            emit_ipc(
                CalibrationProgressEvent(
                    phase=cmd.stage or "hardware_check",
                    percent=float(self.baseline_mgr.current_step_index * 20.0),
                    step_index=self.baseline_mgr.current_step_index,
                    total_steps=5,
                    target_index=cmd.target_idx,
                    message=f"Stage {cmd.stage} started",
                )
            )
        elif cmd.name == "complete_gaze_target":
            res = self.baseline_mgr.complete_current_gaze_target()
            next_t = res.get("next_target")
            emit_ipc(
                CalibrationProgressEvent(
                    phase="gaze_calibration",
                    percent=40.0 + (float(res.get("completed_targets", 0)) / 6.0) * 20.0,
                    step_index=2,
                    total_steps=5,
                    target_index=self.baseline_mgr.current_gaze_target_idx,
                    target_label=next_t.get("label") if next_t else "All targets done",
                    valid_samples=res.get("measurement", {}).get("valid_samples", 0),
                    message="Gaze target saved",
                )
            )
        elif cmd.name == "finalize_calibration":
            res = self.baseline_mgr.validate_and_finalize()
            self.calibrating = False
            emit_ipc(
                CalibrationProgressEvent(
                    phase="complete" if res.get("passed") else "failed",
                    percent=100.0 if res.get("passed") else 0.0,
                    step_index=4,
                    total_steps=5,
                    valid_samples=res.get("total_valid_samples", 0),
                    rejected_samples=res.get("rejected_samples", 0),
                    calibration_data=res.get("baseline"),
                    failed_checks=res.get("failed_checks"),
                    message="Calibration verified & saved" if res.get("passed") else "Validation failed",
                )
            )
        elif cmd.name == "get_calibration":
            emit_ipc(
                CalibrationProgressEvent(
                    phase="complete" if self.baseline_mgr.profile.status == "complete" else "idle",
                    percent=100.0 if self.baseline_mgr.profile.status == "complete" else 0.0,
                    step_index=4,
                    total_steps=5,
                    calibration_data={
                        "calibration_id": self.baseline_mgr.profile.calibration_id,
                        "status": self.baseline_mgr.profile.status,
                        "samples_count": self.baseline_mgr.profile.samples_count,
                    },
                    message="Active calibration retrieved",
                )
            )
        elif cmd.name == "get_history":
            recs = self.history_mgr.get_history(filter_state=cmd.filter_state, start_ts=cmd.start_ts, end_ts=cmd.end_ts)
            emit_ipc(HistoryListEvent(records=recs))
        elif cmd.name == "review_observation":
            if cmd.id and cmd.kind:
                self.history_mgr.update_feedback(cmd.id, cmd.kind, notes=cmd.notes)
                recs = self.history_mgr.get_history()
                emit_ipc(HistoryListEvent(records=recs))
        elif cmd.name == "delete_observation":
            if cmd.id:
                self.history_mgr.delete_observation(cmd.id)
                recs = self.history_mgr.get_history()
                emit_ipc(HistoryListEvent(records=recs))
        elif cmd.name == "clear_history":
            self.history_mgr.clear_all()
            emit_ipc(HistoryListEvent(records=[]))
        elif cmd.name == "generate_report":
            rep = self.history_mgr.generate_report(start_ts=cmd.start_ts, end_ts=cmd.end_ts)
            emit_ipc(ReportGeneratedEvent(report=rep))
        elif cmd.name == "feedback":
            if cmd.kind:
                self.state_engine.record_feedback(cmd.kind)
                self.intervention_mgr.record_feedback(cmd.kind)
        elif cmd.name == "snooze":
            duration = cmd.duration_minutes or 15
            self.intervention_mgr.snooze(duration)
        elif cmd.name == "set_settings":
            if cmd.settings:
                self.intervention_mgr.update_settings(cmd.settings)
        elif cmd.name == "delete_all_data":
            self.baseline_mgr.reset()
            self.history_mgr.clear_all()
        elif cmd.name == "set_inspector":
            if cmd.inspector_active is not None:
                self.inspector_active = cmd.inspector_active
            if cmd.show_camera_preview is not None:
                self.show_camera_preview = cmd.show_camera_preview
        elif cmd.name == "sequencer_send_message":
            asst_msg, contract = self.sequencer_service.send_message(
                conversation_id=cmd.conversation_id,
                user_text=cmd.message_text or "",
                energy_level=cmd.energy_level,
            )
            emit_ipc(
                SequencerResponseEvent(
                    conversation_id=asst_msg.conversation_id,
                    message_id=asst_msg.id,
                    contract=contract.model_dump(),
                    task=contract.current_task.model_dump() if contract.current_task else None,
                )
            )
        elif cmd.name == "sequencer_action":
            asst_msg, contract = self.sequencer_service.handle_action(
                conversation_id=cmd.conversation_id or "",
                action=cmd.action_name or "",
                task_id=cmd.task_id,
                feedback_comment=cmd.feedback_comment,
            )
            emit_ipc(
                SequencerResponseEvent(
                    conversation_id=asst_msg.conversation_id,
                    message_id=asst_msg.id,
                    contract=contract.model_dump(),
                    task=contract.current_task.model_dump() if contract.current_task else None,
                )
            )
        elif cmd.name == "sequencer_get_conversations":
            convs = [c.model_dump() for c in self.sequencer_service.list_conversations()]
            emit_ipc(SequencerConversationsListEvent(conversations=convs))
        elif cmd.name == "sequencer_get_conversation":
            if cmd.conversation_id:
                msgs = [m.model_dump() for m in self.sequencer_service.get_conversation_messages(cmd.conversation_id)]
                active_t = self.sequencer_service.db.get_latest_task_for_conversation(cmd.conversation_id)
                emit_ipc(
                    SequencerConversationLoadedEvent(
                        conversation_id=cmd.conversation_id,
                        messages=msgs,
                        active_task=active_t.model_dump() if active_t else None,
                    )
                )
        elif cmd.name == "sequencer_new_conversation":
            summary = self.sequencer_service.new_conversation(cmd.title or "New Task Support")
            convs = [c.model_dump() for c in self.sequencer_service.list_conversations()]
            emit_ipc(SequencerConversationsListEvent(conversations=convs))
            emit_ipc(
                SequencerConversationLoadedEvent(
                    conversation_id=summary.id,
                    messages=[],
                    active_task=None,
                )
            )
        elif cmd.name == "sequencer_delete_conversation":
            if cmd.conversation_id:
                self.sequencer_service.delete_conversation(cmd.conversation_id)
                convs = [c.model_dump() for c in self.sequencer_service.list_conversations()]
                emit_ipc(SequencerConversationsListEvent(conversations=convs))
        elif cmd.name == "sequencer_clear_history":
            self.sequencer_service.clear_all_history()
            emit_ipc(SequencerConversationsListEvent(conversations=[]))
        elif cmd.name == "sequencer_update_preferences":
            if cmd.preferences:
                try:
                    p = UserPreferences.model_validate(cmd.preferences)
                    self.sequencer_service.update_preferences(p)
                except Exception:
                    pass
            diag = self.sequencer_service.get_diagnostics()
            emit_ipc(SequencerDiagnosticsEvent(diagnostics=diag.model_dump()))
        elif cmd.name == "sequencer_rebuild_index":
            self.sequencer_service.rebuild_rag_index()
            diag = self.sequencer_service.get_diagnostics()
            emit_ipc(SequencerDiagnosticsEvent(diagnostics=diag.model_dump()))
        elif cmd.name == "sequencer_get_diagnostics":
            diag = self.sequencer_service.get_diagnostics()
            emit_ipc(SequencerDiagnosticsEvent(diagnostics=diag.model_dump()))
            st = self.sequencer_service.get_status()
            emit_ipc(
                SequencerStatusEvent(
                    llm_provider=st["llm_provider"],
                    model_name=st["model_name"],
                    ollama_connected=st["ollama_connected"],
                    model_installed=st["model_installed"],
                    available_models=st["available_models"],
                    rag_index_ready=st["rag_index_ready"],
                    rag_documents_count=st["rag_documents_count"],
                    rag_chunks_count=st["rag_chunks_count"],
                    error_message=st["error_message"],
                )
            )
        elif cmd.name == "sequencer_cancel_generation":
            self.sequencer_service.cancel_generation()
        elif cmd.name == "start_eye_control":
            self.gaze_tracker.set_enabled(True)
            self._emit_gaze_status()
        elif cmd.name == "pause_eye_control":
            self.gaze_tracker.set_paused(True)
            self._emit_gaze_status()
        elif cmd.name == "resume_eye_control":
            self.gaze_tracker.set_paused(False)
            self._emit_gaze_status()
        elif cmd.name == "stop_eye_control":
            self.gaze_tracker.set_enabled(False)
            self._emit_gaze_status()
        elif cmd.name == "emergency_stop":
            self.gaze_tracker.emergency_stop()
            self._emit_gaze_status()
        elif cmd.name == "gaze_start_calibration":
            self.gaze_tracker.start_calibration()
            self._emit_gaze_status()
        elif cmd.name == "gaze_advance_calibration":
            res = self.gaze_tracker.advance_calibration_target()
            emit_ipc(GazeCalibrationEvent(
                success=res.get("success", False),
                finished=res.get("finished", False),
                message=res.get("message"),
                next_target_idx=res.get("next_target_idx"),
                next_target=res.get("next_target"),
                quality_label=res.get("quality_label"),
                validation_error=res.get("validation_error"),
                profile=res.get("profile"),
            ))
            self._emit_gaze_status()
        elif cmd.name == "gaze_reset_calibration":
            self.gaze_tracker.reset_calibration()
            self._emit_gaze_status()
        elif cmd.name == "gaze_update_settings":
            if cmd.gaze_settings:
                self.gaze_tracker.update_settings(cmd.gaze_settings)
            self._emit_gaze_status()
        elif cmd.name == "gaze_get_status":
            self._emit_gaze_status()
        elif cmd.name == "gaze_start_diagnostic":
            dur = float(cmd.duration_minutes or 5.0)
            self.gaze_tracker.start_diagnostic(duration_seconds=dur)
            self._emit_gaze_status()
        elif cmd.name == "gaze_finish_diagnostic":
            diag_res = self.gaze_tracker.finish_diagnostic()
            if diag_res.get("success"):
                emit_ipc(GazeDiagnosticEvent(**diag_res))
            self._emit_gaze_status()
        elif cmd.name == "gaze_set_tracking_mode":
            if cmd.tracking_mode:
                self.gaze_tracker.set_tracking_mode(cmd.tracking_mode)
            self._emit_gaze_status()
        elif cmd.name == "gaze_set_preset":
            if cmd.preset:
                self.gaze_tracker.apply_preset(cmd.preset)
            self._emit_gaze_status()
        elif cmd.name == "gaze_recenter":
            self.gaze_tracker.recenter()
            self._emit_gaze_status()
        elif cmd.name == "gaze_reset_cursor":
            self.gaze_tracker.reset_cursor_to_center()
            self._emit_gaze_status()

    def _emit_gaze_status(self) -> None:
        st = self.gaze_tracker.get_status()
        emit_ipc(GazeStatusEvent(**st))

    def handle_os_signals(self, signals: OsSignalsEvent) -> None:
        self.desktop_input = DesktopInputTelemetry(
            idle_seconds=signals.idle_seconds,
            seconds_since_last_key=signals.seconds_since_last_key,
            seconds_since_last_mouse=signals.seconds_since_last_mouse,
            seconds_since_last_scroll=signals.seconds_since_last_scroll,
            key_count_window=signals.key_count_window,
            mouse_move_count_window=signals.mouse_move_count_window,
            mouse_click_count_window=signals.mouse_click_count_window,
            mouse_scroll_count_window=signals.mouse_scroll_count_window,
            window_switch_count_60s=signals.window_switch_count,
            productive_input_score=signals.productive_input_score if hasattr(signals, "productive_input_score") else max(0.0, 1.0 - (signals.idle_seconds / 15.0)),
            monitor_status=signals.monitor_status,
        )

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
        stdin_thread = threading.Thread(target=self.run_stdin_listener, daemon=True)
        stdin_thread.start()

        self.camera.start()
        last_state_emit = 0.0
        last_telemetry_emit = 0.0

        # Emit initial sequencer status on startup
        try:
            st = self.sequencer_service.get_status()
            emit_ipc(
                SequencerStatusEvent(
                    llm_provider=st["llm_provider"],
                    model_name=st["model_name"],
                    ollama_connected=st["ollama_connected"],
                    model_installed=st["model_installed"],
                    available_models=st["available_models"],
                    rag_index_ready=st["rag_index_ready"],
                    rag_documents_count=st["rag_documents_count"],
                    rag_chunks_count=st["rag_chunks_count"],
                    error_message=st["error_message"],
                )
            )
        except Exception:
            pass

        try:
            while self.running:
                now = time.time()
                frame, frame_ts = self.camera.get_latest_frame()

                res = None
                feat = None
                frame_b64 = None
                wireframe_coords = None

                if frame is not None and not self.paused:
                    if not self.first_frame_received:
                        self.first_frame_received = True

                    res = self.landmarker.process_frame(frame)
                    if res is not None:
                        feat = self.feature_extractor.extract_frame_features(
                            frame_bgr=frame,
                            landmarks=res.landmarks,
                            blendshapes=res.blendshapes,
                            timestamp=now,
                        )
                        # Always extract wireframe coordinates when face is detected
                        wireframe_coords = [
                            [round(float(res.landmarks[idx, 0]), 4), round(float(res.landmarks[idx, 1]), 4)]
                            for idx in _WIREFRAME_INDICES
                            if idx < len(res.landmarks)
                        ]
                    else:
                        feat = self.feature_extractor.extract_frame_features(
                            frame_bgr=frame,
                            landmarks=None,
                            blendshapes=None,
                            timestamp=now,
                        )

                    # Process Track 4 Eye-Gaze Mouse
                    gaze_res = self.gaze_tracker.process_frame(
                        landmarks=res.landmarks if res is not None else None,
                        ear=feat.ear if feat is not None else 0.0,
                        pitch=feat.pitch if feat is not None else 0.0,
                        yaw=feat.yaw if feat is not None else 0.0,
                        timestamp=now,
                    )

                    # If eye control is active, emit cursor movement event for native OS mouse control
                    if (
                        self.gaze_tracker.enabled
                        and not self.gaze_tracker.paused
                        and not self.gaze_tracker.emergency_stopped
                        and gaze_res.get("valid")
                    ):
                        emit_ipc(
                            GazeCursorMoveEvent(
                                norm_x=gaze_res["norm_x"],
                                norm_y=gaze_res["norm_y"],
                                valid=True,
                                timestamp=now,
                            )
                        )

                    # If a diagnostic test finished during this frame, emit the diagnostic event
                    if gaze_res.get("diagnostic_result") and gaze_res["diagnostic_result"].get("success"):
                        emit_ipc(GazeDiagnosticEvent(**gaze_res["diagnostic_result"]))
                        self._emit_gaze_status()

                    # Encode lightweight JPEG thumbnail when preview is enabled
                    if self.show_camera_preview:
                        try:
                            thumb = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_AREA)
                            ret, buf = cv2.imencode(".jpg", thumb, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
                            if ret:
                                frame_b64 = base64.b64encode(buf).decode("ascii")
                        except Exception:
                            pass

                    # Optional dev debug overlay window
                    if self.debug_overlay:
                        self._render_debug_overlay(frame, res, feat)

                    del frame
                else:
                    # Camera is unavailable, paused, or starting
                    feat = FrameFeatures(
                        timestamp=now,
                        valid=False,
                        quality_reason=self.camera_status or "camera_unavailable",
                    )

                # Continuous telemetry calculation (10 Hz for responsive UI & landmark tracking)
                telemetry_interval = 0.10
                should_emit_telemetry = (now - last_telemetry_emit >= telemetry_interval)
                should_emit_state = (now - last_state_emit >= 1.0)

                if should_emit_telemetry or should_emit_state:
                    self.seq += 1
                    win_feat = self.feature_extractor.aggregate_windows(now)

                    if self.calibrating and feat:
                        self.baseline_mgr.feed_calibration_frame(feat, win_feat, now=now)
                        pct = self.baseline_mgr.update_calibration(win_feat, feat.ear)
                        if pct is not None:
                            emit_ipc(
                                CalibrationProgressEvent(
                                    phase=self.baseline_mgr.calibration_phase,
                                    percent=pct,
                                    step_index=self.baseline_mgr.current_step_index,
                                    total_steps=5,
                                    valid_samples=self.baseline_mgr.valid_frames_count,
                                    rejected_samples=self.baseline_mgr.rejected_frames_count,
                                )
                            )
                            if pct >= 100.0:
                                self.calibrating = False
                                self._handle_camera_status("on", self.measured_fps)

                    # Compute state using state engine
                    state_event = self.state_engine.compute_state(
                        features=win_feat,
                        frame_feat=feat,
                        baseline=self.baseline_mgr.profile,
                        idle_seconds=self.desktop_input.idle_seconds,
                        window_switch_count=self.desktop_input.window_switch_count_60s,
                        now=now,
                    )

                    if state_event.state in ("FOCUSED", "RELAXED") and feat and feat.valid:
                        self.baseline_mgr.adapt_slowly(win_feat, feat.ear)

                    # Check for gentle non-intrusive intervention
                    intv_event = self.intervention_mgr.maybe_create_intervention(state_event.state, now=now)
                    if intv_event is not None:
                        emit_ipc(intv_event)

                    # Update local evidence history (deduplicated episodes, no intrusive alert)
                    closed_ep = self.history_mgr.update_or_record_episode(
                        state=state_event.state,
                        score=state_event.confidence,
                        features=getattr(self.state_engine, "last_structured_observations", []),
                        evidence_strength=getattr(self.state_engine.last_prediction_telemetry, "exact_decision_rule", ""),
                        qualification_reason=f"Sustained state {state_event.state} with confidence {state_event.confidence:.2f}",
                        data_quality="valid" if (feat and feat.valid) else "degraded",
                        now=now,
                    )
                    if closed_ep:
                        emit_ipc(ObservationItemEvent(observation=closed_ep.to_dict()))

                    if should_emit_state:
                        last_state_emit = now
                        emit_ipc(state_event)

                    if should_emit_telemetry:
                        last_telemetry_emit = now
                        # Construct comprehensive TelemetryEvent
                        b = self.baseline_mgr.profile
                        face_valid = bool(res is not None and feat is not None and feat.valid)
                        unavail_reason = feat.quality_reason if (feat and feat.quality_reason) else "No face detected in webcam frame"

                        cam_diag = self.camera.get_diagnostics()
                        land_diag = self.landmarker.get_diagnostics()
                        pipeline_diag = PipelineDiagnostics(
                            camera_fps=float(cam_diag.get("fps", 0.0)),
                            camera_frames_captured=int(cam_diag.get("total_frames_captured", 0)),
                            camera_brightness=float(cam_diag.get("latest_brightness", 0.0)),
                            landmarker_model_loaded=bool(land_diag.get("model_loaded", False)),
                            landmarker_total_inferences=int(land_diag.get("total_inferences", 0)),
                            landmarker_successful_detections=int(land_diag.get("successful_detections", 0)),
                            landmarker_detection_rate_pct=float(land_diag.get("detection_rate_pct", 0.0)),
                            landmarker_last_landmark_count=int(land_diag.get("last_landmark_count", 0)),
                            ipc_sequence_number=self.seq,
                        )

                        pred_telem = self.state_engine.last_prediction_telemetry or PredictionTelemetry(
                            state=state_event.state,
                            confidence=state_event.confidence,
                            top_signals=state_event.top_signals,
                        )
                        # Sync live intervention status
                        pred_telem.intervention_status = self.intervention_mgr.get_status_telemetry(state_event.state, now=now)

                        telemetry = TelemetryEvent(
                            seq=self.seq,
                            ts=now,
                            camera=CameraTelemetry(
                                status=self.camera_status,
                                fps=self.measured_fps if self.camera_status == "on" else 0.0,
                                width=CONFIG.camera.frame_width,
                                height=CONFIG.camera.frame_height,
                                device_index=CONFIG.camera.device_index,
                            ),
                            vision=VisionTelemetry(
                                face_detected=(res is not None),
                                quality_valid=face_valid,
                                quality_reason=unavail_reason if not face_valid else "Face tracked",
                                mean_brightness=float(cam_diag.get("latest_brightness", 0.0)),
                                landmark_count=len(res.landmarks) if res is not None else 0,
                                frame_timestamp=frame_ts if ("frame_ts" in locals() and frame_ts is not None) else now,
                                frame_seq=self.seq,
                                ear=EarTelemetry(
                                    left=feat.left_ear if (feat and face_valid) else 0.0,
                                    right=feat.right_ear if (feat and face_valid) else 0.0,
                                    avg=feat.ear if (feat and face_valid) else 0.0,
                                    baseline_mean=b.ear.mean,
                                    baseline_std=b.ear.std,
                                    is_blink=feat.is_blink if (feat and face_valid) else False,
                                    valid=face_valid,
                                    quality_reason="Valid" if face_valid else unavail_reason,
                                ),
                                blinks=BlinkTelemetry(
                                    count_total=win_feat.blink_count_total,
                                    rate_30s=win_feat.blink_rate_30s if face_valid else 0.0,
                                    rate_60s=win_feat.blink_rate_60s if face_valid else 0.0,
                                    rate_180s=win_feat.blink_rate_180s if face_valid else 0.0,
                                    irregularity=win_feat.blink_irregularity if face_valid else 1.0,
                                    valid=face_valid,
                                    quality_reason="Valid" if face_valid else unavail_reason,
                                ),
                                gaze=GazeTelemetry(
                                    x=feat.gaze_x if (feat and face_valid) else 0.5,
                                    y=feat.gaze_y if (feat and face_valid) else 0.5,
                                    raw_x=feat.gaze_x if (feat and face_valid) else 0.5,
                                    raw_y=feat.gaze_y if (feat and face_valid) else 0.5,
                                    iris_l=[float(res.landmarks[468, 0]), float(res.landmarks[468, 1])] if res is not None else [0.4, 0.4],
                                    iris_r=[float(res.landmarks[473, 0]), float(res.landmarks[473, 1])] if res is not None else [0.6, 0.4],
                                    dispersion_4s=win_feat.dispersion_4s if face_valid else 0.0,
                                    dispersion_30s=win_feat.dispersion_30s if face_valid else 0.0,
                                    dispersion_120s=win_feat.dispersion_120s if face_valid else 0.0,
                                    shifts_per_min=win_feat.gaze_shifts_per_min if face_valid else 0.0,
                                    baseline_disp_mean=b.dispersion.mean,
                                    valid=face_valid,
                                    quality_reason="Valid" if face_valid else unavail_reason,
                                ),
                                tension=TensionTelemetry(
                                    index=feat.tension_index if (feat and face_valid) else 0.0,
                                    brow_down=feat.brow_down if (feat and face_valid) else 0.0,
                                    mouth_press=feat.mouth_press if (feat and face_valid) else 0.0,
                                    jaw_clench=feat.jaw_clench if (feat and face_valid) else 0.0,
                                    eye_squint=feat.eye_squint if (feat and face_valid) else 0.0,
                                    baseline_mean=b.tension.mean,
                                    baseline_std=b.tension.std,
                                    valid=face_valid,
                                    quality_reason="Valid" if face_valid else unavail_reason,
                                ),
                                head_pose=HeadPoseTelemetry(
                                    pitch=feat.pitch if (feat and face_valid) else 0.0,
                                    yaw=feat.yaw if (feat and face_valid) else 0.0,
                                    roll=feat.roll if (feat and face_valid) else 0.0,
                                    variance_4s=win_feat.head_pose_var_4s if face_valid else 0.0,
                                    variance_30s=win_feat.head_pose_var_30s if face_valid else 0.0,
                                    baseline_var_mean=b.head_variance.mean,
                                    valid=face_valid,
                                    quality_reason="Valid" if face_valid else unavail_reason,
                                ),
                                landmarks_wireframe=wireframe_coords,
                                frame_jpeg_base64=frame_b64,
                            ),
                            desktop_input=self.desktop_input,
                            prediction=pred_telem,
                            diagnostics=pipeline_diag,
                        )
                        emit_ipc(telemetry)
                        self.sequencer_service.update_observer_telemetry(telemetry.model_dump())
                        self._emit_gaze_status()

                time.sleep(0.04)  # ~25 Hz loop frequency

        finally:
            self.camera.stop()
            self.landmarker.close()
            if self.debug_overlay:
                try:
                    cv2.destroyAllWindows()
                except Exception:
                    pass

    def _render_debug_overlay(self, frame: np.ndarray, res, feat) -> None:
        try:
            h, w = frame.shape[:2]
            vis = frame.copy()

            if res is not None:
                l_iris = (int(res.landmarks[468, 0] * w), int(res.landmarks[468, 1] * h))
                r_iris = (int(res.landmarks[473, 0] * w), int(res.landmarks[473, 1] * h))
                cv2.circle(vis, l_iris, 3, (0, 255, 0), -1)
                cv2.circle(vis, r_iris, 3, (0, 255, 0), -1)

            status_text = f"FPS: {self.measured_fps:.1f} | EAR: {feat.ear:.2f} | Blinks: {self.feature_extractor.blink_count_total}"
            cv2.putText(vis, status_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            tension_text = f"Tension: {feat.tension_index:.2f} | Pitch: {feat.pitch:.1f} Yaw: {feat.yaw:.1f}"
            cv2.putText(vis, tension_text, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            cv2.imshow("Observer Real Camera Debug Overlay (Press ESC to close)", vis)
            if cv2.waitKey(1) & 0xFF == 27:
                self.debug_overlay = False
                cv2.destroyAllWindows()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Observer Real Engine")
    parser.add_argument("--live", action="store_true", default=True, help="Run live camera pipeline (DEFAULT)")
    parser.add_argument("--demo", action="store_true", help="Run synthetic demo timeline without webcam")
    parser.add_argument("--selftest", action="store_true", help="Run 5-second camera diagnostic and exit")
    parser.add_argument("--debug-overlay", action="store_true", help="Display live OpenCV visual debug window")
    parser.add_argument("--simulate", type=str, default="", help="Replay recorded video file")
    parser.add_argument("--model", type=str, default="", help="Path to face_landmarker.task")
    parser.add_argument("--fake", action="store_true", help="Run fake engine for tests")
    args = parser.parse_args()

    # 1. Self-test mode
    if args.selftest:
        code = run_selftest()
        sys.exit(code)

    # 2. Offline Video Simulation Mode
    if args.simulate:
        code = run_simulation(args.simulate, model_path=args.model if args.model else None)
        sys.exit(code)

    # 3. Demo mode (Explicitly requested)
    if args.demo or args.fake:
        engine = FakeEngine()
        engine.demo_mode = True
        try:
            engine.run()
        except KeyboardInterrupt:
            pass
        return

    # 4. Live mode (DEFAULT)
    runner = LiveEngineRunner(
        debug_overlay=args.debug_overlay,
        model_path=args.model if args.model else None,
    )
    try:
        runner.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        sys.stderr.write(f"[Engine Fatal Error] {e}\n")
        emit_ipc(
            ErrorEvent(
                code="ENGINE_INIT_ERROR",
                message_friendly="The camera tracking engine encountered an unexpected error.",
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

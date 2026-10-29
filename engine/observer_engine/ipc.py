"""
observer_engine.ipc
Defines Pydantic v2 models and serialization for the IPC contract.
All messages are Newline-Delimited JSON (NDJSON) over stdin/stdout.
"""

from typing import List, Literal, Optional, Dict, Any, Union
import json
from pydantic import BaseModel, Field, ConfigDict

SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------
# Event Models (Engine -> Host/UI)
# ---------------------------------------------------------

class BaseIPCModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schema_version: str = SCHEMA_VERSION


class StatusEvent(BaseIPCModel):
    type: Literal["status"] = "status"
    camera: Literal["off", "starting", "on", "blocked", "unplugged"] = "off"
    mode: Literal["live", "demo"] = "live"
    calibrating: bool = False
    paused: bool = False
    fps: float = 0.0
    engine_ok: bool = True


class GazeStatusEvent(BaseIPCModel):
    type: Literal["gaze_status"] = "gaze_status"
    enabled: bool = False
    paused: bool = False
    emergency_stopped: bool = False
    tracking_valid: bool = False
    tracking_reason: str = ""
    last_valid_ts: float = 0.0
    cursor_norm_x: float = 0.5
    cursor_norm_y: float = 0.5
    is_calibrated: bool = False
    quality_label: str = "Uncalibrated"
    validation_error: float = 0.0
    sensitivity: float = 1.2
    dead_zone: float = 0.008
    max_speed: float = 0.08
    smoothing_mode: str = "balanced"
    tracking_mode: str = "hybrid"
    preset: str = "maximum_stability"
    is_calibrating: bool = False
    calib_target_idx: int = 0
    outlier_count: int = 0
    is_diagnosing: bool = False
    neutral_yaw: float = 0.0
    neutral_pitch: float = 0.0
    current_yaw: float = 0.0
    current_pitch: float = 0.0
    deflection_x: float = 0.0
    deflection_y: float = 0.0
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    in_dead_zone: bool = True
    frame_age_ms: float = 0.0
    hz: float = 0.0
    is_neutral_calibrated: bool = False


class GazeCalibrationEvent(BaseIPCModel):
    type: Literal["gaze_calibration_event"] = "gaze_calibration_event"
    success: bool = True
    finished: bool = False
    message: Optional[str] = None
    next_target_idx: Optional[int] = None
    next_target: Optional[Dict[str, Any]] = None
    quality_label: Optional[str] = None
    validation_error: Optional[float] = None
    profile: Optional[Dict[str, Any]] = None


class GazeDiagnosticEvent(BaseIPCModel):
    type: Literal["gaze_diagnostic_event"] = "gaze_diagnostic_event"
    timestamp: float
    duration_seconds: float
    sample_count: int
    validity_rate_pct: float
    outlier_rate_pct: float
    stationary_jitter_px: float
    drift_rate_px_per_sec: float
    avg_latency_ms: float
    stability_score: float
    quality_rating: str
    tracking_mode: str
    preset: str


class GazeCursorMoveEvent(BaseIPCModel):
    type: Literal["event"] = "event"
    name: Literal["gaze_cursor_move"] = "gaze_cursor_move"
    norm_x: float
    norm_y: float
    valid: bool
    timestamp: float


# ---------------------------------------------------------
# High-Resolution Telemetry Models for Observability
# ---------------------------------------------------------

class CameraTelemetry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: Literal["off", "starting", "on", "blocked", "unplugged"]
    fps: float
    width: int = 640
    height: int = 480
    device_index: int = 0


class EarTelemetry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    valid: bool = False
    quality_reason: str = ""
    left: float = 0.0
    right: float = 0.0
    avg: float = 0.0
    baseline_mean: float = 0.28
    baseline_std: float = 0.04
    is_blink: bool = False


class BlinkTelemetry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    valid: bool = False
    quality_reason: str = ""
    count_total: int = 0
    rate_30s: float = 0.0
    rate_60s: float = 0.0
    rate_180s: float = 0.0
    irregularity: float = 0.0


class GazeTelemetry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    valid: bool = False
    quality_reason: str = ""
    x: float = 0.5
    y: float = 0.5
    raw_x: float = 0.5
    raw_y: float = 0.5
    iris_l: List[float] = Field(default_factory=lambda: [0.4, 0.4])
    iris_r: List[float] = Field(default_factory=lambda: [0.6, 0.4])
    dispersion_4s: float = 0.5
    dispersion_30s: float = 0.5
    dispersion_120s: float = 0.5
    shifts_per_min: float = 0.0
    baseline_disp_mean: float = 0.35


class TensionTelemetry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    valid: bool = False
    quality_reason: str = ""
    index: float = 0.0
    brow_down: float = 0.0
    mouth_press: float = 0.0
    jaw_clench: float = 0.0
    eye_squint: float = 0.0
    baseline_mean: float = 0.18
    baseline_std: float = 0.08


class HeadPoseTelemetry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    valid: bool = False
    quality_reason: str = ""
    pitch: float = 0.0
    yaw: float = 0.0
    roll: float = 0.0
    variance_4s: float = 0.0
    variance_30s: float = 0.0
    baseline_var_mean: float = 1.20


class VisionTelemetry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    face_detected: bool = False
    quality_valid: bool = False
    quality_reason: str = "camera_unavailable"
    mean_brightness: float = 0.0
    landmark_count: int = 0
    frame_timestamp: float = 0.0
    frame_seq: int = 0
    ear: EarTelemetry = Field(default_factory=EarTelemetry)
    blinks: BlinkTelemetry = Field(default_factory=BlinkTelemetry)
    gaze: GazeTelemetry = Field(default_factory=GazeTelemetry)
    tension: TensionTelemetry = Field(default_factory=TensionTelemetry)
    head_pose: HeadPoseTelemetry = Field(default_factory=HeadPoseTelemetry)
    landmarks_wireframe: Optional[List[List[float]]] = None
    frame_jpeg_base64: Optional[str] = None


class PipelineDiagnostics(BaseModel):
    model_config = ConfigDict(extra="ignore")
    camera_status: str = "off"
    frames_captured: int = 0
    frames_processed: int = 0
    faces_detected_count: int = 0
    detection_rate_pct: float = 0.0
    actual_landmark_count: int = 0
    model_initialized: bool = False
    last_inference_ts: float = 0.0
    last_detection_ts: float = 0.0
    ipc_publications_count: int = 0
    mean_brightness: float = 0.0


class DesktopInputTelemetry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    idle_seconds: float = 0.0
    seconds_since_last_key: float = 0.0
    seconds_since_last_mouse: float = 0.0
    seconds_since_last_scroll: float = 0.0
    key_count_window: int = 0
    mouse_move_count_window: int = 0
    mouse_click_count_window: int = 0
    mouse_scroll_count_window: int = 0
    window_switch_count_60s: int = 0
    productive_input_score: float = 0.0
    monitor_status: Literal["active", "permission_denied", "unsupported", "disabled"] = "active"


class FrozenComponents(BaseModel):
    model_config = ConfigDict(extra="ignore")
    fixation: float = 0.0
    idle: float = 0.0
    tension: float = 0.0
    blink_anomaly: float = 0.0
    stillness: float = 0.0


class SpinningComponents(BaseModel):
    model_config = ConfigDict(extra="ignore")
    switching: float = 0.0
    tension: float = 0.0
    unproductive: float = 0.0


class InterventionStatusTelemetry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    eligible: bool = False
    reason: str = "Monitoring active"
    cooldown_remaining_s: float = 0.0


class PredictionTelemetry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    state: Literal["RELAXED", "FOCUSED", "PARALYSIS_LIKELY", "OVERLOAD_LIKELY", "UNKNOWN"]
    frozen_score: float = 0.0
    frozen_components: FrozenComponents = Field(default_factory=FrozenComponents)
    frozen_weights: FrozenComponents = Field(
        default_factory=lambda: FrozenComponents(fixation=0.30, idle=0.25, tension=0.25, blink_anomaly=0.10, stillness=0.10)
    )
    spinning_score: float = 0.0
    spinning_components: SpinningComponents = Field(default_factory=SpinningComponents)
    smoothed_frozen: float = 0.0
    smoothed_spinning: float = 0.0
    enter_threshold: float = 0.65
    exit_threshold: float = 0.45
    dwell_duration_seconds: float = 0.0
    dwell_required_seconds: float = 90.0
    dwell_satisfied: bool = False
    confidence: float = 0.50
    top_signals: List[str] = Field(default_factory=list)
    excluded_or_invalid_signals: List[str] = Field(default_factory=list)
    exact_decision_rule: str = ""
    intervention_status: InterventionStatusTelemetry = Field(default_factory=InterventionStatusTelemetry)


class TelemetryEvent(BaseIPCModel):
    type: Literal["telemetry"] = "telemetry"
    seq: int = 0
    ts: float = 0.0
    camera: CameraTelemetry
    vision: VisionTelemetry
    desktop_input: DesktopInputTelemetry
    prediction: PredictionTelemetry


class CalibrationProgressEvent(BaseIPCModel):
    type: Literal["calibration_progress"] = "calibration_progress"
    phase: str = "relaxed_baseline"
    percent: float = 0.0
    step_index: int = 0
    total_steps: int = 5
    target_index: Optional[int] = None
    target_label: Optional[str] = None
    valid_samples: int = 0
    rejected_samples: int = 0
    tracking_quality_pct: float = 0.0
    message: Optional[str] = None
    calibration_data: Optional[Dict[str, Any]] = None
    failed_checks: Optional[List[str]] = None


class StateProbabilities(BaseModel):
    model_config = ConfigDict(extra="ignore")
    relaxed: float = 0.0
    focused: float = 0.0
    paralysis: float = 0.0
    overload: float = 0.0


class StateUpdateEvent(BaseIPCModel):
    type: Literal["state_update"] = "state_update"
    state: Literal["RELAXED", "FOCUSED", "PARALYSIS_LIKELY", "OVERLOAD_LIKELY", "UNKNOWN"]
    probabilities: StateProbabilities
    confidence: float
    top_signals: List[str]
    ts: float


class ObservationItemEvent(BaseIPCModel):
    type: Literal["observation_item"] = "observation_item"
    observation: Dict[str, Any]


class HistoryListEvent(BaseIPCModel):
    type: Literal["history_list"] = "history_list"
    records: List[Dict[str, Any]]


class ReportGeneratedEvent(BaseIPCModel):
    type: Literal["report_generated"] = "report_generated"
    report: Dict[str, Any]


class InterventionAction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    label: str


class InterventionEvent(BaseIPCModel):
    type: Literal["intervention"] = "intervention"
    tier: int = Field(ge=0, le=3)
    id: str
    text: str
    actions: List[InterventionAction]


class ErrorEvent(BaseIPCModel):
    type: Literal["error"] = "error"
    code: str
    message_friendly: str


# ---------------------------------------------------------
# Track 2: Task Sequencer Event Models
# ---------------------------------------------------------

class SequencerStatusEvent(BaseIPCModel):
    type: Literal["sequencer_status"] = "sequencer_status"
    llm_provider: str = "ollama"
    model_name: str = "llama3.2:latest"
    ollama_connected: bool = False
    model_installed: bool = False
    available_models: List[str] = Field(default_factory=list)
    rag_index_ready: bool = False
    rag_documents_count: int = 0
    rag_chunks_count: int = 0
    error_message: Optional[str] = None


class SequencerResponseEvent(BaseIPCModel):
    type: Literal["sequencer_response"] = "sequencer_response"
    conversation_id: str
    message_id: str
    contract: Dict[str, Any]
    task: Optional[Dict[str, Any]] = None


class SequencerDiagnosticsEvent(BaseIPCModel):
    type: Literal["sequencer_diagnostics"] = "sequencer_diagnostics"
    diagnostics: Dict[str, Any]


class SequencerConversationsListEvent(BaseIPCModel):
    type: Literal["sequencer_conversations_list"] = "sequencer_conversations_list"
    conversations: List[Dict[str, Any]]


class SequencerConversationLoadedEvent(BaseIPCModel):
    type: Literal["sequencer_conversation_loaded"] = "sequencer_conversation_loaded"
    conversation_id: str
    messages: List[Dict[str, Any]]
    active_task: Optional[Dict[str, Any]] = None


EngineEvent = Union[
    StatusEvent,
    TelemetryEvent,
    CalibrationProgressEvent,
    StateUpdateEvent,
    InterventionEvent,
    ErrorEvent,
    ObservationItemEvent,
    HistoryListEvent,
    ReportGeneratedEvent,
    SequencerStatusEvent,
    SequencerResponseEvent,
    SequencerDiagnosticsEvent,
    SequencerConversationsListEvent,
    SequencerConversationLoadedEvent,
    GazeStatusEvent,
    GazeCalibrationEvent,
    GazeDiagnosticEvent,
]

# ---------------------------------------------------------
# Host Context Signals (Host/Rust -> Engine)
# ---------------------------------------------------------

class OsSignalsEvent(BaseIPCModel):
    type: Literal["os_signals"] = "os_signals"
    idle_seconds: float = 0.0
    seconds_since_last_key: float = 0.0
    seconds_since_last_mouse: float = 0.0
    seconds_since_last_scroll: float = 0.0
    key_count_window: int = 0
    mouse_move_count_window: int = 0
    mouse_click_count_window: int = 0
    mouse_scroll_count_window: int = 0
    window_switch_count: int = 0
    fullscreen_media: bool = False
    monitor_status: Literal["active", "permission_denied", "unsupported", "disabled"] = "active"

# ---------------------------------------------------------
# Command Models (UI -> Host/Rust -> Engine)
# ---------------------------------------------------------

class SettingsPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sensitivity: Optional[float] = 0.65
    cooldown_mins: Optional[int] = 20
    quiet_hours_enabled: Optional[bool] = False
    quiet_hours_start: Optional[str] = "22:00"
    quiet_hours_end: Optional[str] = "08:00"
    intervention_tier: Optional[int] = 2
    enabled_signals: Optional[Dict[str, bool]] = None


class CommandMessage(BaseIPCModel):
    type: Literal["command"] = "command"
    name: Literal[
        "start_calibration",
        "cancel_calibration",
        "start_calibration_stage",
        "complete_gaze_target",
        "finalize_calibration",
        "get_calibration",
        "get_history",
        "review_observation",
        "delete_observation",
        "clear_history",
        "generate_report",
        "pause",
        "resume",
        "set_settings",
        "feedback",
        "snooze",
        "delete_all_data",
        "start_demo",
        "stop_demo",
        "shutdown",
        "set_inspector",
        "sequencer_send_message",
        "sequencer_action",
        "sequencer_get_conversations",
        "sequencer_get_conversation",
        "sequencer_new_conversation",
        "sequencer_delete_conversation",
        "sequencer_clear_history",
        "sequencer_update_preferences",
        "sequencer_rebuild_index",
        "sequencer_get_diagnostics",
        "sequencer_cancel_generation",
        "start_eye_control",
        "pause_eye_control",
        "resume_eye_control",
        "stop_eye_control",
        "emergency_stop",
        "gaze_start_calibration",
        "gaze_advance_calibration",
        "gaze_reset_calibration",
        "gaze_update_settings",
        "gaze_get_status",
        "gaze_start_diagnostic",
        "gaze_finish_diagnostic",
        "gaze_set_tracking_mode",
        "gaze_set_preset",
        "gaze_recenter",
        "gaze_reset_cursor",
    ]
    settings: Optional[SettingsPayload] = None
    gaze_settings: Optional[Dict[str, Any]] = None
    tracking_mode: Optional[str] = None
    preset: Optional[str] = None
    id: Optional[str] = None
    kind: Optional[Literal["helped", "not_now", "wrong_guess", "useful", "incorrect", "uncertain"]] = None
    duration_minutes: Optional[int] = None
    scenario: Optional[str] = None
    inspector_active: Optional[bool] = None
    show_camera_preview: Optional[bool] = None
    stage: Optional[str] = None
    target_idx: Optional[int] = None
    filter_state: Optional[str] = None
    notes: Optional[str] = None
    start_ts: Optional[float] = None
    end_ts: Optional[float] = None
    # Sequencer fields
    conversation_id: Optional[str] = None
    message_text: Optional[str] = None
    action_name: Optional[str] = None
    task_id: Optional[str] = None
    energy_level: Optional[int] = None
    feedback_comment: Optional[str] = None
    title: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------
# Serialization Helpers
# ---------------------------------------------------------

def serialize_message(model: BaseModel) -> str:
    """Serializes a pydantic model to a single-line JSON string."""
    return model.model_dump_json()


def parse_incoming_line(line: str) -> Optional[Union[CommandMessage, OsSignalsEvent]]:
    """Parses a newline-delimited JSON line received from stdin."""
    stripped = line.strip()
    if not stripped:
        return None
    try:
        data = json.loads(stripped)
        msg_type = data.get("type")
        if msg_type == "command":
            return CommandMessage.model_validate(data)
        elif msg_type == "os_signals":
            return OsSignalsEvent.model_validate(data)
        return None
    except Exception:
        return None

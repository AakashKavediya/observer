/**
 * IPC Schema TypeScript Definitions
 * Observer Version 1.0.0
 */

export const SCHEMA_VERSION = "1.0.0";

export type CameraStatus = "off" | "starting" | "on" | "blocked" | "unplugged";
export type EngineMode = "live" | "demo";

export interface StatusEvent {
  schema_version: string;
  type: "status";
  camera: CameraStatus;
  mode: EngineMode;
  calibrating: boolean;
  paused: boolean;
  fps: number;
  engine_ok: boolean;
}

export interface CameraTelemetry {
  status: CameraStatus;
  fps: number;
  width: number;
  height: number;
  device_index: number;
}

export interface EarTelemetry {
  left: number;
  right: number;
  avg: number;
  baseline_mean: number;
  baseline_std: number;
  is_blink: boolean;
  valid?: boolean;
  quality_reason?: string;
}

export interface BlinkTelemetry {
  count_total: number;
  rate_30s: number;
  rate_60s: number;
  rate_180s: number;
  irregularity: number;
  valid?: boolean;
  quality_reason?: string;
}

export interface GazeTelemetry {
  x: number;
  y: number;
  raw_x: number;
  raw_y: number;
  iris_l: [number, number];
  iris_r: [number, number];
  dispersion_4s: number;
  dispersion_30s: number;
  dispersion_120s: number;
  shifts_per_min: number;
  baseline_disp_mean: number;
  valid?: boolean;
  quality_reason?: string;
}

export interface TensionTelemetry {
  index: number;
  brow_down: number;
  mouth_press: number;
  jaw_clench: number;
  eye_squint: number;
  baseline_mean: number;
  baseline_std: number;
  valid?: boolean;
  quality_reason?: string;
}

export interface HeadPoseTelemetry {
  pitch: number;
  yaw: number;
  roll: number;
  variance_4s: number;
  variance_30s: number;
  baseline_var_mean: number;
  valid?: boolean;
  quality_reason?: string;
}

export interface VisionTelemetry {
  face_detected: boolean;
  quality_valid: boolean;
  quality_reason: string;
  mean_brightness: number;
  landmark_count?: number;
  frame_timestamp?: number;
  frame_seq?: number;
  ear: EarTelemetry;
  blinks: BlinkTelemetry;
  gaze: GazeTelemetry;
  tension: TensionTelemetry;
  head_pose: HeadPoseTelemetry;
  landmarks_wireframe?: number[][];
  frame_jpeg_base64?: string | null;
}

export interface DesktopInputTelemetry {
  idle_seconds: number;
  seconds_since_last_key: number;
  seconds_since_last_mouse: number;
  seconds_since_last_scroll: number;
  key_count_window: number;
  mouse_move_count_window: number;
  mouse_click_count_window: number;
  mouse_scroll_count_window: number;
  window_switch_count_60s: number;
  productive_input_score: number;
  monitor_status: "active" | "permission_denied" | "unsupported" | "disabled";
}

export interface FrozenComponents {
  fixation: number;
  idle: number;
  tension: number;
  blink_anomaly: number;
  stillness: number;
}

export interface SpinningComponents {
  switching: number;
  tension: number;
  unproductive: number;
}

export interface InterventionStatusTelemetry {
  eligible: boolean;
  reason: string;
  cooldown_remaining_s: number;
}

export interface PredictionTelemetry {
  state: ObserverState;
  frozen_score: number;
  frozen_components: FrozenComponents;
  frozen_weights: FrozenComponents;
  spinning_score: number;
  spinning_components: SpinningComponents;
  smoothed_frozen: number;
  smoothed_spinning: number;
  enter_threshold: number;
  exit_threshold: number;
  dwell_duration_seconds: number;
  dwell_required_seconds: number;
  dwell_satisfied: boolean;
  confidence: number;
  top_signals: string[];
  excluded_or_invalid_signals: string[];
  exact_decision_rule: string;
  intervention_status: InterventionStatusTelemetry;
}

export interface PipelineDiagnostics {
  camera_fps: number;
  camera_frames_captured: number;
  camera_brightness: number;
  landmarker_model_loaded: boolean;
  landmarker_total_inferences: number;
  landmarker_successful_detections: number;
  landmarker_detection_rate_pct: number;
  landmarker_last_landmark_count: number;
  ipc_sequence_number: number;
}

export interface TelemetryEvent {
  schema_version: string;
  type: "telemetry";
  seq: number;
  ts: number;
  camera: CameraTelemetry;
  vision: VisionTelemetry;
  desktop_input: DesktopInputTelemetry;
  prediction: PredictionTelemetry;
  diagnostics?: PipelineDiagnostics;
}

export interface CalibrationProgressEvent {
  schema_version: string;
  type: "calibration_progress";
  phase: string;
  percent: number;
  step_index?: number;
  total_steps?: number;
  target_index?: number | null;
  target_label?: string | null;
  valid_samples?: number;
  rejected_samples?: number;
  tracking_quality_pct?: number;
  message?: string | null;
  calibration_data?: Record<string, unknown> | null;
  failed_checks?: string[] | null;
}

export interface ObservationContributingFeature {
  feature: string;
  measured_value: string;
  baseline_value: string;
  deviation: string;
  window: string;
  valid: boolean;
  contribution: string;
}

export interface ObservationRecord {
  event_id: string;
  start_ts: number;
  end_ts: number;
  duration_seconds: number;
  state: ObserverState;
  score: number;
  scoring_method: string;
  contributing_features: ObservationContributingFeature[];
  evidence_strength: string;
  data_quality_status: string;
  qualification_reason: string;
  user_review?: "useful" | "incorrect" | "uncertain" | null;
  user_notes?: string | null;
  created_at_iso: string;
}

export interface ObservationItemEvent {
  schema_version: string;
  type: "observation_item";
  observation: ObservationRecord;
}

export interface HistoryListEvent {
  schema_version: string;
  type: "history_list";
  records: ObservationRecord[];
}

export interface ReportGeneratedEvent {
  schema_version: string;
  type: "report_generated";
  report: {
    reporting_period: string;
    total_observations: number;
    total_episode_duration_seconds: number;
    state_distribution: Record<string, number>;
    user_feedback_summary: Record<string, number>;
    records: ObservationRecord[];
    csv_export: string;
    limitations_notice: string;
  };
}

export type ObserverState =
  | "RELAXED"
  | "FOCUSED"
  | "PARALYSIS_LIKELY"
  | "OVERLOAD_LIKELY"
  | "UNKNOWN";

export interface StateProbabilities {
  relaxed: number;
  focused: number;
  paralysis: number;
  overload: number;
}

export interface StateUpdateEvent {
  schema_version: string;
  type: "state_update";
  state: ObserverState;
  probabilities: StateProbabilities;
  confidence: number;
  top_signals: string[];
  ts: number;
}

export interface InterventionAction {
  id: string;
  label: string;
}

export interface InterventionEvent {
  schema_version: string;
  type: "intervention";
  tier: number;
  id: string;
  text: string;
  actions: InterventionAction[];
}

export interface ErrorEvent {
  schema_version: string;
  type: "error";
  code: string;
  message_friendly: string;
}

// ---------------------------------------------------------
// Track 2: Task Sequencer Types
// ---------------------------------------------------------

export interface SourceReference {
  doc_id: string;
  title: string;
  url?: string;
  author_or_org?: string;
  category?: string;
  excerpt: string;
  relevance_score: number;
}

export interface MicroStep {
  step_id: string;
  action_text: string;
  why_suggested: string;
  estimated_effort: string;
  started_immediately: boolean;
  setup_required?: string;
  source_strategy?: string;
  completed: boolean;
  completed_at?: number | null;
}

export interface TaskRecord {
  task_id: string;
  title: string;
  description?: string;
  status: "pending" | "in_progress" | "completed" | "paused" | "deferred";
  current_micro_step?: MicroStep | null;
  step_history: MicroStep[];
  energy_level_reported: number;
  deadline?: string | null;
  planner_task_id?: string | null;
  created_at: number;
  updated_at: number;
}

export interface SequencerResponseContract {
  message: string;
  intent: string;
  current_task?: TaskRecord | null;
  micro_step?: MicroStep | null;
  estimated_effort: string;
  alternatives: string[];
  break_option: boolean;
  sources: SourceReference[];
  requires_clarification: boolean;
  limitations: string;
}

export interface SequencerMessageItem {
  id: string;
  conversation_id: string;
  sender: "user" | "assistant" | "system";
  content: string;
  contract?: SequencerResponseContract | null;
  created_at: number;
}

export interface SequencerConversationSummary {
  id: string;
  title: string;
  message_count: number;
  created_at: number;
  updated_at: number;
}

export interface SequencerDiagnosticsData {
  llm_provider: string;
  model_name: string;
  ollama_endpoint: string;
  ollama_connected: boolean;
  model_installed: boolean;
  available_models: string[];
  embedding_model: string;
  vector_index_ready: boolean;
  indexed_documents_count: number;
  indexed_chunks_count: number;
  last_index_build_ts: number;
  last_retrieval_query: string;
  last_retrieval_matches_count: number;
  last_retrieval_latency_ms: number;
  last_generation_latency_ms: number;
  observer_integration_active: boolean;
  observer_state_estimate: string;
  planner_integration_active: boolean;
  planner_status_message: string;
}

export interface SequencerStatusEvent {
  schema_version: string;
  type: "sequencer_status";
  llm_provider: string;
  model_name: string;
  ollama_connected: boolean;
  model_installed: boolean;
  available_models: string[];
  rag_index_ready: boolean;
  rag_documents_count: number;
  rag_chunks_count: number;
  error_message?: string | null;
}

export interface SequencerResponseEvent {
  schema_version: string;
  type: "sequencer_response";
  conversation_id: string;
  message_id: string;
  contract: SequencerResponseContract;
  task?: TaskRecord | null;
}

export interface SequencerDiagnosticsEvent {
  schema_version: string;
  type: "sequencer_diagnostics";
  diagnostics: SequencerDiagnosticsData;
}

export interface SequencerConversationsListEvent {
  schema_version: string;
  type: "sequencer_conversations_list";
  conversations: SequencerConversationSummary[];
}

export interface SequencerConversationLoadedEvent {
  schema_version: string;
  type: "sequencer_conversation_loaded";
  conversation_id: string;
  messages: SequencerMessageItem[];
  active_task?: TaskRecord | null;
}

export type EngineEvent =
  | StatusEvent
  | TelemetryEvent
  | CalibrationProgressEvent
  | StateUpdateEvent
  | InterventionEvent
  | ErrorEvent
  | ObservationItemEvent
  | HistoryListEvent
  | ReportGeneratedEvent
  | SequencerStatusEvent
  | SequencerResponseEvent
  | SequencerDiagnosticsEvent
  | SequencerConversationsListEvent
  | SequencerConversationLoadedEvent
  | GazeStatusEvent
  | GazeCalibrationEvent
  | GazeDiagnosticEvent
  | GazeCursorMoveEvent
  | MotionQDwellEvent
  | MotionQProfileListEvent
  | MotionQPredictionEvent
  | MotionQCalibrationStatusEvent
  | HealthTechSnapshotEvent
  | HealthTechCheckInListEvent
  | HealthTechObservationsListEvent
  | HealthTechSessionsListEvent
  | HealthTechEventsListEvent
  | HealthTechBaselineEvent
  | HealthTechReportEvent;

// ---------------------------------------------------------
// Health-Tech Physiological & Behavioral Interfaces
// ---------------------------------------------------------

export interface HealthTechSnapshotEvent {
  schema_version: string;
  type: "ht_snapshot";
  session_id: string;
  timestamp: number;
  valid: boolean;
  quality_reason: string;
  ear_left?: number | null;
  ear_right?: number | null;
  ear_avg?: number | null;
  is_blink: boolean;
  blink_count_total: number;
  blink_rate_60s?: number | null;
  ibi_median?: number | null;
  ibi_std?: number | null;
  last_closure_duration?: number | null;
  is_long_closure: boolean;
  eye_aperture_variability_30s?: number | null;
  gaze_dispersion_30s?: number | null;
  gaze_shifts_per_min?: number | null;
  mouth_corner_elevation_left?: number | null;
  mouth_corner_elevation_right?: number | null;
  mouth_width_ratio?: number | null;
  smile_score_avg?: number | null;
  smile_asymmetry?: number | null;
  smile_duration_above_thresh_30s?: number | null;
  smile_event_count_total: number;
  brow_elevation_left?: number | null;
  brow_elevation_right?: number | null;
  brow_asymmetry?: number | null;
  mouth_opening_ratio?: number | null;
  jaw_open_score?: number | null;
  pitch?: number | null;
  yaw?: number | null;
  roll?: number | null;
  angular_velocity?: number | null;
  head_movement_range_30s?: number | null;
  direction_changes_per_min?: number | null;
  low_movement_duration_s: number;
  upper_body_available: boolean;
  upper_body_reason: string;
  shoulder_tilt_deg?: number | null;
  usable_ratio: number;
  mean_brightness: number;
  blur_score: number;
  fps: number;
  coverage_ratio: number;
}

export interface HealthTechCheckInRecord {
  checkin_id: string;
  session_id?: string | null;
  timestamp: number;
  energy?: number | null;
  effort?: number | null;
  task_difficulty?: number | null;
  feeling_stuck?: boolean | null;
  discomfort?: number | null;
  stress?: number | null;
  sleep_quality?: number | null;
  notes?: string | null;
  task_id?: string | null;
  created_at_iso?: string;
}

export interface HealthTechCheckInListEvent {
  schema_version: string;
  type: "ht_checkins_list";
  checkins: HealthTechCheckInRecord[];
}

export interface HealthTechObservationItem {
  observation_id: string;
  session_id: string;
  timestamp: number;
  monotonic_time: number;
  feature_name: string;
  measured_value?: number | null;
  unit: string;
  definition_version: string;
  source_stream: string;
  validity_status: string;
  missing_data_reason?: string | null;
  signal_quality?: Record<string, unknown> | null;
  baseline_reference?: Record<string, unknown> | null;
  algorithm_version: string;
  provenance: string;
}

export interface HealthTechObservationsListEvent {
  schema_version: string;
  type: "ht_observations_list";
  observations: HealthTechObservationItem[];
}

export interface HealthTechSessionItem {
  session_id: string;
  start_time: number;
  end_time?: number | null;
  duration_seconds: number;
  total_frames: number;
  valid_frames: number;
  coverage_ratio: number;
  active_streams: string[];
  associated_task_id?: string | null;
  associated_task_title?: string | null;
  checkin_count: number;
  event_count: number;
  status: string;
}

export interface HealthTechSessionsListEvent {
  schema_version: string;
  type: "ht_sessions_list";
  sessions: HealthTechSessionItem[];
}

export interface HealthTechEventItem {
  event_id: string;
  session_id: string;
  event_type: string;
  start_time: number;
  end_time: number;
  duration_seconds: number;
  supporting_measurements: Array<{ name: string; value: unknown; threshold?: string }>;
  feature_validity: string;
  baseline_comparison: string;
  rule_version: string;
  explanation: string;
  uncertainty: string;
  is_user_reported: boolean;
  created_at_iso?: string;
}

export interface HealthTechEventsListEvent {
  schema_version: string;
  type: "ht_events_list";
  events: HealthTechEventItem[];
}

export interface HealthTechBaselineEvent {
  schema_version: string;
  type: "ht_baseline_event";
  profile: Record<string, unknown>;
}

export interface HealthTechReportEvent {
  schema_version: string;
  type: "ht_report_event";
  report: Record<string, unknown>;
}

export interface SettingsPayload {
  sensitivity?: number;
  cooldown_mins?: number;
  quiet_hours_enabled?: boolean;
  quiet_hours_start?: string;
  quiet_hours_end?: string;
  intervention_tier?: number;
  enabled_signals?: {
    gaze_fixation?: boolean;
    facial_tension?: boolean;
    blink_anomaly?: boolean;
    idle_time?: boolean;
    window_switching?: boolean;
  };
  high_contrast?: boolean;
  reduce_motion?: boolean;
  font_size_scale?: number;
  start_with_windows?: boolean;
}

export type FeedbackKind = "helped" | "not_now" | "wrong_guess" | "useful" | "incorrect" | "uncertain";

export type CommandMessage =
  | { schema_version: string; type: "command"; name: "start_calibration" }
  | { schema_version: string; type: "command"; name: "cancel_calibration" }
  | { schema_version: string; type: "command"; name: "start_calibration_stage"; stage: string; target_idx?: number }
  | { schema_version: string; type: "command"; name: "complete_gaze_target" }
  | { schema_version: string; type: "command"; name: "finalize_calibration" }
  | { schema_version: string; type: "command"; name: "get_calibration" }
  | { schema_version: string; type: "command"; name: "get_history"; filter_state?: string; start_ts?: number; end_ts?: number }
  | { schema_version: string; type: "command"; name: "review_observation"; id: string; kind: FeedbackKind; notes?: string }
  | { schema_version: string; type: "command"; name: "delete_observation"; id: string }
  | { schema_version: string; type: "command"; name: "clear_history" }
  | { schema_version: string; type: "command"; name: "generate_report"; start_ts?: number; end_ts?: number }
  | { schema_version: string; type: "command"; name: "pause" }
  | { schema_version: string; type: "command"; name: "resume" }
  | { schema_version: string; type: "command"; name: "set_settings"; settings: SettingsPayload }
  | { schema_version: string; type: "command"; name: "feedback"; id: string; kind: FeedbackKind }
  | { schema_version: string; type: "command"; name: "snooze"; duration_minutes: number }
  | { schema_version: string; type: "command"; name: "delete_all_data" }
  | { schema_version: string; type: "command"; name: "set_inspector"; inspector_active: boolean; show_camera_preview: boolean }
  | { schema_version: string; type: "command"; name: "start_demo"; scenario?: string }
  | { schema_version: string; type: "command"; name: "stop_demo" }
  | { schema_version: string; type: "command"; name: "shutdown" }
  | { schema_version: string; type: "command"; name: "sequencer_send_message"; conversation_id?: string; message_text: string; energy_level?: number }
  | { schema_version: string; type: "command"; name: "sequencer_action"; conversation_id: string; action_name: string; task_id?: string; feedback_comment?: string }
  | { schema_version: string; type: "command"; name: "sequencer_get_conversations" }
  | { schema_version: string; type: "command"; name: "sequencer_get_conversation"; conversation_id: string }
  | { schema_version: string; type: "command"; name: "sequencer_new_conversation"; title?: string }
  | { schema_version: string; type: "command"; name: "sequencer_delete_conversation"; conversation_id: string }
  | { schema_version: string; type: "command"; name: "sequencer_clear_history" }
  | { schema_version: string; type: "command"; name: "sequencer_update_preferences"; preferences: Record<string, unknown> }
  | { schema_version: string; type: "command"; name: "sequencer_rebuild_index" }
  | { schema_version: string; type: "command"; name: "sequencer_get_diagnostics" }
  | { schema_version: string; type: "command"; name: "sequencer_cancel_generation" }
  | { schema_version: string; type: "command"; name: "start_eye_control" }
  | { schema_version: string; type: "command"; name: "pause_eye_control" }
  | { schema_version: string; type: "command"; name: "resume_eye_control" }
  | { schema_version: string; type: "command"; name: "stop_eye_control" }
  | { schema_version: string; type: "command"; name: "emergency_stop" }
  | { schema_version: string; type: "command"; name: "gaze_start_calibration" }
  | { schema_version: string; type: "command"; name: "gaze_advance_calibration" }
  | { schema_version: string; type: "command"; name: "gaze_reset_calibration" }
  | { schema_version: string; type: "command"; name: "gaze_update_settings"; gaze_settings: Record<string, unknown> }
  | { schema_version: string; type: "command"; name: "gaze_get_status" }
  | { schema_version: string; type: "command"; name: "gaze_start_diagnostic"; duration_minutes?: number }
  | { schema_version: string; type: "command"; name: "gaze_finish_diagnostic" }
  | { schema_version: string; type: "command"; name: "gaze_set_tracking_mode"; tracking_mode: string }
  | { schema_version: string; type: "command"; name: "gaze_set_preset"; preset: string }
  | { schema_version: string; type: "command"; name: "gaze_set_controller_mode"; controller_mode: "relative" | "absolute" | "motionq_eye" }
  | { schema_version: string; type: "command"; name: "gaze_recenter" }
  | { schema_version: string; type: "command"; name: "gaze_reset_cursor" }
  | { schema_version: string; type: "command"; name: "motionq_get_status" }
  | { schema_version: string; type: "command"; name: "motionq_register_target"; target_data: Record<string, unknown> }
  | { schema_version: string; type: "command"; name: "motionq_unregister_target"; target_id: string }
  | { schema_version: string; type: "command"; name: "motionq_clear_targets" }
  | { schema_version: string; type: "command"; name: "motionq_set_click_mode"; click_mode: "single" | "double" | null }
  | { schema_version: string; type: "command"; name: "motionq_toggle_click_mode"; click_mode: "single" | "double" }
  | { schema_version: string; type: "command"; name: "motionq_start_calibration" }
  | { schema_version: string; type: "command"; name: "motionq_advance_calibration" }
  | { schema_version: string; type: "command"; name: "motionq_cancel_calibration" }
  | { schema_version: string; type: "command"; name: "motionq_load_profile"; profile_name: string }
  | { schema_version: string; type: "command"; name: "motionq_save_profile"; profile_name: string; profile_data: Record<string, unknown> }
  | { schema_version: string; type: "command"; name: "motionq_list_profiles" }
  | { schema_version: string; type: "command"; name: "motionq_create_profile"; profile_name: string }
  | { schema_version: string; type: "command"; name: "motionq_delete_profile"; profile_name: string }
  | { schema_version: string; type: "command"; name: "motionq_reset_profile"; profile_name?: string }
  | { schema_version: string; type: "command"; name: "motionq_set_head_scroll"; head_scroll_enabled?: boolean; head_neutral_y?: number; head_tilt_threshold?: number }
  | { schema_version: string; type: "command"; name: "motionq_word_predict"; prefix: string; language?: string }
  | { schema_version: string; type: "command"; name: "motionq_voice_command"; transcript: string }
  | { schema_version: string; type: "command"; name: "motionq_type_text"; text: string }
  | { schema_version: string; type: "command"; name: "motionq_key_combo"; combo: string }
  | { schema_version: string; type: "command"; name: "motionq_key_press"; key: string };

export interface GazeStatusEvent {
  schema_version: string;
  type: "gaze_status";
  enabled: boolean;
  paused: boolean;
  emergency_stopped: boolean;
  tracking_valid: boolean;
  tracking_reason: string;
  last_valid_ts: number;
  cursor_norm_x: number;
  cursor_norm_y: number;
  is_calibrated: boolean;
  quality_label: string;
  validation_error: number;
  sensitivity: number;
  dead_zone: number;
  max_speed: number;
  smoothing_mode: string;
  controller_mode?: "relative" | "absolute" | "motionq_eye";
  tracking_mode: "nose_bridge" | "head_pose" | "hybrid";
  preset: "maximum_stability" | "balanced" | "responsive";
  is_calibrating: boolean;
  calib_target_idx: number;
  outlier_count: number;
  is_diagnosing: boolean;
  neutral_yaw?: number;
  neutral_pitch?: number;
  current_yaw?: number;
  current_pitch?: number;
  deflection_x?: number;
  deflection_y?: number;
  normalized_ux?: number;
  normalized_uy?: number;
  scale_x?: number;
  scale_y?: number;
  noise_mad?: number;
  velocity_x?: number;
  velocity_y?: number;
  in_dead_zone?: boolean;
  frame_age_ms?: number;
  hz?: number;
  is_neutral_calibrated?: boolean;
  dwell_progress?: number;
  dwell_target_name?: string | null;
  click_mode?: "single" | "double" | null;
  head_scroll_direction?: string | null;
  current_profile?: string;
  keyboard_language?: string;
}

export interface MotionQDwellEvent {
  schema_version: string;
  type: "motionq_dwell_event";
  progress: number;
  center_x: number;
  center_y: number;
  active_target?: Record<string, unknown> | null;
  click_mode?: "single" | "double" | null;
  fired: boolean;
  action?: string | null;
}

export interface MotionQProfileListEvent {
  schema_version: string;
  type: "motionq_profile_list_event";
  profiles: string[];
  active_profile: string;
  data?: Record<string, unknown> | null;
}

export interface MotionQPredictionEvent {
  schema_version: string;
  type: "motionq_prediction_event";
  prefix: string;
  language: string;
  predictions: string[];
}

export interface MotionQCalibrationStatusEvent {
  schema_version: string;
  type: "motionq_calibration_status";
  stage: string;
  target_index: number;
  target_label?: string | null;
  screen_x?: number | null;
  screen_y?: number | null;
  message?: string | null;
  validation_error_px?: number | null;
  complete: boolean;
}

export interface GazeDiagnosticEvent {
  schema_version: string;
  type: "gaze_diagnostic_event";
  timestamp: number;
  duration_seconds: number;
  sample_count: number;
  validity_rate_pct: number;
  outlier_rate_pct: number;
  stationary_jitter_px: number;
  drift_rate_px_per_sec: number;
  avg_latency_ms: number;
  stability_score: number;
  quality_rating: "Exceptional" | "Stable" | "Acceptable" | "Jittery";
  tracking_mode: string;
  preset: string;
}

export interface GazeCalibrationEvent {
  schema_version: string;
  type: "gaze_calibration_event";
  success: boolean;
  finished: boolean;
  message?: string;
  next_target_idx?: number;
  next_target?: {
    target_id: string;
    screen_x: number;
    screen_y: number;
    label: string;
  };
  quality_label?: string;
  validation_error?: number;
  profile?: Record<string, unknown>;
}

export interface GazeCursorMoveEvent {
  schema_version: string;
  type: "event";
  name: "gaze_cursor_move";
  norm_x: number;
  norm_y: number;
  valid: boolean;
  timestamp: number;
}

export interface AccessibilityPermissionStatus {
  granted: boolean;
  message: string;
}

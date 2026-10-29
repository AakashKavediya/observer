import { create } from "zustand";
import { parseVoiceCommand, voiceDispatcher } from "../services/voiceControl";
import {
  StatusEvent,
  CalibrationProgressEvent,
  StateUpdateEvent,
  InterventionEvent,
  ErrorEvent,
  EngineEvent,
  SettingsPayload,
  FeedbackKind,
  SCHEMA_VERSION,
} from "../types/ipc";

interface ObserverState {
  // Navigation & Consent
  consentGiven: boolean;
  activeScreen:
    | "welcome"
    | "home"
    | "sequencer"
    | "eye_control"
    | "calibration"
    | "intervention"
    | "settings"
    | "demo"
    | "privacy"
    | "observations";

  // Vision Inspector Popup
  inspectorOpen: boolean;
  showCameraPreview: boolean;
  latestTelemetry: import("../types/ipc").TelemetryEvent | null;
  eventsReceivedCount: number;

  // Track 4: Eye Control & Voice Mouse State
  gazeStatus: import("../types/ipc").GazeStatusEvent | null;
  gazeCursor: { norm_x: number; norm_y: number; valid: boolean; timestamp: number };
  gazeCalibrationEvent: import("../types/ipc").GazeCalibrationEvent | null;
  gazeDiagnosticResult: import("../types/ipc").GazeDiagnosticEvent | null;
  accessibilityPermission: import("../types/ipc").AccessibilityPermissionStatus | null;
  voiceControlActive: boolean;
  lastVoiceResult: import("../services/voiceControl").ExecutionResult | null;

  // Track 2: Task Sequencer State
  sequencerConversations: import("../types/ipc").SequencerConversationSummary[];
  activeConversationId: string | null;
  sequencerMessages: import("../types/ipc").SequencerMessageItem[];
  sequencerActiveTask: import("../types/ipc").TaskRecord | null;
  sequencerStatus: import("../types/ipc").SequencerStatusEvent | null;
  sequencerDiagnostics: import("../types/ipc").SequencerDiagnosticsData | null;
  sequencerLoading: boolean;
  sequencerError: string | null;
  userEnergyLevel: number;

  // Engine State
  engineConnected: boolean;
  status: StatusEvent;
  currentState: StateUpdateEvent | null;
  calibrationProgress: CalibrationProgressEvent | null;
  activeIntervention: InterventionEvent | null;
  lastError: ErrorEvent | null;

  // History & Reports State
  historyRecords: import("../types/ipc").ObservationRecord[];
  generatedReport: import("../types/ipc").ReportGeneratedEvent["report"] | null;

  // Settings
  settings: SettingsPayload;

  // Actions
  setConsentGiven: (val: boolean) => void;
  setActiveScreen: (screen: ObserverState["activeScreen"]) => void;
  handleIncomingEngineEvent: (event: EngineEvent) => void;
  sendPause: () => Promise<void>;
  sendResume: () => Promise<void>;
  sendStartCalibration: () => Promise<void>;
  sendCancelCalibration: () => Promise<void>;
  sendStartCalibrationStage: (stage: string, target_idx?: number) => Promise<void>;
  sendCompleteGazeTarget: () => Promise<void>;
  sendFinalizeCalibration: () => Promise<void>;
  sendGetCalibration: () => Promise<void>;
  fetchHistory: (filterState?: string, startTs?: number, endTs?: number) => Promise<void>;
  sendReviewObservation: (id: string, kind: FeedbackKind, notes?: string) => Promise<void>;
  sendDeleteObservation: (id: string) => Promise<void>;
  sendClearHistory: () => Promise<void>;
  sendGenerateReport: (startTs?: number, endTs?: number) => Promise<void>;
  clearGeneratedReport: () => void;
  sendFeedback: (id: string, kind: FeedbackKind) => Promise<void>;
  sendStartDemo: () => Promise<void>;
  sendStopDemo: () => Promise<void>;
  sendDeleteAllData: () => Promise<void>;
  updateSettings: (newSettings: Partial<SettingsPayload>) => Promise<void>;
  dismissIntervention: () => void;
  openInspector: () => void;
  closeInspector: () => void;
  toggleCameraPreview: () => void;

  // Track 2: Sequencer Actions
  sendSequencerMessage: (text: string, energyLevel?: number) => Promise<void>;
  sendSequencerAction: (
    action:
      | "make_smaller"
      | "make_easier"
      | "change_approach"
      | "explain_another_way"
      | "next_step"
      | "complete_step"
      | "done"
      | "say_it_again"
      | "take_break"
      | "not_now",
    comment?: string
  ) => Promise<void>;
  fetchSequencerConversations: () => Promise<void>;
  loadSequencerConversation: (id: string) => Promise<void>;
  createSequencerConversation: (title?: string) => Promise<void>;
  deleteSequencerConversation: (id: string) => Promise<void>;
  clearSequencerHistory: () => Promise<void>;
  setUserEnergyLevel: (level: number) => Promise<void>;
  rebuildRagIndex: () => Promise<void>;
  fetchSequencerDiagnostics: () => Promise<void>;
  cancelSequencerGeneration: () => Promise<void>;

  // Track 4: Eye Control & Voice Mouse Actions
  startEyeControl: () => Promise<void>;
  pauseEyeControl: () => Promise<void>;
  resumeEyeControl: () => Promise<void>;
  stopEyeControl: () => Promise<void>;
  emergencyStop: () => Promise<void>;
  recenterNeutral: () => Promise<void>;
  resetCursorToCenter: () => Promise<void>;
  gazeStartCalibration: () => Promise<void>;
  gazeAdvanceCalibration: () => Promise<void>;
  gazeResetCalibration: () => Promise<void>;
  gazeUpdateSettings: (settings: Record<string, unknown>) => Promise<void>;
  setTrackingMode: (mode: "nose_bridge" | "head_pose" | "hybrid") => Promise<void>;
  setStabilityPreset: (preset: "maximum_stability" | "balanced" | "responsive") => Promise<void>;
  startStabilityDiagnostic: (durationSeconds?: number) => Promise<void>;
  finishStabilityDiagnostic: () => Promise<void>;
  fetchGazeStatus: () => Promise<void>;
  checkAccessibilityPermission: () => Promise<void>;
  nativeMouseClick: (button: string, double?: boolean) => Promise<void>;
  nativeMouseScroll: (delta_y: number) => Promise<void>;
  nativeMouseMove: (norm_x: number, norm_y: number) => Promise<void>;
  setVoiceControlActive: (active: boolean) => void;
  dispatchVoiceCommand: (transcript: string) => import("../services/voiceControl").ExecutionResult;
}

// Safely attempt Tauri invoke if available
async function safeTauriInvoke(command: string, args: Record<string, unknown> = {}): Promise<unknown> {
  if (typeof window !== "undefined" && ("__TAURI_INTERNALS__" in window || "__TAURI__" in window)) {
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      return await invoke(command, args);
    } catch (err) {
      console.warn(`[Tauri Invoke Error] ${command}:`, err);
    }
  } else {
    // In browser mock / dev without Tauri
    console.debug(`[Mock IPC Dispatch] ${command}`, args);
  }
  return null;
}

export const useObserverStore = create<ObserverState>((set, get) => ({
  consentGiven: false,
  activeScreen: "welcome",

  inspectorOpen: false,
  showCameraPreview: true,
  latestTelemetry: null,
  eventsReceivedCount: 0,

  // Track 4 Initial State
  gazeStatus: null,
  gazeCursor: { norm_x: 0.5, norm_y: 0.5, valid: false, timestamp: 0 },
  gazeCalibrationEvent: null,
  gazeDiagnosticResult: null,
  accessibilityPermission: null,
  voiceControlActive: false,
  lastVoiceResult: null,

  // Track 2 Sequencer initial state
  sequencerConversations: [],
  activeConversationId: null,
  sequencerMessages: [],
  sequencerActiveTask: null,
  sequencerStatus: null,
  sequencerDiagnostics: null,
  sequencerLoading: false,
  sequencerError: null,
  userEnergyLevel: 3,

  historyRecords: [],
  generatedReport: null,

  engineConnected: true,
  status: {
    schema_version: SCHEMA_VERSION,
    type: "status",
    camera: "starting",
    mode: "live",
    calibrating: false,
    paused: false,
    fps: 0.0,
    engine_ok: true,
  },
  currentState: null,
  calibrationProgress: null,
  activeIntervention: null,
  lastError: null,

  settings: {
    sensitivity: 0.65,
    cooldown_mins: 20,
    quiet_hours_enabled: false,
    quiet_hours_start: "22:00",
    quiet_hours_end: "08:00",
    intervention_tier: 2,
    enabled_signals: {
      gaze_fixation: true,
      facial_tension: true,
      blink_anomaly: true,
      idle_time: true,
      window_switching: true,
    },
    high_contrast: false,
    reduce_motion: false,
    font_size_scale: 1.0,
    start_with_windows: false,
  },

  setConsentGiven: (val: boolean) => set({ consentGiven: val, activeScreen: val ? "home" : "welcome" }),

  setActiveScreen: (screen) => set({ activeScreen: screen }),

  handleIncomingEngineEvent: (event: EngineEvent) => {
    set((s) => ({ eventsReceivedCount: s.eventsReceivedCount + 1 }));
    switch (event.type) {
      case "status":
        set({ status: event });
        break;
      case "telemetry":
        set((s) => ({
          latestTelemetry: event,
          status: {
            ...s.status,
            camera: event.camera.status,
            fps: event.camera.fps,
          },
          currentState: {
            schema_version: SCHEMA_VERSION,
            type: "state_update",
            state: event.prediction.state,
            probabilities: {
              relaxed: event.prediction.state === "RELAXED" ? 0.8 : 0.1,
              focused: event.prediction.state === "FOCUSED" ? 0.8 : 0.1,
              paralysis: event.prediction.frozen_score,
              overload: event.prediction.spinning_score,
            },
            confidence: event.prediction.confidence,
            top_signals: event.prediction.top_signals,
            ts: event.ts,
          },
        }));
        break;
      case "calibration_progress":
        set({ calibrationProgress: event });
        break;
      case "observation_item":
        set((s) => ({
          historyRecords: [event.observation, ...s.historyRecords.filter((r) => r.event_id !== event.observation.event_id)],
        }));
        break;
      case "history_list":
        set({ historyRecords: event.records });
        break;
      case "report_generated":
        set({ generatedReport: event.report });
        break;
      case "state_update":
        set({ currentState: event });
        break;
      case "intervention":
        set({ activeIntervention: event });
        break;
      case "error":
        set({ lastError: event });
        break;
      case "sequencer_status":
        set({ sequencerStatus: event });
        break;
      case "sequencer_response":
        set((s) => {
          const newMsg: import("../types/ipc").SequencerMessageItem = {
            id: event.message_id,
            conversation_id: event.conversation_id,
            sender: "assistant",
            content: event.contract.message,
            contract: event.contract,
            created_at: Date.now() / 1000,
          };
          return {
            sequencerLoading: false,
            activeConversationId: event.conversation_id,
            sequencerMessages: [...s.sequencerMessages, newMsg],
            sequencerActiveTask: event.task ?? s.sequencerActiveTask,
          };
        });
        break;
      case "sequencer_diagnostics":
        set({ sequencerDiagnostics: event.diagnostics });
        break;
      case "sequencer_conversations_list":
        set({ sequencerConversations: event.conversations });
        break;
      case "sequencer_conversation_loaded":
        set({
          activeConversationId: event.conversation_id,
          sequencerMessages: event.messages,
          sequencerActiveTask: event.active_task ?? null,
          sequencerLoading: false,
        });
        break;
      case "gaze_status":
        set({ gazeStatus: event as import("../types/ipc").GazeStatusEvent });
        break;
      case "gaze_calibration_event":
        set({ gazeCalibrationEvent: event as import("../types/ipc").GazeCalibrationEvent });
        break;
      case "gaze_diagnostic_event":
        set({ gazeDiagnosticResult: event as import("../types/ipc").GazeDiagnosticEvent });
        break;
      case "event":
        if ((event as any).name === "gaze_cursor_move") {
          const move = event as import("../types/ipc").GazeCursorMoveEvent;
          set({
            gazeCursor: {
              norm_x: move.norm_x,
              norm_y: move.norm_y,
              valid: move.valid,
              timestamp: move.timestamp,
            },
          });
        }
        break;
    }
  },

  sendPause: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "pause" },
    });
    set((s) => ({ status: { ...s.status, paused: true, camera: "off", fps: 0.0 } }));
  },

  sendResume: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "resume" },
    });
    set((s) => ({ status: { ...s.status, paused: false, camera: "starting" } }));
  },

  sendStartCalibration: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "start_calibration" },
    });
    set((s) => ({ status: { ...s.status, calibrating: true } }));
  },

  sendCancelCalibration: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "cancel_calibration" },
    });
    set((s) => ({
      status: { ...s.status, calibrating: false },
      calibrationProgress: null,
    }));
  },

  sendStartCalibrationStage: async (stage: string, target_idx?: number) => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "start_calibration_stage", stage, target_idx },
    });
    set((s) => ({ status: { ...s.status, calibrating: true } }));
  },

  sendCompleteGazeTarget: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "complete_gaze_target" },
    });
  },

  sendFinalizeCalibration: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "finalize_calibration" },
    });
  },

  sendGetCalibration: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "get_calibration" },
    });
  },

  fetchHistory: async (filterState?: string, startTs?: number, endTs?: number) => {
    await safeTauriInvoke("send_engine_command", {
      command: {
        schema_version: SCHEMA_VERSION,
        type: "command",
        name: "get_history",
        filter_state: filterState,
        start_ts: startTs,
        end_ts: endTs,
      },
    });
  },

  sendReviewObservation: async (id: string, kind: FeedbackKind, notes?: string) => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "review_observation", id, kind, notes },
    });
    // Optimistically update
    set((s) => ({
      historyRecords: s.historyRecords.map((r) =>
        r.event_id === id ? { ...r, user_review: kind as "useful" | "incorrect" | "uncertain", user_notes: notes } : r
      ),
    }));
  },

  sendDeleteObservation: async (id: string) => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "delete_observation", id },
    });
    set((s) => ({
      historyRecords: s.historyRecords.filter((r) => r.event_id !== id),
    }));
  },

  sendClearHistory: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "clear_history" },
    });
    set({ historyRecords: [] });
  },

  sendGenerateReport: async (startTs?: number, endTs?: number) => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "generate_report", start_ts: startTs, end_ts: endTs },
    });
  },

  clearGeneratedReport: () => set({ generatedReport: null }),

  sendFeedback: async (id: string, kind: FeedbackKind) => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "feedback", id, kind },
    });
    set({ activeIntervention: null });
  },

  sendStartDemo: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "start_demo" },
    });
  },

  sendStopDemo: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "stop_demo" },
    });
  },

  sendDeleteAllData: async () => {
    await safeTauriInvoke("delete_all_data");
    set({
      currentState: null,
      calibrationProgress: null,
      activeIntervention: null,
    });
  },

  updateSettings: async (newSettings: Partial<SettingsPayload>) => {
    const updated = { ...get().settings, ...newSettings };
    set({ settings: updated });
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "set_settings", settings: updated },
    });
  },

  dismissIntervention: () => set({ activeIntervention: null }),

  openInspector: () => {
    set({ inspectorOpen: true });
    safeTauriInvoke("send_engine_command", {
      command: {
        schema_version: SCHEMA_VERSION,
        type: "command",
        name: "set_inspector",
        inspector_active: true,
        show_camera_preview: get().showCameraPreview,
      },
    });
  },

  closeInspector: () => {
    set({ inspectorOpen: false });
    safeTauriInvoke("send_engine_command", {
      command: {
        schema_version: SCHEMA_VERSION,
        type: "command",
        name: "set_inspector",
        inspector_active: false,
        show_camera_preview: false,
      },
    });
  },

  toggleCameraPreview: () => {
    const nextVal = !get().showCameraPreview;
    set({ showCameraPreview: nextVal });
    safeTauriInvoke("send_engine_command", {
      command: {
        schema_version: SCHEMA_VERSION,
        type: "command",
        name: "set_inspector",
        inspector_active: get().inspectorOpen,
        show_camera_preview: nextVal,
      },
    });
  },

  sendSequencerMessage: async (text: string, energyLevel?: number) => {
    const cid = get().activeConversationId || undefined;
    const energy = energyLevel ?? get().userEnergyLevel;
    const optUserMsg: import("../types/ipc").SequencerMessageItem = {
      id: `temp_${Date.now()}`,
      conversation_id: cid || "",
      sender: "user",
      content: text,
      created_at: Date.now() / 1000,
    };
    set((s) => ({
      sequencerLoading: true,
      sequencerError: null,
      sequencerMessages: [...s.sequencerMessages, optUserMsg],
    }));

    await safeTauriInvoke("send_engine_command", {
      command: {
        schema_version: SCHEMA_VERSION,
        type: "command",
        name: "sequencer_send_message",
        conversation_id: cid,
        message_text: text,
        energy_level: energy,
      },
    });
  },

  sendSequencerAction: async (action, comment) => {
    const cid = get().activeConversationId;
    if (!cid) return;
    const task = get().sequencerActiveTask;
    set({ sequencerLoading: true });
    await safeTauriInvoke("send_engine_command", {
      command: {
        schema_version: SCHEMA_VERSION,
        type: "command",
        name: "sequencer_action",
        conversation_id: cid,
        action_name: action,
        task_id: task?.task_id,
        feedback_comment: comment,
      },
    });
  },

  fetchSequencerConversations: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "sequencer_get_conversations" },
    });
  },

  loadSequencerConversation: async (id: string) => {
    set({ sequencerLoading: true });
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "sequencer_get_conversation", conversation_id: id },
    });
  },

  createSequencerConversation: async (title?: string) => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "sequencer_new_conversation", title: title || "New Task Support" },
    });
  },

  deleteSequencerConversation: async (id: string) => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "sequencer_delete_conversation", conversation_id: id },
    });
    if (get().activeConversationId === id) {
      set({ activeConversationId: null, sequencerMessages: [], sequencerActiveTask: null });
    }
  },

  clearSequencerHistory: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "sequencer_clear_history" },
    });
    set({ sequencerConversations: [], activeConversationId: null, sequencerMessages: [], sequencerActiveTask: null });
  },

  setUserEnergyLevel: async (level: number) => {
    set({ userEnergyLevel: level });
    await safeTauriInvoke("send_engine_command", {
      command: {
        schema_version: SCHEMA_VERSION,
        type: "command",
        name: "sequencer_update_preferences",
        preferences: { energy_level: level },
      },
    });
  },

  rebuildRagIndex: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "sequencer_rebuild_index" },
    });
  },

  fetchSequencerDiagnostics: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "sequencer_get_diagnostics" },
    });
  },

  cancelSequencerGeneration: async () => {
    set({ sequencerLoading: false });
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "sequencer_cancel_generation" },
    });
  },

  // Track 4 Actions
  startEyeControl: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "start_eye_control" },
    });
    set((s) => ({
      gazeStatus: s.gazeStatus
        ? { ...s.gazeStatus, enabled: true, paused: false, emergency_stopped: false }
        : null,
    }));
  },

  pauseEyeControl: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "pause_eye_control" },
    });
    set((s) => ({
      gazeStatus: s.gazeStatus ? { ...s.gazeStatus, paused: true } : null,
    }));
  },

  resumeEyeControl: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "resume_eye_control" },
    });
    set((s) => ({
      gazeStatus: s.gazeStatus
        ? { ...s.gazeStatus, paused: false, emergency_stopped: false }
        : null,
    }));
  },

  stopEyeControl: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "stop_eye_control" },
    });
    set((s) => ({
      gazeStatus: s.gazeStatus ? { ...s.gazeStatus, enabled: false } : null,
    }));
  },

  emergencyStop: async () => {
    await safeTauriInvoke("native_mouse_emergency_stop");
    set((s) => ({
      gazeStatus: s.gazeStatus
        ? { ...s.gazeStatus, emergency_stopped: true, enabled: false, paused: true }
        : null,
    }));
  },

  recenterNeutral: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "gaze_recenter" },
    });
  },

  resetCursorToCenter: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "gaze_reset_cursor" },
    });
  },

  gazeStartCalibration: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "gaze_start_calibration" },
    });
  },

  gazeAdvanceCalibration: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "gaze_advance_calibration" },
    });
  },

  gazeResetCalibration: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "gaze_reset_calibration" },
    });
  },

  gazeUpdateSettings: async (settings: Record<string, unknown>) => {
    await safeTauriInvoke("send_engine_command", {
      command: {
        schema_version: SCHEMA_VERSION,
        type: "command",
        name: "gaze_update_settings",
        gaze_settings: settings,
      },
    });
  },

  setTrackingMode: async (mode: "nose_bridge" | "head_pose" | "hybrid") => {
    await safeTauriInvoke("send_engine_command", {
      command: {
        schema_version: SCHEMA_VERSION,
        type: "command",
        name: "gaze_set_tracking_mode",
        tracking_mode: mode,
      },
    });
  },

  setStabilityPreset: async (preset: "maximum_stability" | "balanced" | "responsive") => {
    await safeTauriInvoke("send_engine_command", {
      command: {
        schema_version: SCHEMA_VERSION,
        type: "command",
        name: "gaze_set_preset",
        preset,
      },
    });
  },

  startStabilityDiagnostic: async (durationSeconds: number = 5.0) => {
    await safeTauriInvoke("send_engine_command", {
      command: {
        schema_version: SCHEMA_VERSION,
        type: "command",
        name: "gaze_start_diagnostic",
        duration_minutes: durationSeconds,
      },
    });
  },

  finishStabilityDiagnostic: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: {
        schema_version: SCHEMA_VERSION,
        type: "command",
        name: "gaze_finish_diagnostic",
      },
    });
  },

  fetchGazeStatus: async () => {
    await safeTauriInvoke("send_engine_command", {
      command: { schema_version: SCHEMA_VERSION, type: "command", name: "gaze_get_status" },
    });
  },

  checkAccessibilityPermission: async () => {
    const res = await safeTauriInvoke("check_accessibility_permission");
    if (res && typeof res === "object") {
      set({ accessibilityPermission: res as import("../types/ipc").AccessibilityPermissionStatus });
    }
  },

  nativeMouseClick: async (button: string, double?: boolean) => {
    await safeTauriInvoke("native_mouse_click", { button, double: !!double });
  },

  nativeMouseScroll: async (delta_y: number) => {
    await safeTauriInvoke("native_mouse_scroll", { deltaY: delta_y });
  },

  nativeMouseMove: async (norm_x: number, norm_y: number) => {
    await safeTauriInvoke("native_mouse_move", { normX: norm_x, normY: norm_y });
  },

  setVoiceControlActive: (active: boolean) => {
    set({ voiceControlActive: active });
  },

  dispatchVoiceCommand: (transcript: string) => {
    const parsed = parseVoiceCommand(transcript);
    const state = get();
    const gateState = {
      isTrackingValid: state.gazeStatus?.tracking_valid ?? false,
      isPaused: state.gazeStatus?.paused ?? false,
      isEmergencyStopped: state.gazeStatus?.emergency_stopped ?? false,
      isEyeControlEnabled: state.gazeStatus?.enabled ?? false,
      lastGazeTs: state.gazeStatus?.last_valid_ts ?? Date.now() / 1000,
    };

    const res = voiceDispatcher.executeCommand(parsed, gateState, {
      onEmergencyStop: async () => state.emergencyStop(),
      onStartEyeControl: async () => state.startEyeControl(),
      onPauseEyeControl: async () => state.pauseEyeControl(),
      onResumeEyeControl: async () => state.resumeEyeControl(),
      onClick: async (double) => state.nativeMouseClick("left", double),
      onRightClick: async () => state.nativeMouseClick("right", false),
      onScroll: async (delta) => state.nativeMouseScroll(delta),
      onRecalibrate: async () => state.gazeStartCalibration(),
    });

    set({ lastVoiceResult: res });
    return res;
  },
}));

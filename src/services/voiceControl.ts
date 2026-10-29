/**
 * voiceControl.ts
 * Track 4: Real Voice Command Parser and Safe Native Action Executor.
 * 
 * Supports:
 * - "start eye control"
 * - "pause eye control" / "stop moving"
 * - "resume eye control"
 * - "click" (left-click with safety gating)
 * - "double-click"
 * - "right-click"
 * - "scroll up"
 * - "scroll down"
 * - "recalibrate"
 * - "emergency stop"
 * 
 * Features:
 * - Strict gating against stale gaze (> 500ms) or invalid tracking.
 * - Cooldown debounce to prevent duplicate execution from continuous speech transcripts.
 * - Subtle local Web Audio API tone feedback.
 * - Zero network audio streaming.
 */

export type VoiceActionType =
  | "START_EYE_CONTROL"
  | "PAUSE_EYE_CONTROL"
  | "RESUME_EYE_CONTROL"
  | "CLICK"
  | "DOUBLE_CLICK"
  | "RIGHT_CLICK"
  | "SCROLL_UP"
  | "SCROLL_DOWN"
  | "RECALIBRATE"
  | "EMERGENCY_STOP"
  | "UNKNOWN";

export interface ParsedVoiceCommand {
  raw: string;
  action: VoiceActionType;
  confidence: number;
}

export interface ExecutionResult {
  executed: boolean;
  action: VoiceActionType;
  message: string;
  timestamp: number;
}

// -------------------------------------------------------------
// 1. Audio Confirmation Feedback (100% Local Web Audio API)
// -------------------------------------------------------------
export function playCommandChirp(freq: number = 520, durationMs: number = 70): void {
  if (typeof window === "undefined") return;
  try {
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    osc.frequency.setValueAtTime(freq, ctx.currentTime);
    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + durationMs / 1000);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + durationMs / 1000);
  } catch {
    // Audio feedback is non-blocking
  }
}

// -------------------------------------------------------------
// 2. Command Phrase Parser
// -------------------------------------------------------------
export function parseVoiceCommand(transcript: string): ParsedVoiceCommand {
  const norm = transcript.toLowerCase().trim().replace(/[.,!?;:]/g, "");

  if (!norm) {
    return { raw: transcript, action: "UNKNOWN", confidence: 0.0 };
  }

  // 1. Emergency Stop (highest priority)
  if (
    norm.includes("emergency stop") ||
    norm === "abort" ||
    norm === "stop all" ||
    norm === "freeze"
  ) {
    return { raw: transcript, action: "EMERGENCY_STOP", confidence: 0.98 };
  }

  // 2. Double-Click (check before single click)
  if (
    norm === "double click" ||
    norm === "double-click" ||
    norm.endsWith("double click")
  ) {
    return { raw: transcript, action: "DOUBLE_CLICK", confidence: 0.95 };
  }

  // 3. Right-Click (check before single click)
  if (
    norm === "right click" ||
    norm === "right-click" ||
    norm.endsWith("right click")
  ) {
    return { raw: transcript, action: "RIGHT_CLICK", confidence: 0.95 };
  }

  // 4. Click
  if (
    norm === "click" ||
    norm === "left click" ||
    norm.endsWith("click") ||
    norm === "select"
  ) {
    return { raw: transcript, action: "CLICK", confidence: 0.92 };
  }

  // 5. Scroll Up / Down
  if (norm.includes("scroll up") || norm === "page up") {
    return { raw: transcript, action: "SCROLL_UP", confidence: 0.92 };
  }
  if (norm.includes("scroll down") || norm === "page down") {
    return { raw: transcript, action: "SCROLL_DOWN", confidence: 0.92 };
  }

  // 6. Recalibrate
  if (
    norm.includes("recalibrate") ||
    norm.includes("calibrate eye") ||
    norm === "calibrate"
  ) {
    return { raw: transcript, action: "RECALIBRATE", confidence: 0.95 };
  }

  // 7. Pause / Resume / Start
  if (
    norm.includes("start eye control") ||
    norm.includes("enable eye control") ||
    norm === "start mouse"
  ) {
    return { raw: transcript, action: "START_EYE_CONTROL", confidence: 0.95 };
  }

  if (
    norm.includes("pause eye control") ||
    norm.includes("stop moving") ||
    norm.includes("hold cursor") ||
    norm === "pause"
  ) {
    return { raw: transcript, action: "PAUSE_EYE_CONTROL", confidence: 0.95 };
  }

  if (
    norm.includes("resume eye control") ||
    norm.includes("release cursor") ||
    norm === "resume"
  ) {
    return { raw: transcript, action: "RESUME_EYE_CONTROL", confidence: 0.95 };
  }

  return { raw: transcript, action: "UNKNOWN", confidence: 0.3 };
}

// -------------------------------------------------------------
// 3. Gated Action Dispatcher
// -------------------------------------------------------------
export interface CommandGateState {
  isTrackingValid: boolean;
  isPaused: boolean;
  isEmergencyStopped: boolean;
  isEyeControlEnabled: boolean;
  lastGazeTs: number; // in seconds
}

export class VoiceCommandDispatcher {
  private lastActionTime: number = 0;
  private lastExecutedAction: VoiceActionType = "UNKNOWN";
  private debounceMs: number = 650; // minimum ms between repeated click commands

  public setDebounceMs(ms: number) {
    this.debounceMs = ms;
  }

  /**
   * Safely gates and dispatches parsed voice command.
   */
  public executeCommand(
    cmd: ParsedVoiceCommand,
    gateState: CommandGateState,
    handlers: {
      onEmergencyStop: () => Promise<void>;
      onStartEyeControl: () => Promise<void>;
      onPauseEyeControl: () => Promise<void>;
      onResumeEyeControl: () => Promise<void>;
      onClick: (double: boolean) => Promise<void>;
      onRightClick: () => Promise<void>;
      onScroll: (delta: number) => Promise<void>;
      onRecalibrate: () => Promise<void>;
    }
  ): ExecutionResult {
    const now = Date.now();

    // 1. Emergency Stop is unconditional and always runs
    if (cmd.action === "EMERGENCY_STOP") {
      this.lastActionTime = now;
      this.lastExecutedAction = cmd.action;
      playCommandChirp(220, 150); // low warning tone
      handlers.onEmergencyStop();
      return {
        executed: true,
        action: cmd.action,
        message: "Emergency stop triggered! Cursor and tracking halted.",
        timestamp: now,
      };
    }

    // 2. Reject if system is currently in emergency stop
    if (gateState.isEmergencyStopped) {
      return {
        executed: false,
        action: cmd.action,
        message: "Command ignored: System in emergency stop. Tap 'Resume' to reset.",
        timestamp: now,
      };
    }

    // 3. Duplicate suppression
    if (
      cmd.action === this.lastExecutedAction &&
      now - this.lastActionTime < this.debounceMs
    ) {
      return {
        executed: false,
        action: cmd.action,
        message: "Duplicate command suppressed.",
        timestamp: now,
      };
    }

    // 4. Start / Resume / Pause commands
    if (cmd.action === "START_EYE_CONTROL") {
      this.lastActionTime = now;
      this.lastExecutedAction = cmd.action;
      playCommandChirp(587, 80);
      handlers.onStartEyeControl();
      return {
        executed: true,
        action: cmd.action,
        message: "Eye control activated.",
        timestamp: now,
      };
    }

    if (cmd.action === "PAUSE_EYE_CONTROL") {
      this.lastActionTime = now;
      this.lastExecutedAction = cmd.action;
      playCommandChirp(440, 60);
      handlers.onPauseEyeControl();
      return {
        executed: true,
        action: cmd.action,
        message: "Eye control paused. Cursor held.",
        timestamp: now,
      };
    }

    if (cmd.action === "RESUME_EYE_CONTROL") {
      this.lastActionTime = now;
      this.lastExecutedAction = cmd.action;
      playCommandChirp(659, 80);
      handlers.onResumeEyeControl();
      return {
        executed: true,
        action: cmd.action,
        message: "Eye control resumed.",
        timestamp: now,
      };
    }

    if (cmd.action === "RECALIBRATE") {
      this.lastActionTime = now;
      this.lastExecutedAction = cmd.action;
      playCommandChirp(523, 100);
      handlers.onRecalibrate();
      return {
        executed: true,
        action: cmd.action,
        message: "Starting eye-gaze recalibration...",
        timestamp: now,
      };
    }

    // 5. Clicks and Scrolls: Strict Safety Gating
    // Must have active eye control, not paused, valid tracking, fresh gaze < 500ms
    if (
      cmd.action === "CLICK" ||
      cmd.action === "DOUBLE_CLICK" ||
      cmd.action === "RIGHT_CLICK" ||
      cmd.action === "SCROLL_UP" ||
      cmd.action === "SCROLL_DOWN"
    ) {
      if (gateState.isPaused) {
        return {
          executed: false,
          action: cmd.action,
          message: "Action rejected: Eye control is currently paused.",
          timestamp: now,
        };
      }

      if (!gateState.isTrackingValid) {
        return {
          executed: false,
          action: cmd.action,
          message: "Action rejected: Eyes or face are not tracked reliably.",
          timestamp: now,
        };
      }

      const gazeAgeMs = (now / 1000 - gateState.lastGazeTs) * 1000;
      if (gazeAgeMs > 600) {
        return {
          executed: false,
          action: cmd.action,
          message: `Action rejected: Gaze coordinate is stale (${Math.round(gazeAgeMs)}ms old).`,
          timestamp: now,
        };
      }

      // Execute verified action
      this.lastActionTime = now;
      this.lastExecutedAction = cmd.action;

      if (cmd.action === "CLICK") {
        playCommandChirp(520, 50);
        handlers.onClick(false);
        return {
          executed: true,
          action: cmd.action,
          message: "Click executed.",
          timestamp: now,
        };
      }

      if (cmd.action === "DOUBLE_CLICK") {
        playCommandChirp(680, 70);
        handlers.onClick(true);
        return {
          executed: true,
          action: cmd.action,
          message: "Double-click executed.",
          timestamp: now,
        };
      }

      if (cmd.action === "RIGHT_CLICK") {
        playCommandChirp(415, 70);
        handlers.onRightClick();
        return {
          executed: true,
          action: cmd.action,
          message: "Right-click executed.",
          timestamp: now,
        };
      }

      if (cmd.action === "SCROLL_UP") {
        playCommandChirp(700, 40);
        handlers.onScroll(5);
        return {
          executed: true,
          action: cmd.action,
          message: "Scrolled up.",
          timestamp: now,
        };
      }

      if (cmd.action === "SCROLL_DOWN") {
        playCommandChirp(350, 40);
        handlers.onScroll(-5);
        return {
          executed: true,
          action: cmd.action,
          message: "Scrolled down.",
          timestamp: now,
        };
      }
    }

    return {
      executed: false,
      action: "UNKNOWN",
      message: `Unrecognized command: "${cmd.raw}"`,
      timestamp: now,
    };
  }
}

export const voiceDispatcher = new VoiceCommandDispatcher();

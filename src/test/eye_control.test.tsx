import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EyeControlScreen } from "@/screens/EyeControlScreen";
import { useObserverStore } from "@/store/useObserverStore";
import {
  parseVoiceCommand,
  VoiceCommandDispatcher,
} from "@/services/voiceControl";

describe("Track 4: Voice Command Parser & Safety Gating", () => {
  it("parses voice commands accurately", () => {
    expect(parseVoiceCommand("click").action).toBe("CLICK");
    expect(parseVoiceCommand("please click").action).toBe("CLICK");
    expect(parseVoiceCommand("double click").action).toBe("DOUBLE_CLICK");
    expect(parseVoiceCommand("right-click").action).toBe("RIGHT_CLICK");
    expect(parseVoiceCommand("scroll up").action).toBe("SCROLL_UP");
    expect(parseVoiceCommand("scroll down").action).toBe("SCROLL_DOWN");
    expect(parseVoiceCommand("start eye control").action).toBe("START_EYE_CONTROL");
    expect(parseVoiceCommand("pause eye control").action).toBe("PAUSE_EYE_CONTROL");
    expect(parseVoiceCommand("stop moving").action).toBe("PAUSE_EYE_CONTROL");
    expect(parseVoiceCommand("resume eye control").action).toBe("RESUME_EYE_CONTROL");
    expect(parseVoiceCommand("recalibrate").action).toBe("RECALIBRATE");
    expect(parseVoiceCommand("emergency stop").action).toBe("EMERGENCY_STOP");
    expect(parseVoiceCommand("some random chatter").action).toBe("UNKNOWN");
  });

  it("safely rejects clicks when gaze tracking is invalid or face lost", () => {
    const dispatcher = new VoiceCommandDispatcher();
    const onClick = vi.fn();

    const gateState = {
      isTrackingValid: false, // face lost
      isPaused: false,
      isEmergencyStopped: false,
      isEyeControlEnabled: true,
      lastGazeTs: Date.now() / 1000,
    };

    const res = dispatcher.executeCommand(
      { raw: "click", action: "CLICK", confidence: 0.95 },
      gateState,
      {
        onEmergencyStop: vi.fn(),
        onStartEyeControl: vi.fn(),
        onPauseEyeControl: vi.fn(),
        onResumeEyeControl: vi.fn(),
        onClick,
        onRightClick: vi.fn(),
        onScroll: vi.fn(),
        onRecalibrate: vi.fn(),
      }
    );

    expect(res.executed).toBe(false);
    expect(res.message).toContain("not tracked reliably");
    expect(onClick).not.toHaveBeenCalled();
  });

  it("safely rejects clicks when gaze estimate is stale (> 600ms)", () => {
    const dispatcher = new VoiceCommandDispatcher();
    const onClick = vi.fn();

    const gateState = {
      isTrackingValid: true,
      isPaused: false,
      isEmergencyStopped: false,
      isEyeControlEnabled: true,
      lastGazeTs: Date.now() / 1000 - 1.5, // 1.5 seconds old (stale)
    };

    const res = dispatcher.executeCommand(
      { raw: "click", action: "CLICK", confidence: 0.95 },
      gateState,
      {
        onEmergencyStop: vi.fn(),
        onStartEyeControl: vi.fn(),
        onPauseEyeControl: vi.fn(),
        onResumeEyeControl: vi.fn(),
        onClick,
        onRightClick: vi.fn(),
        onScroll: vi.fn(),
        onRecalibrate: vi.fn(),
      }
    );

    expect(res.executed).toBe(false);
    expect(res.message).toContain("stale");
    expect(onClick).not.toHaveBeenCalled();
  });

  it("safely rejects clicks when eye control is paused", () => {
    const dispatcher = new VoiceCommandDispatcher();
    const onClick = vi.fn();

    const gateState = {
      isTrackingValid: true,
      isPaused: true, // paused
      isEmergencyStopped: false,
      isEyeControlEnabled: true,
      lastGazeTs: Date.now() / 1000,
    };

    const res = dispatcher.executeCommand(
      { raw: "click", action: "CLICK", confidence: 0.95 },
      gateState,
      {
        onEmergencyStop: vi.fn(),
        onStartEyeControl: vi.fn(),
        onPauseEyeControl: vi.fn(),
        onResumeEyeControl: vi.fn(),
        onClick,
        onRightClick: vi.fn(),
        onScroll: vi.fn(),
        onRecalibrate: vi.fn(),
      }
    );

    expect(res.executed).toBe(false);
    expect(res.message).toContain("paused");
    expect(onClick).not.toHaveBeenCalled();
  });

  it("successfully executes click when tracking is valid and gaze is fresh", () => {
    const dispatcher = new VoiceCommandDispatcher();
    const onClick = vi.fn();

    const gateState = {
      isTrackingValid: true,
      isPaused: false,
      isEmergencyStopped: false,
      isEyeControlEnabled: true,
      lastGazeTs: Date.now() / 1000,
    };

    const res = dispatcher.executeCommand(
      { raw: "click", action: "CLICK", confidence: 0.95 },
      gateState,
      {
        onEmergencyStop: vi.fn(),
        onStartEyeControl: vi.fn(),
        onPauseEyeControl: vi.fn(),
        onResumeEyeControl: vi.fn(),
        onClick,
        onRightClick: vi.fn(),
        onScroll: vi.fn(),
        onRecalibrate: vi.fn(),
      }
    );

    expect(res.executed).toBe(true);
    expect(res.message).toContain("Click executed");
    expect(onClick).toHaveBeenCalledWith(false);
  });

  it("suppresses rapid duplicate clicks within debounce window", () => {
    const dispatcher = new VoiceCommandDispatcher();
    dispatcher.setDebounceMs(600);
    const onClick = vi.fn();

    const gateState = {
      isTrackingValid: true,
      isPaused: false,
      isEmergencyStopped: false,
      isEyeControlEnabled: true,
      lastGazeTs: Date.now() / 1000,
    };

    // First click
    const res1 = dispatcher.executeCommand(
      { raw: "click", action: "CLICK", confidence: 0.95 },
      gateState,
      {
        onEmergencyStop: vi.fn(),
        onStartEyeControl: vi.fn(),
        onPauseEyeControl: vi.fn(),
        onResumeEyeControl: vi.fn(),
        onClick,
        onRightClick: vi.fn(),
        onScroll: vi.fn(),
        onRecalibrate: vi.fn(),
      }
    );
    expect(res1.executed).toBe(true);

    // Immediate second click (duplicate speech recognition callback)
    const res2 = dispatcher.executeCommand(
      { raw: "click", action: "CLICK", confidence: 0.95 },
      gateState,
      {
        onEmergencyStop: vi.fn(),
        onStartEyeControl: vi.fn(),
        onPauseEyeControl: vi.fn(),
        onResumeEyeControl: vi.fn(),
        onClick,
        onRightClick: vi.fn(),
        onScroll: vi.fn(),
        onRecalibrate: vi.fn(),
      }
    );
    expect(res2.executed).toBe(false);
    expect(res2.message).toContain("Duplicate command suppressed");
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("unconditionally executes Emergency Stop and blocks subsequent commands", () => {
    const dispatcher = new VoiceCommandDispatcher();
    const onEmergencyStop = vi.fn();
    const onClick = vi.fn();

    const gateState = {
      isTrackingValid: true,
      isPaused: false,
      isEmergencyStopped: false,
      isEyeControlEnabled: true,
      lastGazeTs: Date.now() / 1000,
    };

    const res = dispatcher.executeCommand(
      { raw: "emergency stop", action: "EMERGENCY_STOP", confidence: 0.99 },
      gateState,
      {
        onEmergencyStop,
        onStartEyeControl: vi.fn(),
        onPauseEyeControl: vi.fn(),
        onResumeEyeControl: vi.fn(),
        onClick,
        onRightClick: vi.fn(),
        onScroll: vi.fn(),
        onRecalibrate: vi.fn(),
      }
    );

    expect(res.executed).toBe(true);
    expect(onEmergencyStop).toHaveBeenCalled();

    // Now state is emergency stopped
    gateState.isEmergencyStopped = true;
    const resAfter = dispatcher.executeCommand(
      { raw: "click", action: "CLICK", confidence: 0.95 },
      gateState,
      {
        onEmergencyStop: vi.fn(),
        onStartEyeControl: vi.fn(),
        onPauseEyeControl: vi.fn(),
        onResumeEyeControl: vi.fn(),
        onClick,
        onRightClick: vi.fn(),
        onScroll: vi.fn(),
        onRecalibrate: vi.fn(),
      }
    );

    expect(resAfter.executed).toBe(false);
    expect(resAfter.message).toContain("emergency stop");
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("EyeControlScreen Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useObserverStore.setState({
      consentGiven: true,
      activeScreen: "eye_control",
      gazeStatus: {
        schema_version: "2.0.0",
        type: "gaze_status",
        enabled: true,
        paused: false,
        emergency_stopped: false,
        tracking_valid: true,
        tracking_reason: "Tracking locked",
        last_valid_ts: Date.now() / 1000,
        cursor_norm_x: 0.45,
        cursor_norm_y: 0.55,
        is_calibrated: true,
        quality_label: "Good",
        validation_error: 0.08,
        sensitivity: 1.2,
        dead_zone: 0.008,
        max_speed: 0.08,
        smoothing_mode: "balanced",
        tracking_mode: "hybrid",
        preset: "balanced",
        is_calibrating: false,
        calib_target_idx: 0,
        outlier_count: 0,
        is_diagnosing: false,
      },
      gazeCursor: { norm_x: 0.45, norm_y: 0.55, valid: true, timestamp: Date.now() / 1000 },
      accessibilityPermission: { granted: true, message: "Permission granted" },
    });
  });

  it("renders header, status indicators, and emergency stop button", () => {
    render(<EyeControlScreen />);
    expect(screen.getByText(/Stability-First Head & Voice Pointer/i)).toBeDefined();
    expect(screen.getByText("Emergency Stop")).toBeDefined();
    expect(screen.getByText("Pause Pointer")).toBeDefined();
    expect(screen.getByText("Disable Head Pointer")).toBeDefined();
  });

  it("renders preview canvas with current coordinates", () => {
    render(<EyeControlScreen />);
    expect(screen.getByText(/Screen Coordinate Tracking Preview/i)).toBeDefined();
    expect(screen.getByText(/X: 45% \| Y: 55%/i)).toBeDefined();
  });

  it("dispatches emergency stop when Escape key is pressed", () => {
    const emergencyStopSpy = vi.spyOn(useObserverStore.getState(), "emergencyStop");
    render(<EyeControlScreen />);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(emergencyStopSpy).toHaveBeenCalled();
  });

  it("switches to Tracking Strategy tab and selects modes", () => {
    render(<EyeControlScreen />);
    const modeTab = screen.getByText("Tracking Strategy");
    fireEvent.click(modeTab);

    expect(screen.getByText(/Hybrid \(Recommended\)/i)).toBeDefined();
    expect(screen.getByText(/Nose Bridge \(Scale-Invariant\)/i)).toBeDefined();
    expect(screen.getByText(/3D Head Pose \(Yaw \/ Pitch\)/i)).toBeDefined();
  });

  it("switches to Stability Presets tab and selects presets", () => {
    render(<EyeControlScreen />);
    const presetsTab = screen.getByText("Stability Presets");
    fireEvent.click(presetsTab);

    expect(screen.getByText("Maximum Stability")).toBeDefined();
    expect(screen.getByText("Balanced (Recommended)")).toBeDefined();
    expect(screen.getByText("Responsive")).toBeDefined();
  });

  it("switches to Calibration tab and displays 5-point calibration", () => {
    render(<EyeControlScreen />);
    const calibTab = screen.getByText("Guided 5-Point Calibration");
    fireEvent.click(calibTab);

    expect(screen.getByText(/Guided 5-Point Calibration & Center Validation/i)).toBeDefined();
    expect(screen.getByText(/Calibration Status: Good/i)).toBeDefined();
  });

  it("switches to Stability Diagnostics tab", () => {
    render(<EyeControlScreen />);
    const diagTab = screen.getByText("Stability Diagnostic");
    fireEvent.click(diagTab);

    expect(screen.getByText(/Real Stability Diagnostic Tool/i)).toBeDefined();
    expect(screen.getByRole("button", { name: /Run 5s Stationary Diagnostic/i })).toBeDefined();
  });
});

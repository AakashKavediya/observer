import React, { useState, useEffect, useRef } from "react";
import {
  Eye,
  Crosshair,
  Mic,
  MicOff,
  AlertOctagon,
  Pause,
  Play,
  RotateCcw,
  Sliders,
  ShieldAlert,
  HelpCircle,
  CheckCircle2,
  AlertTriangle,
  MousePointer,
  ChevronRight,
  BookOpen,
  Activity,
  Compass,
  Gauge,
  Sparkles,
  Target,
  Keyboard,
  Layers,
  User,
  Plus,
  RefreshCw,
} from "lucide-react";
import { useObserverStore } from "@/store/useObserverStore";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { isSpeechRecognitionAvailable } from "@/services/voiceService";

export const EyeControlScreen: React.FC = () => {
  const {
    gazeStatus,
    gazeCursor,
    gazeDiagnosticResult,
    accessibilityPermission,
    lastVoiceResult,
    startEyeControl,
    pauseEyeControl,
    resumeEyeControl,
    stopEyeControl,
    emergencyStop,
    recenterNeutral,
    resetCursorToCenter,
    gazeStartCalibration,
    gazeAdvanceCalibration,
    gazeResetCalibration,
    gazeUpdateSettings,
    setTrackingMode,
    setStabilityPreset,
    setControllerMode,
    startStabilityDiagnostic,
    finishStabilityDiagnostic,
    fetchGazeStatus,
    checkAccessibilityPermission,
    nativeMouseClick,
    nativeMouseScroll,
    setVoiceControlActive,
    dispatchVoiceCommand,
    showAssistiveToolbar,
    showVirtualKeyboard,
    toggleAssistiveToolbar,
    toggleVirtualKeyboard,
    motionqProfiles,
    motionqActiveProfile,
    fetchMotionQProfiles,
    loadMotionQProfile,
    createMotionQProfile,
    resetMotionQProfile,
  } = useObserverStore();

  const [activeTab, setActiveTab] = useState<
    "controls" | "mode" | "presets" | "calibration" | "diagnostics" | "tutorial"
  >("controls");
  const [voiceTranscript, setVoiceTranscript] = useState("");
  const [isVoiceListening, setIsVoiceListening] = useState(false);
  const [diagnosticTimer, setDiagnosticTimer] = useState<number | null>(null);
  const [newProfileName, setNewProfileName] = useState("");

  // Settings local state
  const [sensitivity, setSensitivity] = useState(gazeStatus?.sensitivity ?? 1.2);
  const [deadZone, setDeadZone] = useState(gazeStatus?.dead_zone ?? 0.008);
  const [maxSpeed, setMaxSpeed] = useState(gazeStatus?.max_speed ?? 0.08);

  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    fetchGazeStatus();
    checkAccessibilityPermission();
    fetchMotionQProfiles();
  }, []);

  // Sync settings when gazeStatus loads
  useEffect(() => {
    if (gazeStatus) {
      setSensitivity(gazeStatus.sensitivity);
      setDeadZone(gazeStatus.dead_zone);
      if (gazeStatus.max_speed !== undefined) {
        setMaxSpeed(gazeStatus.max_speed);
      }
    }
  }, [gazeStatus?.sensitivity, gazeStatus?.dead_zone, gazeStatus?.max_speed]);

  // Global Emergency Stop Keyboard Shortcut: Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        emergencyStop();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [emergencyStop]);

  // Diagnostic countdown effect
  useEffect(() => {
    if (gazeStatus?.is_diagnosing) {
      setDiagnosticTimer(5);
      const interval = setInterval(() => {
        setDiagnosticTimer((prev) => {
          if (prev === null || prev <= 1) {
            clearInterval(interval);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => clearInterval(interval);
    } else {
      setDiagnosticTimer(null);
    }
  }, [gazeStatus?.is_diagnosing]);

  // Voice Command Listener using local SpeechRecognition
  const toggleVoiceListening = () => {
    if (isVoiceListening) {
      stopVoiceListening();
    } else {
      startVoiceListening();
    }
  };

  const startVoiceListening = () => {
    if (!isSpeechRecognitionAvailable()) {
      alert("Local speech recognition is not supported in this webview. Use keyboard shortcuts or click buttons.");
      return;
    }

    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const rec = new SpeechRec();
    rec.continuous = true;
    rec.interimResults = false;
    rec.lang = "en-US";

    rec.onstart = () => {
      setIsVoiceListening(true);
      setVoiceControlActive(true);
    };

    rec.onresult = (event: any) => {
      const lastIdx = event.results.length - 1;
      const transcript = event.results[lastIdx][0].transcript.trim();
      setVoiceTranscript(transcript);
      dispatchVoiceCommand(transcript);
    };

    rec.onerror = (event: any) => {
      console.warn("[EyeControl] Voice command error:", event.error);
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setIsVoiceListening(false);
        setVoiceControlActive(false);
      }
    };

    rec.onend = () => {
      if (isVoiceListening) {
        try {
          rec.start();
        } catch {
          setIsVoiceListening(false);
        }
      }
    };

    recognitionRef.current = rec;
    try {
      rec.start();
    } catch {
      setIsVoiceListening(false);
    }
  };

  const stopVoiceListening = () => {
    setIsVoiceListening(false);
    setVoiceControlActive(false);
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
      recognitionRef.current = null;
    }
  };

  const isEnabled = gazeStatus?.enabled ?? false;
  const isPaused = gazeStatus?.paused ?? false;
  const isStopped = gazeStatus?.emergency_stopped ?? false;
  const isTracking = gazeStatus?.tracking_valid ?? false;
  const isCalibrating = gazeStatus?.is_calibrating ?? false;
  const calibTargetIdx = gazeStatus?.calib_target_idx ?? 0;
  const activeTrackingMode = gazeStatus?.tracking_mode ?? "hybrid";
  const activePreset = gazeStatus?.preset ?? "balanced";

  // Calibration Target coordinates for visual wizard (6-step guided procedure)
  const calibTargets = [
    { id: "center_neutral", x: 50, y: 50, label: "1. Center Neutral Resting Pose" },
    { id: "move_left", x: 15, y: 50, label: "2. Turn/Tilt Head Left" },
    { id: "move_right", x: 85, y: 50, label: "3. Turn/Tilt Head Right" },
    { id: "move_up", x: 50, y: 15, label: "4. Tilt Head Upward" },
    { id: "move_down", x: 50, y: 85, label: "5. Tilt Head Downward" },
    { id: "validation_center", x: 50, y: 50, label: "6. Return to Center Validation" },
  ];

  const currentCalibTarget = calibTargets[Math.min(calibTargetIdx, calibTargets.length - 1)];

  return (
    <div className="max-w-5xl mx-auto py-5 px-4 space-y-4">
      {/* Top Header & Emergency Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-panel p-4 rounded-2xl border border-black/5 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-ink flex items-center gap-2">
              <Eye className="w-5 h-5 text-sage" aria-hidden="true" />
              Stability-First Head &amp; Voice Pointer
            </h2>
            <Badge variant="default" className="text-[10px] bg-sage text-white">
              Track 4 • Hands-Free
            </Badge>
          </div>
          <p className="text-xs text-ink-muted">
            Smooth, jitter-free desktop pointer control using scale-invariant facial geometry with hands-free voice clicks.
          </p>
        </div>

        {/* Global Action & Safety Buttons */}
        <div className="flex items-center flex-wrap gap-2">
          {/* Recenter Neutral Reference Button */}
          <Button
            variant="secondary"
            size="sm"
            onClick={recenterNeutral}
            className="h-9 px-3 gap-1.5 text-xs font-semibold bg-ivory border border-black/10 hover:border-sage hover:text-sage"
            title="Recenter resting head pose to current head orientation without moving cursor"
          >
            <Target className="w-3.5 h-3.5 text-sage" />
            <span>Recenter Neutral</span>
          </Button>

          {/* Center Cursor Button */}
          <Button
            variant="ghost"
            size="sm"
            onClick={resetCursorToCenter}
            className="h-9 px-2.5 text-xs text-ink-muted border border-black/10 hover:text-ink"
            title="Reset cursor position to center (0.5, 0.5)"
          >
            <Crosshair className="w-3.5 h-3.5" />
            <span>Center Cursor</span>
          </Button>

          {/* Floating Assistive Toolbar Toggle */}
          <Button
            variant={showAssistiveToolbar ? "primary" : "secondary"}
            size="sm"
            onClick={() => toggleAssistiveToolbar()}
            className={`h-9 px-3 gap-1.5 text-xs font-semibold ${
              showAssistiveToolbar
                ? "bg-sage text-white shadow-xs"
                : "bg-ivory border border-black/10 hover:border-sage hover:text-sage"
            }`}
            title="Toggle floating assistive dwell toolbar"
          >
            <Layers className="w-3.5 h-3.5" />
            <span>{showAssistiveToolbar ? "Hide Toolbar" : "Toolbar"}</span>
          </Button>

          {/* Virtual Keyboard Toggle */}
          <Button
            variant={showVirtualKeyboard ? "primary" : "secondary"}
            size="sm"
            onClick={() => toggleVirtualKeyboard()}
            className={`h-9 px-3 gap-1.5 text-xs font-semibold ${
              showVirtualKeyboard
                ? "bg-sage text-white shadow-xs"
                : "bg-ivory border border-black/10 hover:border-sage hover:text-sage"
            }`}
            title="Toggle multilingual on-screen dwell virtual keyboard"
          >
            <Keyboard className="w-3.5 h-3.5" />
            <span>{showVirtualKeyboard ? "Hide Keyboard" : "Keyboard"}</span>
          </Button>

          {/* Emergency Stop Button (Esc) */}
          <Button
            variant="danger"
            size="sm"
            onClick={emergencyStop}
            className="h-9 px-3 gap-1.5 font-bold shadow-xs text-xs"
            title="Immediately halt all cursor movement and disable voice actions (Shortcut: Esc)"
          >
            <AlertOctagon className="w-4 h-4" />
            <span>Emergency Stop</span>
            <kbd className="hidden sm:inline bg-black/20 text-[10px] px-1.5 py-0.5 rounded font-mono">
              ESC
            </kbd>
          </Button>

          {/* Pause / Resume Button */}
          {isEnabled && (
            <Button
              variant={isPaused ? "primary" : "secondary"}
              size="sm"
              onClick={isPaused ? resumeEyeControl : pauseEyeControl}
              className="h-9 px-3 gap-1.5 text-xs font-semibold"
            >
              {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
              <span>{isPaused ? "Resume Pointer" : "Pause Pointer"}</span>
            </Button>
          )}

          {/* Master Enable Toggle */}
          <Button
            variant={isEnabled ? "ghost" : "primary"}
            size="sm"
            onClick={isEnabled ? stopEyeControl : startEyeControl}
            className={`h-9 px-3.5 text-xs font-bold gap-1.5 ${
              isEnabled ? "border border-black/10 text-ink-muted hover:text-clay" : ""
            }`}
          >
            <MousePointer className="w-4 h-4" />
            <span>{isEnabled ? "Disable Head Pointer" : "Enable Head Pointer"}</span>
          </Button>
        </div>
      </div>

      {/* Real-time Status Indicator Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
        {/* Tracking Status */}
        <div className="bg-panel p-3 rounded-xl border border-black/5 flex items-center justify-between">
          <span className="text-ink-muted font-medium">Tracking:</span>
          <span
            className={`font-bold inline-flex items-center gap-1 ${
              isTracking ? "text-sage" : "text-clay"
            }`}
          >
            {isTracking ? (
              <>
                <CheckCircle2 className="w-3.5 h-3.5" /> Locked
              </>
            ) : (
              <>
                <AlertTriangle className="w-3.5 h-3.5" /> {gazeStatus?.tracking_reason || "No Face"}
              </>
            )}
          </span>
        </div>

        {/* State Mode */}
        <div className="bg-panel p-3 rounded-xl border border-black/5 flex items-center justify-between">
          <span className="text-ink-muted font-medium">Mode:</span>
          <span className="font-bold">
            {isStopped ? (
              <span className="text-clay font-bold">EMERGENCY STOPPED</span>
            ) : isPaused ? (
              <span className="text-amber-600 font-semibold">PAUSED</span>
            ) : isEnabled ? (
              <span className="text-sage font-bold">ACTIVE</span>
            ) : (
              <span className="text-ink-muted">DISABLED</span>
            )}
          </span>
        </div>

        {/* Tracking Strategy & Preset */}
        <div className="bg-panel p-3 rounded-xl border border-black/5 flex items-center justify-between">
          <span className="text-ink-muted font-medium">Strategy:</span>
          <span className="font-bold text-ink uppercase text-[11px]">
            {activeTrackingMode} • {activePreset}
          </span>
        </div>

        {/* Voice Command Recognition Status */}
        <div className="bg-panel p-3 rounded-xl border border-black/5 flex items-center justify-between">
          <span className="text-ink-muted font-medium">Voice Command:</span>
          <span
            className={`font-bold inline-flex items-center gap-1 ${
              isVoiceListening ? "text-sage" : "text-ink-muted"
            }`}
          >
            {isVoiceListening ? (
              <>
                <span className="w-2 h-2 rounded-full bg-sage animate-ping" />
                Listening
              </>
            ) : (
              "Idle"
            )}
          </span>
        </div>
      </div>

      {/* Permission Warning Banner if macOS Accessibility permission missing */}
      {accessibilityPermission && !accessibilityPermission.granted && (
        <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start justify-between gap-3 text-xs text-ink">
          <div className="flex items-start gap-2.5">
            <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-amber-700">macOS Accessibility Permission Required</p>
              <p className="text-ink-muted mt-0.5">
                To move the cursor across the desktop and execute clicks outside this window, Observer requires Accessibility permissions.
                Go to <b>System Settings &gt; Privacy &amp; Security &gt; Accessibility</b> and toggle Observer ON.
              </p>
            </div>
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={checkAccessibilityPermission}
            className="text-xs border border-amber-500/30 text-amber-700 hover:bg-amber-500/10 flex-shrink-0"
          >
            Check Again
          </Button>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex border-b border-black/5 gap-2 text-xs font-semibold overflow-x-auto pb-1">
        {[
          { id: "controls", label: "Control Surface & Preview", icon: Crosshair },
          { id: "mode", label: "Tracking Strategy", icon: Compass },
          { id: "presets", label: "Stability Presets", icon: Sliders },
          { id: "calibration", label: "Guided 5-Point Calibration", icon: Eye },
          { id: "diagnostics", label: "Stability Diagnostic", icon: Activity },
          { id: "tutorial", label: "Voice Guide", icon: HelpCircle },
        ].map((tab) => {
          const Icon = tab.icon;
          const isSelected = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`pb-2.5 px-3 flex items-center gap-1.5 transition-colors border-b-2 whitespace-nowrap ${
                isSelected
                  ? "border-sage text-sage font-bold"
                  : "border-transparent text-ink-muted hover:text-ink"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* TAB 1: Main Control Surface & Visual Preview */}
      {activeTab === "controls" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* 2D Pointer Target Preview Canvas */}
          <Card className="md:col-span-2 p-4 bg-panel border-black/5 shadow-xs space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-ink flex items-center gap-1.5">
                <Crosshair className="w-4 h-4 text-sage" /> Screen Coordinate Tracking Preview
              </span>
              <span className="font-mono text-[11px] text-ink-muted">
                X: {Math.round(gazeCursor.norm_x * 100)}% | Y: {Math.round(gazeCursor.norm_y * 100)}%
              </span>
            </div>

            {/* Interactive Screen Simulation Canvas */}
            <div className="relative w-full aspect-16/10 bg-ivory rounded-xl border border-black/10 overflow-hidden shadow-inner flex items-center justify-center">
              {/* Calibration Target Anchors */}
              {calibTargets.map((t) => (
                <div
                  key={t.id}
                  style={{ left: `${t.x}%`, top: `${t.y}%` }}
                  className="absolute -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full border border-black/20 bg-black/5"
                  title={t.label}
                />
              ))}

              {/* Dead-zone indicator at center */}
              <div
                style={{
                  width: `${(gazeStatus?.dead_zone ?? 0.008) * 800}%`,
                  height: `${(gazeStatus?.dead_zone ?? 0.008) * 800}%`,
                }}
                className="rounded-full border border-dashed border-sage/30 pointer-events-none"
              />

              {/* Real-time Pointer Dot */}
              <div
                style={{
                  left: `${gazeCursor.norm_x * 100}%`,
                  top: `${gazeCursor.norm_y * 100}%`,
                }}
                className={`absolute -translate-x-1/2 -translate-y-1/2 pointer-events-none transition-all duration-75 ${
                  gazeCursor.valid ? "opacity-100" : "opacity-30"
                }`}
              >
                <div className="relative flex items-center justify-center">
                  <div className="w-6 h-6 rounded-full bg-sage/20 border-2 border-sage animate-ping absolute" />
                  <div className="w-3.5 h-3.5 rounded-full bg-sage shadow-md border-2 border-white" />
                </div>
              </div>

              {!isTracking && (
                <div className="absolute inset-0 bg-white/70 backdrop-blur-xs flex items-center justify-center text-xs text-ink-muted font-medium">
                  {gazeStatus?.tracking_reason || "Looking for facial landmarks..."}
                </div>
              )}
            </div>

            {/* Manual Click Testing Controls */}
            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-black/5 text-xs">
              <span className="text-ink-muted font-medium">Manual Trigger Test:</span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => nativeMouseClick("left", false)}
                  className="text-xs h-7"
                >
                  Left Click
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => nativeMouseClick("left", true)}
                  className="text-xs h-7"
                >
                  Double Click
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => nativeMouseClick("right", false)}
                  className="text-xs h-7"
                >
                  Right Click
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => nativeMouseScroll(5)}
                  className="text-xs h-7 border border-black/10"
                >
                  Scroll Up
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => nativeMouseScroll(-5)}
                  className="text-xs h-7 border border-black/10"
                >
                  Scroll Down
                </Button>
              </div>
            </div>

            {/* Real-time Head Pose, Deflection & Dead-Zone Diagnostics */}
            <div className="p-3.5 rounded-xl bg-ivory border border-black/10 space-y-2.5 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-bold text-ink flex items-center gap-1.5">
                  <Gauge className="w-4 h-4 text-sage" /> Real-Time Signal &amp; Dead-Zone Telemetry
                </span>
                {gazeStatus?.in_dead_zone ? (
                  <Badge variant="default" className="bg-sage/15 text-sage border border-sage/30 text-[11px] font-bold gap-1 px-2 py-0.5">
                    <span className="w-2 h-2 rounded-full bg-sage inline-block animate-pulse" />
                    DEAD ZONE (Stationary • 0.0px Jitter)
                  </Badge>
                ) : (
                  <Badge variant="default" className="bg-amber-500/15 text-amber-700 border border-amber-500/30 text-[11px] font-bold gap-1 px-2 py-0.5">
                    <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" />
                    ACTIVE VELOCITY (Speed: {Math.sqrt((gazeStatus?.velocity_x ?? 0) ** 2 + (gazeStatus?.velocity_y ?? 0) ** 2).toFixed(2)} norm/s)
                  </Badge>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono">
                <div className="bg-white p-2 rounded-lg border border-black/5">
                  <div className="text-ink-muted text-[10px] font-sans font-medium">Head Pose (P / Y):</div>
                  <div className="text-ink font-bold">{gazeStatus?.current_pitch?.toFixed(1) ?? "0.0"}° / {gazeStatus?.current_yaw?.toFixed(1) ?? "0.0"}°</div>
                </div>
                <div className="bg-white p-2 rounded-lg border border-black/5">
                  <div className="text-ink-muted text-[10px] font-sans font-medium">Normalized (ux, uy):</div>
                  <div className="text-ink font-bold">{gazeStatus?.normalized_ux?.toFixed(2) ?? "0.00"}, {gazeStatus?.normalized_uy?.toFixed(2) ?? "0.00"}</div>
                </div>
                <div className="bg-white p-2 rounded-lg border border-black/5">
                  <div className="text-ink-muted text-[10px] font-sans font-medium">Learned Scales (Sx, Sy):</div>
                  <div className="text-ink font-bold">{gazeStatus?.scale_x?.toFixed(2) ?? "0.12"}, {gazeStatus?.scale_y?.toFixed(2) ?? "0.10"}</div>
                </div>
                <div className="bg-white p-2 rounded-lg border border-black/5">
                  <div className="text-ink-muted text-[10px] font-sans font-medium">Mode &amp; Latency:</div>
                  <div className="text-ink font-bold uppercase">{gazeStatus?.controller_mode ?? "relative"} ({gazeStatus?.hz?.toFixed(0) ?? "30"} Hz)</div>
                </div>
              </div>
            </div>
          </Card>

          {/* Voice Command Console */}
          <Card className="p-4 bg-panel border-black/5 shadow-xs space-y-3 flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-ink flex items-center gap-1.5">
                  <Mic className="w-4 h-4 text-sage" /> Voice Command Listener
                </span>
                <button
                  onClick={toggleVoiceListening}
                  className={`p-1.5 rounded-full transition-colors ${
                    isVoiceListening
                      ? "bg-clay text-white shadow-xs"
                      : "bg-sage/15 text-sage hover:bg-sage hover:text-white"
                  }`}
                  aria-label={isVoiceListening ? "Stop voice listening" : "Start voice listening"}
                  title="Toggle continuous voice commands"
                >
                  {isVoiceListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                </button>
              </div>

              {/* Status Pill */}
              <div className="p-2.5 rounded-xl bg-ivory border border-black/5 text-xs space-y-1">
                <div className="flex justify-between items-center text-[11px] font-bold text-ink-muted">
                  <span>Voice Status:</span>
                  <span className={isVoiceListening ? "text-sage" : "text-ink-muted"}>
                    {isVoiceListening ? "Active (say 'click', 'scroll', etc.)" : "Paused"}
                  </span>
                </div>
                {voiceTranscript && (
                  <p className="font-mono text-xs text-ink truncate">
                    Heard: "{voiceTranscript}"
                  </p>
                )}
              </div>

              {/* Last Executed Command Feedback */}
              {lastVoiceResult && (
                <div
                  className={`p-2.5 rounded-xl border text-xs space-y-0.5 ${
                    lastVoiceResult.executed
                      ? "bg-sage/10 border-sage/30 text-sage"
                      : "bg-clay/10 border-clay/30 text-clay"
                  }`}
                >
                  <div className="font-bold uppercase tracking-wider text-[10px]">
                    {lastVoiceResult.action}
                  </div>
                  <p className="font-medium">{lastVoiceResult.message}</p>
                </div>
              )}

              {/* Quick Spoken Commands Reference */}
              <div className="space-y-1.5 text-xs text-ink-muted">
                <span className="font-bold text-ink text-[11px]">Commands:</span>
                <ul className="space-y-1 text-[11px]">
                  <li className="flex justify-between">
                    <code className="font-mono font-bold text-ink">"click"</code>
                    <span>Left click cursor</span>
                  </li>
                  <li className="flex justify-between">
                    <code className="font-mono font-bold text-ink">"double-click"</code>
                    <span>Double click</span>
                  </li>
                  <li className="flex justify-between">
                    <code className="font-mono font-bold text-ink">"right-click"</code>
                    <span>Right click</span>
                  </li>
                  <li className="flex justify-between">
                    <code className="font-mono font-bold text-ink">"scroll up / down"</code>
                    <span>Page scroll</span>
                  </li>
                  <li className="flex justify-between">
                    <code className="font-mono font-bold text-ink">"stop moving"</code>
                    <span>Pause cursor</span>
                  </li>
                  <li className="flex justify-between">
                    <code className="font-mono font-bold text-ink">"emergency stop"</code>
                    <span>Halt all</span>
                  </li>
                </ul>
              </div>
            </div>

            <Button
              size="sm"
              variant={isVoiceListening ? "danger" : "primary"}
              onClick={toggleVoiceListening}
              className="w-full text-xs h-8 gap-1.5"
            >
              {isVoiceListening ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
              <span>{isVoiceListening ? "Stop Voice Listener" : "Enable Voice Listener"}</span>
            </Button>
          </Card>
        </div>
      )}

      {/* TAB 2: Tracking Strategy & Controller Mode Selection */}
      {activeTab === "mode" && (
        <Card className="p-5 bg-panel border-black/5 shadow-xs space-y-5">
          {/* Section 1: Controller Mode (Mode A vs Mode B) */}
          <div className="space-y-3">
            <div>
              <h3 className="text-sm font-bold text-ink flex items-center gap-1.5">
                <Sliders className="w-4 h-4 text-sage" /> Pointer Controller Mode (Section 5)
              </h3>
              <p className="text-xs text-ink-muted mt-0.5">
                Choose between relative rate/velocity control or regularized absolute screen mapping.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              {/* Mode A: Relative Head Movement */}
              <div
                onClick={() => setControllerMode("relative")}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  (gazeStatus?.controller_mode ?? "relative") === "relative"
                    ? "bg-sage/10 border-sage shadow-xs"
                    : "bg-ivory border-black/5 hover:border-black/20"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-ink flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-sage" /> Mode A: Relative Rate (Recommended)
                  </span>
                  {(gazeStatus?.controller_mode ?? "relative") === "relative" && (
                    <Badge variant="default" className="text-[10px] bg-sage text-white">Active</Badge>
                  )}
                </div>
                <p className="text-ink-muted leading-relaxed">
                  Head deflection outside the adaptive dead zone drives cursor velocity. Features 0.00 px stationary jitter inside neutral dead zone, smooth non-linear transfer curve, and seamless 1-click recentering.
                </p>
              </div>

              {/* Mode B: Calibrated Absolute Screen Mapping */}
              <div
                onClick={() => setControllerMode("absolute")}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  gazeStatus?.controller_mode === "absolute"
                    ? "bg-sage/10 border-sage shadow-xs"
                    : "bg-ivory border-black/5 hover:border-black/20"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-ink">Mode B: Absolute Screen Mapping</span>
                  {gazeStatus?.controller_mode === "absolute" && (
                    <Badge variant="default" className="text-[10px] bg-sage text-white">Active</Badge>
                  )}
                </div>
                <p className="text-ink-muted leading-relaxed">
                  Regularized 2D bilinear Ridge regression maps validated head deflections directly to screen coordinates. Requires deliberate 5-point calibration; filtered by One-Euro filter.
                </p>
              </div>

              {/* Mode C: MotionQ-blink Calibrated Iris Gaze */}
              <div
                onClick={() => setControllerMode("motionq_eye")}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  gazeStatus?.controller_mode === "motionq_eye"
                    ? "bg-sage/10 border-sage shadow-xs"
                    : "bg-ivory border-black/5 hover:border-black/20"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-ink flex items-center gap-1.5">
                    <Eye className="w-4 h-4 text-sage" /> Mode C: MotionQ Iris Gaze
                  </span>
                  {gazeStatus?.controller_mode === "motionq_eye" && (
                    <Badge variant="default" className="text-[10px] bg-sage text-white">Active</Badge>
                  )}
                </div>
                <p className="text-ink-muted leading-relaxed">
                  Direct MediaPipe iris gaze tracking (469-472, 474-477) with nonlinear 1.2 curve, dwell engine magnetic attraction, proximity slowdown, and head-tilt vertical scrolling.
                </p>
              </div>
            </div>
          </div>

          <hr className="border-black/5" />

          {/* Section 2: Facial Feature Strategy */}
          <div className="space-y-3">
            <div>
              <h3 className="text-sm font-bold text-ink flex items-center gap-1.5">
                <Compass className="w-4 h-4 text-sage" /> Facial Feature Reference Strategy
              </h3>
              <p className="text-xs text-ink-muted mt-0.5">
                Select how facial landmarks are normalized relative to the inter-eye distance and head geometry.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            {/* Hybrid */}
            <div
              onClick={() => setTrackingMode("hybrid")}
              className={`p-4 rounded-xl border cursor-pointer transition-all ${
                activeTrackingMode === "hybrid"
                  ? "bg-sage/10 border-sage shadow-xs"
                  : "bg-ivory border-black/5 hover:border-black/20"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-ink flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-sage" /> Hybrid (Recommended)
                </span>
                {activeTrackingMode === "hybrid" && (
                  <Badge variant="default" className="text-[10px] bg-sage text-white">Active</Badge>
                )}
              </div>
              <p className="text-ink-muted leading-relaxed">
                Combines scale-invariant nose bridge displacement (60%) and 3D rotational head pose (40%). Produces the lowest stationary jitter and natural diagonal movement.
              </p>
            </div>

            {/* Nose Bridge */}
            <div
              onClick={() => setTrackingMode("nose_bridge")}
              className={`p-4 rounded-xl border cursor-pointer transition-all ${
                activeTrackingMode === "nose_bridge"
                  ? "bg-sage/10 border-sage shadow-xs"
                  : "bg-ivory border-black/5 hover:border-black/20"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-ink">Nose Bridge (Scale-Invariant)</span>
                {activeTrackingMode === "nose_bridge" && (
                  <Badge variant="default" className="text-[10px] bg-sage text-white">Active</Badge>
                )}
              </div>
              <p className="text-ink-muted leading-relaxed">
                Tracks the position of the nasion (landmark 168) normalized strictly by inter-ocular distance. Zero drift when leaning towards or away from the webcam.
              </p>
            </div>

            {/* Head Pose */}
            <div
              onClick={() => setTrackingMode("head_pose")}
              className={`p-4 rounded-xl border cursor-pointer transition-all ${
                activeTrackingMode === "head_pose"
                  ? "bg-sage/10 border-sage shadow-xs"
                  : "bg-ivory border-black/5 hover:border-black/20"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-ink">3D Head Pose (Yaw / Pitch)</span>
                {activeTrackingMode === "head_pose" && (
                  <Badge variant="default" className="text-[10px] bg-sage text-white">Active</Badge>
                )}
              </div>
              <p className="text-ink-muted leading-relaxed">
                Uses 3D facial solvePnP orientation angles. Great for reaching monitor edges with small head rotations, with zero dependence on face translation.
              </p>
            </div>
          </div>
        </div>

        <hr className="border-black/5" />

        {/* Section 3: MotionQ Profiles & Accessible Environment */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-ink flex items-center gap-1.5">
                <User className="w-4 h-4 text-sage" /> MotionQ Assistive Profiles &amp; Dwell Tools
              </h3>
              <p className="text-xs text-ink-muted mt-0.5">
                Manage user calibration profiles, floating toolbar targets, and multilingual virtual keyboard layouts.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant={showAssistiveToolbar ? "primary" : "ghost"}
                onClick={() => toggleAssistiveToolbar()}
                className="text-xs h-7 px-2.5 gap-1 border border-black/10"
              >
                <Layers className="w-3.5 h-3.5" />
                <span>{showAssistiveToolbar ? "Toolbar Active" : "Open Toolbar"}</span>
              </Button>
              <Button
                size="sm"
                variant={showVirtualKeyboard ? "primary" : "ghost"}
                onClick={() => toggleVirtualKeyboard()}
                className="text-xs h-7 px-2.5 gap-1 border border-black/10"
              >
                <Keyboard className="w-3.5 h-3.5" />
                <span>{showVirtualKeyboard ? "Keyboard Active" : "Open Keyboard"}</span>
              </Button>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-ivory border border-black/10 space-y-3 text-xs">
            {/* Active profile switch row */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-ink">Active Profile:</span>
                <span className="font-bold text-sage bg-sage/10 px-2.5 py-1 rounded-lg border border-sage/20 uppercase tracking-wide">
                  {motionqActiveProfile || "default"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => resetMotionQProfile(motionqActiveProfile)}
                  className="text-xs h-7 px-2 border border-black/10 text-ink-muted hover:text-clay"
                  title="Reset active profile to factory defaults"
                >
                  <RefreshCw className="w-3 h-3 mr-1" />
                  Reset Profile
                </Button>
              </div>
            </div>

            {/* Profile chips */}
            <div className="space-y-1.5">
              <span className="text-[11px] font-semibold text-ink-muted">Available Profiles:</span>
              <div className="flex flex-wrap gap-2">
                {motionqProfiles.map((p) => {
                  const isCur = (p === motionqActiveProfile) || (!motionqActiveProfile && p === "default");
                  return (
                    <button
                      key={p}
                      onClick={() => loadMotionQProfile(p)}
                      className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
                        isCur
                          ? "bg-sage text-white border-sage shadow-xs"
                          : "bg-white text-ink border-black/10 hover:border-black/20"
                      }`}
                    >
                      {p}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Create new profile input */}
            <div className="flex items-center gap-2 pt-2 border-t border-black/5">
              <input
                type="text"
                placeholder="New profile name (e.g. bedside, standing)..."
                value={newProfileName}
                onChange={(e) => setNewProfileName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && newProfileName.trim()) {
                    createMotionQProfile(newProfileName.trim());
                    setNewProfileName("");
                  }
                }}
                className="flex-1 bg-white border border-black/10 rounded-lg px-3 py-1.5 text-xs text-ink placeholder:text-ink-muted focus:outline-none focus:border-sage"
              />
              <Button
                size="sm"
                variant="secondary"
                disabled={!newProfileName.trim()}
                onClick={() => {
                  if (newProfileName.trim()) {
                    createMotionQProfile(newProfileName.trim());
                    setNewProfileName("");
                  }
                }}
                className="text-xs h-8 px-3 gap-1 bg-white border border-black/10 font-medium"
              >
                <Plus className="w-3.5 h-3.5" />
                Create
              </Button>
            </div>

            <div className="text-[10px] text-ink-muted pt-1 flex items-center justify-between">
              <span>Profiles persist in <code className="font-mono text-ink">~/.observer/profiles/</code> with atomic JSON healing.</span>
              <span className="italic">Adapted from MotionQ-blink (MIT License)</span>
            </div>
          </div>
        </div>
      </Card>
      )}

      {/* TAB 3: Stability Presets */}
      {activeTab === "presets" && (
        <Card className="p-5 bg-panel border-black/5 shadow-xs space-y-5">
          <div>
            <h3 className="text-sm font-bold text-ink flex items-center gap-1.5">
              <Sliders className="w-4 h-4 text-sage" /> Cursor Dynamics &amp; Stability Presets
            </h3>
            <p className="text-xs text-ink-muted mt-0.5">
              Select an empirically tuned preset or adjust custom One Euro Filter and velocity clamping thresholds.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            {/* Maximum Stability */}
            <div
              onClick={() => setStabilityPreset("maximum_stability")}
              className={`p-4 rounded-xl border cursor-pointer transition-all ${
                activePreset === "maximum_stability"
                  ? "bg-sage/10 border-sage shadow-xs"
                  : "bg-ivory border-black/5 hover:border-black/20"
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-bold text-ink">Maximum Stability</span>
                {activePreset === "maximum_stability" && (
                  <Badge variant="default" className="text-[10px] bg-sage text-white">Active</Badge>
                )}
              </div>
              <p className="text-ink-muted text-[11px] leading-relaxed mb-3">
                Fixation priority. Suppresses micro-tremors and head jitter for reading and clicking small targets.
              </p>
              <div className="text-[10px] font-mono text-ink-muted space-y-0.5 border-t border-black/5 pt-2">
                <div>Min Cutoff: 0.4 Hz | Beta: 0.15</div>
                <div>Dead Zone: 1.2% | Max Speed: 4%/frame</div>
              </div>
            </div>

            {/* Balanced */}
            <div
              onClick={() => setStabilityPreset("balanced")}
              className={`p-4 rounded-xl border cursor-pointer transition-all ${
                activePreset === "balanced"
                  ? "bg-sage/10 border-sage shadow-xs"
                  : "bg-ivory border-black/5 hover:border-black/20"
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-bold text-ink">Balanced (Recommended)</span>
                {activePreset === "balanced" && (
                  <Badge variant="default" className="text-[10px] bg-sage text-white">Active</Badge>
                )}
              </div>
              <p className="text-ink-muted text-[11px] leading-relaxed mb-3">
                Balanced responsiveness and stability for everyday desktop navigation.
              </p>
              <div className="text-[10px] font-mono text-ink-muted space-y-0.5 border-t border-black/5 pt-2">
                <div>Min Cutoff: 0.8 Hz | Beta: 0.40</div>
                <div>Dead Zone: 0.8% | Max Speed: 8%/frame</div>
              </div>
            </div>

            {/* Responsive */}
            <div
              onClick={() => setStabilityPreset("responsive")}
              className={`p-4 rounded-xl border cursor-pointer transition-all ${
                activePreset === "responsive"
                  ? "bg-sage/10 border-sage shadow-xs"
                  : "bg-ivory border-black/5 hover:border-black/20"
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-bold text-ink">Responsive</span>
                {activePreset === "responsive" && (
                  <Badge variant="default" className="text-[10px] bg-sage text-white">Active</Badge>
                )}
              </div>
              <p className="text-ink-muted text-[11px] leading-relaxed mb-3">
                High tracking speed and snappy cursor movement across large or multi-monitor screens.
              </p>
              <div className="text-[10px] font-mono text-ink-muted space-y-0.5 border-t border-black/5 pt-2">
                <div>Min Cutoff: 1.5 Hz | Beta: 0.80</div>
                <div>Dead Zone: 0.4% | Max Speed: 16%/frame</div>
              </div>
            </div>
          </div>

          {/* Fine Tuning Sliders */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2 border-t border-black/5 text-xs">
            {/* Sensitivity */}
            <div className="space-y-1.5 bg-ivory p-3 rounded-xl border border-black/5">
              <label className="font-bold text-ink flex justify-between">
                <span>Sensitivity</span>
                <span className="font-mono text-sage">{sensitivity.toFixed(1)}x</span>
              </label>
              <input
                type="range"
                min="0.5"
                max="2.5"
                step="0.1"
                value={sensitivity}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  setSensitivity(val);
                  gazeUpdateSettings({ sensitivity: val });
                }}
                className="w-full accent-sage"
              />
            </div>

            {/* Dead Zone */}
            <div className="space-y-1.5 bg-ivory p-3 rounded-xl border border-black/5">
              <label className="font-bold text-ink flex justify-between">
                <span>Dead Zone</span>
                <span className="font-mono text-sage">{(deadZone * 100).toFixed(1)}%</span>
              </label>
              <input
                type="range"
                min="0.0"
                max="0.03"
                step="0.002"
                value={deadZone}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  setDeadZone(val);
                  gazeUpdateSettings({ dead_zone: val });
                }}
                className="w-full accent-sage"
              />
            </div>

            {/* Max Speed */}
            <div className="space-y-1.5 bg-ivory p-3 rounded-xl border border-black/5">
              <label className="font-bold text-ink flex justify-between">
                <span>Max Speed Clamp</span>
                <span className="font-mono text-sage">{(maxSpeed * 100).toFixed(0)}%/frame</span>
              </label>
              <input
                type="range"
                min="0.02"
                max="0.25"
                step="0.01"
                value={maxSpeed}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  setMaxSpeed(val);
                  gazeUpdateSettings({ max_speed: val });
                }}
                className="w-full accent-sage"
              />
            </div>
          </div>
        </Card>
      )}

      {/* TAB 4: Guided Calibration Workflow (5 targets + 1 center validation) */}
      {activeTab === "calibration" && (
        <Card className="p-5 bg-panel border-black/5 shadow-xs space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-black/5 pb-3">
            <div>
              <h3 className="text-sm font-bold text-ink flex items-center gap-1.5">
                <Eye className="w-4 h-4 text-sage" /> Guided 5-Point Calibration &amp; Center Validation
              </h3>
              <p className="text-xs text-ink-muted mt-0.5">
                Captures 5 primary screen targets with Median + MAD outlier rejection, followed by a held-out center validation target.
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={gazeResetCalibration}
                className="text-xs text-clay border border-clay/30 hover:bg-clay/10"
              >
                <RotateCcw className="w-3.5 h-3.5 mr-1" /> Reset Calibration
              </Button>
              {!isCalibrating ? (
                <Button
                  size="sm"
                  variant="primary"
                  onClick={gazeStartCalibration}
                  className="text-xs gap-1"
                >
                  <Play className="w-3.5 h-3.5" /> Start 5+1 Calibration
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="primary"
                  onClick={gazeAdvanceCalibration}
                  className="text-xs gap-1"
                >
                  <span>Capture Target ({calibTargetIdx + 1}/6)</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </Button>
              )}
            </div>
          </div>

          {/* Active Calibration Stage Screen */}
          <div className="relative w-full aspect-16/9 bg-ivory rounded-2xl border border-black/10 overflow-hidden flex items-center justify-center p-4">
            {isCalibrating ? (
              <div
                style={{
                  left: `${currentCalibTarget.x}%`,
                  top: `${currentCalibTarget.y}%`,
                }}
                className="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-2 transition-all duration-300"
              >
                {/* Large pulsating calibration dot */}
                <div className="relative flex items-center justify-center">
                  <div className="w-12 h-12 rounded-full bg-sage/20 border-2 border-sage animate-ping absolute" />
                  <div className="w-6 h-6 rounded-full bg-sage shadow-md border-2 border-white flex items-center justify-center">
                    <div className="w-2 h-2 rounded-full bg-white" />
                  </div>
                </div>
                <span className="bg-panel/90 px-2 py-0.5 rounded text-[11px] font-bold text-ink shadow-xs border border-black/5 whitespace-nowrap">
                  {currentCalibTarget.label}
                </span>
              </div>
            ) : (
              <div className="text-center space-y-2 max-w-sm">
                <div className="w-10 h-10 rounded-full bg-sage/10 text-sage mx-auto flex items-center justify-center">
                  <Eye className="w-5 h-5" />
                </div>
                <h4 className="text-xs font-bold text-ink">
                  Calibration Status: {gazeStatus?.quality_label || "Uncalibrated (Default Affine)"}
                </h4>
                <p className="text-[11px] text-ink-muted">
                  Validation Residual: {gazeStatus?.validation_error ? `${(gazeStatus.validation_error * 100).toFixed(1)}% screen error` : "N/A"}.
                  Regularized Ridge regression maps your posture comfortably to the corners of your screen.
                </p>
                <Button
                  size="sm"
                  variant="primary"
                  onClick={gazeStartCalibration}
                  className="text-xs mt-2"
                >
                  Begin Calibration
                </Button>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* TAB 5: Stability Diagnostics */}
      {activeTab === "diagnostics" && (
        <Card className="p-5 bg-panel border-black/5 shadow-xs space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-black/5 pb-3">
            <div>
              <h3 className="text-sm font-bold text-ink flex items-center gap-1.5">
                <Activity className="w-4 h-4 text-sage" /> Real Stability Diagnostic Tool
              </h3>
              <p className="text-xs text-ink-muted mt-0.5">
                Measures stationary cursor jitter, unintended drift, outlier rejection rate, and latency over a 5-second fixation test.
              </p>
            </div>
            {gazeStatus?.is_diagnosing ? (
              <Button
                size="sm"
                variant="danger"
                onClick={finishStabilityDiagnostic}
                className="text-xs gap-1.5"
              >
                <Pause className="w-3.5 h-3.5" />
                <span>Finish Now ({diagnosticTimer}s)</span>
              </Button>
            ) : (
              <Button
                size="sm"
                variant="primary"
                onClick={() => startStabilityDiagnostic(5.0)}
                className="text-xs gap-1.5"
              >
                <Gauge className="w-4 h-4" />
                <span>Run 5s Stationary Diagnostic</span>
              </Button>
            )}
          </div>

          {/* Diagnostic Results Card */}
          {gazeDiagnosticResult ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                {/* Score */}
                <div className="bg-ivory p-3.5 rounded-xl border border-black/5">
                  <span className="text-ink-muted font-medium text-[11px]">Stability Score:</span>
                  <div className="text-xl font-bold text-sage mt-1">
                    {gazeDiagnosticResult.stability_score.toFixed(1)}
                    <span className="text-xs font-normal text-ink-muted"> / 100</span>
                  </div>
                  <span className="text-[10px] font-semibold text-sage">
                    {gazeDiagnosticResult.quality_rating}
                  </span>
                </div>

                {/* Stationary Jitter */}
                <div className="bg-ivory p-3.5 rounded-xl border border-black/5">
                  <span className="text-ink-muted font-medium text-[11px]">Stationary Jitter:</span>
                  <div className="text-xl font-bold text-ink mt-1">
                    {gazeDiagnosticResult.stationary_jitter_px.toFixed(1)}
                    <span className="text-xs font-normal text-ink-muted"> px</span>
                  </div>
                  <span className="text-[10px] text-ink-muted">RMS on 1920x1080 display</span>
                </div>

                {/* Drift Rate */}
                <div className="bg-ivory p-3.5 rounded-xl border border-black/5">
                  <span className="text-ink-muted font-medium text-[11px]">Unintended Drift:</span>
                  <div className="text-xl font-bold text-ink mt-1">
                    {gazeDiagnosticResult.drift_rate_px_per_sec.toFixed(1)}
                    <span className="text-xs font-normal text-ink-muted"> px/s</span>
                  </div>
                  <span className="text-[10px] text-ink-muted">Linear trend over duration</span>
                </div>

                {/* Latency */}
                <div className="bg-ivory p-3.5 rounded-xl border border-black/5">
                  <span className="text-ink-muted font-medium text-[11px]">Pipeline Latency:</span>
                  <div className="text-xl font-bold text-sage mt-1">
                    {gazeDiagnosticResult.avg_latency_ms.toFixed(2)}
                    <span className="text-xs font-normal text-ink-muted"> ms</span>
                  </div>
                  <span className="text-[10px] text-ink-muted">Stage 1-8 execution time</span>
                </div>
              </div>

              {/* Formula & Diagnostic Details */}
              <div className="p-3.5 rounded-xl bg-panel border border-black/5 text-[11px] text-ink-muted space-y-1.5">
                <div className="font-bold text-ink">Empirical Stability Formula:</div>
                <div className="font-mono text-[10px] bg-ivory p-2 rounded-lg border border-black/5">
                  Stability = 100 - (1.5 × Jitter_px) - (0.5 × Drift_px/s) - (0.8 × Outlier_%) - (1.0 × (100 - Validity_%))
                </div>
                <div className="flex gap-4 text-[10px] pt-1">
                  <span>Samples: <b>{gazeDiagnosticResult.sample_count}</b></span>
                  <span>Tracking Validity: <b>{gazeDiagnosticResult.validity_rate_pct.toFixed(1)}%</b></span>
                  <span>Outlier Rate: <b>{gazeDiagnosticResult.outlier_rate_pct.toFixed(1)}%</b></span>
                  <span>Strategy: <b>{gazeDiagnosticResult.tracking_mode}</b></span>
                  <span>Preset: <b>{gazeDiagnosticResult.preset}</b></span>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-6 text-center text-xs text-ink-muted bg-ivory rounded-xl border border-dashed border-black/10">
              Click "Run 5s Stationary Diagnostic" while looking steadily at the center crosshair to measure pointer stability metrics.
            </div>
          )}
        </Card>
      )}

      {/* TAB 6: Voice Guide */}
      {activeTab === "tutorial" && (
        <Card className="p-5 bg-panel border-black/5 shadow-xs space-y-4">
          <div>
            <h3 className="text-sm font-bold text-ink flex items-center gap-1.5">
              <BookOpen className="w-4 h-4 text-sage" /> Hands-Free Accessibility Guide
            </h3>
            <p className="text-xs text-ink-muted mt-0.5">
              How to safely navigate and control your desktop without hands.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div className="p-4 rounded-xl bg-ivory border border-black/5 space-y-2">
              <h4 className="font-bold text-ink flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-sage text-white text-[11px] flex items-center justify-center font-bold">
                  1
                </span>
                Head-Pointer Targeting
              </h4>
              <p className="text-ink-muted leading-relaxed text-[11px]">
                Turn your head gently towards the screen element you want to select. Scale-invariant nose bridge and pose tracking guides the cursor smoothly, while the dead-zone completely locks the pointer in place when reading.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-ivory border border-black/5 space-y-2">
              <h4 className="font-bold text-ink flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-sage text-white text-[11px] flex items-center justify-center font-bold">
                  2
                </span>
                Voice-Triggered Actions
              </h4>
              <p className="text-ink-muted leading-relaxed text-[11px]">
                Say <b>"click"</b> to left-click, <b>"double-click"</b> to open files, or <b>"right-click"</b> for context menus. The safety gate verifies that tracking is locked and recent before executing the click.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-ivory border border-black/5 space-y-2">
              <h4 className="font-bold text-ink flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-sage text-white text-[11px] flex items-center justify-center font-bold">
                  3
                </span>
                Blink Hold &amp; Scrolling
              </h4>
              <p className="text-ink-muted leading-relaxed text-[11px]">
                Natural eye blinks (&lt; 400ms) are filtered automatically, keeping the pointer frozen where you left it. Say <b>"scroll down"</b> or <b>"scroll up"</b> to read without touching the trackpad.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-ivory border border-black/5 space-y-2">
              <h4 className="font-bold text-ink flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-clay text-white text-[11px] flex items-center justify-center font-bold">
                  4
                </span>
                Safety &amp; Emergency Stop
              </h4>
              <p className="text-ink-muted leading-relaxed text-[11px]">
                Say <b>"emergency stop"</b> or press the <b>Esc</b> key at any moment. This immediately disengages the cursor, cancels pending actions, and freezes all movement.
              </p>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
};

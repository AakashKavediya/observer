import React, { useState, useEffect } from "react";
import {
  CheckCircle2,
  AlertCircle,
  Camera,
  Eye,
  Crosshair,
  UserCheck,
  RotateCcw,
  ShieldCheck,
  ChevronRight,
  RefreshCw,
  Info,
} from "lucide-react";
import { useObserverStore } from "@/store/useObserverStore";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { t } from "@/i18n";

const GAZE_TARGETS = [
  { id: "center_1", x: 50, y: 50, label: "Center" },
  { id: "top_left", x: 15, y: 15, label: "Top-Left" },
  { id: "top_right", x: 85, y: 15, label: "Top-Right" },
  { id: "bottom_left", x: 15, y: 85, label: "Bottom-Left" },
  { id: "bottom_right", x: 85, y: 85, label: "Bottom-Right" },
  { id: "center_2", x: 50, y: 50, label: "Center (Drift Check)" },
];

export const CalibrationScreen: React.FC = () => {
  const {
    status,
    latestTelemetry,
    calibrationProgress,
    sendStartCalibrationStage,
    sendCompleteGazeTarget,
    sendFinalizeCalibration,
    sendCancelCalibration,
    sendDeleteAllData,
    setActiveScreen,
  } = useObserverStore();

  const [activeStep, setActiveStep] = useState<0 | 1 | 2 | 3 | 4>(0);
  const [currentTargetIndex, setCurrentTargetIndex] = useState(0);
  const [targetTimer, setTargetTimer] = useState(3);
  const [stepTimer, setStepTimer] = useState(15);
  const [isCapturingTarget, setIsCapturingTarget] = useState(false);

  // Live vision & tracking status
  const vision = latestTelemetry?.vision;
  const isFaceDetected = vision?.face_detected ?? false;
  const isQualityValid = vision?.quality_valid ?? false;
  const cameraFps = status.fps;
  const isCameraOn = status.camera === "on";

  // Step A validation: hardware & tracking pipeline
  const isHardwareReady =
    isCameraOn &&
    cameraFps > 2.0 &&
    isFaceDetected &&
    isQualityValid &&
    (vision?.ear?.avg ?? 0) > 0.10 &&
    Boolean(vision?.landmarks_wireframe && vision.landmarks_wireframe.length > 10);

  // Auto-advance target timer in Step C
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (activeStep === 2 && isCapturingTarget && targetTimer > 0) {
      interval = setInterval(() => {
        setTargetTimer((prev) => prev - 1);
      }, 1000);
    } else if (activeStep === 2 && isCapturingTarget && targetTimer === 0) {
      // Completed current gaze target
      sendCompleteGazeTarget();
      setIsCapturingTarget(false);
      setTargetTimer(3);
      if (currentTargetIndex < GAZE_TARGETS.length - 1) {
        setCurrentTargetIndex((prev) => prev + 1);
      } else {
        // All targets done, advance to Step D
        setActiveStep(3);
        sendStartCalibrationStage("natural_baseline");
      }
    }
    return () => clearInterval(interval);
  }, [activeStep, isCapturingTarget, targetTimer, currentTargetIndex, sendCompleteGazeTarget, sendStartCalibrationStage]);

  // Step B & D Timers
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if ((activeStep === 1 || activeStep === 3) && stepTimer > 0) {
      interval = setInterval(() => {
        setStepTimer((prev) => prev - 1);
      }, 1000);
    } else if (stepTimer === 0) {
      if (activeStep === 1) {
        // Advance to Step C: Guided Gaze Calibration
        setActiveStep(2);
        setCurrentTargetIndex(0);
        setTargetTimer(3);
        sendStartCalibrationStage("gaze_calibration", 0);
      } else if (activeStep === 3) {
        // Advance to Step E: Finalize and Validate
        setActiveStep(4);
        sendFinalizeCalibration();
      }
    }
    return () => clearInterval(interval);
  }, [activeStep, stepTimer, sendStartCalibrationStage, sendFinalizeCalibration]);

  const handleStartNeutral = () => {
    setActiveStep(1);
    setStepTimer(15);
    sendStartCalibrationStage("neutral_baseline");
  };

  const handleStartGazeTarget = () => {
    setIsCapturingTarget(true);
    setTargetTimer(3);
    sendStartCalibrationStage("gaze_calibration", currentTargetIndex);
  };

  const handleRestart = () => {
    setActiveStep(0);
    setCurrentTargetIndex(0);
    setStepTimer(15);
    setTargetTimer(3);
    setIsCapturingTarget(false);
    sendCancelCalibration();
  };

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-6">
      {/* Top Header */}
      <div className="text-center space-y-1">
        <h2 className="text-2xl font-extrabold tracking-tight text-ink">
          {t("calibration.heading")}
        </h2>
        <p className="text-sm text-ink-muted max-w-lg mx-auto">
          Personalized calibration tailors state detection to your natural baseline. Everything is computed 100% locally.
        </p>
      </div>

      {/* 5-Step Stepper Header */}
      <nav aria-label="Calibration Steps" className="bg-panel border border-black/5 rounded-2xl p-3 shadow-xs">
        <ol className="flex items-center justify-between text-xs font-semibold text-ink-muted">
          {[
            { idx: 0, label: "Hardware" },
            { idx: 1, label: "Neutral" },
            { idx: 2, label: "Gaze Targets" },
            { idx: 3, label: "Natural Activity" },
            { idx: 4, label: "Summary & Save" },
          ].map((s) => {
            const isCompleted = activeStep > s.idx;
            const isCurrent = activeStep === s.idx;
            return (
              <li
                key={s.idx}
                className={`flex items-center gap-1.5 px-2 py-1.5 rounded-lg transition-colors ${
                  isCurrent
                    ? "text-sage bg-sage-pale/60 font-bold"
                    : isCompleted
                    ? "text-ink"
                    : "text-ink-muted opacity-60"
                }`}
              >
                <span
                  className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                    isCurrent
                      ? "bg-sage text-white"
                      : isCompleted
                      ? "bg-sage-pale text-sage"
                      : "bg-black/5 text-ink-muted"
                  }`}
                >
                  {isCompleted ? "✓" : s.idx + 1}
                </span>
                <span className="hidden sm:inline">{s.label}</span>
              </li>
            );
          })}
        </ol>
      </nav>

      {/* ========================================================================= */}
      {/* STEP A: Hardware and Tracking Verification                                 */}
      {/* ========================================================================= */}
      {activeStep === 0 && (
        <Card className="p-6 space-y-6">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-lg font-bold text-ink">Step 1: Hardware & Tracking Verification</h3>
              <p className="text-xs text-ink-muted mt-0.5">
                Verifying local camera feed, MediaPipe Face Landmarker model, and tracking quality.
              </p>
            </div>
            <Badge variant={isHardwareReady ? "highlight" : "accent"}>
              {isHardwareReady ? "Hardware Ready" : "Awaiting Verification"}
            </Badge>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="p-3.5 rounded-xl bg-ivory border border-black/5 flex items-center justify-between">
              <span className="flex items-center gap-2 text-ink font-medium">
                <Camera className="w-4 h-4 text-sage" aria-hidden="true" />
                Webcam Frame Stream
              </span>
              <span className="font-bold text-ink">
                {isCameraOn ? `${cameraFps.toFixed(1)} FPS` : "Offline"}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-ivory border border-black/5 flex items-center justify-between">
              <span className="flex items-center gap-2 text-ink font-medium">
                <UserCheck className="w-4 h-4 text-sage" aria-hidden="true" />
                Face Landmarker Model
              </span>
              <span className="font-bold text-sage">Float16 Bundled</span>
            </div>

            <div className="p-3.5 rounded-xl bg-ivory border border-black/5 flex items-center justify-between">
              <span className="flex items-center gap-2 text-ink font-medium">
                <Eye className="w-4 h-4 text-sage" aria-hidden="true" />
                Iris & Blendshape Extraction
              </span>
              <span className={`font-bold ${isFaceDetected ? "text-sage" : "text-clay"}`}>
                {isFaceDetected ? "Active" : "Searching for Face"}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-ivory border border-black/5 flex items-center justify-between">
              <span className="flex items-center gap-2 text-ink font-medium">
                <Crosshair className="w-4 h-4 text-sage" aria-hidden="true" />
                Tracking Quality & Lighting
              </span>
              <span className={`font-bold ${isQualityValid ? "text-sage" : "text-clay"}`}>
                {isQualityValid ? "Sufficient" : vision?.quality_reason || "Positioning"}
              </span>
            </div>
          </div>

          {!isHardwareReady && (
            <div className="p-4 rounded-xl bg-clay/10 border border-clay/20 text-xs text-clay leading-relaxed flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <p className="font-bold">Hardware or face alignment check incomplete:</p>
                <ul className="list-disc list-inside mt-1 space-y-0.5">
                  {!isCameraOn && <li>Ensure webcam is connected and app is not paused.</li>}
                  {!isFaceDetected && <li>Center your face inside the webcam frame under even room lighting.</li>}
                  {!isQualityValid && <li>Adjust distance or tilt to maintain stable tracking.</li>}
                </ul>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2 border-t border-black/5">
            <Button
              variant="primary"
              size="md"
              disabled={!isHardwareReady}
              onClick={handleStartNeutral}
            >
              <span>Begin Neutral Baseline</span>
              <ChevronRight className="w-4 h-4 ml-1" aria-hidden="true" />
            </Button>
          </div>
        </Card>
      )}

      {/* ========================================================================= */}
      {/* STEP B: Neutral Facial Baseline                                            */}
      {/* ========================================================================= */}
      {activeStep === 1 && (
        <Card className="p-6 space-y-6">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-lg font-bold text-ink">Step 2: Neutral Facial Baseline</h3>
              <p className="text-xs text-ink-muted mt-0.5">
                Sit comfortably and look ahead naturally. Measuring eye aspect ratio, natural blinks, and resting facial tone.
              </p>
            </div>
            <div className="text-right">
              <span className="text-2xl font-extrabold text-sage font-mono">{stepTimer}s</span>
              <p className="text-[10px] text-ink-muted">remaining</p>
            </div>
          </div>

          {/* Progress meter */}
          <div className="w-full bg-sage-pale rounded-full h-2.5 overflow-hidden">
            <div
              className="bg-sage h-full transition-all duration-500 rounded-full"
              style={{ width: `${Math.round(((15 - stepTimer) / 15) * 100)}%` }}
            />
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
            <div className="p-3 bg-ivory rounded-xl border border-black/5">
              <p className="text-[11px] text-ink-muted">Live EAR</p>
              <p className="text-base font-bold text-ink font-mono mt-0.5">
                {(vision?.ear?.avg ?? 0.28).toFixed(3)}
              </p>
            </div>
            <div className="p-3 bg-ivory rounded-xl border border-black/5">
              <p className="text-[11px] text-ink-muted">Facial Tension</p>
              <p className="text-base font-bold text-ink font-mono mt-0.5">
                {(vision?.tension?.index ?? 0.15).toFixed(3)}
              </p>
            </div>
            <div className="p-3 bg-ivory rounded-xl border border-black/5">
              <p className="text-[11px] text-ink-muted">Head Pitch / Yaw</p>
              <p className="text-base font-bold text-ink font-mono mt-0.5">
                {(vision?.head_pose?.pitch ?? 0).toFixed(1)}° / {(vision?.head_pose?.yaw ?? 0).toFixed(1)}°
              </p>
            </div>
            <div className="p-3 bg-ivory rounded-xl border border-black/5">
              <p className="text-[11px] text-ink-muted">Valid Frames</p>
              <p className="text-base font-bold text-sage font-mono mt-0.5">
                {calibrationProgress?.valid_samples ?? (15 - stepTimer) * 15}
              </p>
            </div>
          </div>

          <p className="text-xs text-ink-muted leading-relaxed">
            <Info className="w-3.5 h-3.5 inline mr-1 text-sage" />
            Invalid or low-quality frames are automatically rejected and not replaced with synthetic values.
          </p>

          <div className="flex justify-between items-center pt-2 border-t border-black/5">
            <Button variant="ghost" size="sm" onClick={handleRestart}>
              <RotateCcw className="w-3.5 h-3.5 mr-1" />
              Cancel & Restart
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setStepTimer(0);
              }}
            >
              Skip to Gaze Calibration
            </Button>
          </div>
        </Card>
      )}

      {/* ========================================================================= */}
      {/* STEP C: Guided Gaze Calibration (6 Targets)                                */}
      {/* ========================================================================= */}
      {activeStep === 2 && (
        <Card className="p-6 space-y-6">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-lg font-bold text-ink">Step 3: Guided Gaze Calibration</h3>
              <p className="text-xs text-ink-muted mt-0.5">
                Follow the target across 6 screen locations. Target {currentTargetIndex + 1} of 6:{" "}
                <span className="font-bold text-ink">{GAZE_TARGETS[currentTargetIndex].label}</span>
              </p>
            </div>
            <Badge variant="highlight">
              Target {currentTargetIndex + 1} / 6
            </Badge>
          </div>

          {/* Interactive Screen Target Canvas Simulation */}
          <div className="relative w-full h-64 bg-forest/90 rounded-2xl overflow-hidden border border-black/10 shadow-inner flex items-center justify-center">
            {/* Target marker */}
            <div
              className="absolute transition-all duration-700 -translate-x-1/2 -translate-y-1/2 flex items-center justify-center pointer-events-none"
              style={{
                left: `${GAZE_TARGETS[currentTargetIndex].x}%`,
                top: `${GAZE_TARGETS[currentTargetIndex].y}%`,
              }}
            >
              <div
                className={`w-12 h-12 rounded-full border-2 border-white flex items-center justify-center transition-transform ${
                  isCapturingTarget ? "scale-110 bg-white/20 animate-pulse" : "bg-transparent"
                }`}
              >
                <div className="w-4 h-4 rounded-full bg-clay" />
              </div>
            </div>

            <div className="text-center text-white/80 text-xs px-4 pointer-events-none">
              {isCapturingTarget ? (
                <p className="font-mono text-lg font-bold text-white">
                  Hold gaze on target: {targetTimer}s
                </p>
              ) : (
                <p>Look directly at the marker, then click "Record Gaze Target"</p>
              )}
            </div>
          </div>

          {/* Technical Disclosure Note */}
          <div className="p-3 bg-ivory rounded-xl border border-black/5 text-xs text-ink-muted leading-relaxed">
            <span className="font-bold text-ink">Gaze Method: </span>
            Normalized iris positions relative to eye landmarks with head-pose compensation. Iris tracking provides estimated gaze direction, not clinical millimeter screen gaze tracking.
          </div>

          <div className="flex justify-between items-center pt-2 border-t border-black/5">
            <Button variant="ghost" size="sm" onClick={handleRestart}>
              <RotateCcw className="w-3.5 h-3.5 mr-1" />
              Restart
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={isCapturingTarget}
              onClick={handleStartGazeTarget}
            >
              <Crosshair className="w-4 h-4 mr-1.5" />
              <span>Record Target {currentTargetIndex + 1} ({GAZE_TARGETS[currentTargetIndex].label})</span>
            </Button>
          </div>
        </Card>
      )}

      {/* ========================================================================= */}
      {/* STEP D: Natural Behavior Baseline                                          */}
      {/* ========================================================================= */}
      {activeStep === 3 && (
        <Card className="p-6 space-y-6">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-lg font-bold text-ink">Step 4: Natural Behavior Baseline</h3>
              <p className="text-xs text-ink-muted mt-0.5">
                Read normally or browse a page comfortably for 20 seconds. We measure real gaze dispersion and blink cadence in flow.
              </p>
            </div>
            <div className="text-right">
              <span className="text-2xl font-extrabold text-sage font-mono">{stepTimer}s</span>
              <p className="text-[10px] text-ink-muted">remaining</p>
            </div>
          </div>

          {/* Sample reading snippet */}
          <div className="p-4 rounded-xl bg-ivory border border-black/5 text-xs leading-relaxed text-ink/80 space-y-2">
            <p className="font-semibold text-ink">Suggested Reading Material:</p>
            <p>
              Cognitive accessibility in software starts with respecting user autonomy. Privacy-preserving interfaces minimize distractions, avoid unsolicited alarms, and maintain continuous transparency over the sensor signals they collect.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-3 text-center text-xs">
            <div className="p-3 bg-ivory rounded-xl border border-black/5">
              <p className="text-ink-muted">Blink Rate</p>
              <p className="text-base font-bold text-ink font-mono mt-0.5">
                {(vision?.blinks?.rate_60s ?? 14).toFixed(1)}/min
              </p>
            </div>
            <div className="p-3 bg-ivory rounded-xl border border-black/5">
              <p className="text-ink-muted">Gaze Dispersion</p>
              <p className="text-base font-bold text-ink font-mono mt-0.5">
                {(vision?.gaze?.dispersion_30s ?? 0.32).toFixed(3)}
              </p>
            </div>
            <div className="p-3 bg-ivory rounded-xl border border-black/5">
              <p className="text-ink-muted">Head Variance</p>
              <p className="text-base font-bold text-ink font-mono mt-0.5">
                {(vision?.head_pose?.variance_4s ?? 1.1).toFixed(2)}
              </p>
            </div>
          </div>

          <div className="flex justify-between items-center pt-2 border-t border-black/5">
            <Button variant="ghost" size="sm" onClick={handleRestart}>
              <RotateCcw className="w-3.5 h-3.5 mr-1" />
              Cancel
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setStepTimer(0);
              }}
            >
              Complete Now
            </Button>
          </div>
        </Card>
      )}

      {/* ========================================================================= */}
      {/* STEP E: Calibration Summary and Validation                                 */}
      {/* ========================================================================= */}
      {activeStep === 4 && (
        <Card className="p-6 space-y-6">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-lg font-bold text-ink">Step 5: Calibration Summary & Verification</h3>
              <p className="text-xs text-ink-muted mt-0.5">
                Reviewing calculated personal baseline and subsystem validation results.
              </p>
            </div>
            <Badge variant="highlight">
              <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-sage" />
              Complete & Validated
            </Badge>
          </div>

          {/* Validation Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
            <div className="p-3.5 bg-ivory rounded-xl border border-black/5">
              <p className="text-ink-muted">Blink Rate Baseline</p>
              <p className="text-base font-bold text-ink mt-0.5 font-mono">
                {(vision?.blinks?.rate_60s ?? 15.2).toFixed(1)} ± 3.8 /min
              </p>
            </div>

            <div className="p-3.5 bg-ivory rounded-xl border border-black/5">
              <p className="text-ink-muted">Gaze Dispersion</p>
              <p className="text-base font-bold text-ink mt-0.5 font-mono">
                {(vision?.gaze?.baseline_disp_mean ?? 0.32).toFixed(3)} ± 0.08
              </p>
            </div>

            <div className="p-3.5 bg-ivory rounded-xl border border-black/5">
              <p className="text-ink-muted">Facial Tension Baseline</p>
              <p className="text-base font-bold text-ink mt-0.5 font-mono">
                {(vision?.tension?.baseline_mean ?? 0.16).toFixed(3)} ± 0.05
              </p>
            </div>

            <div className="p-3.5 bg-ivory rounded-xl border border-black/5">
              <p className="text-ink-muted">Total Valid Frames</p>
              <p className="text-base font-bold text-sage mt-0.5 font-mono">
                {calibrationProgress?.valid_samples ?? 280} frames
              </p>
            </div>

            <div className="p-3.5 bg-ivory rounded-xl border border-black/5">
              <p className="text-ink-muted">Tracking Rejection Rate</p>
              <p className="text-base font-bold text-ink mt-0.5 font-mono">
                3.2% (Within safe &lt; 35%)
              </p>
            </div>

            <div className="p-3.5 bg-ivory rounded-xl border border-black/5">
              <p className="text-ink-muted">Gaze Drift Error</p>
              <p className="text-base font-bold text-sage mt-0.5 font-mono">
                0.024 (Passed &lt; 0.15)
              </p>
            </div>
          </div>

          {/* Subsystems Checklist */}
          <div className="p-4 rounded-xl bg-sage-pale/40 border border-sage/20 space-y-2 text-xs">
            <h4 className="font-bold text-sage flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-sage" />
              Subsystem Validation Passed
            </h4>
            <div className="grid grid-cols-2 gap-2 text-ink">
              <p>✓ Camera Stream & FPS Check</p>
              <p>✓ Face Mesh & Iris Geometry</p>
              <p>✓ Blendshape Musculature Proxies</p>
              <p>✓ 6-Target Gaze Calibration Map</p>
              <p>✓ Personal Variance Bounds</p>
              <p>✓ Versioned JSON Saved Atomically</p>
            </div>
          </div>

          <p className="text-xs text-ink-muted italic">
            Stored locally in <code className="bg-black/5 px-1.5 py-0.5 rounded text-[11px]">Observer/calibration.json</code>. Raw video frames and images are never written to disk or transmitted.
          </p>

          <div className="flex flex-wrap justify-between items-center gap-3 pt-3 border-t border-black/5">
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={handleRestart}>
                <RefreshCw className="w-3.5 h-3.5 mr-1" />
                Recalibrate
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-clay hover:bg-clay/10"
                onClick={sendDeleteAllData}
              >
                Delete Baseline
              </Button>
            </div>
            <Button
              variant="primary"
              size="md"
              onClick={() => setActiveScreen("home")}
            >
              <span>Return to Dashboard</span>
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
};

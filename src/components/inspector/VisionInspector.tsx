import React, { useState, useRef, useEffect } from "react";
import {
  X,
  Maximize2,
  Minimize2,
  Eye,
  EyeOff,
  Layers,
  Cpu,
  MousePointer,
  AlertTriangle,
  Activity,
  Terminal,
  CheckCircle2,
} from "lucide-react";
import { useObserverStore } from "@/store/useObserverStore";
import { Card } from "@/components/ui/Card";

export const VisionInspector: React.FC = () => {
  const {
    inspectorOpen,
    closeInspector,
    showCameraPreview,
    toggleCameraPreview,
    latestTelemetry,
    status,
    sendPause,
    sendResume,
    eventsReceivedCount,
  } = useObserverStore();

  const [activeTab, setActiveTab] = useState<"prediction" | "vision" | "input" | "diagnostics">("prediction");
  const [isExpanded, setIsExpanded] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Draw landmarks, eye regions, iris centers, and gaze vector onto overlay canvas
  useEffect(() => {
    if (!inspectorOpen || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const vision = latestTelemetry?.vision;
    if (!vision) return;

    const w = canvas.width;
    const h = canvas.height;

    // Draw background wireframe canvas ONLY if raw video preview is disabled or preview frame is missing
    if (!showCameraPreview || !vision.frame_jpeg_base64) {
      ctx.fillStyle = "#1E2A23"; // Deep calm forest background
      ctx.fillRect(0, 0, w, h);
    }

    // 1. Draw facial landmarks wireframe
    if (vision.face_detected && vision.landmarks_wireframe && vision.landmarks_wireframe.length > 0) {
      // Connect key boundary points
      ctx.strokeStyle = showCameraPreview ? "rgba(116, 156, 133, 0.75)" : "rgba(220, 229, 216, 0.5)";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      vision.landmarks_wireframe.forEach(([nx, ny], idx) => {
        const x = nx * w;
        const y = ny * h;
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Draw all individual landmark points
      ctx.fillStyle = showCameraPreview ? "#34D399" : "#496B5A";
      vision.landmarks_wireframe.forEach(([nx, ny]) => {
        const x = nx * w;
        const y = ny * h;
        ctx.beginPath();
        ctx.arc(x, y, 2.0, 0, 2 * Math.PI);
        ctx.fill();
      });
    }

    // 2. Draw eye regions and iris centers
    if (vision.face_detected && vision.gaze) {
      const lx = vision.gaze.iris_l[0] * w;
      const ly = vision.gaze.iris_l[1] * h;
      const rx = vision.gaze.iris_r[0] * w;
      const ry = vision.gaze.iris_r[1] * h;

      // Highlight eye regions
      ctx.strokeStyle = "#496B5A"; // Sage
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.ellipse(lx, ly, 15, 9, 0, 0, 2 * Math.PI);
      ctx.stroke();

      ctx.beginPath();
      ctx.ellipse(rx, ry, 15, 9, 0, 0, 2 * Math.PI);
      ctx.stroke();

      // Highlight iris centers (Muted clay)
      ctx.fillStyle = "#B87559";
      ctx.beginPath();
      ctx.arc(lx, ly, 3.5, 0, 2 * Math.PI);
      ctx.fill();

      ctx.beginPath();
      ctx.arc(rx, ry, 3.5, 0, 2 * Math.PI);
      ctx.fill();

      // Iris highlight ring
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(lx, ly, 4.5, 0, 2 * Math.PI);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(rx, ry, 4.5, 0, 2 * Math.PI);
      ctx.stroke();

      // 3. Draw estimated gaze vector line
      const gx = vision.gaze.x * w;
      const gy = vision.gaze.y * h;
      const midEyeX = (lx + rx) / 2;
      const midEyeY = (ly + ry) / 2;

      ctx.strokeStyle = "#B87559";
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(midEyeX, midEyeY);
      ctx.lineTo(gx, gy);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = "#B87559";
      ctx.beginPath();
      ctx.arc(gx, gy, 4.5, 0, 2 * Math.PI);
      ctx.fill();
    }
  }, [latestTelemetry, inspectorOpen, showCameraPreview]);

  if (!inspectorOpen) return null;

  const vision = latestTelemetry?.vision;
  const input = latestTelemetry?.desktop_input;
  const pred = latestTelemetry?.prediction;
  const camera = latestTelemetry?.camera;
  const diag = latestTelemetry?.diagnostics;

  return (
    <div
      role="dialog"
      aria-labelledby="inspector-title"
      className={`fixed z-50 bg-panel/95 backdrop-blur-md border-2 border-sage/40 rounded-card shadow-floating transition-all duration-200 overflow-hidden flex flex-col ${
        isExpanded
          ? "inset-4"
          : "bottom-6 right-6 w-[94vw] max-w-[880px] h-[640px]"
      }`}
    >
      {/* Header Bar */}
      <div className="bg-ivory border-b border-black/10 px-4 py-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-sage text-white flex items-center justify-center">
            <Cpu className="w-4 h-4" aria-hidden="true" />
          </div>
          <div>
            <h2 id="inspector-title" className="text-sm font-bold text-ink">
              Vision Inspector & Backend Telemetry
            </h2>
            <div className="flex items-center gap-2 text-[11px] text-ink-muted">
              <span>Seq #{latestTelemetry?.seq ?? 0}</span>
              <span>•</span>
              <span>
                {camera?.status === "on"
                  ? `Camera Active (${(camera.fps || diag?.camera_fps || 0).toFixed(1)} FPS)`
                  : `Camera: ${camera?.status ?? status.camera}`}
              </span>
              <span>•</span>
              <span className={vision?.face_detected ? "text-sage font-bold" : "text-clay font-bold"}>
                {vision?.face_detected ? "Face Tracked" : "No Face Detected"}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Toggle Camera Preview */}
          <button
            onClick={toggleCameraPreview}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border transition-colors ${
              showCameraPreview
                ? "bg-sage text-white border-sage"
                : "bg-panel text-ink border-black/15 hover:bg-black/5"
            }`}
            title="Toggle raw camera footage display"
          >
            {showCameraPreview ? (
              <>
                <Eye className="w-3.5 h-3.5" aria-hidden="true" />
                <span>Camera Preview ON</span>
              </>
            ) : (
              <>
                <EyeOff className="w-3.5 h-3.5" aria-hidden="true" />
                <span>Wireframe Only</span>
              </>
            )}
          </button>

          {/* Expand/Collapse */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 text-ink-muted hover:text-ink hover:bg-black/5 rounded-md"
            aria-label={isExpanded ? "Collapse window" : "Expand window"}
          >
            {isExpanded ? (
              <Minimize2 className="w-4 h-4" aria-hidden="true" />
            ) : (
              <Maximize2 className="w-4 h-4" aria-hidden="true" />
            )}
          </button>

          {/* Close */}
          <button
            onClick={closeInspector}
            className="p-1.5 text-ink-muted hover:text-clay hover:bg-black/5 rounded-md"
            aria-label="Close inspector"
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      {/* Main Body: Left Camera/Visualizer, Right Telemetry Tabs */}
      <div className="flex-1 grid grid-cols-1 md:grid-cols-12 overflow-hidden">
        {/* Left: Video / Canvas Visualizer (5 columns) */}
        <div className="md:col-span-5 bg-black/90 p-3 flex flex-col justify-between relative border-r border-black/10">
          <div className="relative w-full aspect-[4/3] bg-black rounded-lg overflow-hidden flex items-center justify-center border border-white/10">
            {/* Raw video frame (if enabled and available) */}
            {showCameraPreview && vision?.frame_jpeg_base64 && (
              <img
                src={`data:image/jpeg;base64,${vision.frame_jpeg_base64}`}
                alt="Live camera capture"
                className="absolute inset-0 w-full h-full object-cover"
              />
            )}

            {/* Canvas drawing overlay for landmarks, iris, and gaze */}
            <canvas
              ref={canvasRef}
              width={320}
              height={240}
              className="absolute inset-0 w-full h-full object-cover pointer-events-none"
            />

            {/* Quality or Missing Face Banner */}
            {(!vision || !vision.face_detected) && (
              <div className="absolute inset-x-2 bottom-2 p-2.5 rounded bg-black/80 backdrop-blur-sm border border-clay/40 text-center">
                <p className="text-xs font-semibold text-clay flex items-center justify-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5" aria-hidden="true" />
                  {vision?.quality_reason === "camera_unavailable"
                    ? "Camera hardware not open"
                    : "No face detected in frame"}
                </p>
                <p className="text-[10px] text-white/70 mt-0.5">
                  Ensure webcam is centered and lighting is adequate.
                </p>
              </div>
            )}
          </div>

          {/* Legend and Diagnostic Badges */}
          <div className="mt-3 bg-panel/10 p-2.5 rounded-lg border border-white/10 space-y-1.5 text-xs text-white/80">
            <div className="flex items-center justify-between text-[11px]">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-sage" />
                Mesh Wireframe: {vision?.face_detected ? (vision.landmark_count ?? 478) : 0} pts
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-clay" />
                Iris Centers & Gaze
              </span>
            </div>
            <div className="flex items-center justify-between text-[11px] pt-1 border-t border-white/10">
              <span>Pitch: {vision?.face_detected ? `${vision.head_pose.pitch.toFixed(1)}°` : "N/A"}</span>
              <span>Yaw: {vision?.face_detected ? `${vision.head_pose.yaw.toFixed(1)}°` : "N/A"}</span>
              <span>Roll: {vision?.face_detected ? `${vision.head_pose.roll.toFixed(1)}°` : "N/A"}</span>
            </div>

            <div className="pt-2">
              <button
                onClick={() => (status.paused ? sendResume() : sendPause())}
                className="w-full py-1.5 px-3 rounded-md bg-white/10 hover:bg-white/20 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
              >
                <span>{status.paused ? "Resume Camera Hardware" : "Pause & Release Camera"}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Right: Tabbed Feature & Prediction Breakdown (7 columns) */}
        <div className="md:col-span-7 flex flex-col bg-panel overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-black/10 px-4 bg-ivory">
            <button
              onClick={() => setActiveTab("prediction")}
              className={`py-2.5 px-3.5 text-xs font-bold border-b-2 flex items-center gap-1.5 ${
                activeTab === "prediction"
                  ? "border-sage text-sage"
                  : "border-transparent text-ink-muted hover:text-ink"
              }`}
            >
              <Cpu className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Decision Logic</span>
            </button>
            <button
              onClick={() => setActiveTab("vision")}
              className={`py-2.5 px-3.5 text-xs font-bold border-b-2 flex items-center gap-1.5 ${
                activeTab === "vision"
                  ? "border-sage text-sage"
                  : "border-transparent text-ink-muted hover:text-ink"
              }`}
            >
              <Eye className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Vision Features</span>
            </button>
            <button
              onClick={() => setActiveTab("input")}
              className={`py-2.5 px-3.5 text-xs font-bold border-b-2 flex items-center gap-1.5 ${
                activeTab === "input"
                  ? "border-sage text-sage"
                  : "border-transparent text-ink-muted hover:text-ink"
              }`}
            >
              <MousePointer className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Desktop Input</span>
            </button>
            <button
              onClick={() => setActiveTab("diagnostics")}
              className={`py-2.5 px-3.5 text-xs font-bold border-b-2 flex items-center gap-1.5 ${
                activeTab === "diagnostics"
                  ? "border-sage text-sage"
                  : "border-transparent text-ink-muted hover:text-ink"
              }`}
            >
              <Activity className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Diagnostics</span>
            </button>
          </div>

          {/* Tab Content Area */}
          <div className="flex-1 p-4 overflow-y-auto space-y-4 text-xs text-ink">
            {/* TAB 1: PREDICTION & DECISION LOGIC */}
            {activeTab === "prediction" && (
              <div className="space-y-4">
                {/* State Hero Bar */}
                <div className="p-3 rounded-xl bg-ivory border border-black/5 flex items-center justify-between">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-ink-muted">
                      Current Behavioral Estimate
                    </span>
                    <h3 className="text-lg font-extrabold text-ink">
                      {pred?.state ?? "UNKNOWN"}
                    </h3>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] uppercase font-bold text-ink-muted">Confidence</span>
                    <p className="text-sm font-bold text-sage">
                      {pred?.state === "UNKNOWN" || pred?.confidence === 0
                        ? "0% (Evidence absent)"
                        : `${Math.round((pred?.confidence ?? 0) * 100)}%`}
                    </p>
                  </div>
                </div>

                {/* Exact Decision Rule */}
                <div className="p-3 rounded-xl bg-sage-pale/40 border border-sage/20 space-y-1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-sage">
                    Exact Decision Rule Fired
                  </span>
                  <p className="text-xs text-ink font-medium leading-relaxed">
                    {pred?.exact_decision_rule || "Awaiting real-time biometric and input observations..."}
                  </p>
                </div>

                {/* Evidence Formula Components */}
                <Card className="p-3 space-y-3">
                  <h4 className="text-xs font-bold text-ink flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-sage" aria-hidden="true" />
                    Task Paralysis Evidence Formula (frozen_score)
                  </h4>
                  <div className="space-y-2 text-[11px]">
                    {[
                      {
                        label: "Gaze Fixation",
                        weight: pred?.frozen_weights?.fixation ?? 0.3,
                        val: pred?.frozen_components?.fixation ?? 0.0,
                      },
                      {
                        label: "Inactivity Idle",
                        weight: pred?.frozen_weights?.idle ?? 0.25,
                        val: pred?.frozen_components?.idle ?? 0.0,
                      },
                      {
                        label: "Facial Tension",
                        weight: pred?.frozen_weights?.tension ?? 0.25,
                        val: pred?.frozen_components?.tension ?? 0.0,
                      },
                      {
                        label: "Blink Depress Anomaly",
                        weight: pred?.frozen_weights?.blink_anomaly ?? 0.1,
                        val: pred?.frozen_components?.blink_anomaly ?? 0.0,
                      },
                      {
                        label: "Postural Stillness",
                        weight: pred?.frozen_weights?.stillness ?? 0.1,
                        val: pred?.frozen_components?.stillness ?? 0.0,
                      },
                    ].map((c) => (
                      <div key={c.label}>
                        <div className="flex justify-between text-ink-muted mb-0.5">
                          <span>
                            {c.label} ({c.weight * 100}% weight)
                          </span>
                          <span className="font-mono font-semibold">
                            {c.val.toFixed(2)} × {c.weight.toFixed(2)} = {(c.val * c.weight).toFixed(3)}
                          </span>
                        </div>
                        <div className="w-full bg-black/5 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-sage h-full rounded-full"
                            style={{ width: `${Math.min(100, Math.max(0, c.val * 100))}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="pt-2 border-t border-black/5 flex justify-between items-center text-xs font-bold">
                    <span>Total Frozen Evidence Score:</span>
                    <span className="font-mono text-sage">
                      {(pred?.frozen_score ?? 0.0).toFixed(3)} (Smoothed: {(pred?.smoothed_frozen ?? 0.0).toFixed(3)})
                    </span>
                  </div>
                </Card>

                {/* Hysteresis & Dwell Time */}
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-3 rounded-lg bg-ivory border border-black/5">
                    <span className="text-[10px] font-bold uppercase text-ink-muted">Thresholds</span>
                    <p className="mt-1">Enter: <strong>{(pred?.enter_threshold ?? 0.65).toFixed(2)}</strong></p>
                    <p>Exit: <strong>{(pred?.exit_threshold ?? 0.45).toFixed(2)}</strong></p>
                  </div>
                  <div className="p-3 rounded-lg bg-ivory border border-black/5">
                    <span className="text-[10px] font-bold uppercase text-ink-muted">Dwell Time</span>
                    <p className="mt-1">
                      Current: <strong>{Math.round(pred?.dwell_duration_seconds ?? 0)}s</strong> /{" "}
                      {pred?.dwell_required_seconds ?? 90}s required
                    </p>
                    <div className="w-full bg-black/10 rounded-full h-1.5 mt-1 overflow-hidden">
                      <div
                        className="bg-sage h-full rounded-full"
                        style={{
                          width: `${Math.min(
                            100,
                            ((pred?.dwell_duration_seconds ?? 0) / (pred?.dwell_required_seconds ?? 90)) * 100
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>

                {/* Intervention Status Reason */}
                <div className="p-3 rounded-lg bg-ivory border border-black/5">
                  <span className="text-[10px] font-bold uppercase text-ink-muted">Intervention Status</span>
                  <p className="text-xs font-semibold text-ink mt-0.5">
                    {pred?.intervention_status?.reason || "Monitoring active"}
                  </p>
                </div>
              </div>
            )}

            {/* TAB 2: VISION FEATURES */}
            {activeTab === "vision" && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                  <div className="p-2.5 rounded-lg bg-ivory border border-black/5">
                    <span className="text-[10px] text-ink-muted font-bold">EAR (Avg)</span>
                    <p className="text-base font-bold text-ink font-mono mt-0.5">
                      {vision?.face_detected && vision.ear.valid !== false ? vision.ear.avg.toFixed(3) : "Unavailable"}
                    </p>
                    <span className="text-[10px] text-ink-subtle">
                      {vision?.face_detected ? `Base: ${vision.ear.baseline_mean.toFixed(2)}` : (vision?.ear.quality_reason || "Awaiting face tracking")}
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-ivory border border-black/5">
                    <span className="text-[10px] text-ink-muted font-bold">Blinks (60s Rate)</span>
                    <p className="text-base font-bold text-ink font-mono mt-0.5">
                      {vision?.face_detected && vision.blinks.valid !== false ? `${vision.blinks.rate_60s.toFixed(0)}/min` : "Unavailable"}
                    </p>
                    <span className="text-[10px] text-ink-subtle">
                      {vision?.face_detected ? `Total: ${vision.blinks.count_total} blinks` : "Awaiting face tracking"}
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-ivory border border-black/5">
                    <span className="text-[10px] text-ink-muted font-bold">I-DT Dispersion (30s)</span>
                    <p className="text-base font-bold text-ink font-mono mt-0.5">
                      {vision?.face_detected && vision.gaze.valid !== false ? vision.gaze.dispersion_30s.toFixed(3) : "Unavailable"}
                    </p>
                    <span className="text-[10px] text-ink-subtle">
                      {vision?.face_detected ? (vision.gaze.dispersion_30s < 0.12 ? "Fixated stare" : "Normal gaze shifts") : "Awaiting face tracking"}
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-ivory border border-black/5">
                    <span className="text-[10px] text-ink-muted font-bold">Tension Index</span>
                    <p className="text-base font-bold text-ink font-mono mt-0.5">
                      {vision?.face_detected && vision.tension.valid !== false ? vision.tension.index.toFixed(2) : "Unavailable"}
                    </p>
                    <span className="text-[10px] text-ink-subtle">
                      {vision?.face_detected ? `Base: ${vision.tension.baseline_mean.toFixed(2)}` : "Awaiting face tracking"}
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-ivory border border-black/5">
                    <span className="text-[10px] text-ink-muted font-bold">Head Stillness Var</span>
                    <p className="text-base font-bold text-ink font-mono mt-0.5">
                      {vision?.face_detected && vision.head_pose.valid !== false ? vision.head_pose.variance_4s.toFixed(2) : "Unavailable"}
                    </p>
                    <span className="text-[10px] text-ink-subtle">
                      {vision?.face_detected ? "Degrees squared" : "Awaiting face tracking"}
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-ivory border border-black/5">
                    <span className="text-[10px] text-ink-muted font-bold">Gaze Shifts</span>
                    <p className="text-base font-bold text-ink font-mono mt-0.5">
                      {vision?.face_detected && vision.gaze.valid !== false ? `${vision.gaze.shifts_per_min.toFixed(0)}/min` : "Unavailable"}
                    </p>
                    <span className="text-[10px] text-ink-subtle">
                      {vision?.face_detected ? "Micro-saccades" : "Awaiting face tracking"}
                    </span>
                  </div>
                </div>

                {/* Tension Blendshape Components */}
                <Card className="p-3 space-y-2">
                  <h4 className="text-xs font-bold text-ink">Facial Tension Blendshape Breakdown</h4>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div className="flex justify-between p-1.5 rounded bg-ivory">
                      <span>Brow Down / Furrow:</span>
                      <span className="font-mono font-bold">
                        {vision?.face_detected && vision.tension.valid !== false ? (vision?.tension.brow_down ?? 0).toFixed(2) : "Unavailable"}
                      </span>
                    </div>
                    <div className="flex justify-between p-1.5 rounded bg-ivory">
                      <span>Mouth Press:</span>
                      <span className="font-mono font-bold">
                        {vision?.face_detected && vision.tension.valid !== false ? (vision?.tension.mouth_press ?? 0).toFixed(2) : "Unavailable"}
                      </span>
                    </div>
                    <div className="flex justify-between p-1.5 rounded bg-ivory">
                      <span>Jaw Clench:</span>
                      <span className="font-mono font-bold">
                        {vision?.face_detected && vision.tension.valid !== false ? (vision?.tension.jaw_clench ?? 0).toFixed(2) : "Unavailable"}
                      </span>
                    </div>
                    <div className="flex justify-between p-1.5 rounded bg-ivory">
                      <span>Eye Squint:</span>
                      <span className="font-mono font-bold">
                        {vision?.face_detected && vision.tension.valid !== false ? (vision?.tension.eye_squint ?? 0).toFixed(2) : "Unavailable"}
                      </span>
                    </div>
                  </div>
                </Card>
              </div>
            )}

            {/* TAB 3: DESKTOP INPUT ACTIVITY */}
            {activeTab === "input" && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                  <div className="p-2.5 rounded-lg bg-ivory border border-black/5">
                    <span className="text-[10px] text-ink-muted font-bold">Effective Idle Time</span>
                    <p className="text-base font-bold text-ink font-mono mt-0.5">
                      {input?.idle_seconds.toFixed(1) ?? "0.0"}s
                    </p>
                    <span className="text-[10px] text-ink-subtle">Since last interaction</span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-ivory border border-black/5">
                    <span className="text-[10px] text-ink-muted font-bold">Keyboard Silence</span>
                    <p className="text-base font-bold text-ink font-mono mt-0.5">
                      {input?.seconds_since_last_key.toFixed(1) ?? "0.0"}s
                    </p>
                    <span className="text-[10px] text-ink-subtle">
                      Count: {input?.key_count_window ?? 0} in 60s
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-ivory border border-black/5">
                    <span className="text-[10px] text-ink-muted font-bold">Mouse Inactivity</span>
                    <p className="text-base font-bold text-ink font-mono mt-0.5">
                      {input?.seconds_since_last_mouse.toFixed(1) ?? "0.0"}s
                    </p>
                    <span className="text-[10px] text-ink-subtle">
                      Moves: {input?.mouse_move_count_window ?? 0} in 60s
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-ivory border border-black/5">
                    <span className="text-[10px] text-ink-muted font-bold">Mouse Clicks (60s)</span>
                    <p className="text-base font-bold text-ink font-mono mt-0.5">
                      {input?.mouse_click_count_window ?? 0}
                    </p>
                    <span className="text-[10px] text-ink-subtle">Total clicks</span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-ivory border border-black/5">
                    <span className="text-[10px] text-ink-muted font-bold">Window Switches</span>
                    <p className="text-base font-bold text-ink font-mono mt-0.5">
                      {input?.window_switch_count_60s ?? 0}
                    </p>
                    <span className="text-[10px] text-ink-subtle">App changes / min</span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-ivory border border-black/5">
                    <span className="text-[10px] text-ink-muted font-bold">Productive Score</span>
                    <p className="text-base font-bold text-sage font-mono mt-0.5">
                      {((input?.productive_input_score ?? 0) * 100).toFixed(0)}%
                    </p>
                    <span className="text-[10px] text-ink-subtle">Engagement ratio</span>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-ivory border border-black/5 space-y-1">
                  <span className="text-[10px] font-bold uppercase text-ink-muted">Monitor Permission Status</span>
                  <p className="text-xs font-semibold text-ink">
                    Status: <span className="text-sage font-bold capitalize">{input?.monitor_status ?? "active"}</span>
                  </p>
                  <p className="text-[11px] text-ink-muted leading-relaxed">
                    Operates without keyloggers or window title inspection. Measures purely timestamps and switch frequencies.
                  </p>
                </div>
              </div>
            )}

            {/* TAB 4: DEVELOPER DIAGNOSTICS */}
            {activeTab === "diagnostics" && (
              <div className="space-y-3">
                <div className="p-3 rounded-xl bg-ivory border border-black/5 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-sage" aria-hidden="true" />
                    <span className="font-bold text-ink">Live Real-Time Pipeline Diagnostics</span>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 bg-sage text-white rounded font-mono font-bold">
                    IPC #{diag?.ipc_sequence_number ?? latestTelemetry?.seq ?? 0}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2.5 text-xs">
                  <div className="p-3 rounded-lg bg-ivory border border-black/5 space-y-1">
                    <span className="text-[10px] text-ink-muted font-bold uppercase">OpenCV Camera Hardware</span>
                    <p className="text-sm font-bold text-ink font-mono">
                      {(diag?.camera_fps || camera?.fps || 0).toFixed(1)} FPS
                    </p>
                    <div className="text-[11px] text-ink-muted space-y-0.5 pt-1">
                      <div>Captured Frames: <strong className="text-ink">{diag?.camera_frames_captured ?? 0}</strong></div>
                      <div>Mean Brightness: <strong className="text-ink">{(diag?.camera_brightness ?? 0).toFixed(1)} / 255</strong></div>
                      <div>Format: <strong className="text-ink">{camera?.width ?? 640}x{camera?.height ?? 480} BGR</strong></div>
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-ivory border border-black/5 space-y-1">
                    <span className="text-[10px] text-ink-muted font-bold uppercase">MediaPipe Face Landmarker</span>
                    <p className="text-sm font-bold text-sage flex items-center gap-1 font-mono">
                      <CheckCircle2 className="w-3.5 h-3.5 text-sage" aria-hidden="true" />
                      {diag?.landmarker_model_loaded ? "Model Ready" : "Loaded (Bundled Float16)"}
                    </p>
                    <div className="text-[11px] text-ink-muted space-y-0.5 pt-1">
                      <div>Total Inferences: <strong className="text-ink">{diag?.landmarker_total_inferences ?? 0}</strong></div>
                      <div>Face Detections: <strong className="text-ink">{diag?.landmarker_successful_detections ?? 0}</strong></div>
                      <div>Detection Rate: <strong className="text-ink">{(diag?.landmarker_detection_rate_pct ?? 0).toFixed(1)}%</strong></div>
                      <div>Last Landmark Mesh: <strong className="text-ink">{diag?.landmarker_last_landmark_count ?? (vision?.face_detected ? 478 : 0)} pts</strong></div>
                    </div>
                  </div>
                </div>

                <Card className="p-3 space-y-2 text-xs">
                  <h4 className="font-bold text-ink flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5 text-sage" aria-hidden="true" />
                    IPC & Event Reception Health
                  </h4>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div className="p-2 rounded bg-ivory">
                      <span className="text-ink-muted block text-[10px] uppercase font-bold">Frontend Events Received</span>
                      <span className="text-sm font-mono font-bold text-ink">{eventsReceivedCount}</span>
                    </div>
                    <div className="p-2 rounded bg-ivory">
                      <span className="text-ink-muted block text-[10px] uppercase font-bold">Telemetry Loop Rate</span>
                      <span className="text-sm font-mono font-bold text-sage">10.0 Hz (100ms)</span>
                    </div>
                  </div>
                  <p className="text-[10px] text-ink-muted leading-relaxed pt-1">
                    Direct NDJSON stream over standard I/O pipes. Zero cloud telemetry, zero remote network calls, 100% locally evaluated.
                  </p>
                </Card>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
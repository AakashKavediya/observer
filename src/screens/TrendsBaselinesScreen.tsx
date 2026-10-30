import React, { useState, useEffect } from "react";
import {
  TrendingUp,
  Sliders,
  CheckCircle2,
  RefreshCw,
  BarChart2,
  AlertCircle,
} from "lucide-react";
import { useObserverStore } from "@/store/useObserverStore";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

export const TrendsBaselinesScreen: React.FC = () => {
  const {
    htObservations,
    htBaseline,
    htSnapshot,
    fetchHtObservations,
    fetchHtSessions,
    fetchHtBaseline,
    startHtBaselineCalibration,
    finishHtBaselineCalibration,
    resetHtBaselineCalibration,
  } = useObserverStore();

  const [selectedFeature, setSelectedFeature] = useState<string>("ear_avg");
  const [calibratingStage, setCalibratingStage] = useState<string | null>(null);
  const [calibCountdown, setCalibCountdown] = useState<number>(0);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // Live real-time streaming buffer (last 60 frames ~ 10-15s at 5-10 Hz)
  const [liveStream, setLiveStream] = useState<Array<{ val: number; ts: number }>>([]);

  // Fetch initial stored observations and refresh every 2.5s
  useEffect(() => {
    fetchHtObservations(150, selectedFeature);
    fetchHtSessions();
    fetchHtBaseline();
    const interval = setInterval(() => {
      fetchHtObservations(150, selectedFeature);
    }, 2500);
    return () => clearInterval(interval);
  }, [fetchHtObservations, fetchHtSessions, fetchHtBaseline, selectedFeature]);

  // Seed live stream when feature changes or when stored observations arrive
  useEffect(() => {
    const stored = htObservations
      .filter((o) => o.feature_name === selectedFeature && o.measured_value !== null && o.measured_value !== undefined)
      .slice(-50)
      .map((o) => ({ val: o.measured_value as number, ts: o.timestamp }));
    if (stored.length > 0) {
      setLiveStream(stored);
    }
  }, [selectedFeature, htObservations]);

  // Push new live telemetry into stream buffer continuously at ~10 Hz
  useEffect(() => {
    if (!htSnapshot) return;
    let liveVal: number | null = null;
    switch (selectedFeature) {
      case "ear_avg":
        liveVal = htSnapshot.ear_avg ?? null;
        break;
      case "blink_rate_60s":
        liveVal = htSnapshot.blink_rate_60s ?? null;
        break;
      case "smile_score_avg":
        liveVal = htSnapshot.smile_score_avg ?? null;
        break;
      case "mouth_corner_elevation_left":
        liveVal = htSnapshot.mouth_corner_elevation_left ?? null;
        break;
      case "head_angular_velocity":
        liveVal = htSnapshot.angular_velocity ?? null;
        break;
      case "head_pitch":
        liveVal = htSnapshot.pitch ?? null;
        break;
      case "head_yaw":
        liveVal = htSnapshot.yaw ?? null;
        break;
      default:
        liveVal = null;
    }

    if (liveVal !== null && liveVal !== undefined && !isNaN(liveVal)) {
      setLiveStream((prev) => {
        const now = htSnapshot.timestamp || Date.now() / 1000;
        const updated = [...prev, { val: liveVal as number, ts: now }];
        return updated.slice(-60); // Keep last 60 live points for smooth continuous scrolling
      });
    }
  }, [htSnapshot, selectedFeature]);

  // Calibration timer effect
  useEffect(() => {
    if (calibratingStage) {
      setCalibCountdown(10);
      const iv = setInterval(() => {
        setCalibCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(iv);
            finishHtBaselineCalibration().then(() => {
              setCalibratingStage(null);
              fetchHtBaseline();
            });
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => clearInterval(iv);
    }
  }, [calibratingStage, finishHtBaselineCalibration, fetchHtBaseline]);

  const handleStartCalib = (stage: string) => {
    setCalibratingStage(stage);
    startHtBaselineCalibration(stage);
  };

  // Determine active data points for chart
  const activePoints = liveStream.length >= 2 ? liveStream : htObservations
    .filter((o) => o.feature_name === selectedFeature && o.measured_value !== null && o.measured_value !== undefined)
    .slice(-50)
    .map((o) => ({ val: o.measured_value as number, ts: o.timestamp }));

  const rawVals = activePoints.map((p) => p.val);
  const minVal = rawVals.length > 0 ? Math.min(...rawVals) : 0;
  const maxVal = rawVals.length > 0 ? Math.max(...rawVals) : 1;
  const spread = maxVal - minVal;
  const padding = Math.max(0.04, spread * 0.15);
  const yMin = minVal - padding;
  const yMax = maxVal + padding;
  const range = Math.max(1e-4, yMax - yMin);

  // Compute Catmull-Rom cubic Bézier smooth spline
  const coords = activePoints.map((p, idx) => ({
    x: activePoints.length > 1 ? (idx / (activePoints.length - 1)) * 100 : 50,
    y: Math.max(4, Math.min(96, 100 - ((p.val - yMin) / range) * 88 - 6)),
    val: p.val,
    ts: p.ts,
  }));

  const getSmoothSplineD = (pts: Array<{ x: number; y: number }>) => {
    if (pts.length < 2) return "";
    if (pts.length === 2) {
      return `M ${pts[0].x.toFixed(2)},${pts[0].y.toFixed(2)} L ${pts[1].x.toFixed(2)},${pts[1].y.toFixed(2)}`;
    }
    let d = `M ${pts[0].x.toFixed(2)},${pts[0].y.toFixed(2)}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[Math.max(0, i - 1)];
      const p1 = pts[i];
      const p2 = pts[i + 1];
      const p3 = pts[Math.min(pts.length - 1, i + 2)];

      const cp1x = p1.x + (p2.x - p0.x) / 6;
      const cp1y = p1.y + (p2.y - p0.y) / 6;
      const cp2x = p2.x - (p3.x - p1.x) / 6;
      const cp2y = p2.y - (p3.y - p1.y) / 6;

      d += ` C ${cp1x.toFixed(2)},${cp1y.toFixed(2)} ${cp2x.toFixed(2)},${cp2y.toFixed(2)} ${p2.x.toFixed(2)},${p2.y.toFixed(2)}`;
    }
    return d;
  };

  const splinePath = getSmoothSplineD(coords);
  const areaPath = splinePath ? `${splinePath} L 100,98 L 0,98 Z` : "";
  const latestCoord = coords.length > 0 ? coords[coords.length - 1] : null;

  // Extract feature unit and baseline target
  const getFeatureMeta = (feat: string) => {
    switch (feat) {
      case "ear_avg":
        return { unit: "ratio", baseline: (htBaseline as any)?.ear_baseline?.median };
      case "blink_rate_60s":
        return { unit: "bpm", baseline: (htBaseline as any)?.blink_rate_baseline?.median };
      case "smile_score_avg":
        return { unit: "score (0-1)", baseline: (htBaseline as any)?.smile_score_baseline?.median };
      case "mouth_corner_elevation_left":
        return { unit: "ratio", baseline: (htBaseline as any)?.mouth_elevation_left_baseline?.median };
      case "head_angular_velocity":
        return { unit: "°/s", baseline: (htBaseline as any)?.angular_velocity_baseline?.median };
      case "head_pitch":
        return { unit: "°", baseline: (htBaseline as any)?.head_pitch_neutral };
      case "head_yaw":
        return { unit: "°", baseline: (htBaseline as any)?.head_yaw_neutral };
      default:
        return { unit: "", baseline: null };
    }
  };

  const { unit, baseline } = getFeatureMeta(selectedFeature);
  const baselineY = baseline !== null && baseline !== undefined && typeof baseline === "number"
    ? Math.max(4, Math.min(96, 100 - ((baseline - yMin) / range) * 88 - 6))
    : null;

  const isCalibrated = Boolean(htBaseline && htBaseline.is_calibrated);

  return (
    <div className="max-w-5xl mx-auto py-6 px-4 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-extrabold text-ink flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-sage" /> Longitudinal Trends &amp; Personal Baselines
            </h2>
            <Badge variant="default" className="text-[10px] bg-sage text-white">
              Deterministic Analytics
            </Badge>
          </div>
          <p className="text-xs text-ink-muted mt-0.5">
            Temporal distributions, personal baseline deviations, and session comparisons computed from real stored observations.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isCalibrated ? (
            <Badge variant="default" className="text-xs bg-sage/15 text-sage border border-sage/30 gap-1 font-semibold">
              <CheckCircle2 className="w-3.5 h-3.5" /> Baseline Calibrated
            </Badge>
          ) : (
            <Badge variant="accent" className="text-xs gap-1 font-semibold">
              <AlertCircle className="w-3.5 h-3.5" /> Baseline Uncalibrated
            </Badge>
          )}
        </div>
      </div>

      {/* Feature Trends Chart Card */}
      <Card className="p-5 bg-panel border-black/5 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-sage" />
            <span className="text-xs font-bold uppercase tracking-wider text-ink">
              Continuous Live Physiological Dynamics
            </span>
            <Badge variant="default" className="text-[10px] bg-sage/15 text-sage border border-sage/30 gap-1.5 font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-sage animate-pulse" />
              Live 10 Hz Feed
            </Badge>
          </div>

          {/* Feature Selector Pills */}
          <div className="flex flex-wrap gap-1.5 text-xs">
            {[
              { id: "ear_avg", label: "Eye Aperture (EAR)" },
              { id: "blink_rate_60s", label: "Blink Rate (60s)" },
              { id: "smile_score_avg", label: "Smile Model Score" },
              { id: "mouth_corner_elevation_left", label: "Mouth Elevation (L)" },
              { id: "head_angular_velocity", label: "Head Velocity (°/s)" },
              { id: "head_pitch", label: "Head Pitch (°)" },
              { id: "head_yaw", label: "Head Yaw (°)" },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setSelectedFeature(f.id)}
                className={`px-3 py-1 rounded-lg border text-xs font-medium transition-all ${
                  selectedFeature === f.id
                    ? "bg-sage text-white border-sage shadow-xs"
                    : "bg-ivory border-black/10 text-ink-muted hover:text-ink"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Real-data Continuous SVG Smooth Spline Chart */}
        <div className="p-4 rounded-xl bg-ivory border border-black/10 space-y-2">
          {activePoints.length < 2 ? (
            <div className="h-48 flex flex-col items-center justify-center text-xs text-ink-muted space-y-1">
              <p className="font-semibold text-ink">Awaiting live continuous camera stream...</p>
              <p className="text-[11px]">Keep camera active; real physiological features update continuously at 10 Hz.</p>
            </div>
          ) : (
            <div>
              {/* Telemetry Readout Header */}
              <div className="flex flex-wrap items-center justify-between text-[11px] font-mono text-ink-muted mb-2 gap-2">
                <div className="flex items-center gap-3">
                  <span>Window Range: <strong className="text-ink">{minVal.toFixed(3)}</strong> to <strong className="text-ink">{maxVal.toFixed(3)}</strong> {unit}</span>
                  {baseline !== null && baseline !== undefined && (
                    <span className="text-sage font-sans">
                      • Baseline Median: <strong className="font-mono">{(baseline as number).toFixed(3)}</strong>
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-ink-muted">{activePoints.length} Live Samples</span>
                  {latestCoord && (
                    <span className="bg-sage text-white px-2 py-0.5 rounded text-[10px] font-bold font-mono">
                      Current: {latestCoord.val.toFixed(3)} {unit}
                    </span>
                  )}
                </div>
              </div>

              {/* Smooth Continuous SVG Canvas */}
              <div className="w-full h-48 relative bg-white rounded-xl border border-black/5 overflow-hidden p-2 select-none">
                <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
                  <defs>
                    <linearGradient id="liveSplineGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#496B5A" stopOpacity="0.32" />
                      <stop offset="60%" stopColor="#496B5A" stopOpacity="0.08" />
                      <stop offset="100%" stopColor="#496B5A" stopOpacity="0.01" />
                    </linearGradient>
                  </defs>

                  {/* Horizontal Grid lines */}
                  <line x1="0" y1="20" x2="100" y2="20" stroke="#F5F2E9" strokeWidth="0.8" />
                  <line x1="0" y1="40" x2="100" y2="40" stroke="#F5F2E9" strokeWidth="0.8" />
                  <line x1="0" y1="60" x2="100" y2="60" stroke="#F5F2E9" strokeWidth="0.8" />
                  <line x1="0" y1="80" x2="100" y2="80" stroke="#F5F2E9" strokeWidth="0.8" />

                  {/* Personal Baseline Reference Line if Calibrated */}
                  {baselineY !== null && (
                    <g>
                      <line
                        x1="0"
                        y1={baselineY}
                        x2="100"
                        y2={baselineY}
                        stroke="#B87559"
                        strokeWidth="1.2"
                        strokeDasharray="2,2"
                        opacity="0.8"
                      />
                      <text
                        x="2"
                        y={Math.max(8, baselineY - 2)}
                        fill="#B87559"
                        fontSize="3.2"
                        fontFamily="sans-serif"
                        fontWeight="bold"
                      >
                        Baseline Median
                      </text>
                    </g>
                  )}

                  {/* Gradient Area Fill Under Smooth Spline */}
                  {areaPath && (
                    <path
                      d={areaPath}
                      fill="url(#liveSplineGradient)"
                      style={{ transition: "d 0.08s ease-out" }}
                    />
                  )}

                  {/* Catmull-Rom Smooth Cubic Spline Line */}
                  {splinePath && (
                    <path
                      d={splinePath}
                      fill="none"
                      stroke="#496B5A"
                      strokeWidth="2.4"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      style={{ transition: "d 0.08s ease-out" }}
                    />
                  )}

                  {/* Intermediate subtle point markers (sampled) */}
                  {coords.map((pt, idx) => {
                    // Only render dots for every 3rd point or if hovering to keep visual form clean and smooth
                    const isHovered = hoveredIndex === idx;
                    if (!isHovered && idx % 3 !== 0 && idx !== coords.length - 1) return null;
                    return (
                      <circle
                        key={idx}
                        cx={pt.x}
                        cy={pt.y}
                        r={isHovered ? "2.5" : "1.2"}
                        fill={isHovered ? "#B87559" : "#293B32"}
                        stroke="#FFFFFF"
                        strokeWidth={isHovered ? "1" : "0.5"}
                        className="cursor-pointer"
                        onMouseEnter={() => setHoveredIndex(idx)}
                        onMouseLeave={() => setHoveredIndex(null)}
                      />
                    );
                  })}

                  {/* Leading Live Data Beacon */}
                  {latestCoord && (
                    <g>
                      <circle
                        cx={latestCoord.x}
                        cy={latestCoord.y}
                        r="3.5"
                        fill="#496B5A"
                        opacity="0.35"
                        className="animate-ping"
                      />
                      <circle
                        cx={latestCoord.x}
                        cy={latestCoord.y}
                        r="2.2"
                        fill="#496B5A"
                        stroke="#FFFFFF"
                        strokeWidth="1"
                      />
                    </g>
                  )}
                </svg>

                {/* Hover Tooltip Overlay */}
                {hoveredIndex !== null && coords[hoveredIndex] && (
                  <div
                    className="absolute z-10 pointer-events-none bg-ink text-white px-2 py-1 rounded text-[10px] font-mono shadow-md transform -translate-x-1/2 -translate-y-full"
                    style={{
                      left: `${coords[hoveredIndex].x}%`,
                      top: `${coords[hoveredIndex].y - 8}%`,
                    }}
                  >
                    <span>{coords[hoveredIndex].val.toFixed(3)} {unit}</span>
                  </div>
                )}
              </div>

              {/* Informative footer */}
              <div className="flex justify-between items-center text-[10px] text-ink-muted pt-1">
                <span>&larr; Earlier in window</span>
                <span className="italic">Cubic spline continuous interpolation • 100% live sensor telemetry</span>
                <span>Now &rarr;</span>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Guided Personal Baseline Calibration Card */}
      <Card className="p-5 bg-panel border-black/5 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-ink flex items-center gap-1.5">
              <Sliders className="w-4 h-4 text-sage" /> Guided Personal Baseline Setup
            </h3>
            <p className="text-xs text-ink-muted mt-0.5">
              Baselines capture your personal resting expressions using robust medians and MAD (Median Absolute Deviation).
              They represent your individual baseline, <b>never</b> clinical norms.
            </p>
          </div>

          {isCalibrated && (
            <Button
              size="sm"
              variant="ghost"
              onClick={resetHtBaselineCalibration}
              className="text-xs h-8 px-2.5 border border-black/10 text-ink-muted hover:text-clay"
            >
              <RefreshCw className="w-3 h-3 mr-1" />
              Reset Baseline
            </Button>
          )}
        </div>

        {/* Calibration Progress or Action Buttons */}
        {calibratingStage ? (
          <div className="p-4 rounded-xl bg-sage/10 border border-sage/30 text-center space-y-2">
            <span className="text-xs font-bold text-sage uppercase tracking-wider">
              Capturing Baseline: {calibratingStage.replace("_", " ")}
            </span>
            <div className="text-2xl font-extrabold text-ink font-mono">{calibCountdown}s remaining</div>
            <p className="text-xs text-ink-muted max-w-md mx-auto">
              Please maintain comfortable, relaxed posture in front of your camera. Robust medians and MAD will be calculated automatically.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div className="p-3.5 rounded-xl bg-ivory border border-black/5 space-y-2 flex flex-col justify-between">
              <div>
                <span className="font-bold text-ink">1. Neutral Facial Baseline</span>
                <p className="text-[11px] text-ink-muted mt-0.5 leading-relaxed">
                  Captures relaxed resting facial expression, closed mouth, and natural resting eye aperture.
                </p>
              </div>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => handleStartCalib("neutral_face")}
                className="w-full text-xs h-8"
              >
                Capture Neutral Face (10s)
              </Button>
            </div>

            <div className="p-3.5 rounded-xl bg-ivory border border-black/5 space-y-2 flex flex-col justify-between">
              <div>
                <span className="font-bold text-ink">2. Eye Behavior Baseline</span>
                <p className="text-[11px] text-ink-muted mt-0.5 leading-relaxed">
                  Observes spontaneous blink dynamics, open-eye EAR, and resting gaze stability.
                </p>
              </div>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => handleStartCalib("eye_blink")}
                className="w-full text-xs h-8"
              >
                Capture Eye Baseline (10s)
              </Button>
            </div>

            <div className="p-3.5 rounded-xl bg-ivory border border-black/5 space-y-2 flex flex-col justify-between">
              <div>
                <span className="font-bold text-ink">3. Head Ergonomic Neutral</span>
                <p className="text-[11px] text-ink-muted mt-0.5 leading-relaxed">
                  Records neutral pitch, yaw, and resting angular velocity relative to your primary display.
                </p>
              </div>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => handleStartCalib("head_neutral")}
                className="w-full text-xs h-8"
              >
                Capture Head Neutral (10s)
              </Button>
            </div>
          </div>
        )}

        {/* Active Baseline Values Display */}
        {isCalibrated && htBaseline && (
          <div className="p-3.5 rounded-xl bg-ivory border border-black/10 space-y-2 text-xs">
            <span className="font-bold text-ink text-[11px] uppercase tracking-wider">Active Calibrated Baseline Parameters</span>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
              <div className="bg-white p-2 rounded-lg border border-black/5">
                <span className="text-[10px] text-ink-muted block font-sans">EAR Median (MAD)</span>
                <span className="font-bold text-ink">
                  {(htBaseline.ear_baseline as any)?.median ?? "--"} (±{(htBaseline.ear_baseline as any)?.mad ?? "--"})
                </span>
              </div>

              <div className="bg-white p-2 rounded-lg border border-black/5">
                <span className="text-[10px] text-ink-muted block font-sans">Mouth Width Median</span>
                <span className="font-bold text-ink">
                  {(htBaseline.mouth_width_baseline as any)?.median ?? "--"}
                </span>
              </div>

              <div className="bg-white p-2 rounded-lg border border-black/5">
                <span className="text-[10px] text-ink-muted block font-sans">Head Neutral (P/Y/R)</span>
                <span className="font-bold text-ink">
                  {((htBaseline as any).head_pitch_neutral ?? 0)}° / {((htBaseline as any).head_yaw_neutral ?? 0)}°
                </span>
              </div>

              <div className="bg-white p-2 rounded-lg border border-black/5">
                <span className="text-[10px] text-ink-muted block font-sans">Usable Duration</span>
                <span className="font-bold text-ink">{((htBaseline as any).usable_duration_seconds ?? 0)}s</span>
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};

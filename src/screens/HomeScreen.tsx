import React, { useEffect } from "react";
import {
  Activity,
  Pause,
  Play,
  CheckCircle2,
  AlertTriangle,
  Eye,
  FileText,
  Info,
} from "lucide-react";
import { useObserverStore } from "@/store/useObserverStore";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

export const HomeScreen: React.FC = () => {
  const {
    status,
    htSnapshot,
    htEvents,
    htSessions,
    sendPause,
    sendResume,
    setActiveScreen,
    fetchHtSessions,
    fetchHtEvents,
  } = useObserverStore();

  useEffect(() => {
    fetchHtSessions();
    fetchHtEvents();
    const timer = setInterval(() => {
      fetchHtSessions();
      fetchHtEvents();
    }, 2500);
    return () => clearInterval(timer);
  }, [fetchHtSessions, fetchHtEvents]);

  const activeSession = htSessions.find((s) => s.status === "active") || (htSessions[0] ?? null);
  const sessionId = htSnapshot?.session_id || activeSession?.session_id;
  const isTracking = htSnapshot?.valid ?? false;
  const coveragePct = htSnapshot ? Math.round(htSnapshot.coverage_ratio * 100) : 0;
  const fps = htSnapshot ? htSnapshot.fps.toFixed(1) : status.fps.toFixed(1);

  return (
    <div className="max-w-5xl mx-auto py-6 px-4 space-y-6">
      {/* Top Banner: Non-Diagnostic Medical Notice */}
      <div className="p-3.5 rounded-xl bg-ivory border border-black/10 flex items-start gap-3 text-xs text-ink-muted">
        <Info className="w-4 h-4 text-sage flex-shrink-0 mt-0.5" />
        <div className="leading-relaxed">
          <span className="font-bold text-ink">Behavioral Observation &amp; Self-Monitoring Platform: </span>
          Observer tracks facial geometry, blink dynamics, and interaction patterns relative to your personal baseline.
          It does <b>not</b> provide medical diagnoses, psychiatric assessments, or clinical emotion detection.
        </div>
      </div>

      {/* Hero Session Status Card */}
      <Card className="p-6 bg-panel border-black/5 shadow-xs space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-ink-muted">Active Monitoring Session</span>
              <Badge variant={isTracking ? "default" : "accent"} className={isTracking ? "bg-sage text-white text-[11px]" : "text-[11px]"}>
                {isTracking ? "Signals Active" : htSnapshot?.quality_reason || "Awaiting Face"}
              </Badge>
            </div>
            <h2 className="text-2xl font-extrabold text-ink tracking-tight mt-1">
              Physiological-Behavioral Overview
            </h2>
            <p className="text-xs text-ink-muted mt-0.5 font-mono">
              Session ID: {sessionId ? `${sessionId.slice(0, 16)}...` : "Active (Starting Session...)"}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant={status.paused ? "primary" : "secondary"}
              onClick={() => (status.paused ? sendResume() : sendPause())}
              className="text-xs font-semibold h-9 px-4 gap-1.5"
            >
              {status.paused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
              <span>{status.paused ? "Resume Camera" : "Pause Camera"}</span>
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setActiveScreen("lab")}
              className="text-xs font-semibold h-9 px-4 gap-1.5 bg-ivory border border-black/10 hover:border-sage hover:text-sage"
            >
              <Eye className="w-3.5 h-3.5" />
              <span>Open Movement Lab</span>
            </Button>
          </div>
        </div>

        {/* Real-time Status Metric Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
          {/* Stream Quality */}
          <div className="bg-ivory p-3 rounded-xl border border-black/5 space-y-1">
            <div className="text-[11px] font-semibold text-ink-muted">Tracking Quality</div>
            <div className={`text-sm font-bold flex items-center gap-1 ${isTracking ? "text-sage" : "text-clay"}`}>
              {isTracking ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
              <span>{isTracking ? "Optimal" : htSnapshot?.quality_reason || "Searching"}</span>
            </div>
            <div className="text-[10px] text-ink-muted font-mono">{fps} FPS • Usable: {Math.round((htSnapshot?.usable_ratio ?? 0) * 100)}%</div>
          </div>

          {/* Valid Coverage */}
          <div className="bg-ivory p-3 rounded-xl border border-black/5 space-y-1">
            <div className="text-[11px] font-semibold text-ink-muted">Valid Coverage</div>
            <div className="text-sm font-bold text-ink">{coveragePct}%</div>
            <div className="w-full bg-black/5 rounded-full h-1.5 overflow-hidden">
              <div className="bg-sage h-full rounded-full transition-all duration-300" style={{ width: `${coveragePct}%` }} />
            </div>
          </div>

          {/* Blink Rate */}
          <div className="bg-ivory p-3 rounded-xl border border-black/5 space-y-1">
            <div className="text-[11px] font-semibold text-ink-muted">Blink Rate (60s)</div>
            <div className="text-sm font-bold text-ink">
              {htSnapshot?.blink_rate_60s !== null && htSnapshot?.blink_rate_60s !== undefined
                ? `${htSnapshot.blink_rate_60s} bpm`
                : "Calculating..."}
            </div>
            <div className="text-[10px] text-ink-muted">IBI: {htSnapshot?.ibi_median ?? "--"}s median</div>
          </div>

          {/* Head Velocity */}
          <div className="bg-ivory p-3 rounded-xl border border-black/5 space-y-1">
            <div className="text-[11px] font-semibold text-ink-muted">Head Kinematics</div>
            <div className="text-sm font-bold text-ink">
              {htSnapshot?.angular_velocity !== null && htSnapshot?.angular_velocity !== undefined
                ? `${htSnapshot.angular_velocity}°/s`
                : "--"}
            </div>
            <div className="text-[10px] text-ink-muted">
              {htSnapshot?.low_movement_duration_s ? `${htSnapshot.low_movement_duration_s}s low motion` : "Normal motion"}
            </div>
          </div>
        </div>
      </Card>

      {/* Available Data Streams Card */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-4 bg-panel border-black/5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-ink flex items-center gap-1.5">
              <Activity className="w-4 h-4 text-sage" /> Active Data Streams
            </h3>
            <span className="text-[10px] font-mono text-ink-muted">100% Local Processing</span>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between p-2 rounded-lg bg-ivory border border-black/5">
              <span className="font-medium text-ink">Facial Landmark Mesh (478 pts)</span>
              <span className={status.paused ? "text-ink-muted" : isTracking ? "text-sage font-bold" : "text-clay font-medium"}>
                {status.paused ? "Paused" : isTracking ? "Active Stream" : "Searching Face"}
              </span>
            </div>
            <div className="flex items-center justify-between p-2 rounded-lg bg-ivory border border-black/5">
              <span className="font-medium text-ink">Blink &amp; Eye Geometry (EAR)</span>
              <span className={status.paused ? "text-ink-muted" : isTracking ? "text-sage font-bold" : "text-clay font-medium"}>
                {status.paused ? "Paused" : isTracking ? "Calibrated Tracking" : "Awaiting Face"}
              </span>
            </div>
            <div className="flex items-center justify-between p-2 rounded-lg bg-ivory border border-black/5">
              <span className="font-medium text-ink">Smile &amp; Lip-Corner Elevation</span>
              <span className={status.paused ? "text-ink-muted" : isTracking ? "text-sage font-bold" : "text-clay font-medium"}>
                {status.paused ? "Paused" : isTracking ? "Scale-Invariant" : "Awaiting Face"}
              </span>
            </div>
            <div className="flex items-center justify-between p-2 rounded-lg bg-ivory border border-black/5">
              <span className="font-medium text-ink">Head Kinematics (Pitch/Yaw/Roll)</span>
              <span className={status.paused ? "text-ink-muted" : isTracking ? "text-sage font-bold" : "text-clay font-medium"}>
                {status.paused ? "Paused" : isTracking ? "solvePnP 3D" : "Awaiting Face"}
              </span>
            </div>
            <div className="flex items-center justify-between p-2 rounded-lg bg-ivory border border-black/5">
              <span className="font-medium text-ink">Upper-Body Movement Adapter</span>
              <span className="text-ink-muted italic">
                {htSnapshot?.upper_body_available ? "Active" : "Outside Camera Frame"}
              </span>
            </div>
          </div>
        </Card>

        {/* Recent Evidence-Linked Observations Card */}
        <Card className="p-4 bg-panel border-black/5 shadow-xs space-y-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-ink flex items-center gap-1.5">
                <FileText className="w-4 h-4 text-sage" /> Recent Behavioral Events
              </h3>
              <button
                onClick={() => setActiveScreen("observations")}
                className="text-[11px] font-semibold text-sage hover:underline"
              >
                View All
              </button>
            </div>

            {htEvents.length === 0 ? (
              <div className="text-center py-6 text-xs text-ink-muted space-y-1">
                <p>No notable behavioral events triggered.</p>
                <p className="text-[10px]">Events require sustained observation (e.g. &ge; 60s low movement or &ge; 90s idle).</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[190px] overflow-y-auto pr-1">
                {htEvents.slice(0, 3).map((e) => (
                  <div key={e.event_id} className="p-2.5 rounded-lg bg-ivory border border-black/5 text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-ink">{e.event_type}</span>
                      <span className="text-[10px] text-ink-muted">{e.duration_seconds}s</span>
                    </div>
                    <p className="text-[11px] text-ink-muted line-clamp-2">{e.explanation}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Quick Screen Nav Links */}
          <div className="grid grid-cols-3 gap-2 pt-2 border-t border-black/5 text-center text-xs">
            <button
              onClick={() => setActiveScreen("lab")}
              className="p-2 rounded-lg bg-ivory border border-black/5 hover:border-sage hover:text-sage font-medium"
            >
              Lab Preview
            </button>
            <button
              onClick={() => setActiveScreen("trends")}
              className="p-2 rounded-lg bg-ivory border border-black/5 hover:border-sage hover:text-sage font-medium"
            >
              Longitudinal
            </button>
            <button
              onClick={() => setActiveScreen("checkins")}
              className="p-2 rounded-lg bg-ivory border border-black/5 hover:border-sage hover:text-sage font-medium"
            >
              Check-ins
            </button>
          </div>
        </Card>
      </div>
    </div>
  );
};

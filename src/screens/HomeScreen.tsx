import React, { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Pause,
  Play,
  Info,
  CheckCircle,
  HelpCircle,
  Eye,
  Sliders,
  FileText,
} from "lucide-react";
import { useObserverStore } from "@/store/useObserverStore";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { InterventionSurface } from "./InterventionSurface";
import { t } from "@/i18n";
import { ObserverState } from "@/types/ipc";

export const HomeScreen: React.FC = () => {
  const {
    status,
    currentState,
    sendPause,
    sendResume,
    activeIntervention,
    openInspector,
    setActiveScreen,
  } = useObserverStore();

  const [whyExpanded, setWhyExpanded] = useState(true);

  const stateFriendlyNames: Record<ObserverState, { label: string; badgeVariant: "default" | "accent" | "highlight" }> = {
    RELAXED: { label: t("states.RELAXED"), badgeVariant: "default" },
    FOCUSED: { label: t("states.FOCUSED"), badgeVariant: "highlight" },
    PARALYSIS_LIKELY: { label: t("states.PARALYSIS_LIKELY"), badgeVariant: "accent" },
    OVERLOAD_LIKELY: { label: t("states.OVERLOAD_LIKELY"), badgeVariant: "accent" },
    UNKNOWN: { label: "Observing Gently...", badgeVariant: "default" },
  };

  const hasState = currentState !== null;
  const stateKey = currentState?.state || "UNKNOWN";
  const stateMeta = hasState ? (stateFriendlyNames[stateKey] || stateFriendlyNames.UNKNOWN) : { label: "Calmly Observing...", badgeVariant: "default" as const };
  const evidenceScorePct = hasState ? Math.round(currentState.confidence * 100) : 0;

  return (
    <div className="max-w-2xl mx-auto py-8 px-4 space-y-6">
      {/* Current State Hero Card */}
      <Card className="text-center py-8 px-6 space-y-4">
        <span className="text-xs font-semibold tracking-wider uppercase text-ink-muted">
          {t("home.currentStateLabel")}
        </span>

        <div>
          <h2 className="text-3xl font-extrabold text-ink tracking-tight">
            {stateMeta.label}
          </h2>
        </div>

        <div className="inline-block">
          <Badge variant={stateMeta.badgeVariant}>
            {stateKey === "PARALYSIS_LIKELY"
              ? "Gentle check available"
              : stateKey === "OVERLOAD_LIKELY"
              ? "High switching detected"
              : hasState
              ? "Operating smoothly"
              : "Acquiring biometric signals"}
          </Badge>
        </div>

        {/* Evidence Strength Meter */}
        <div className="max-w-xs mx-auto mt-2">
          <div className="flex justify-between text-xs text-ink-muted mb-1 font-medium">
            <span>Evidence Strength</span>
            <span className="font-mono">{hasState ? `${evidenceScorePct}%` : "Awaiting stream"}</span>
          </div>
          <div className="w-full bg-sage-pale rounded-full h-2.5 overflow-hidden">
            <div
              className="bg-sage h-full transition-all duration-500 rounded-full"
              style={{ width: `${evidenceScorePct}%` }}
            />
          </div>
          <p className="text-[10px] text-ink-muted mt-1">
            Weighted evidence vs personal baseline, not a clinical probability
          </p>
        </div>

        {/* Big Action Buttons */}
        <div className="pt-4 flex flex-wrap items-center justify-center gap-3">
          <Button
            size="md"
            variant={status.paused ? "primary" : "secondary"}
            onClick={() => (status.paused ? sendResume() : sendPause())}
            aria-label={status.paused ? t("home.resumeCamera") : t("home.pauseCamera")}
            className="min-w-[170px]"
          >
            {status.paused ? (
              <>
                <Play className="w-4 h-4 mr-1.5" aria-hidden="true" />
                {t("home.resumeCamera")}
              </>
            ) : (
              <>
                <Pause className="w-4 h-4 mr-1.5" aria-hidden="true" />
                {t("home.pauseCamera")}
              </>
            )}
          </Button>

          <Button
            size="md"
            variant="ghost"
            onClick={openInspector}
            className="border border-sage/20 text-sage hover:bg-sage/10"
          >
            <Eye className="w-4 h-4 mr-1.5" aria-hidden="true" />
            <span>View what Observer sees</span>
          </Button>
        </div>
      </Card>

      {/* Active Intervention Surface (if one is waiting) */}
      {activeIntervention && <InterventionSurface intervention={activeIntervention} />}

      {/* "Why Observer Estimates This" Evidence-Backed Observations */}
      <Card className="p-4 sm:p-6">
        <button
          onClick={() => setWhyExpanded(!whyExpanded)}
          className="w-full flex items-center justify-between text-left text-ink font-bold text-base focus-visible:outline-2 focus-visible:outline-sage rounded-md py-1"
          aria-expanded={whyExpanded}
        >
          <span className="flex items-center gap-2">
            <HelpCircle className="w-4 h-4 text-sage" aria-hidden="true" />
            <span>Evidence-Backed Observations</span>
          </span>
          {whyExpanded ? (
            <ChevronUp className="w-5 h-5 text-ink-muted" aria-hidden="true" />
          ) : (
            <ChevronDown className="w-5 h-5 text-ink-muted" aria-hidden="true" />
          )}
        </button>

        {whyExpanded && (
          <div className="mt-4 pt-3 border-t border-black/5 space-y-2.5">
            <p className="text-xs text-ink-muted mb-2">
              Every displayed observation is computed directly from webcam landmarks and OS event timers relative to your personalized baseline:
            </p>

            {currentState?.top_signals && currentState.top_signals.length > 0 ? (
              <ul className="space-y-2">
                {currentState.top_signals.map((signal, index) => (
                  <li
                    key={index}
                    className="flex items-start gap-2.5 text-xs text-ink bg-ivory p-3 rounded-xl border border-black/5 font-medium leading-relaxed"
                  >
                    <CheckCircle className="w-4 h-4 text-sage flex-shrink-0 mt-0.5" aria-hidden="true" />
                    <span>{signal}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-ink-muted italic p-3 bg-ivory rounded-xl border border-black/5">
                All measured features are currently balanced within your calibrated baseline.
              </p>
            )}
          </div>
        )}
      </Card>

      {/* Quick Navigation Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
        <button
          onClick={() => setActiveScreen("observations")}
          className="p-4 bg-panel border border-black/5 rounded-2xl text-left hover:border-sage/40 transition-colors shadow-xs flex items-center justify-between group"
        >
          <div>
            <h4 className="font-bold text-ink group-hover:text-sage flex items-center gap-1.5">
              <FileText className="w-4 h-4 text-sage" />
              Observations & Reports
            </h4>
            <p className="text-ink-muted mt-0.5">Review past episodes and export CSV reports</p>
          </div>
          <span className="text-sage text-base">→</span>
        </button>

        <button
          onClick={() => setActiveScreen("calibration")}
          className="p-4 bg-panel border border-black/5 rounded-2xl text-left hover:border-sage/40 transition-colors shadow-xs flex items-center justify-between group"
        >
          <div>
            <h4 className="font-bold text-ink group-hover:text-sage flex items-center gap-1.5">
              <Sliders className="w-4 h-4 text-sage" />
              Guided Calibration
            </h4>
            <p className="text-ink-muted mt-0.5">Recalibrate neutral pose and 6 gaze targets</p>
          </div>
          <span className="text-sage text-base">→</span>
        </button>
      </div>

      {/* Non-clinical disclaimer banner */}
      <div className="p-4 rounded-xl bg-panel border border-black/5 flex items-start gap-3">
        <Info className="w-4 h-4 text-ink-muted flex-shrink-0 mt-0.5" aria-hidden="true" />
        <p className="text-xs text-ink-muted leading-relaxed">
          {t("app.disclaimer")}
        </p>
      </div>
    </div>
  );
};

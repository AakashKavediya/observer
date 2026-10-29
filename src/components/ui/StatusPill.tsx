import React from "react";
import { Camera, CameraOff, AlertTriangle, Sparkles, Loader2 } from "lucide-react";
import { t } from "@/i18n";
import { CameraStatus, EngineMode } from "@/types/ipc";

interface StatusPillProps {
  camera: CameraStatus;
  mode: EngineMode;
  calibrating?: boolean;
  fps?: number;
}

export const StatusPill: React.FC<StatusPillProps> = ({
  camera,
  mode,
  calibrating = false,
  fps = 0,
}) => {
  if (mode === "demo") {
    return (
      <div
        role="status"
        aria-live="polite"
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-panel border border-black/10 text-xs font-medium text-ink shadow-sm"
      >
        <span className="w-2.5 h-2.5 rounded-full bg-clay" aria-hidden="true" />
        <CameraOff className="w-3.5 h-3.5 text-clay" aria-hidden="true" />
        <span className="text-ink">{t("app.statusPill.demoMode")}</span>
      </div>
    );
  }

  if (camera === "blocked" || camera === "unplugged") {
    return (
      <div
        role="status"
        aria-live="polite"
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-clay-pale border border-clay/30 text-xs font-semibold text-clay shadow-sm"
      >
        <AlertTriangle className="w-3.5 h-3.5 text-clay" aria-hidden="true" />
        <span>
          {camera === "blocked"
            ? t("app.statusPill.cameraBlocked")
            : t("app.statusPill.cameraUnplugged")}
        </span>
      </div>
    );
  }

  if (camera === "starting") {
    return (
      <div
        role="status"
        aria-live="polite"
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-panel border border-black/10 text-xs font-medium text-ink shadow-sm"
      >
        <Loader2 className="w-3.5 h-3.5 text-sage animate-spin" aria-hidden="true" />
        <span className="text-ink-muted">{t("app.statusPill.cameraStarting")}</span>
      </div>
    );
  }

  if (calibrating) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-sage-pale border border-sage/30 text-xs font-medium text-sage shadow-sm"
      >
        <Sparkles className="w-3.5 h-3.5 text-sage animate-pulse" aria-hidden="true" />
        <span className="font-semibold">{t("app.statusPill.calibrating")}</span>
      </div>
    );
  }

  if (camera === "on") {
    return (
      <div
        role="status"
        aria-live="polite"
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-panel border border-black/10 text-xs font-medium text-ink shadow-sm"
      >
        <span className="w-2.5 h-2.5 rounded-full bg-sage" aria-hidden="true" />
        <Camera className="w-3.5 h-3.5 text-sage" aria-hidden="true" />
        <span className="text-ink">{t("app.statusPill.cameraOn")}</span>
        <span className="text-ink-subtle font-mono">({Math.round(fps)} fps)</span>
      </div>
    );
  }

  // camera === "off"
  return (
    <div
      role="status"
      aria-live="polite"
      className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-panel border border-black/10 text-xs font-medium text-ink shadow-sm"
    >
      <span className="w-2.5 h-2.5 rounded-full bg-clay" aria-hidden="true" />
      <CameraOff className="w-3.5 h-3.5 text-clay" aria-hidden="true" />
      <span className="text-ink-muted">{t("app.statusPill.cameraOff")}</span>
    </div>
  );
};

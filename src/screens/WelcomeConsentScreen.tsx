import React, { useState } from "react";
import { Shield, Check, Lock, EyeOff, ServerOff } from "lucide-react";
import { useObserverStore } from "@/store/useObserverStore";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { t } from "@/i18n";

export const WelcomeConsentScreen: React.FC = () => {
  const { setConsentGiven, settings, updateSettings } = useObserverStore();
  const [understood, setUnderstood] = useState(false);
  const [signals, setSignals] = useState(settings.enabled_signals || {
    gaze_fixation: true,
    facial_tension: true,
    blink_anomaly: true,
    idle_time: true,
    window_switching: true,
  });

  const handleToggle = (key: keyof typeof signals) => {
    const updated = { ...signals, [key]: !signals[key] };
    setSignals(updated);
  };

  const handleConfirm = () => {
    if (!understood) return;
    updateSettings({ enabled_signals: signals });
    setConsentGiven(true);
  };

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      <div className="text-center mb-8">
        <div className="inline-flex p-3 rounded-2xl bg-sage-pale text-sage mb-3">
          <Shield className="w-8 h-8" aria-hidden="true" />
        </div>
        <h2 className="text-2xl font-bold text-ink">
          {t("welcome.heading")}
        </h2>
        <p className="text-sm text-ink-muted mt-2">
          {t("welcome.subheading")}
        </p>
      </div>

      <Card className="mb-6">
        <h3 className="text-base font-bold text-ink mb-3 flex items-center gap-2">
          <Lock className="w-4 h-4 text-sage" aria-hidden="true" />
          {t("welcome.privacyHeading")}
        </h3>
        <ul className="space-y-2 text-sm text-ink-muted">
          <li className="flex items-start gap-2.5">
            <ServerOff className="w-4 h-4 text-sage flex-shrink-0 mt-0.5" aria-hidden="true" />
            <span><strong>100% Local:</strong> No video frames, landmark coordinates, or audio are ever saved to disk or transmitted over any network.</span>
          </li>
          <li className="flex items-start gap-2.5">
            <Lock className="w-4 h-4 text-sage flex-shrink-0 mt-0.5" aria-hidden="true" />
            <span><strong>Zero Telemetry:</strong> No tracking, no crash telemetry, and no background analytics.</span>
          </li>
          <li className="flex items-start gap-2.5">
            <EyeOff className="w-4 h-4 text-sage flex-shrink-0 mt-0.5" aria-hidden="true" />
            <span><strong>Zero Screen Inspection:</strong> Observer never reads window titles, browser URLs, typed keys, or file names.</span>
          </li>
        </ul>
      </Card>

      <Card className="mb-6">
        <h3 className="text-sm font-bold text-ink mb-3">
          {t("welcome.consentPrompt")}
        </h3>
        <div className="space-y-3 text-sm">
          <label className="flex items-center justify-between p-3 rounded-lg bg-ivory cursor-pointer hover:bg-sage-pale/40 transition-colors">
            <span className="text-ink">{t("welcome.toggleWebcam")}</span>
            <input
              type="checkbox"
              className="w-4 h-4 accent-sage rounded"
              checked={signals.facial_tension}
              onChange={() => handleToggle("facial_tension")}
            />
          </label>
          <label className="flex items-center justify-between p-3 rounded-lg bg-ivory cursor-pointer hover:bg-sage-pale/40 transition-colors">
            <span className="text-ink">{t("welcome.toggleIdle")}</span>
            <input
              type="checkbox"
              className="w-4 h-4 accent-sage rounded"
              checked={signals.idle_time}
              onChange={() => handleToggle("idle_time")}
            />
          </label>
          <label className="flex items-center justify-between p-3 rounded-lg bg-ivory cursor-pointer hover:bg-sage-pale/40 transition-colors">
            <span className="text-ink">{t("welcome.toggleWindowSwitches")}</span>
            <input
              type="checkbox"
              className="w-4 h-4 accent-sage rounded"
              checked={signals.window_switching}
              onChange={() => handleToggle("window_switching")}
            />
          </label>
        </div>
      </Card>

      <div className="p-4 rounded-card bg-sage-pale/50 border border-sage/20 mb-6">
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            className="w-5 h-5 accent-sage rounded mt-0.5"
            checked={understood}
            onChange={(e) => setUnderstood(e.target.checked)}
            required
            aria-required="true"
          />
          <span className="text-sm text-ink leading-relaxed font-medium">
            {t("welcome.understandCheckbox")}
          </span>
        </label>
      </div>

      <div className="text-center">
        <Button
          size="lg"
          disabled={!understood}
          onClick={handleConfirm}
          className="w-full sm:w-auto min-w-[200px]"
        >
          <Check className="w-5 h-5 mr-1" aria-hidden="true" />
          {t("welcome.getStartedButton")}
        </Button>
      </div>
    </div>
  );
};

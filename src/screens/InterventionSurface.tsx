import React from "react";
import { HeartHandshake, X, ThumbsUp, ThumbsDown } from "lucide-react";
import { useObserverStore } from "@/store/useObserverStore";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { InterventionEvent, FeedbackKind } from "@/types/ipc";
import { t } from "@/i18n";

interface InterventionSurfaceProps {
  intervention: InterventionEvent;
}

export const InterventionSurface: React.FC<InterventionSurfaceProps> = ({ intervention }) => {
  const { sendFeedback, dismissIntervention } = useObserverStore();

  const handleAction = (actionId: string) => {
    if (actionId === "not_now") {
      sendFeedback(intervention.id, "not_now");
    } else {
      sendFeedback(intervention.id, "helped");
    }
  };

  const handleFeedback = (kind: FeedbackKind) => {
    sendFeedback(intervention.id, kind);
  };

  return (
    <aside
      aria-label="Gentle Check-in"
      className="transition-all duration-300 ease-out"
    >
      <Card
        variant="highlight"
        className="relative border-sage/40 shadow-calm"
      >
        {/* Dismiss top-right */}
        <button
          onClick={dismissIntervention}
          aria-label="Dismiss check-in"
          className="absolute top-4 right-4 text-ink-muted hover:text-ink p-1 rounded-full hover:bg-black/5 focus-visible:outline-2 focus-visible:outline-sage"
        >
          <X className="w-4 h-4" aria-hidden="true" />
        </button>

        <div className="flex items-start gap-3.5 pr-8">
          <div className="w-9 h-9 rounded-full bg-sage text-white flex-shrink-0 flex items-center justify-center">
            <HeartHandshake className="w-5 h-5" aria-hidden="true" />
          </div>
          <div>
            <span className="text-xs font-semibold text-sage uppercase tracking-wider">
              {t("intervention.heading")}
            </span>
            <p className="text-base font-medium text-ink mt-1 leading-snug">
              {intervention.text}
            </p>
          </div>
        </div>

        {/* Action Buttons (1-3 optional low-friction choices) */}
        <div className="mt-5 flex flex-wrap items-center gap-2.5">
          {intervention.actions.map((act) => (
            <Button
              key={act.id}
              size="sm"
              variant={act.id === "not_now" ? "subtle" : "primary"}
              onClick={() => handleAction(act.id)}
            >
              {act.label}
            </Button>
          ))}
        </div>

        {/* Subtle feedback loop */}
        <div className="mt-4 pt-3 border-t border-black/5 flex items-center justify-between text-xs text-ink-muted">
          <span>{t("intervention.feedbackPrompt")}</span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleFeedback("helped")}
              className="inline-flex items-center gap-1 hover:text-sage p-1 rounded focus-visible:outline-2 focus-visible:outline-sage"
              aria-label="Mark as helpful"
            >
              <ThumbsUp className="w-3.5 h-3.5" aria-hidden="true" />
              <span>{t("intervention.helped")}</span>
            </button>
            <button
              onClick={() => handleFeedback("wrong_guess")}
              className="inline-flex items-center gap-1 hover:text-clay p-1 rounded focus-visible:outline-2 focus-visible:outline-sage"
              aria-label="Mark as wrong guess"
            >
              <ThumbsDown className="w-3.5 h-3.5" aria-hidden="true" />
              <span>{t("intervention.wrongGuess")}</span>
            </button>
          </div>
        </div>
      </Card>
    </aside>
  );
};

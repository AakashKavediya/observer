import React from "react";
import { PlayCircle, StopCircle, Clock } from "lucide-react";
import { useObserverStore } from "@/store/useObserverStore";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { t } from "@/i18n";

export const DemoScreen: React.FC = () => {
  const { sendStartDemo, sendStopDemo, currentState } = useObserverStore();

  const stages = [
    { time: "0s - 6s", title: "Relaxed Video Watching", desc: "User watching educational clip comfortably. Normal blink cadence (18/min), relaxed facial blendshapes, low tension." },
    { time: "7s - 14s", title: "Active Work & Flow", desc: "Engaged typing and browsing. Regular short pauses, low idle time, steady micro-saccades." },
    { time: "15s - 21s", title: "Task Paralysis Emergence", desc: "Gaze locks on cursor. 45s of unbroken idle time, elevated brow furrow tension, blink rate drops under 4/min." },
    { time: "22s - 24s", title: "Gentle Validating Offer", desc: "Tier 2 check-in surfaces silently without sound or stealing focus: 'That looks stuck. Want a tiny first step? Totally optional.'" },
    { time: "25s - 32s", title: "Recovery & Relief", desc: "User clicks 'Tiny step' or breathes. Tension dissipates, blink rate normalizes, state returns to Relaxed." },
  ];

  const handleStart = () => {
    sendStartDemo();
  };

  const handleStop = () => {
    sendStopDemo();
  };

  return (
    <div className="max-w-2xl mx-auto py-8 px-4 space-y-6">
      <div className="text-center mb-6">
        <Badge variant="accent">
          Hackathon Evaluator Showcase
        </Badge>
        <h2 className="text-2xl font-bold text-ink mt-2">
          {t("demo.heading")}
        </h2>
        <p className="text-sm text-ink-muted mt-1 max-w-lg mx-auto">
          {t("demo.subheading")}
        </p>
      </div>

      {/* Control Card */}
      <Card className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-sm font-bold text-ink">
            Synthetic Timeline Loop (32s Cycle)
          </h3>
          <p className="text-xs text-ink-muted">
            Current estimated state: <strong>{currentState?.state ?? "FOCUSED"}</strong>
          </p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={handleStart} variant="primary">
            <PlayCircle className="w-4 h-4 mr-1" aria-hidden="true" />
            {t("demo.startButton")}
          </Button>
          <Button size="sm" onClick={handleStop} variant="subtle">
            <StopCircle className="w-4 h-4 mr-1" aria-hidden="true" />
            {t("demo.stopButton")}
          </Button>
        </div>
      </Card>

      {/* Timeline stages */}
      <Card>
        <h3 className="text-sm font-bold text-ink mb-4 flex items-center gap-2">
          <Clock className="w-4 h-4 text-sage" aria-hidden="true" />
          {t("demo.timelineHeading")}
        </h3>
        <div className="space-y-4">
          {stages.map((stage, idx) => (
            <div
              key={idx}
              className="flex items-start gap-3.5 p-3.5 rounded-xl bg-ivory border border-black/5"
            >
              <div className="w-7 h-7 rounded-full bg-sage text-white text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                {idx + 1}
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-bold text-ink">{stage.title}</h4>
                  <span className="text-xs text-ink-muted font-mono">{stage.time}</span>
                </div>
                <p className="text-xs text-ink-muted mt-1 leading-relaxed">
                  {stage.desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

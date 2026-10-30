import React, { useState, useEffect } from "react";
import {
  ClipboardList,
  Clock,
  MessageSquare,
  Info,
} from "lucide-react";
import { useObserverStore } from "@/store/useObserverStore";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

export const CheckInsScreen: React.FC = () => {
  const {
    htCheckins,
    recordHtCheckin,
    fetchHtCheckins,
  } = useObserverStore();

  const [energy, setEnergy] = useState<number>(3);
  const [effort, setEffort] = useState<number>(3);
  const [taskDifficulty, setTaskDifficulty] = useState<number>(3);
  const [feelingStuck, setFeelingStuck] = useState<boolean>(false);
  const [discomfort, setDiscomfort] = useState<number>(1);
  const [stress, setStress] = useState<number>(2);
  const [sleepQuality, setSleepQuality] = useState<number>(3);
  const [notes, setNotes] = useState<string>("");
  const [submittedFeedback, setSubmittedFeedback] = useState<boolean>(false);

  useEffect(() => {
    fetchHtCheckins();
  }, [fetchHtCheckins]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await recordHtCheckin({
      energy,
      effort,
      task_difficulty: taskDifficulty,
      feeling_stuck: feelingStuck,
      discomfort,
      stress,
      sleep_quality: sleepQuality,
      notes: notes.trim() || undefined,
    });
    setNotes("");
    setSubmittedFeedback(true);
    setTimeout(() => setSubmittedFeedback(false), 3000);
    fetchHtCheckins();
  };

  const renderRatingPills = (
    label: string,
    val: number,
    setVal: (v: number) => void,
    lowLabel: string,
    highLabel: string
  ) => (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs font-semibold text-ink">
        <span>{label}</span>
        <span className="text-ink-muted text-[11px] font-mono">
          {val}/5 ({val <= 2 ? lowLabel : val >= 4 ? highLabel : "Moderate"})
        </span>
      </div>
      <div className="grid grid-cols-5 gap-1.5">
        {[1, 2, 3, 4, 5].map((num) => (
          <button
            key={num}
            type="button"
            onClick={() => setVal(num)}
            className={`py-1.5 rounded-lg border text-xs font-bold transition-all ${
              val === num
                ? "bg-sage text-white border-sage shadow-xs"
                : "bg-white text-ink border-black/10 hover:border-black/20"
            }`}
          >
            {num}
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="max-w-5xl mx-auto py-6 px-4 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-extrabold text-ink flex items-center gap-2">
              <ClipboardList className="w-5 h-5 text-sage" /> User Check-ins &amp; Self-Reported Context
            </h2>
            <Badge variant="default" className="text-[10px] bg-sage text-white">
              Subjective Provenance
            </Badge>
          </div>
          <p className="text-xs text-ink-muted mt-0.5">
            Optional, non-intrusive self-reports clearly differentiated from objective camera measurements.
          </p>
        </div>
      </div>

      {/* Side-by-side comparison & entry grid */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-5">
        {/* Left: Self-Report Entry Form */}
        <div className="md:col-span-7">
          <Card className="p-5 bg-panel border-black/5 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-ink flex items-center gap-1.5">
                <MessageSquare className="w-4 h-4 text-sage" /> Record Optional Check-In
              </h3>
              <span className="text-[10px] text-ink-muted font-mono">Never Required</span>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {renderRatingPills("Perceived Energy", energy, setEnergy, "Exhausted", "Energized")}
                {renderRatingPills("Perceived Effort", effort, setEffort, "Low Effort", "High Effort")}
                {renderRatingPills("Task Difficulty", taskDifficulty, setTaskDifficulty, "Easy", "Overwhelming")}
                {renderRatingPills("Self-Reported Stress", stress, setStress, "Calm", "Very Stressed")}
                {renderRatingPills("Physical Discomfort", discomfort, setDiscomfort, "None", "Severe")}
                {renderRatingPills("Sleep Quality (Last Night)", sleepQuality, setSleepQuality, "Poor", "Restful")}
              </div>

              {/* Feeling Stuck Binary Toggle */}
              <div className="p-3 rounded-xl bg-ivory border border-black/5 flex items-center justify-between">
                <div>
                  <span className="font-bold text-ink">Feeling Stuck or Paralysis?</span>
                  <p className="text-[11px] text-ink-muted">Self-report whether you currently feel blocked on your active task.</p>
                </div>
                <button
                  type="button"
                  onClick={() => setFeelingStuck((s) => !s)}
                  className={`px-3.5 py-1.5 rounded-lg border text-xs font-bold transition-all ${
                    feelingStuck
                      ? "bg-clay text-white border-clay shadow-xs"
                      : "bg-white text-ink border-black/10"
                  }`}
                >
                  {feelingStuck ? "Yes, Stuck" : "No, Unblocked"}
                </button>
              </div>

              {/* Optional Context Note */}
              <div className="space-y-1">
                <label className="font-bold text-ink text-xs">Optional Context Note:</label>
                <textarea
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g. Slept poorly, complex refactor, noisy environment..."
                  className="w-full bg-white border border-black/10 rounded-lg p-2.5 text-xs text-ink placeholder:text-ink-muted focus:outline-none focus:border-sage"
                />
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-[10px] text-ink-muted italic">
                  Self-reports are tagged with `provenance: self_reported`.
                </span>
                <Button size="sm" variant="primary" type="submit" className="h-8 px-4 font-bold text-xs">
                  Submit Check-In
                </Button>
              </div>

              {submittedFeedback && (
                <div className="p-2 rounded-lg bg-sage/10 text-sage border border-sage/30 text-xs text-center font-semibold">
                  Check-in saved and linked to active observation session.
                </div>
              )}
            </form>
          </Card>
        </div>

        {/* Right: Side-by-Side Distinction & History */}
        <div className="md:col-span-5 space-y-4">
          {/* Provenance Separation Notice */}
          <Card className="p-4 bg-panel border-black/5 shadow-xs space-y-2 text-xs">
            <span className="font-bold text-ink flex items-center gap-1.5">
              <Info className="w-4 h-4 text-sage" /> Provenance Separation
            </span>
            <p className="text-[11px] text-ink-muted leading-relaxed">
              Observer strictly isolates <b>objective camera observations</b> (EAR, blink counts, head kinematics)
              from <b>subjective self-reports</b> (perceived stress, effort). Associations between feeling stuck and
              interaction slowdowns are descriptive and do not imply medical causation.
            </p>
          </Card>

          {/* Historical Check-ins Log */}
          <Card className="p-4 bg-panel border-black/5 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-ink flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-sage" /> Check-in History
              </span>
              <span className="text-[10px] text-ink-muted font-mono">{htCheckins.length} recorded</span>
            </div>

            {htCheckins.length === 0 ? (
              <div className="text-center py-6 text-xs text-ink-muted space-y-1">
                <p>No check-ins recorded yet.</p>
                <p className="text-[10px]">Use the form to log optional contextual feelings.</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                {htCheckins.map((c) => (
                  <div key={c.checkin_id} className="p-2.5 rounded-lg bg-ivory border border-black/5 text-xs space-y-1">
                    <div className="flex justify-between items-center text-[10px] text-ink-muted font-mono">
                      <span>{new Date(c.timestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                      {c.feeling_stuck && (
                        <span className="bg-clay/10 text-clay border border-clay/20 px-1.5 py-0.5 rounded font-bold">
                          STUCK
                        </span>
                      )}
                    </div>
                    <div className="grid grid-cols-3 gap-1 text-[11px] font-semibold text-ink">
                      <div>Energy: {c.energy ?? "--"}/5</div>
                      <div>Stress: {c.stress ?? "--"}/5</div>
                      <div>Effort: {c.effort ?? "--"}/5</div>
                    </div>
                    {c.notes && <p className="text-[11px] text-ink-muted italic">"{c.notes}"</p>}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};

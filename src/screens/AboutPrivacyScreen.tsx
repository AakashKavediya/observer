import React from "react";
import { ShieldCheck, Lock, EyeOff, Cpu, Heart } from "lucide-react";
import { Card } from "@/components/ui/Card";

export const AboutPrivacyScreen: React.FC = () => {
  return (
    <div className="max-w-2xl mx-auto py-8 px-4 space-y-6">
      <div className="text-center mb-6">
        <div className="w-12 h-12 rounded-2xl bg-sage-pale text-sage mx-auto flex items-center justify-center mb-3">
          <ShieldCheck className="w-7 h-7" aria-hidden="true" />
        </div>
        <h2 className="text-2xl font-bold text-ink">
          Privacy Architecture & Ethics
        </h2>
        <p className="text-sm text-ink-muted mt-1">
          Built for neurodivergent autonomy: privacy by physical design, not just policy.
        </p>
      </div>

      {/* Primary Ethical Principle */}
      <Card variant="highlight" className="border-sage/40">
        <div className="flex items-start gap-3">
          <Heart className="w-5 h-5 text-sage flex-shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <h3 className="text-sm font-bold text-ink">
              Estimates, Never Diagnoses
            </h3>
            <p className="text-xs text-ink-muted mt-1 leading-relaxed">
              Observer provides purely local behavioral estimates to offer timely, optional support. It is not a medical device, mental health diagnostic tool, or clinical measure. No judgmental language (like "lazy", "failed", or productivity streaks) is ever used.
            </p>
          </div>
        </div>
      </Card>

      {/* Core Privacy Pillars */}
      <Card className="space-y-4">
        <h3 className="text-base font-bold text-ink mb-2">
          Strict Offline Privacy Principles
        </h3>

        <div className="flex items-start gap-3 p-3 rounded-lg bg-ivory">
          <Cpu className="w-5 h-5 text-sage flex-shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <h4 className="text-sm font-bold text-ink">100% Local Inference</h4>
            <p className="text-xs text-ink-muted mt-0.5 leading-relaxed">
              Every landmark calculation and state assessment is computed directly on your computer's CPU. The application has zero outbound network capabilities, zero cloud dependencies, and zero analytics pings.
            </p>
          </div>
        </div>

        <div className="flex items-start gap-3 p-3 rounded-lg bg-ivory">
          <EyeOff className="w-5 h-5 text-sage flex-shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <h4 className="text-sm font-bold text-ink">Ephemeral Frame Pipeline</h4>
            <p className="text-xs text-ink-muted mt-0.5 leading-relaxed">
              Webcam frames live strictly in temporary memory during landmark extraction and are discarded instantly. Raw images, facial snapshots, or landmark streams are NEVER recorded to disk.
            </p>
          </div>
        </div>

        <div className="flex items-start gap-3 p-3 rounded-lg bg-ivory">
          <Lock className="w-5 h-5 text-sage flex-shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <h4 className="text-sm font-bold text-ink">No Application or Keystroke Spying</h4>
            <p className="text-xs text-ink-muted mt-0.5 leading-relaxed">
              Observer never inspects window titles, URL bars, typed characters, or process names. OS context is limited exclusively to aggregate idle seconds and window switch counters.
            </p>
          </div>
        </div>
      </Card>

      {/* Open Verification */}
      <Card>
        <h3 className="text-sm font-bold text-ink mb-1">
          Open Verification & Auditing
        </h3>
        <p className="text-xs text-ink-muted leading-relaxed">
          The observer engine includes runtime safety guards (`privacy.py`) that verify no network sockets are opened and no temporary media files exist. An offline verification script (`scripts/verify_offline.ps1`) is provided to test the app in a sealed, blocked-network sandbox.
        </p>
      </Card>
    </div>
  );
};

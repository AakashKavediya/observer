import React from "react";
import {
  Activity,
  Sliders,
  Settings,
  PlayCircle,
  ShieldCheck,
  FileText,
  Sparkles,
  Crosshair,
} from "lucide-react";
import { useObserverStore } from "../../store/useObserverStore";
import { t } from "../../i18n";

export const Navigation: React.FC = () => {
  const { activeScreen, setActiveScreen, consentGiven } = useObserverStore();

  const navItems = [
    { id: "home", label: t("nav.home"), icon: Activity },
    { id: "sequencer", label: "Task Sequencer", icon: Sparkles },
    { id: "eye_control", label: "Eye Control (Track 4)", icon: Crosshair },
    { id: "calibration", label: t("nav.calibration"), icon: Sliders },
    { id: "observations", label: "Observations & Reports", icon: FileText },
    { id: "demo", label: t("nav.demo"), icon: PlayCircle },
    { id: "settings", label: t("nav.settings"), icon: Settings },
    { id: "privacy", label: t("nav.privacy"), icon: ShieldCheck },
  ] as const;

  if (!consentGiven) {
    return null;
  }

  return (
    <nav
      role="navigation"
      aria-label="Main Navigation"
      className="bg-panel border-b border-black/5 px-6 flex gap-1 sm:gap-2 overflow-x-auto"
    >
      {navItems.map((item) => {
        const Icon = item.icon;
        const isActive = activeScreen === item.id;
        return (
          <button
            key={item.id}
            onClick={() => setActiveScreen(item.id)}
            role="tab"
            aria-selected={isActive}
            className={`flex items-center gap-2 py-3 px-3.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap focus-visible:outline-2 focus-visible:outline-sage ${
              isActive
                ? "border-sage text-sage font-bold"
                : "border-transparent text-ink-muted hover:text-ink hover:border-black/10"
            }`}
          >
            <Icon className="w-4 h-4" aria-hidden="true" />
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
};

import React from "react";
import {
  Activity,
  Settings,
  PlayCircle,
  FileText,
  Sparkles,
  Crosshair,
  TrendingUp,
  ClipboardList,
  Eye,
} from "lucide-react";
import { useObserverStore } from "../../store/useObserverStore";

export const Navigation: React.FC = () => {
  const { activeScreen, setActiveScreen, consentGiven } = useObserverStore();

  const navItems = [
    { id: "home", label: "Overview", icon: Activity },
    { id: "lab", label: "Facial & Movement Lab", icon: Eye },
    { id: "trends", label: "Trends & Baselines", icon: TrendingUp },
    { id: "observations", label: "Observations & Reports", icon: FileText },
    { id: "checkins", label: "Check-ins", icon: ClipboardList },
    { id: "sequencer", label: "Task Sequencer", icon: Sparkles },
    { id: "eye_control", label: "Assistive Gaze", icon: Crosshair },
    { id: "settings", label: "Settings & Privacy", icon: Settings },
    { id: "demo", label: "Demo Mode", icon: PlayCircle },
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

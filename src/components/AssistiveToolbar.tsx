/**
 * AssistiveToolbar.tsx
 * Adapted from MotionQ-blink (toolbar.py) for Observer.
 * 
 * Provides an accessible, dwell-operated assistive floating toolbar:
 * - Keyboard toggle
 * - Tab Left / Tab Right (window/browser navigation)
 * - Back
 * - Language (EN / HI / MR)
 * - Scroll Up / Scroll Down
 * - Single-Click Mode / Double-Click Mode (mutually exclusive)
 * - Pause / Resume Eye Control
 * - Recenter
 * - Emergency Stop
 * - Dynamic Dwell Target Registration
 */

import React, { useEffect, useRef, useState } from "react";
import { useObserverStore } from "../store/useObserverStore";
import {
  Keyboard,
  ArrowLeft,
  ArrowRight,
  RotateCcw,
  Languages,
  ArrowUp,
  ArrowDown,
  MousePointer,
  Sparkles,
  Pause,
  Play,
  Crosshair,
  OctagonAlert,
  X,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

export const AssistiveToolbar: React.FC = () => {
  const {
    showAssistiveToolbar,
    toggleAssistiveToolbar,
    showVirtualKeyboard,
    toggleVirtualKeyboard,
    keyboardLanguage,
    cycleKeyboardLanguage,
    gazeStatus,
    setMotionQClickMode,
    toggleMotionQClickMode,
    startEyeControl,
    pauseEyeControl,
    resumeEyeControl,
    recenterNeutral,
    emergencyStop,
    registerDwellTarget,
    sendKeyCombo,
    nativeMouseScroll,
  } = useObserverStore();

  const [minimized, setMinimized] = useState(false);
  const toolbarRef = useRef<HTMLDivElement>(null);
  const activeClickMode = gazeStatus?.click_mode ?? null;
  const isPaused = gazeStatus?.paused ?? false;
  const isEnabled = gazeStatus?.enabled ?? false;

  // Dynamic Dwell Target Registration
  useEffect(() => {
    if (!showAssistiveToolbar || minimized) {
      return;
    }

    const timer = setTimeout(() => {
      if (!toolbarRef.current) return;
      const buttons = toolbarRef.current.querySelectorAll<HTMLButtonElement>("[data-dwell-action]");
      
      buttons.forEach((btn) => {
        const rect = btn.getBoundingClientRect();
        const action = btn.getAttribute("data-dwell-action");
        const name = btn.getAttribute("data-dwell-name") || action || "btn";
        
        registerDwellTarget({
          x: Math.round(rect.left),
          y: Math.round(rect.top),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          target_id: `toolbar_${action}`,
          action: action,
          name: name,
          duration_ms: action === "emergency_stop" ? 500 : 800,
        });
      });
    }, 300);

    return () => {
      clearTimeout(timer);
    };
  }, [showAssistiveToolbar, minimized, isPaused, isEnabled, activeClickMode, keyboardLanguage]);

  if (!showAssistiveToolbar) {
    return null;
  }

  const handleAction = async (action: string) => {
    switch (action) {
      case "keyboard":
        toggleVirtualKeyboard();
        break;
      case "tab_left":
        await sendKeyCombo("tab_left");
        break;
      case "tab_right":
        await sendKeyCombo("tab_right");
        break;
      case "back":
        if (showVirtualKeyboard) {
          toggleVirtualKeyboard(false);
        } else if (activeClickMode !== null) {
          await setMotionQClickMode(null);
        } else {
          await sendKeyCombo("browser_back");
        }
        break;
      case "language":
        await cycleKeyboardLanguage();
        break;
      case "scroll_up":
        await nativeMouseScroll(4);
        break;
      case "scroll_down":
        await nativeMouseScroll(-4);
        break;
      case "click_single":
        await toggleMotionQClickMode("single");
        break;
      case "click_double":
        await toggleMotionQClickMode("double");
        break;
      case "pause_resume":
        if (isPaused) {
          await resumeEyeControl();
        } else if (isEnabled) {
          await pauseEyeControl();
        } else {
          await startEyeControl();
        }
        break;
      case "recenter":
        await recenterNeutral();
        break;
      case "emergency_stop":
        await emergencyStop();
        break;
      case "close":
        toggleAssistiveToolbar(false);
        break;
      default:
        break;
    }
  };

  return (
    <div
      ref={toolbarRef}
      className="fixed top-2 left-1/2 -translate-x-1/2 z-50 flex items-center bg-sand-light/95 dark:bg-panel border border-black/10 dark:border-white/10 rounded-2xl shadow-lg backdrop-blur-md px-2.5 py-1.5 transition-all select-none animate-in fade-in slide-in-from-top-2"
      style={{ maxWidth: "98vw" }}
    >
      {/* Minimized toggle button */}
      <button
        onClick={() => setMinimized(!minimized)}
        className="p-1.5 rounded-lg text-ink-muted hover:text-ink hover:bg-black/5 dark:hover:bg-white/5 transition-colors mr-1"
        title={minimized ? "Expand Toolbar" : "Minimize Toolbar"}
      >
        {minimized ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
      </button>

      {minimized ? (
        <span className="text-xs font-bold text-ink px-2 flex items-center gap-1.5">
          <MousePointer className="w-3.5 h-3.5 text-sage" /> MotionQ Toolbar
        </span>
      ) : (
        <div className="flex items-center gap-1 overflow-x-auto py-0.5">
          {/* Virtual Keyboard */}
          <button
            data-dwell-action="keyboard"
            data-dwell-name="Keyboard"
            onClick={() => handleAction("keyboard")}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-medium transition-all ${
              showVirtualKeyboard
                ? "bg-sage text-white shadow-xs font-bold"
                : "bg-ivory dark:bg-black/20 text-ink hover:bg-black/5 border border-black/5"
            }`}
          >
            <Keyboard className="w-3.5 h-3.5" />
            <span>Keyboard</span>
          </button>

          {/* Tab Left */}
          <button
            data-dwell-action="tab_left"
            data-dwell-name="Tab Left"
            onClick={() => handleAction("tab_left")}
            className="flex items-center gap-1 px-2 py-1.5 rounded-xl text-xs bg-ivory dark:bg-black/20 text-ink hover:bg-black/5 border border-black/5 transition-all"
            title="Tab Left (Cmd+Shift+[)"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Tab L</span>
          </button>

          {/* Tab Right */}
          <button
            data-dwell-action="tab_right"
            data-dwell-name="Tab Right"
            onClick={() => handleAction("tab_right")}
            className="flex items-center gap-1 px-2 py-1.5 rounded-xl text-xs bg-ivory dark:bg-black/20 text-ink hover:bg-black/5 border border-black/5 transition-all"
            title="Tab Right (Cmd+Shift+])"
          >
            <span>Tab R</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>

          {/* Back */}
          <button
            data-dwell-action="back"
            data-dwell-name="Back"
            onClick={() => handleAction("back")}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs bg-ivory dark:bg-black/20 text-ink hover:bg-black/5 border border-black/5 transition-all"
            title="Browser Back or Dismiss"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Back</span>
          </button>

          {/* Language Switcher */}
          <button
            data-dwell-action="language"
            data-dwell-name="Language"
            onClick={() => handleAction("language")}
            className="flex items-center gap-1 px-2 py-1.5 rounded-xl text-xs bg-ivory dark:bg-black/20 text-ink hover:bg-black/5 border border-black/5 transition-all"
            title="Cycle Language (EN / HI / MR)"
          >
            <Languages className="w-3.5 h-3.5 text-sage" />
            <span className="font-bold">{keyboardLanguage}</span>
          </button>

          {/* Scroll Up */}
          <button
            data-dwell-action="scroll_up"
            data-dwell-name="Scroll Up"
            onClick={() => handleAction("scroll_up")}
            className="flex items-center gap-1 px-2 py-1.5 rounded-xl text-xs bg-ivory dark:bg-black/20 text-ink hover:bg-black/5 border border-black/5 transition-all"
            title="Scroll Up"
          >
            <ArrowUp className="w-3.5 h-3.5" />
          </button>

          {/* Scroll Down */}
          <button
            data-dwell-action="scroll_down"
            data-dwell-name="Scroll Down"
            onClick={() => handleAction("scroll_down")}
            className="flex items-center gap-1 px-2 py-1.5 rounded-xl text-xs bg-ivory dark:bg-black/20 text-ink hover:bg-black/5 border border-black/5 transition-all"
            title="Scroll Down"
          >
            <ArrowDown className="w-3.5 h-3.5" />
          </button>

          {/* Single Click Mode Toggle */}
          <button
            data-dwell-action="click_single"
            data-dwell-name="Single Click"
            onClick={() => handleAction("click_single")}
            className={`flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium transition-all ${
              activeClickMode === "single"
                ? "bg-[#2e7d32] text-white shadow-xs font-bold"
                : "bg-ivory dark:bg-black/20 text-ink hover:bg-black/5 border border-black/5"
            }`}
            title="Single-Click Mode (dwell anywhere to click)"
          >
            <MousePointer className="w-3.5 h-3.5" />
            <span>Click</span>
          </button>

          {/* Double Click Mode Toggle */}
          <button
            data-dwell-action="click_double"
            data-dwell-name="Double Click"
            onClick={() => handleAction("click_double")}
            className={`flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium transition-all ${
              activeClickMode === "double"
                ? "bg-[#e65100] text-white shadow-xs font-bold"
                : "bg-ivory dark:bg-black/20 text-ink hover:bg-black/5 border border-black/5"
            }`}
            title="Double-Click Mode (dwell anywhere to double-click)"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Dbl Click</span>
          </button>

          {/* Pause / Resume */}
          <button
            data-dwell-action="pause_resume"
            data-dwell-name="Pause Resume"
            onClick={() => handleAction("pause_resume")}
            className="flex items-center gap-1 px-2 py-1.5 rounded-xl text-xs bg-ivory dark:bg-black/20 text-ink hover:bg-black/5 border border-black/5 transition-all"
            title={isPaused ? "Resume Eye Control" : "Pause Eye Control"}
          >
            {isPaused ? <Play className="w-3.5 h-3.5 text-sage" /> : <Pause className="w-3.5 h-3.5 text-terra" />}
          </button>

          {/* Recenter */}
          <button
            data-dwell-action="recenter"
            data-dwell-name="Recenter"
            onClick={() => handleAction("recenter")}
            className="flex items-center gap-1 px-2 py-1.5 rounded-xl text-xs bg-ivory dark:bg-black/20 text-ink hover:bg-black/5 border border-black/5 transition-all"
            title="Recenter Head Reference"
          >
            <Crosshair className="w-3.5 h-3.5" />
          </button>

          {/* Emergency Stop */}
          <button
            data-dwell-action="emergency_stop"
            data-dwell-name="Emergency Stop"
            onClick={() => handleAction("emergency_stop")}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-bold bg-[#c62828] text-white hover:bg-red-700 transition-all shadow-xs"
            title="Emergency Stop (Esc)"
          >
            <OctagonAlert className="w-3.5 h-3.5" />
            <span>Stop</span>
          </button>
        </div>
      )}

      {/* Close button */}
      <button
        onClick={() => toggleAssistiveToolbar(false)}
        className="p-1 rounded-lg text-ink-muted hover:text-ink hover:bg-black/5 dark:hover:bg-white/5 transition-colors ml-1"
        title="Hide Toolbar"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};

import React, { useEffect, useRef } from "react";
import { useObserverStore } from "./store/useObserverStore";
import { Header } from "./components/layout/Header";
import { Navigation } from "./components/layout/Navigation";
import { WelcomeConsentScreen } from "./screens/WelcomeConsentScreen";
import { HomeScreen } from "./screens/HomeScreen";
import { TaskSequencerScreen } from "./screens/TaskSequencerScreen";
import { EyeControlScreen } from "./screens/EyeControlScreen";
import { CalibrationScreen } from "./screens/CalibrationScreen";
import { ObservationsReportsScreen } from "./screens/ObservationsReportsScreen";
import { DemoScreen } from "./screens/DemoScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { AboutPrivacyScreen } from "./screens/AboutPrivacyScreen";
import { VisionInspector } from "./components/inspector/VisionInspector";
import { EngineEvent } from "./types/ipc";
import { listen } from "@tauri-apps/api/event";

export const App: React.FC = () => {
  const { consentGiven, activeScreen, handleIncomingEngineEvent } = useObserverStore();
  const lastInputRecordTs = useRef<number>(0);

  useEffect(() => {
    let active = true;
    let unlistenFn: (() => void) | undefined;

    // Listen for Tauri events emitted by the Rust sidecar bridge
    listen<EngineEvent>("engine://event", (event) => {
      if (active) {
        handleIncomingEngineEvent(event.payload);
      }
    })
      .then((unlisten) => {
        if (!active) {
          unlisten();
        } else {
          unlistenFn = unlisten;
        }
      })
      .catch((err) => {
        console.warn("[Tauri Event Setup Error]", err);
      });

    return () => {
      active = false;
      if (unlistenFn) unlistenFn();
    };
  }, [handleIncomingEngineEvent]);

  // Track in-app user keyboard and pointer activity to update OS idle timers
  useEffect(() => {
    const notifyActivity = (eventType: string) => {
      const now = Date.now();
      if (now - lastInputRecordTs.current < 400) return; // throttle 400ms
      lastInputRecordTs.current = now;

      if (typeof window !== "undefined" && ("__TAURI_INTERNALS__" in window || "__TAURI__" in window)) {
        import("@tauri-apps/api/core").then(({ invoke }) => {
          invoke("record_ui_activity", { eventType }).catch(() => {});
        }).catch(() => {});
      }
    };

    const handleKey = () => notifyActivity("key");
    const handleMouse = () => notifyActivity("mouse");
    const handleScroll = () => notifyActivity("scroll");

    window.addEventListener("keydown", handleKey, { passive: true });
    window.addEventListener("pointerdown", handleMouse, { passive: true });
    window.addEventListener("wheel", handleScroll, { passive: true });

    return () => {
      window.removeEventListener("keydown", handleKey);
      window.removeEventListener("pointerdown", handleMouse);
      window.removeEventListener("wheel", handleScroll);
    };
  }, []);

  return (
    <div className="min-h-screen bg-ivory text-ink flex flex-col font-sans transition-colors duration-200">
      <Header />
      <Navigation />

      <main role="main" className="flex-1 overflow-y-auto">
        {!consentGiven ? (
          <WelcomeConsentScreen />
        ) : (
          <>
            {activeScreen === "home" && <HomeScreen />}
            {activeScreen === "sequencer" && <TaskSequencerScreen />}
            {activeScreen === "eye_control" && <EyeControlScreen />}
            {activeScreen === "calibration" && <CalibrationScreen />}
            {activeScreen === "observations" && <ObservationsReportsScreen />}
            {activeScreen === "demo" && <DemoScreen />}
            {activeScreen === "settings" && <SettingsScreen />}
            {activeScreen === "privacy" && <AboutPrivacyScreen />}
          </>
        )}
      </main>

      {/* Floating Non-Modal Vision Inspector Popup */}
      <VisionInspector />
    </div>
  );
};

export default App;

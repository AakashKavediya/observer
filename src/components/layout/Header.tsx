import React from "react";
import { Eye, Pause, Play } from "lucide-react";
import { useObserverStore } from "../../store/useObserverStore";
import { StatusPill } from "../ui/StatusPill";
import { Button } from "../ui/Button";
import { t } from "../../i18n";

export const Header: React.FC = () => {
  const { status, sendPause, sendResume, openInspector } = useObserverStore();
  const isPaused = status.paused;

  return (
    <header
      role="banner"
      className="bg-panel border-b border-black/5 px-6 py-4 flex flex-wrap items-center justify-between gap-4 shadow-sm"
    >
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-sage-pale flex items-center justify-center text-sage">
          <Eye className="w-6 h-6" aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-ink">
            {t("app.title")}
          </h1>
          <p className="text-xs text-ink-muted hidden sm:block">
            {t("app.subtitle")}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        <Button
          variant="secondary"
          size="sm"
          onClick={openInspector}
          className="bg-sage/10 hover:bg-sage/20 text-sage border border-sage/20"
          aria-label="View what Observer sees"
        >
          <Eye className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
          <span>View what Observer sees</span>
        </Button>

        <StatusPill
          camera={status.camera}
          mode={status.mode}
          calibrating={status.calibrating}
          fps={status.fps}
        />

        <Button
          variant={isPaused ? "primary" : "secondary"}
          size="sm"
          onClick={() => (isPaused ? sendResume() : sendPause())}
          aria-label={isPaused ? t("home.resumeCamera") : t("home.pauseCamera")}
        >
          {isPaused ? (
            <>
              <Play className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
              <span>{t("home.resumeCamera")}</span>
            </>
          ) : (
            <>
              <Pause className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
              <span>{t("home.pauseCamera")}</span>
            </>
          )}
        </Button>
      </div>
    </header>
  );
};

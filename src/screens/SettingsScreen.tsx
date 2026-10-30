import React, { useState } from "react";
import {
  Trash2,
  RefreshCw,
} from "lucide-react";
import { useObserverStore } from "@/store/useObserverStore";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { t } from "@/i18n";

export const SettingsScreen: React.FC = () => {
  const { settings, updateSettings, sendDeleteAllData, purgeAllHtData, sendStartCalibration } =
    useObserverStore();

  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteStatus, setDeleteStatus] = useState<string | null>(null);

  const handleSensitivityChange = (val: number) => {
    updateSettings({ sensitivity: val });
  };

  const handleTierChange = (tier: number) => {
    updateSettings({ intervention_tier: tier });
  };

  const handleToggleTheme = () => {
    const nextVal = !settings.high_contrast;
    updateSettings({ high_contrast: nextVal });
    if (nextVal) {
      document.documentElement.setAttribute("data-theme", "high-contrast");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  };

  const handleToggleMotion = () => {
    updateSettings({ reduce_motion: !settings.reduce_motion });
  };

  const handleToggleWindowsStart = () => {
    updateSettings({ start_with_windows: !settings.start_with_windows });
  };

  const handleDeleteData = async () => {
    await sendDeleteAllData();
    await purgeAllHtData();
    setConfirmDelete(false);
    setDeleteStatus("All local calibration, observation records, check-ins, and reports wiped permanently.");
    setTimeout(() => setDeleteStatus(null), 4000);
  };

  return (
    <div className="max-w-2xl mx-auto py-8 px-4 space-y-6">
      <div className="mb-4">
        <h2 className="text-2xl font-bold text-ink">
          {t("settings.heading")}
        </h2>
      </div>

      {/* Intervention Level Tier */}
      <Card>
        <h3 className="text-base font-bold text-ink mb-1">
          {t("settings.tierLabel")}
        </h3>
        <p className="text-xs text-ink-muted mb-4">
          Choose the degree of gentle interaction that feels comfortable to you.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {[
            { tier: 0, label: t("settings.tierOptions.0"), desc: "Silent status monitoring only" },
            { tier: 1, label: t("settings.tierOptions.1"), desc: "Subtle indicator change in status" },
            { tier: 2, label: t("settings.tierOptions.2"), desc: "Gentle validating question (<12 words)" },
            { tier: 3, label: t("settings.tierOptions.3"), desc: "Optional single micro-step offer" },
          ].map((item) => (
            <button
              key={item.tier}
              onClick={() => handleTierChange(item.tier)}
              className={`p-3.5 rounded-xl text-left border transition-all ${
                settings.intervention_tier === item.tier
                  ? "bg-sage-pale/60 border-sage font-bold text-ink"
                  : "bg-ivory border-black/5 hover:border-black/15 text-ink-muted"
              }`}
            >
              <div className="text-sm font-semibold text-ink">{item.label}</div>
              <div className="text-xs text-ink-muted mt-0.5">{item.desc}</div>
            </button>
          ))}
        </div>
      </Card>

      {/* Sensitivity Slider */}
      <Card>
        <div className="flex justify-between items-center mb-1">
          <h3 className="text-base font-bold text-ink">
            {t("settings.sensitivityLabel")}
          </h3>
          <span className="text-xs font-bold text-sage">
            {Math.round((settings.sensitivity ?? 0.65) * 100)}%
          </span>
        </div>
        <p className="text-xs text-ink-muted mb-4">
          {t("settings.sensitivityDesc")}
        </p>
        <input
          type="range"
          min="0.3"
          max="0.9"
          step="0.05"
          value={settings.sensitivity ?? 0.65}
          onChange={(e) => handleSensitivityChange(parseFloat(e.target.value))}
          className="w-full accent-sage cursor-pointer"
          aria-label={t("settings.sensitivityLabel")}
        />
        <div className="flex justify-between text-xs text-ink-muted mt-1.5 font-medium">
          <span>Patient (Requires longer freeze)</span>
          <span>Responsive</span>
        </div>
      </Card>

      {/* Accessibility & Visual Comfort */}
      <Card>
        <h3 className="text-base font-bold text-ink mb-3">
          Visual Comfort & Accessibility
        </h3>
        <div className="space-y-3">
          <label className="flex items-center justify-between p-3 rounded-lg bg-ivory cursor-pointer hover:bg-sage-pale/40 transition-colors">
            <div>
              <span className="text-sm font-medium text-ink">{t("settings.highContrast")}</span>
              <p className="text-xs text-ink-muted">Increases line contrast using the warm palette family</p>
            </div>
            <input
              type="checkbox"
              className="w-4 h-4 accent-sage rounded"
              checked={!!settings.high_contrast}
              onChange={handleToggleTheme}
            />
          </label>
          <label className="flex items-center justify-between p-3 rounded-lg bg-ivory cursor-pointer hover:bg-sage-pale/40 transition-colors">
            <div>
              <span className="text-sm font-medium text-ink">{t("settings.reduceMotion")}</span>
              <p className="text-xs text-ink-muted">Disables all transition animations</p>
            </div>
            <input
              type="checkbox"
              className="w-4 h-4 accent-sage rounded"
              checked={!!settings.reduce_motion}
              onChange={handleToggleMotion}
            />
          </label>
          <label className="flex items-center justify-between p-3 rounded-lg bg-ivory cursor-pointer hover:bg-sage-pale/40 transition-colors">
            <div>
              <span className="text-sm font-medium text-ink">{t("settings.startWithWindows")}</span>
              <p className="text-xs text-ink-muted">Launch silently minimized to tray (off by default)</p>
            </div>
            <input
              type="checkbox"
              className="w-4 h-4 accent-sage rounded"
              checked={!!settings.start_with_windows}
              onChange={handleToggleWindowsStart}
            />
          </label>
        </div>
      </Card>

      {/* Data Management & Danger Zone */}
      <Card className="border border-clay/30">
        <h3 className="text-base font-bold text-clay flex items-center gap-2 mb-2">
          <Trash2 className="w-4 h-4 text-clay" aria-hidden="true" />
          {t("settings.dangerZone")}
        </h3>
        <p className="text-xs text-ink-muted mb-4">
          All baseline weights and preferences exist solely on this computer. You maintain complete control.
        </p>

        {deleteStatus && (
          <div className="p-3 mb-4 rounded-lg bg-sage-pale text-sage text-xs font-semibold">
            {deleteStatus}
          </div>
        )}

        <div className="flex flex-wrap gap-3">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => sendStartCalibration()}
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
            {t("settings.resetCalibration")}
          </Button>

          {!confirmDelete ? (
            <Button
              variant="danger"
              size="sm"
              onClick={() => setConfirmDelete(true)}
            >
              <Trash2 className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
              {t("settings.deleteAllData")}
            </Button>
          ) : (
            <div className="flex items-center gap-2">
              <Button
                variant="danger"
                size="sm"
                onClick={handleDeleteData}
              >
                Confirm Delete All
              </Button>
              <Button
                variant="subtle"
                size="sm"
                onClick={() => setConfirmDelete(false)}
              >
                Cancel
              </Button>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
};

//! settings.rs
//! Handles persistence of user preferences and consent.
//! Stored strictly as minimal JSON (numbers, booleans) in local app data.
//! NEVER stores video, landmarks, or personal content.

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppSettings {
    #[serde(default = "default_sensitivity")]
    pub sensitivity: f64,
    #[serde(default = "default_cooldown")]
    pub cooldown_mins: u32,
    #[serde(default)]
    pub quiet_hours_enabled: bool,
    #[serde(default = "default_quiet_start")]
    pub quiet_hours_start: String,
    #[serde(default = "default_quiet_end")]
    pub quiet_hours_end: String,
    #[serde(default = "default_tier")]
    pub intervention_tier: u32,
    #[serde(default)]
    pub high_contrast: bool,
    #[serde(default)]
    pub reduce_motion: bool,
    #[serde(default)]
    pub start_with_windows: bool,
    #[serde(default)]
    pub consent_given: bool,
}

fn default_sensitivity() -> f64 { 0.65 }
fn default_cooldown() -> u32 { 20 }
fn default_quiet_start() -> String { "22:00".to_string() }
fn default_quiet_end() -> String { "08:00".to_string() }
fn default_tier() -> u32 { 2 }

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            sensitivity: default_sensitivity(),
            cooldown_mins: default_cooldown(),
            quiet_hours_enabled: false,
            quiet_hours_start: default_quiet_start(),
            quiet_hours_end: default_quiet_end(),
            intervention_tier: default_tier(),
            high_contrast: false,
            reduce_motion: false,
            start_with_windows: false,
            consent_given: false,
        }
    }
}

pub struct SettingsManager {
    data_dir: PathBuf,
}

impl SettingsManager {
    pub fn new() -> Self {
        let mut data_dir = dirs::data_local_dir().unwrap_or_else(|| PathBuf::from("."));
        data_dir.push("Observer");
        let _ = fs::create_dir_all(&data_dir);
        Self { data_dir }
    }

    fn settings_path(&self) -> PathBuf {
        self.data_dir.join("settings.json")
    }

    fn baseline_path(&self) -> PathBuf {
        self.data_dir.join("baseline.json")
    }

    pub fn load_settings(&self) -> AppSettings {
        let path = self.settings_path();
        if path.exists() {
            if let Ok(content) = fs::read_to_string(&path) {
                if let Ok(settings) = serde_json::from_str::<AppSettings>(&content) {
                    return settings;
                }
            }
        }
        AppSettings::default()
    }

    pub fn save_settings(&self, settings: &AppSettings) -> Result<(), String> {
        let path = self.settings_path();
        let content = serde_json::to_string_pretty(settings)
            .map_err(|e| format!("Serialization error: {}", e))?;
        fs::write(path, content).map_err(|e| format!("Write error: {}", e))?;
        Ok(())
    }

    /// Completely wipes settings and the calibration baseline.
    pub fn delete_all_data(&self) -> Result<(), String> {
        let _ = fs::remove_file(self.settings_path());
        let _ = fs::remove_file(self.baseline_path());
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_settings() {
        let settings = AppSettings::default();
        assert_eq!(settings.sensitivity, 0.65);
        assert_eq!(settings.cooldown_mins, 20);
        assert_eq!(settings.intervention_tier, 2);
        assert!(!settings.consent_given);
    }

    #[test]
    fn test_save_and_load_settings() {
        let tmp_dir = std::env::temp_dir().join(format!("observer_test_{}", std::process::id()));
        let _ = fs::create_dir_all(&tmp_dir);

        let manager = SettingsManager { data_dir: tmp_dir.clone() };
        let mut settings = AppSettings::default();
        settings.sensitivity = 0.85;
        settings.consent_given = true;

        assert!(manager.save_settings(&settings).is_ok());

        let loaded = manager.load_settings();
        assert_eq!(loaded.sensitivity, 0.85);
        assert!(loaded.consent_given);

        assert!(manager.delete_all_data().is_ok());
        let _ = fs::remove_dir_all(&tmp_dir);
    }
}


"""
MotionQ Assistive Control System - Profile Manager for Observer
Adapted from MotionQ-blink (profile_manager.py)
Copyright (c) 2026 Aakash Kavediya
Licensed under the MIT License. See LICENSE.MotionQ-blink for details.

Profile schema persistence, validation, and migration:
- Stored locally in ~/.observer/profiles/<name>.json
- Zero external uploads.
- Validates JSON structure, handles corrupt files gracefully with safe defaults.
"""

import os
import json
import shutil
from typing import Dict, Any, List, Optional

_PROFILES_DIR = os.path.expanduser("~/.observer/profiles")
_current_profile_name = "default"


def get_profiles_dir() -> str:
    os.makedirs(_PROFILES_DIR, exist_ok=True)
    return _PROFILES_DIR


def set_profiles_dir(custom_path: str) -> None:
    global _PROFILES_DIR
    _PROFILES_DIR = custom_path
    os.makedirs(_PROFILES_DIR, exist_ok=True)


def get_default_profile() -> Dict[str, Any]:
    """Default valid profile data with full schema."""
    return {
        "schema_version": "1.0.0",
        "name": "default",
        "gaze": {
            "calibration_points": [],
            "screen_width": 1920,
            "screen_height": 1080,
            "sensitivity": 3.0,
            "nonlinear_exponent": 1.2,
            "smoothing_factor": 0.7,
            "proximity_radius": 80.0,
            "magnet_radius": 40.0,
            "magnet_force": 0.20,
        },
        "head": {
            "neutral_y": None,
            "tilt_threshold": 20.0,
            "scroll_amount": 30,
            "tilt_frame_threshold": 3,
            "enabled": True,
        },
        "dwell": {
            "duration_ms": 1000,
            "entry_delay_ms": 300,
            "stability_radius": 50,
            "click_cooldown_sec": 1.0,
        },
        "lighting": {
            "brightness_offset": 0.0,
            "contrast_scale": 1.0,
        },
        "language": "EN",
        "preferences": {
            "high_contrast": False,
            "auditory_feedback": True,
            "show_dwell_circle": True,
            "show_toolbar": True,
        },
    }


def _profile_path(profile_name: str) -> str:
    safe_name = "".join(c for c in profile_name if c.isalnum() or c in ("-", "_")).strip()
    if not safe_name:
        safe_name = "default"
    return os.path.join(get_profiles_dir(), f"{safe_name}.json")


def load_profile(profile_name: str = "default") -> Dict[str, Any]:
    """
    Load profile by name.
    If file is missing or corrupted, returns default data and heals file.
    """
    global _current_profile_name
    _current_profile_name = profile_name

    path = _profile_path(profile_name)
    if not os.path.exists(path):
        data = get_default_profile()
        data["name"] = profile_name
        save_profile(profile_name, data)
        return data

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Schema validation & merging with defaults for any missing keys
        defaults = get_default_profile()
        defaults["name"] = profile_name

        for sec, val in defaults.items():
            if sec not in data:
                data[sec] = val
            elif isinstance(val, dict) and isinstance(data[sec], dict):
                for k, v in val.items():
                    if k not in data[sec]:
                        data[sec][k] = v

        return data
    except Exception as e:
        print(f"[ProfileManager] Warning: failed to parse {path} ({e}). Recovering with defaults.")
        data = get_default_profile()
        data["name"] = profile_name
        save_profile(profile_name, data)
        return data


def save_profile(profile_name: str, data: Dict[str, Any]) -> bool:
    """Save profile dictionary to ~/.observer/profiles/<name>.json."""
    try:
        path = _profile_path(profile_name)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # Write to temp file then atomic rename
        temp_path = path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, path)
        return True
    except Exception as e:
        print(f"[ProfileManager] Error saving profile {profile_name}: {e}")
        return False


def list_profiles() -> List[str]:
    """Return sorted list of profile names."""
    d = get_profiles_dir()
    profiles = []
    try:
        for fname in os.listdir(d):
            if fname.endswith(".json"):
                profiles.append(fname[:-5])
    except Exception:
        pass
    if "default" not in profiles:
        profiles.append("default")
    return sorted(list(set(profiles)))


def create_profile(profile_name: str, base_profile: Optional[str] = None) -> bool:
    """Create a new profile. If base_profile given, clones it."""
    path = _profile_path(profile_name)
    if os.path.exists(path):
        return False

    if base_profile:
        base_data = load_profile(base_profile)
    else:
        base_data = get_default_profile()

    base_data["name"] = profile_name
    return save_profile(profile_name, base_data)


def delete_profile(profile_name: str) -> bool:
    """Delete a profile. 'default' profile cannot be deleted (resets to defaults)."""
    if profile_name == "default":
        return reset_profile("default")

    path = _profile_path(profile_name)
    try:
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
    except Exception as e:
        print(f"[ProfileManager] Error deleting {profile_name}: {e}")
        return False


def reset_profile(profile_name: str) -> bool:
    """Reset profile back to clean initial factory defaults."""
    data = get_default_profile()
    data["name"] = profile_name
    return save_profile(profile_name, data)


def update_profile(profile_name: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge updates into profile and save."""
    data = load_profile(profile_name)

    for key, value in updates.items():
        if key in data and isinstance(data[key], dict) and isinstance(value, dict):
            data[key].update(value)
        else:
            data[key] = value

    save_profile(profile_name, data)
    return data


def get_current_profile_name() -> str:
    return _current_profile_name

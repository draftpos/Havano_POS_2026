# =============================================================================
# settings/pharmacy_settings.py  —  Terminal-local pharmacy-mode flag
# =============================================================================
#
# Persists a tiny JSON blob at <app_data>/pharmacy_settings.json that only
# lives on THIS terminal (never synced to the server). Other settings can
# be added later — see load_pharmacy_settings() / save_pharmacy_settings().
#
# Style note: these are plain imperative helpers, not a dataclass, to match
# the surrounding code (see database/db.py _load_settings()).
# =============================================================================

import sys
import json
from pathlib import Path

_FILENAME = "pharmacy_settings.json"

# Default shape — leave room for future keys but do NOT speculate.
_DEFAULTS = {
    "pharmacy_mode": False,
}


def _get_app_data_dir() -> Path:
    """
    Mirrors main.py:get_app_data_dir() and database/db.py:_get_app_data_dir().
    Returns the writable app_data folder that sits next to the .exe (bundled)
    or next to main.py (dev mode).
    """
    if hasattr(sys, "_MEIPASS"):
        # Bundled .exe — parent of sys.executable is the exe folder
        return Path(sys.executable).parent / "app_data"
    # Dev mode — project root is one level above settings/
    return Path(__file__).resolve().parent.parent / "app_data"


def _settings_path() -> Path:
    return _get_app_data_dir() / _FILENAME


# =============================================================================
# PUBLIC
# =============================================================================

def load_pharmacy_settings() -> dict:
    """
    Return the full pharmacy-settings dict, merged over defaults.
    If the file doesn't exist yet, returns the defaults (does NOT create it).
    """
    path = _settings_path()
    if not path.exists():
        return dict(_DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
    except Exception as e:
        print(f"[pharmacy_settings] ⚠️  Load error: {e} — using defaults")
        return dict(_DEFAULTS)

    merged = dict(_DEFAULTS)
    merged.update({k: v for k, v in data.items() if k in _DEFAULTS})
    return merged


def save_pharmacy_settings(settings: dict) -> None:
    """Persist the provided dict (merged over defaults) to disk."""
    if not isinstance(settings, dict):
        raise TypeError("settings must be a dict")

    merged = dict(_DEFAULTS)
    merged.update({k: v for k, v in settings.items() if k in _DEFAULTS})

    path = _settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=4, ensure_ascii=False)
        print(f"[pharmacy_settings] ✅ Saved → pharmacy_mode={merged.get('pharmacy_mode')}")
    except Exception as e:
        print(f"[pharmacy_settings] ❌ Save error: {e}")


def get_pharmacy_mode() -> bool:
    """Return True if pharmacy mode is enabled on this terminal."""
    return bool(load_pharmacy_settings().get("pharmacy_mode", False))


def set_pharmacy_mode(enabled: bool) -> None:
    """Enable or disable pharmacy mode on this terminal."""
    current = load_pharmacy_settings()
    current["pharmacy_mode"] = bool(enabled)
    save_pharmacy_settings(current)

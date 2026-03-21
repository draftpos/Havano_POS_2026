# =============================================================================
# services/site_config.py
#
# Single source of truth for the Frappe base URL.
# Reads "api_url" from app_data/sql_settings.json.
# All other credentials/tokens are handled by company_defaults as before.
#
# Usage:
#   from services.site_config import get_host, get_host_label
# =============================================================================

from __future__ import annotations
import json
import logging
from pathlib import Path

log = logging.getLogger("SiteConfig")

_DEFAULT_HOST  = "https://apk.havano.cloud"
_SETTINGS_FILE = Path("app_data/sql_settings.json")

_cached: str | None = None


def get_host() -> str:
    """Returns the full base URL, no trailing slash e.g. https://apk.havano.cloud"""
    global _cached
    if _cached:
        return _cached
    try:
        if _SETTINGS_FILE.exists():
            data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
            url  = str(data.get("api_url") or "").strip().rstrip("/")
            if url:
                _cached = url
                return url
    except Exception as e:
        log.warning("[site_config] Could not read sql_settings.json: %s", e)
    _cached = _DEFAULT_HOST
    return _DEFAULT_HOST


def get_host_label() -> str:
    """Returns just the domain for display e.g. apk.havano.cloud"""
    return get_host().replace("https://", "").replace("http://", "").rstrip("/")


def invalidate_cache():
    """Call after saving new sql_settings.json so next get_host() re-reads."""
    global _cached
    _cached = None
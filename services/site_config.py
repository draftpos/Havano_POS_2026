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

# =============================================================================
# SERVER CHANGE DETECTION & DB WIPE
# =============================================================================

_LAST_URL_FILE = Path("app_data/last_known_url.txt")

def check_url_changed() -> bool:
    """True if current api_url differs from last saved URL."""
    current = get_host().strip().lower()
    if not _LAST_URL_FILE.exists():
        return False
    try:
        last = _LAST_URL_FILE.read_text(encoding="utf-8").strip().lower()
        return current != last
    except Exception:
        return False

def save_current_url():
    """Save current api_url so check_url_changed() returns False on next run."""
    try:
        _LAST_URL_FILE.write_text(get_host().strip(), encoding="utf-8")
    except Exception as e:
        log.error("[site_config] Could not save current URL: %s", e)

def wipe_database():
    """Drops all application tables to ensure clean sync with a different server."""
    from database.db import get_connection
    conn = get_connection()
    cur  = conn.cursor()
    
    tables = [
        "products", "customers", "users", "sales", "sale_items", 
        "shifts", "shift_rows", "item_prices", "payment_entries",
        "warehouses", "cost_centers", "price_lists", "companies",
        "company_defaults", "customer_groups", "schema_info"
    ]
    
    print("[site_config] Wiping database for fresh server sync...")
    for t in tables:
        try:
            cur.execute(f"IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[{t}]') AND type in (N'U')) DROP TABLE [dbo].[{t}]")
            print(f"  - Dropped table {t}")
        except Exception as e:
            print(f"  ! Error dropping {t}: {e}")
            
    conn.commit()
    conn.close()
    print("[site_config] Database wipe complete.")
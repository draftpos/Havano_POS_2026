# =============================================================================
# database/hardware_settings_db.py
#
# Hybrid hardware-settings persistence layer.
#
#   PRIMARY  → app_data/hardware_settings.json   (your existing flow, untouched)
#   FALLBACK → SQL Server table: workstation_hardware_settings
#              keyed by socket.gethostname() so every workstation is independent
#
# The table is auto-created if it does not exist (migrate() is called on first
# use — same pattern as shift.py).  You never need to run a manual SQL script.
#
# Public API (drop-in replacements for the existing _load_hw / _save_hw):
#   load_hw()  → dict
#   save_hw(data: dict) → None
#   migrate()  → None   (idempotent, safe to call many times)
# =============================================================================

from __future__ import annotations

import json
import logging
import socket
from pathlib import Path

log = logging.getLogger(__name__)

# ── Anchored path — same logic as settings_dialog, always absolute ────────────
import sys as _sys

def _hw_file() -> Path:
    if getattr(_sys, "frozen", False):
        base = Path(_sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent  # database/ → project root
    return base / "app_data" / "hardware_settings.json"

_EMPTY_HW: dict = {"main_printer": "(None)", "kitchen_printing_enabled": False,
                   "pharmacy_label_printer": "(None)", "orders": {}}

# ── Workstation identity ──────────────────────────────────────────────────────
def _hostname() -> str:
    """Return a stable, lowercase workstation name."""
    return socket.gethostname().strip().lower()


# =============================================================================
# DB migration — auto-creates the table once per database
# =============================================================================
def migrate() -> None:
    """
    Idempotent: creates `workstation_hardware_settings` if it does not exist.
    Safe to call on every startup or on first use.
    """
    ddl = """
    IF NOT EXISTS (
        SELECT 1
        FROM   INFORMATION_SCHEMA.TABLES
        WHERE  TABLE_NAME = 'workstation_hardware_settings'
    )
    BEGIN
        CREATE TABLE workstation_hardware_settings (
            workstation   NVARCHAR(120)  NOT NULL PRIMARY KEY,
            settings_json NVARCHAR(MAX)  NOT NULL,
            updated_at    DATETIME2      NOT NULL DEFAULT GETDATE()
        );
    END
    """
    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(ddl)
        conn.commit()
        conn.close()
        log.debug("hardware_settings_db: migrate() OK")
    except Exception as exc:
        # Non-fatal — JSON fallback will still work
        log.warning("hardware_settings_db: migrate() failed: %s", exc)


# =============================================================================
# Load — JSON first, DB fallback
# =============================================================================
def load_hw() -> dict:
    """
    Load hardware settings.

    Priority
    --------
    1. app_data/hardware_settings.json   (fast, local, your existing flow)
    2. workstation_hardware_settings DB  (fallback if file missing / corrupt)
    3. Hard-coded empty defaults          (last resort — app still starts)
    """
    # ── 1. JSON (primary) ────────────────────────────────────────────────────
    data = _load_from_json()
    if data is not None:
        return data

    log.info("hardware_settings_db: JSON missing/corrupt — trying DB fallback")

    # ── 2. DB fallback ───────────────────────────────────────────────────────
    data = _load_from_db()
    if data is not None:
        # Opportunistically restore the JSON so future loads are fast again
        _write_json(data)
        log.info("hardware_settings_db: restored JSON from DB")
        return data

    log.warning("hardware_settings_db: both JSON and DB unavailable — using defaults")

    # ── 3. Hard defaults ─────────────────────────────────────────────────────
    return dict(_EMPTY_HW)


def _load_from_json() -> dict | None:
    try:
        hw_path = _hw_file()
        hw_path.parent.mkdir(parents=True, exist_ok=True)
        if hw_path.exists():
            with open(hw_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and data:
                return data
    except Exception as exc:
        log.warning("hardware_settings_db: JSON read error: %s", exc)
    return None


def _load_from_db() -> dict | None:
    try:
        migrate()  # ensure table exists before querying
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "SELECT settings_json FROM workstation_hardware_settings WHERE workstation = ?",
            (_hostname(),)
        )
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            data = json.loads(row[0])
            if isinstance(data, dict):
                return data
    except Exception as exc:
        log.warning("hardware_settings_db: DB read error: %s", exc)
    return None


# =============================================================================
# Save — JSON always, DB best-effort (never blocks the UI on failure)
# =============================================================================
def save_hw(data: dict) -> None:
    """
    Persist hardware settings.

    • Always writes JSON (your primary flow — unchanged).
    • Also upserts into the DB so the fallback stays fresh.
      A DB error is logged but silently swallowed — the app still works.
    """
    # ── 1. JSON (always) ─────────────────────────────────────────────────────
    json_ok = _write_json(data)

    # ── 2. DB (best-effort) ──────────────────────────────────────────────────
    _upsert_db(data)

    if not json_ok:
        # JSON failed but DB might have saved it — warn but don't crash
        log.error("hardware_settings_db: JSON write failed (DB may have saved a copy)")


def _write_json(data: dict) -> bool:
    """Write data to JSON. Returns True on success."""
    try:
        hw_path = _hw_file()
        hw_path.parent.mkdir(parents=True, exist_ok=True)
        with open(hw_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        return True
    except Exception as exc:
        log.error("hardware_settings_db: JSON write error: %s", exc)
        return False


def _upsert_db(data: dict) -> bool:
    """Upsert workstation row. Returns True on success, False on any error."""
    try:
        migrate()  # ensure table exists
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            """
            MERGE workstation_hardware_settings AS t
            USING (SELECT ? AS ws, ? AS js) AS s
                  ON t.workstation = s.ws
            WHEN MATCHED THEN
                UPDATE SET settings_json = s.js,
                           updated_at    = GETDATE()
            WHEN NOT MATCHED THEN
                INSERT (workstation, settings_json, updated_at)
                VALUES (s.ws, s.js, GETDATE());
            """,
            (_hostname(), json.dumps(data))
        )
        conn.commit()
        conn.close()
        log.debug("hardware_settings_db: DB upsert OK for '%s'", _hostname())
        return True
    except Exception as exc:
        # DB down, network blip, table not yet there — all non-fatal
        log.warning("hardware_settings_db: DB upsert failed: %s", exc)
        return False
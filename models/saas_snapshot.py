# models/saas_snapshot.py
import logging
from datetime import datetime
from database.db import get_connection, fetchone_dict, fetchall_dict

log = logging.getLogger("saas_snapshot")

def ensure_snapshot_tables():
    """Ensure saas_company_defaults_snapshot and mode_audit_log tables exist in database."""
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 1. SaaS Company Defaults Snapshot table
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'saas_company_defaults_snapshot'
            )
            CREATE TABLE saas_company_defaults_snapshot (
                id                         INT IDENTITY(1,1) PRIMARY KEY,
                company_name               NVARCHAR(255) NULL,
                api_key                    NVARCHAR(255) NULL,
                api_secret                 NVARCHAR(MAX) NULL,
                server_api_host            NVARCHAR(255) NULL,
                server_company             NVARCHAR(255) NULL,
                server_warehouse           NVARCHAR(255) NULL,
                server_cost_center         NVARCHAR(255) NULL,
                server_terminal_id         NVARCHAR(255) NULL,
                server_shop_id             NVARCHAR(255) NULL,
                default_price_list_id      NVARCHAR(255) NULL,
                system_mode                NVARCHAR(50) DEFAULT 'saas',
                created_at                 DATETIME DEFAULT GETDATE()
            )
        """)

        # 2. Mode Change Audit Log table
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'mode_audit_log'
            )
            CREATE TABLE mode_audit_log (
                id          INT IDENTITY(1,1) PRIMARY KEY,
                timestamp   DATETIME DEFAULT GETDATE(),
                username    NVARCHAR(255) NULL,
                old_mode    NVARCHAR(50) NULL,
                new_mode    NVARCHAR(50) NULL,
                action      NVARCHAR(100) NULL,
                details     NVARCHAR(MAX) NULL
            )
        """)

        conn.commit()
        conn.close()
    except Exception as e:
        log.warning("[saas_snapshot] Table creation check failed: %s", e)


def take_saas_snapshot_once(username: str = "Admin") -> bool:
    """
    Writes current company_defaults into saas_company_defaults_snapshot ONCE if empty
    and system is in SaaS mode.
    Returns True if snapshot was taken, False if snapshot already existed or failed.
    """
    ensure_snapshot_tables()
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM saas_company_defaults_snapshot")
        cnt = cur.fetchone()[0] or 0

        if cnt > 0:
            conn.close()
            return False

        # Read current company_defaults or fallback to get_defaults()
        row = fetchone_dict(cur, "SELECT TOP 1 * FROM company_defaults")
        if not row:
            from models.company_defaults import get_defaults
            get_defaults()
            row = fetchone_dict(cur, "SELECT TOP 1 * FROM company_defaults") or {}

        mode = str(row.get("system_mode") or "").strip().lower()
        from services.credentials import get_system_mode
        active_mode = (get_system_mode() or mode).strip().lower()

        # Strict check: snapshot NEVER writes anything if mode is NOT saas
        if active_mode != "saas" and mode != "saas":
            conn.close()
            return False

        cur.execute("""
            INSERT INTO saas_company_defaults_snapshot (
                company_name, api_key, api_secret, server_api_host,
                server_company, server_warehouse, server_cost_center,
                server_terminal_id, server_shop_id, default_price_list_id,
                system_mode, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'saas', GETDATE())
        """, (
            row.get("company_name") or "",
            row.get("api_key") or "",
            row.get("api_secret") or "",
            row.get("server_api_host") or "",
            row.get("server_company") or "",
            row.get("server_warehouse") or "",
            row.get("server_cost_center") or "",
            row.get("server_terminal_id") or "",
            row.get("server_shop_id") or "",
            row.get("default_price_list_id") or "",
        ))
        conn.commit()
        conn.close()

        log_mode_action(
            username=username,
            old_mode=row.get("system_mode") or "saas",
            new_mode="saas",
            action="SNAPSHOT_TAKEN",
            details="Initial SaaS company defaults snapshot locked."
        )
        return True
    except Exception as e:
        log.error("[saas_snapshot] Failed to take SaaS snapshot: %s", e)
        return False


def update_or_take_saas_snapshot(username: str = "Admin") -> bool:
    """
    Called when reindexing is executed for SaaS mode:
    Updates or inserts the snapshot table with the active company_defaults settings.
    """
    ensure_snapshot_tables()
    try:
        conn = get_connection()
        cur = conn.cursor()

        row = fetchone_dict(cur, "SELECT TOP 1 * FROM company_defaults")
        if not row:
            from models.company_defaults import get_defaults
            get_defaults()
            row = fetchone_dict(cur, "SELECT TOP 1 * FROM company_defaults") or {}

        mode = str(row.get("system_mode") or "").strip().lower()
        from services.credentials import get_system_mode
        active_mode = (get_system_mode() or mode).strip().lower()

        # Strict check: snapshot NEVER writes anything if mode is NOT saas
        if active_mode != "saas" and mode != "saas":
            conn.close()
            return False

        cur.execute("SELECT COUNT(*) FROM saas_company_defaults_snapshot")
        cnt = cur.fetchone()[0] or 0

        if cnt == 0:
            cur.execute("""
                INSERT INTO saas_company_defaults_snapshot (
                    company_name, api_key, api_secret, server_api_host,
                    server_company, server_warehouse, server_cost_center,
                    server_terminal_id, server_shop_id, default_price_list_id,
                    system_mode, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'saas', GETDATE())
            """, (
                row.get("company_name") or "",
                row.get("api_key") or "",
                row.get("api_secret") or "",
                row.get("server_api_host") or "",
                row.get("server_company") or "",
                row.get("server_warehouse") or "",
                row.get("server_cost_center") or "",
                row.get("server_terminal_id") or "",
                row.get("server_shop_id") or "",
                row.get("default_price_list_id") or "",
            ))
        else:
            cur.execute("""
                UPDATE saas_company_defaults_snapshot
                SET company_name = ?, api_key = ?, api_secret = ?, server_api_host = ?,
                    server_company = ?, server_warehouse = ?, server_cost_center = ?,
                    server_terminal_id = ?, server_shop_id = ?, default_price_list_id = ?,
                    system_mode = 'saas', created_at = GETDATE()
                WHERE id = (SELECT MAX(id) FROM saas_company_defaults_snapshot)
            """, (
                row.get("company_name") or "",
                row.get("api_key") or "",
                row.get("api_secret") or "",
                row.get("server_api_host") or "",
                row.get("server_company") or "",
                row.get("server_warehouse") or "",
                row.get("server_cost_center") or "",
                row.get("server_terminal_id") or "",
                row.get("server_shop_id") or "",
                row.get("default_price_list_id") or "",
            ))
        conn.commit()
        conn.close()

        log_mode_action(
            username=username,
            old_mode="saas",
            new_mode="saas",
            action="REINDEX_SNAPSHOT_UPDATE",
            details="SaaS snapshot table updated via Reindexing."
        )
        return True
    except Exception as e:
        log.error("[saas_snapshot] Failed to update SaaS snapshot: %s", e)
        return False



def restore_saas_defaults_from_snapshot() -> bool:
    """
    Restores company_defaults and sql_settings.json from saas_company_defaults_snapshot
    if in SaaS mode and defaults/config deviated or were overwritten.
    """
    ensure_snapshot_tables()
    try:
        conn = get_connection()
        cur = conn.cursor()

        snap = fetchone_dict(cur, "SELECT TOP 1 * FROM saas_company_defaults_snapshot ORDER BY id DESC")
        if not snap:
            conn.close()
            return False

        cur.execute("""
            UPDATE company_defaults
            SET api_key = ?,
                api_secret = ?,
                server_api_host = ?,
                server_company = ?,
                server_warehouse = ?,
                server_cost_center = ?,
                server_terminal_id = ?,
                server_shop_id = ?,
                default_price_list_id = ?,
                system_mode = 'saas'
            WHERE id = (SELECT MIN(id) FROM company_defaults)
        """, (
            snap.get("api_key") or "",
            snap.get("api_secret") or "",
            snap.get("server_api_host") or "",
            snap.get("server_company") or "",
            snap.get("server_warehouse") or "",
            snap.get("server_cost_center") or "",
            snap.get("server_terminal_id") or "",
            snap.get("server_shop_id") or "",
            snap.get("default_price_list_id") or "",
        ))
        conn.commit()
        conn.close()

        # Rewrite sql_settings.json to saas mode right away
        try:
            from services.credentials import _write_mode_files
            _write_mode_files("saas")
        except Exception as _ex_wm:
            log.warning("[saas_snapshot] Could not sync sql_settings.json: %s", _ex_wm)

        log.info("[saas_snapshot] Restored company defaults and sql_settings.json from SaaS snapshot.")
        return True
    except Exception as e:
        log.error("[saas_snapshot] Restore failed: %s", e)
        return False


def verify_saas_snapshot_lock_on_login() -> bool:
    """
    Called on every login / startup:
    If a SaaS snapshot exists in saas_company_defaults_snapshot, check if company_defaults
    or sql_settings.json has deviated from 'saas'. If so, immediately rewrite both
    company_defaults and sql_settings.json back to 'saas' right away using the locked snapshot!
    """
    ensure_snapshot_tables()
    try:
        conn = get_connection()
        cur = conn.cursor()
        snap = fetchone_dict(cur, "SELECT TOP 1 * FROM saas_company_defaults_snapshot ORDER BY id DESC")
        if not snap:
            conn.close()
            return False

        # Check DB mode
        cur.execute("SELECT TOP 1 system_mode FROM company_defaults WHERE id = (SELECT MIN(id) FROM company_defaults)")
        cd_row = cur.fetchone()
        cd_mode = str(cd_row[0] or "").strip().lower() if cd_row else ""
        conn.close()

        sql_mode = get_sql_settings_mode()

        if cd_mode != "saas" or sql_mode != "saas":
            log.info("[saas_snapshot] Mode deviation detected on login (DB: %s, SQL: %s). Self-healing back to SaaS...", cd_mode, sql_mode)
            restored = restore_saas_defaults_from_snapshot()
            if restored:
                log_mode_action(
                    username="System/Login",
                    old_mode=cd_mode or sql_mode,
                    new_mode="saas",
                    action="LOGIN_SELF_HEAL_SAAS",
                    details=f"Rewrote company_defaults & sql_settings.json to SaaS mode from locked snapshot."
                )
            return True
    except Exception as e:
        log.warning("[saas_snapshot] Login lock verification warning: %s", e)
    return False



def wipe_saas_snapshot(username: str = "Admin") -> bool:
    """Wipes saas_company_defaults_snapshot table when switching modes or reindexing reset."""
    ensure_snapshot_tables()
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM saas_company_defaults_snapshot")
        conn.commit()
        conn.close()

        log_mode_action(
            username=username,
            old_mode="saas",
            new_mode="other",
            action="SNAPSHOT_WIPED",
            details="SaaS snapshot wiped upon mode transition."
        )
        return True
    except Exception as e:
        log.error("[saas_snapshot] Wipe failed: %s", e)
        return False


def get_saas_snapshot_info() -> dict:
    """Returns snapshot status dict."""
    ensure_snapshot_tables()
    try:
        conn = get_connection()
        cur = conn.cursor()
        row = fetchone_dict(cur, "SELECT TOP 1 * FROM saas_company_defaults_snapshot ORDER BY id DESC")
        conn.close()
        if row:
            return {"exists": True, "created_at": str(row.get("created_at") or ""), "api_key": row.get("api_key") or ""}
    except Exception:
        pass
    return {"exists": False, "created_at": "", "api_key": ""}


def log_mode_action(username: str, old_mode: str, new_mode: str, action: str, details: str = ""):
    """Appends entry to mode_audit_log."""
    ensure_snapshot_tables()
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO mode_audit_log (timestamp, username, old_mode, new_mode, action, details)
            VALUES (GETDATE(), ?, ?, ?, ?, ?)
        """, (
            username or "Admin",
            old_mode or "",
            new_mode or "",
            action or "MODE_CHANGE",
            details or ""
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning("[saas_snapshot] Log audit action failed: %s", e)


def get_recent_mode_audit_logs(limit: int = 10) -> list:
    """Returns list of recent mode audit log dicts."""
    ensure_snapshot_tables()
    try:
        conn = get_connection()
        cur = conn.cursor()
        rows = fetchall_dict(cur, f"SELECT TOP {int(limit)} * FROM mode_audit_log ORDER BY id DESC")
        conn.close()
        return rows or []
    except Exception:
        return []


def get_company_defaults_mode() -> str:
    """Reads system_mode from DB company_defaults table."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT TOP 1 system_mode FROM company_defaults WHERE id = (SELECT MIN(id) FROM company_defaults)")
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return str(row[0]).strip().lower()
    except Exception:
        pass
    return "unknown"


def get_saas_snapshot_mode() -> str:
    """Reads system_mode from DB saas_company_defaults_snapshot table."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT TOP 1 system_mode FROM saas_company_defaults_snapshot ORDER BY id DESC")
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return str(row[0]).strip().lower()
    except Exception:
        pass
    return "none"


def get_sql_settings_mode() -> str:
    """Reads system_mode from app_data/sql_settings.json file."""
    try:
        import json, sys, os
        from pathlib import Path
        if hasattr(sys, "_MEIPASS"):
            app_data_dir = Path(sys.executable).parent / "app_data"
        else:
            app_data_dir = Path(os.path.abspath(".")) / "app_data"
        settings_file = app_data_dir / "sql_settings.json"
        if settings_file.exists():
            data = json.loads(settings_file.read_text(encoding="utf-8"))
            if data.get("system_mode"):
                return str(data["system_mode"]).strip().lower()
    except Exception:
        pass
    return "unknown"


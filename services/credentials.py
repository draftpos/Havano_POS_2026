# =============================================================================
# services/credentials.py
#
# Single credential store for all sync daemons.
#
# The token changes every login - so this module:
#   1. On first call, reads whatever is stored in company_defaults (last session)
#   2. After login, the new token is pushed here via set_session()
#   3. Any daemon calling get_credentials() always gets the latest token
#
# Column it reads/writes: api_key + api_secret in company_defaults (id=1)
# =============================================================================

import logging
log = logging.getLogger("credentials")

_session: dict = {}
_loaded_from_db: bool = False   # only read DB once per process


def set_session(api_key: str, api_secret: str, **extra):
    """
    Called after every login (PIN or password).
    Stores in memory AND persists to DB (encrypted in SaaS mode).
    """
    global _loaded_from_db
    k = str(api_key    or "").strip()
    s = str(api_secret or "").strip()
    
    # Ensure in-memory secret is ALWAYS plain text (never raw ciphertext 'enc:...')
    try:
        from utils.crypto import decrypt_secret
        plain_s = decrypt_secret(s)
    except Exception:
        plain_s = s
    
    _session.clear()
    _session["api_key"]    = k
    _session["api_secret"] = plain_s
    _session.update(extra)
    _loaded_from_db = True

    # Persist to DB
    try:
        from database.db import get_connection
        from utils.crypto import encrypt_secret
        conn = get_connection()
        cur  = conn.cursor()
        
        # Determine mode - preserve current system_mode (saas/frappe/odoo)
        mode = extra.get("system_mode") or get_system_mode() or "saas"
        token = extra.get("odoo_token") or ""
        
        # Encrypt api_secret for SaaS mode persistence
        db_secret = encrypt_secret(plain_s) if mode.lower() == "saas" else plain_s
        
        cur.execute("""
            UPDATE company_defaults
            SET    api_key = ?, api_secret = ?, odoo_token = ?, system_mode = ?
            WHERE  id = (SELECT MIN(id) FROM company_defaults)
        """, (k, db_secret, token, mode))
        conn.commit()
        conn.close()
        log.debug("[credentials] Persisted to DB (Mode: %s, Encrypted Secret)", mode)
    except Exception as e:
        log.warning("[credentials] Could not persist to DB: %s", e)

    # Force-lock ERP modules if we are logging into Frappe or Odoo mode
    try:
        current_mode = get_system_mode()
        if current_mode in ("frappe", "odoo"):
            from models.advance_settings import AdvanceSettings
            import os
            from pathlib import Path
            _here = Path(os.path.abspath(__file__)).parent.parent
            _path = str(_here / "settings" / "advance_settings.json")
            
            settings = AdvanceSettings.load_from_file(_path)
            settings.showAppSales = False
            settings.showAppSuppliers = False
            settings.showAppMaintenance = False
            settings.showAppFinance = False
            settings.showAppInventory = False
            settings.showAppExpenses = False
            settings.save_to_file(_path)
            log.debug(f"[credentials] Enforced ERP module lock for {current_mode} mode upon login.")
    except Exception as e:
        log.warning("[credentials] Failed to enforce ERP module lock: %s", e)


def build_auth_header(api_key: str = None, api_secret: str = None) -> str:
    """Returns clean Authorization header value without trailing colons or duplicate prefixes."""
    if api_key is None or api_secret is None:
        k, s = get_credentials()
        api_key = api_key if api_key is not None else k
        api_secret = api_secret if api_secret is not None else s
    
    k = str(api_key or "").strip()
    s = str(api_secret or "").strip()

    if not k:
        return ""

    if k.lower().startswith("token ") or k.lower().startswith("bearer "):
        return k

    if ":" in k:
        return f"token {k}"

    if k and s:
        return f"token {k}:{s}"

    return f"token {k}"


def get_credentials() -> tuple[str, str]:
    """
    Backward compatible getter. Returns (api_key, api_secret).
    """
    creds = get_all_credentials()
    return creds.get("api_key", ""), creds.get("api_secret", "")


def get_all_credentials() -> dict:
    """
    Returns a dict with all available credentials (Frappe + Odoo).
    Loads from DB on first call, decrypting SaaS api_secret in memory.
    """
    global _loaded_from_db

    if not _loaded_from_db:
        _loaded_from_db = True
        try:
            from database.db import get_connection
            from utils.crypto import decrypt_secret
            conn = get_connection()
            cur  = conn.cursor()
            cur.execute("""
                SELECT api_key, api_secret, odoo_token, system_mode
                FROM   company_defaults
                WHERE  id = (SELECT MIN(id) FROM company_defaults)
            """)
            row = cur.fetchone()
            conn.close()
            if row:
                raw_secret = str(row[1] or "").strip()
                _session["api_key"]    = str(row[0] or "").strip()
                _session["api_secret"] = decrypt_secret(raw_secret)
                _session["odoo_token"] = str(row[2] or "").strip()
                _session["system_mode"] = get_system_mode()
                log.debug("[credentials] Loaded from DB (Mode: %s)", _session["system_mode"])
        except Exception as e:
            log.debug("[credentials] DB read error: %s", e)

    return dict(_session)


def get_system_mode() -> str:
    """
    Primary authority for system mode is app_data/sql_settings.json ("system_mode").
    """
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
                mode = str(data["system_mode"]).strip().lower()
                _session["system_mode"] = mode
                return mode
    except Exception as e:
        log.debug("[credentials] Could not read system_mode from sql_settings.json: %s", e)

    if "system_mode" in _session and _session["system_mode"]:
        return str(_session["system_mode"]).strip().lower()

    try:
        from models.advance_settings import AdvanceSettings
        settings = AdvanceSettings.load_from_file()
        if settings.systemModeOverride:
            return settings.systemModeOverride.lower()
    except Exception:
        pass

    return get_all_credentials().get("system_mode", "frappe")


def get_odoo_token() -> str:
    return get_all_credentials().get("odoo_token", "")


def has_credentials() -> bool:
    """Returns True if we have valid auth for the current mode."""
    creds = get_all_credentials()
    mode = str(creds.get("system_mode") or get_system_mode() or "frappe").strip().lower()
    if mode == "odoo":
        return bool(creds.get("api_key") or creds.get("odoo_token") or _session.get("api_key"))
    elif mode == "saas":
        return bool(creds.get("api_key") or _session.get("api_key"))
    return bool(creds.get("api_key") or _session.get("api_key"))


def check_credentials(api_key: str, api_secret: str) -> bool:
    """Check if provided api_key and api_secret are valid for active mode (SaaS allows empty api_secret, Frappe requires both)."""
    mode = str(get_system_mode() or "frappe").strip().lower()
    if mode == "saas":
        return bool(api_key)
    elif mode == "odoo":
        return bool(api_key)
    return bool(api_key and api_secret)


def _db_has_active_data() -> bool:
    """Check if the local SQL Server database exists and has active tables."""
    try:
        from database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
        tbl_count = cur.fetchone()[0] or 0
        conn.close()
        return tbl_count > 0
    except Exception as e:
        log.debug("[credentials] _db_has_active_data check warning: %s", e)
        return False


def _prompt_wipe_confirmation(current_mode: str, new_mode: str, parent=None) -> bool:
    """Prompt the user with a concise confirmation dialog warning that the database will be wiped."""
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance()
        if app:
            new_disp = new_mode.upper()

            msg_box = QMessageBox(parent)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("Switch Mode")
            msg_box.setText(f"<b>Wipe database and switch to {new_disp} mode?</b>")
            msg_box.setInformativeText(
                f"Changing mode will wipe local data to prevent mixing mode data.\n\n"
                f"Proceed with database wipe?"
            )
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.No)
            result = msg_box.exec()
            return result == QMessageBox.Yes
    except Exception as e:
        log.warning("[credentials] Failed to present wipe confirmation dialog: %s", e)
    return True


def clear_session_credentials() -> None:
    """Clear all in-memory cached session credentials and force reload on next access."""
    global _session, _loaded_from_db
    _session.clear()
    _loaded_from_db = False
    log.info("[credentials] Session credentials cleared.")


def _wipe_db_for_mode_switch():
    """Completely drop all database tables and re-run migrations from scratch right away."""
    clear_session_credentials()
    try:
        from database.tenant_reset import drop_all_tables_completely
        summary = drop_all_tables_completely()
        log.info("[credentials] Database dropped completely for mode switch: %s", summary)
    except Exception as e:
        log.error("[credentials] Error during database drop: %s", e)

    try:
        import setup_database
        setup_database.run()
        log.info("[credentials] setup_database.run() completed after database drop.")
    except Exception as e:
        log.error("[credentials] Error during database re-setup after drop: %s", e)

    clear_session_credentials()


def set_system_mode(mode: str, parent=None, confirm_wipe: bool = True) -> bool:
    """
    Single canonical writer for system mode.

    Prompts user and wipes database if mode is changing while a local database exists.
    Returns True if mode was updated, False if cancelled by user.
    """
    new_mode = (mode or "frappe").strip().lower()

    # Determine existing mode from sql_settings.json before updating
    current_mode = ""
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
            current_mode = str(data.get("system_mode") or "").strip().lower()
    except Exception:
        pass

    if not current_mode:
        current_mode = (get_system_mode() or "").strip().lower()

    if current_mode and new_mode != current_mode:
        if _db_has_active_data():
            if confirm_wipe:
                user_confirmed = _prompt_wipe_confirmation(current_mode, new_mode, parent=parent)
                if not user_confirmed:
                    log.info("[credentials] System mode change from %s to %s cancelled by user.", current_mode, new_mode)
                    return False

            log.info("[credentials] Mode switch (%s -> %s) executing database wipe...", current_mode, new_mode)
            _wipe_db_for_mode_switch()

    _write_mode_files(new_mode)
    return True


def _write_mode_files(mode: str) -> None:
    _session["system_mode"] = mode
    log.debug("[credentials] _write_mode_files -> %s", mode)

    # ── 1. sql_settings.json ──────────────────────────────────────────────
    try:
        import json, sys, os
        from pathlib import Path
        if hasattr(sys, "_MEIPASS"):
            app_data_dir = Path(sys.executable).parent / "app_data"
        else:
            app_data_dir = Path(os.path.abspath(".")) / "app_data"
        settings_file = app_data_dir / "sql_settings.json"
        data: dict = {}
        if settings_file.exists():
            try:
                data = json.loads(settings_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        data["system_mode"] = mode
        settings_file.write_text(json.dumps(data, indent=4), encoding="utf-8")
        log.debug("[credentials] sql_settings.json updated -> system_mode=%s", mode)
    except Exception as e:
        log.warning("[credentials] Could not write sql_settings.json: %s", e)

    # ── 2. settings/advance_settings.json (systemModeOverride) ───────────
    try:
        import os
        from pathlib import Path
        _here = Path(os.path.abspath(__file__)).parent.parent  # project root
        _adv_path = str(_here / "settings" / "advance_settings.json")
        from models.advance_settings import AdvanceSettings
        adv = AdvanceSettings.load_from_file(_adv_path)
        adv.systemModeOverride = mode
        adv.save_to_file(_adv_path)
        log.debug("[credentials] advance_settings.json updated -> systemModeOverride=%s", mode)
    except Exception as e:
        log.warning("[credentials] Could not write advance_settings.json: %s", e)

    # ── 3. company_defaults database table ────────────────────────────────
    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("UPDATE company_defaults SET system_mode = ? WHERE id = (SELECT MIN(id) FROM company_defaults)", (mode,))
        conn.commit()
        conn.close()
        log.debug("[credentials] company_defaults table updated -> system_mode=%s", mode)
    except Exception as _ex_cd:
        log.debug("[credentials] company_defaults table system_mode update skipped: %s", _ex_cd)
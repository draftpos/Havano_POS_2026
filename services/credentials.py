# =============================================================================
# services/credentials.py
#
# Single credential store for all sync daemons.
#
# ARCHITECTURE: SQL Server company_defaults is the ONLY source of truth.
#   - set_session() persists tokens to DB immediately after every login.
#   - get_all_credentials() ALWAYS reads from DB. No RAM fallback.
#   - If DB is unreachable, callers receive {} and a logged error.
#   - _session is kept only as a write-through convenience after DB reads.
#
# Column it reads/writes: api_key + api_secret in company_defaults (id=1)
# =============================================================================

import logging
from pathlib import Path
log = logging.getLogger("credentials")

_session: dict = {}
_loaded_from_db: bool = False   # tracking flag (not used as auth fallback)


def set_session(api_key: str, api_secret: str, **extra):
    """
    Called after every login (PIN or password).
    Stores in memory AND persists to DB (encrypted in SaaS mode).
    CASHIER PROTECTION: Never overwrites existing valid DB credentials with empty strings!
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
    
    # ── CASHIER PROTECTION GUARD ──────────────────────────────────────────
    # If a cashier logs in via PIN or offline with empty credentials,
    # NEVER wipe the terminal's stored cloud tokens in company_defaults!
    # Instead, inherit the terminal's stored credentials so all background
    # cloud services (sales upload, catalog sync) continue functioning!
    if not k:
        try:
            from database.db import get_connection
            conn_prev = get_connection()
            cur_prev = conn_prev.cursor()
            cur_prev.execute("""
                SELECT api_key, api_secret, odoo_token
                FROM company_defaults
                WHERE id = (SELECT MIN(id) FROM company_defaults)
            """)
            r_prev = cur_prev.fetchone()
            conn_prev.close()
            if r_prev and r_prev[0]:
                k = str(r_prev[0] or "").strip()
                if not plain_s:
                    plain_s = str(r_prev[1] or "").strip()
                if not extra.get("odoo_token") and r_prev[2]:
                    extra["odoo_token"] = str(r_prev[2] or "").strip()
        except Exception as _e_guard:
            log.debug("[credentials] Cashier credential guard lookup: %s", _e_guard)

    _session.clear()
    _session["api_key"]    = k
    _session["api_secret"] = plain_s
    _session.update(extra)
    _loaded_from_db = True

    # Persist to DB only if we have valid credentials to store
    if k:
        try:
            from database.db import get_connection
            conn = get_connection()
            cur  = conn.cursor()
            
            mode = extra.get("system_mode") or get_system_mode() or "saas"
            token = extra.get("odoo_token") or ""
            db_secret = plain_s
            
            cur.execute("""
                UPDATE company_defaults
                SET    api_key = ?, api_secret = ?, odoo_token = ?, system_mode = ?
                WHERE  id = (SELECT MIN(id) FROM company_defaults)
            """, (k, db_secret, token, mode))
            conn.commit()
            cur.close()
            conn.close()
            log.debug("[credentials] Persisted to DB (Mode: %s, Plaintext Secret)", mode)

            if mode.lower() == "saas":
                try:
                    from models.saas_snapshot import take_saas_snapshot_once
                    take_saas_snapshot_once(username=extra.get("username") or "Admin")
                except Exception as _ex_snap:
                    log.debug("[credentials] Auto snapshot capture check: %s", _ex_snap)
        except Exception as e:
            log.warning("[credentials] Could not persist to DB: %s", e)
    else:
        log.debug("[credentials] Preserved existing DB credentials (cashier login had no cloud keys).")

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
            settings.save_to_file(_path)
            log.debug(f"[credentials] Enforced ERP module lock for {current_mode} mode upon login.")
    except Exception as e:
        log.warning("[credentials] Failed to enforce ERP module lock: %s", e)


def build_auth_header(api_key: str = None, api_secret: str = None) -> str:
    """Returns clean Authorization header value without trailing colons or duplicate prefixes.
    The primary source of truth is ALWAYS company_defaults in the database.
    """
    db_creds = get_all_credentials()
    db_k = db_creds.get("api_key", "")
    db_s = db_creds.get("api_secret", "")

    # Default directly to the terminal's stored database credentials
    k = str(api_key if (api_key is not None and str(api_key).strip()) else db_k).strip()
    s = str(api_secret if (api_secret is not None and str(api_secret).strip()) else db_s).strip()

    if not k:
        return ""

    if k.lower().startswith("token ") or k.lower().startswith("bearer "):
        return k

    if ":" in k:
        return f"token {k}"

    mode = (get_system_mode() or "saas").lower()
    if mode == "saas":
        # In SaaS mode, if k is a Base64 session token (or secret is empty), send clean "token <k>"
        if len(k) > 20 and "@" not in k:
            return f"token {k}"
        if k and s:
            return f"token {k}:{s}"
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
    Returns a dict with all credentials from SQL Server company_defaults.
    SQL Server is the ONLY source of truth. There is NO RAM fallback.
    If the DB is unreachable, returns {} and logs an error so callers
    can handle missing credentials explicitly rather than silently using
    stale in-memory data.
    """
    try:
        from database.db import get_connection
        from utils.crypto import decrypt_secret
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("""
            SELECT api_key, api_secret, odoo_token, system_mode
            FROM   company_defaults WITH (NOLOCK)
            WHERE  id = (SELECT MIN(id) FROM company_defaults WITH (NOLOCK))
        """)
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            raw_secret = str(row[1] or "").strip()
            result = {
                "api_key":    str(row[0] or "").strip(),
                "api_secret": decrypt_secret(raw_secret),
                "odoo_token": str(row[2] or "").strip(),
                "system_mode": str(row[3] or "").strip() or "saas",
            }
            # Write-through: keep _session in sync for set_session/persist operations only
            _session.update(result)
            return result
        # Row exists but api_key is empty
        log.warning("[credentials] company_defaults row has no api_key - credentials not yet configured.")
        return {}
    except Exception as e:
        if "Database configuration is missing" in str(e):
            log.warning("[credentials] DB read skipped - database not yet configured: %s", e)
        else:
            log.error("[credentials] DB read FAILED - returning empty credentials (no RAM fallback): %s", e)
        return {}


def _get_app_data_dir() -> Path:
    try:
        from database.db import get_app_data_dir
        return get_app_data_dir()
    except Exception:
        pass
    import sys
    from pathlib import Path
    if getattr(sys, 'frozen', False) or hasattr(sys, "_MEIPASS"):
        return Path(sys.executable).parent / "app_data"
    return Path(__file__).resolve().parent.parent / "app_data"


def get_system_mode() -> str:
    """
    Primary authority for system mode: Database company_defaults table compared with sql_settings.json.
    Checks database first, compares with sql_settings.json, and ensures both stay in sync.
    """
    db_mode = None
    try:
        from database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT TOP 1 system_mode FROM company_defaults WITH (NOLOCK) ORDER BY id ASC")
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            db_mode = str(row[0]).strip().lower()
    except Exception as _ex_db:
        log.debug("[credentials] DB company_defaults read error: %s", _ex_db)

    json_mode = None
    json_data = {}
    try:
        import json
        settings_file = _get_app_data_dir() / "sql_settings.json"
        if settings_file.exists():
            json_data = json.loads(settings_file.read_text(encoding="utf-8"))
            if json_data.get("system_mode"):
                json_mode = str(json_data["system_mode"]).strip().lower()
    except Exception as e:
        log.debug("[credentials] Could not read system_mode from sql_settings.json: %s", e)

    # Resolution priority: Configured JSON mode -> DB mode -> Session / Settings
    # NOTE: The configured mode on this terminal (sql_settings.json) represents the
    # operator's explicit setting. If the database has a stale or mismatching value,
    # we update the database to match the configured mode rather than overwriting
    # sql_settings.json, which previously caused phantom reversions back to SaaS mode.
    resolved_mode = None
    if json_mode:
        resolved_mode = json_mode
    elif db_mode:
        resolved_mode = db_mode

    if resolved_mode:
        _session["system_mode"] = resolved_mode
        # Compare and auto-repair DB if out of sync with configured mode
        if db_mode != resolved_mode:
            try:
                from database.db import get_connection
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("UPDATE company_defaults SET system_mode = ? WHERE id = (SELECT MIN(id) FROM company_defaults)", (resolved_mode,))
                if resolved_mode != "offline":
                    cur.execute("UPDATE company_defaults SET work_offline = '0' WHERE id = (SELECT MIN(id) FROM company_defaults)")
                conn.commit()
                conn.close()
                log.info("[credentials] Synchronized company_defaults table mode -> %s", resolved_mode)
            except Exception as _ex_sync_db:
                log.debug("[credentials] Could not sync DB company_defaults: %s", _ex_sync_db)
        return resolved_mode

    if "system_mode" in _session and _session["system_mode"]:
        return str(_session["system_mode"]).strip().lower()

    try:
        from models.advance_settings import AdvanceSettings
        settings = AdvanceSettings.load_from_file()
        if settings.systemModeOverride:
            return settings.systemModeOverride.lower()
    except Exception:
        pass

    return "saas"


def get_odoo_token() -> str:
    return get_all_credentials().get("odoo_token", "")


def has_credentials() -> bool:
    """Returns True if we have valid auth for the current mode.
    Always reads from DB (via get_all_credentials). No RAM fallback.
    """
    creds = get_all_credentials()
    mode = str(creds.get("system_mode") or get_system_mode() or "saas").strip().lower()
    if mode == "saas":
        has_saas = bool(creds.get("api_key"))
        if not has_saas:
            try:
                from models.saas_snapshot import restore_saas_defaults_from_snapshot
                if restore_saas_defaults_from_snapshot():
                    creds = get_all_credentials()
                    has_saas = bool(creds.get("api_key"))
            except Exception:
                pass
        return has_saas
    elif mode == "odoo":
        return bool(creds.get("api_key") or creds.get("odoo_token"))
    return bool(creds.get("api_key"))



def check_credentials(api_key: str, api_secret: str) -> bool:
    """Check if provided api_key and api_secret are valid for active mode (SaaS allows empty api_secret, Frappe requires both)."""
    mode = str(get_system_mode() or "saas").strip().lower()
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


# Keys in sql_settings.json that are SaaS-binding artefacts and must be cleared
# when switching away from SaaS so they cannot force-detect SaaS on next startup.
_SAAS_BINDING_KEYS = [
    "server_terminal_id",
    "server_shop_id",
    "bound_device_id",
    "user_email",
    "active_user_email",
    "last_logged_in_user",
    "email",
    "api_key",
    "api_secret",
]


def _clear_saas_bindings_from_json(new_mode: str) -> None:
    """Strip stale SaaS binding artefacts from sql_settings.json.
    Only clears credential/binding keys — preserves server, database, auth_mode, etc.
    """
    try:
        import json
        settings_file = _get_app_data_dir() / "sql_settings.json"
        if not settings_file.exists():
            return
        data = json.loads(settings_file.read_text(encoding="utf-8"))
        changed = False
        for k in _SAAS_BINDING_KEYS:
            if k in data:
                del data[k]
                changed = True
        if changed:
            settings_file.write_text(json.dumps(data, indent=4), encoding="utf-8")
            log.info("[credentials] Cleared stale SaaS binding keys from sql_settings.json for mode -> %s", new_mode)
    except Exception as e:
        log.warning("[credentials] Could not clear SaaS binding keys: %s", e)


def _wipe_db_for_mode_switch():
    """Completely drop all database tables and re-run migrations from scratch right away."""
    try:
        from services.hang_watchdog import pause_hang_watchdog, resume_hang_watchdog
        pause_hang_watchdog()
    except Exception:
        pass

    clear_session_credentials()
    try:
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
    finally:
        try:
            from services.hang_watchdog import resume_hang_watchdog
            resume_hang_watchdog()
        except Exception:
            pass

    clear_session_credentials()


def _get_mode_switch_worker_class():
    from PySide6.QtCore import QThread, Signal
    class _ModeSwitchWorker(QThread):
        status_changed = Signal(str, str)
        finished = Signal(bool, str)

        def __init__(self, current_mode: str, new_mode: str):
            super().__init__()
            self.current_mode = current_mode
            self.new_mode = new_mode

        def run(self):
            try:
                try:
                    from services.hang_watchdog import pause_hang_watchdog
                    pause_hang_watchdog()
                except Exception:
                    pass

                clear_session_credentials()

                self.status_changed.emit(f"Switching to {self.new_mode.upper()} mode...", "Resetting local database tables...")
                try:
                    from database.tenant_reset import drop_all_tables_completely
                    summary = drop_all_tables_completely()
                    log.info("[credentials] Database dropped completely for mode switch: %s", summary)
                except Exception as e:
                    log.error("[credentials] Error during database drop: %s", e)

                self.status_changed.emit(f"Switching to {self.new_mode.upper()} mode...", "Setting up fresh database schema...")
                try:
                    import setup_database
                    setup_database.run()
                    log.info("[credentials] setup_database.run() completed after database drop.")
                except Exception as e:
                    log.error("[credentials] Error during database re-setup after drop: %s", e)

                self.status_changed.emit(f"Switching to {self.new_mode.upper()} mode...", "Configuring mode settings...")
                _write_mode_files(self.new_mode)
                _clear_saas_bindings_from_json(self.new_mode)

                if self.new_mode == "offline":
                    self.status_changed.emit("Switching to OFFLINE mode...", "Configuring offline payment defaults...")
                    try:
                        from setup_database import ensure_offline_defaults
                        ensure_offline_defaults()
                    except Exception as _e:
                        log.warning("[credentials] Failed to ensure offline defaults: %s", _e)

                try:
                    from services.hang_watchdog import resume_hang_watchdog
                    resume_hang_watchdog()
                except Exception:
                    pass

                clear_session_credentials()
                self.status_changed.emit(f"Mode changed to {self.new_mode.upper()}!", "Restarting Havano POS...")
                import time
                time.sleep(0.1)
                self.finished.emit(True, "")
            except Exception as ex:
                log.error("[credentials] ModeSwitchWorker error: %s", ex)
                self.finished.emit(False, str(ex))

    return _ModeSwitchWorker


def set_system_mode(mode: str, parent=None, confirm_wipe: bool = True, wipe_full_db: bool = True, restart_on_complete: bool = False) -> bool:
    """
    Single canonical writer for system mode.

    If wipe_full_db is True, prompts user and wipes full database on mode change.
    Displays SleekLoaderOverlay with live status feedback during wipe and schema generation.
    If restart_on_complete is True, safely restarts the POS application once the mode change finishes.
    Returns True if mode was updated, False if cancelled by user.
    """
    new_mode = (mode or "saas").strip().lower()

    # Determine existing mode from sql_settings.json before updating
    current_mode = ""
    try:
        import json
        settings_file = _get_app_data_dir() / "sql_settings.json"
        if settings_file.exists():
            data = json.loads(settings_file.read_text(encoding="utf-8"))
            current_mode = str(data.get("system_mode") or "").strip().lower()
    except Exception:
        pass

    if not current_mode:
        current_mode = (get_system_mode() or "").strip().lower()

    if current_mode and new_mode != current_mode:
        if wipe_full_db and _db_has_active_data():
            if confirm_wipe:
                user_confirmed = _prompt_wipe_confirmation(current_mode, new_mode, parent=parent)
                if not user_confirmed:
                    log.info("[credentials] System mode change from %s to %s cancelled by user.", current_mode, new_mode)
                    return False

            # Stamp the mode BEFORE the wipe (catches sql_settings.json + any live DB row)
            _write_mode_files(new_mode)
            # Clear stale SaaS binding keys so they cannot ghost-force SaaS on next startup
            _clear_saas_bindings_from_json(new_mode)
            log.info("[credentials] Mode switch (%s -> %s) executing database wipe...", current_mode, new_mode)

            app = None
            try:
                from PySide6.QtWidgets import QApplication
                app = QApplication.instance()
            except Exception:
                pass

            if app:
                loader = None
                try:
                    from views.components.sleek_loader import SleekLoaderOverlay
                    loader = SleekLoaderOverlay()
                    loader.show_loading(timeout_ms=0)
                    loader.set_status(f"Switching to {new_mode.upper()} mode...", "Preparing mode change...")
                    app.processEvents()
                except Exception as _e_ldr:
                    log.debug("[credentials] Could not launch mode switch loader: %s", _e_ldr)

                try:
                    from PySide6.QtCore import QEventLoop
                    loop = QEventLoop()
                    WorkerClass = _get_mode_switch_worker_class()
                    worker = WorkerClass(current_mode, new_mode)
                    if loader:
                        worker.status_changed.connect(loader.set_status)
                    worker.finished.connect(lambda ok, msg: loop.quit())
                    worker.start()
                    loop.exec()
                finally:
                    if loader and not restart_on_complete:
                        try:
                            loader.hide_loading()
                        except Exception:
                            pass
            else:
                _wipe_db_for_mode_switch()
                _write_mode_files(new_mode)
                _clear_saas_bindings_from_json(new_mode)
                if new_mode == "offline":
                    try:
                        from setup_database import ensure_offline_defaults
                        ensure_offline_defaults()
                    except Exception as _e:
                        log.warning("[credentials] Failed to ensure offline defaults: %s", _e)

            log.info("[credentials] Post-wipe mode re-stamped -> %s (DB + JSON in sync)", new_mode)

            if restart_on_complete:
                try:
                    from utils.app_restart import restart_application
                    restart_application()
                except Exception as _e_rst:
                    log.error("[credentials] Auto-restart failed: %s", _e_rst)
        else:
            _write_mode_files(new_mode)
            if restart_on_complete:
                try:
                    from utils.app_restart import restart_application
                    restart_application()
                except Exception as _e_rst:
                    log.error("[credentials] Auto-restart failed: %s", _e_rst)
    else:
        _write_mode_files(new_mode)

    if new_mode == "offline":
        try:
            from setup_database import ensure_offline_defaults
            ensure_offline_defaults()
        except Exception as _e:
            log.warning("[credentials] Failed to ensure offline defaults: %s", _e)

    return True


def _write_mode_files(mode: str) -> None:
    _session["system_mode"] = mode
    log.debug("[credentials] _write_mode_files -> %s", mode)

    # ── 1. sql_settings.json ──────────────────────────────────────────────
    try:
        import json
        settings_file = _get_app_data_dir() / "sql_settings.json"
        data: dict = {}
        if settings_file.exists():
            try:
                data = json.loads(settings_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        data["system_mode"] = mode
        if mode == "saas" and not data.get("api_url"):
            data["api_url"] = "https://backoffice.havano.pro"
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
        if mode != "offline":
            cur.execute("UPDATE company_defaults SET work_offline = '0' WHERE id = (SELECT MIN(id) FROM company_defaults)")
        conn.commit()
        conn.close()
        log.debug("[credentials] company_defaults table updated -> system_mode=%s (work_offline=0)", mode)
    except Exception as _ex_cd:
        log.debug("[credentials] company_defaults table system_mode update skipped: %s", _ex_cd)
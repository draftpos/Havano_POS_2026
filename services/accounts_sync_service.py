# =============================================================================
# services/accounts_sync_service.py
#
# Compatibility shim - all real sync logic lives in services/sync_service.py.
# This file exists so that any import of:
#   start_accounts_sync_daemon
#   sync_accounts_and_rates
#   sync_exchange_rates
#   sync_gl_accounts
#   sync_modes_of_payment
# from this module continues to work without changes to main_window.py or
# any other caller.
# =============================================================================

from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger("AccountsSync")

# Re-export all sync functions from the canonical location
from services.sync_service import (
    sync_gl_accounts,
    sync_modes_of_payment,
    sync_exchange_rates,
)

SYNC_INTERVAL = 60 * 60   # 1 hour

_sync_lock:   threading.Lock          = threading.Lock()
_sync_thread: threading.Thread | None = None


def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        return "", ""


def _get_host() -> str:
    try:
        from services.site_config import get_host
        return get_host()
    except Exception:
        return ""


def _get_defaults() -> dict:
    try:
        from models.company_defaults import get_defaults
        return get_defaults() or {}
    except Exception:
        return {}


# =============================================================================
# COMBINED SYNC  - callable on-demand from anywhere
# =============================================================================

def sync_accounts_and_rates() -> dict:
    """
    Syncs GL accounts, Modes of Payment, and exchange rates in one call.
    Returns {"accounts": N, "rates": N, "mops": N}.
    """
    result = {"accounts": 0, "rates": 0, "mops": 0}

    from services.credentials import has_credentials, get_system_mode
    if get_system_mode() == "odoo":
        # Odoo handles its own account/rate sync if implemented
        # log.debug("[accounts-sync] Odoo mode - skipping Frappe account sync.")
        return result
        
    if not has_credentials():
        log.warning("[accounts-sync] No credentials - skipping.")
        return result

    api_key, api_secret = _get_credentials()

    host     = _get_host()
    if not host:
        log.info("[accounts-sync] Host URL is blank (offline mode) - skipping.")
        return result
        
    defaults = _get_defaults()
    company  = defaults.get("server_company", "")

    try:
        result["accounts"] = sync_gl_accounts(api_key, api_secret, host, company)
    except Exception as e:
        log.error("[accounts-sync] GL account sync failed: %s", e)

    try:
        result["mops"] = sync_modes_of_payment(api_key, api_secret, host, company)
    except Exception as e:
        log.error("[accounts-sync] MOP sync failed: %s", e)

    # Exchange rates must run AFTER GL accounts so currencies are known
    try:
        result["rates"] = sync_exchange_rates(api_key, api_secret, host)
    except Exception as e:
        log.error("[accounts-sync] Rate sync failed: %s", e)

    log.info(
        "[accounts-sync] [OK] Done - %d GL accounts, %d MOPs, %d rate pair(s).",
        result["accounts"], result["mops"], result["rates"],
    )
    return result


# =============================================================================
# BACKGROUND DAEMON  - started once from main_window.py on startup
# =============================================================================

def _sync_loop():
    global _sync_thread_running
    log.info("[accounts-sync] Daemon started (interval=%d min).", SYNC_INTERVAL // 60)
    _sync_thread_running = True
    while _sync_thread_running:
        if _sync_lock.acquire(blocking=False):
            try:
                sync_accounts_and_rates()
            except Exception as e:
                log.error("[accounts-sync] Cycle error: %s", e)
            finally:
                _sync_lock.release()
        else:
            log.debug("[accounts-sync] Previous sync still running - skipping.")
        time.sleep(SYNC_INTERVAL)

def stop_accounts_sync_daemon() -> None:
    global _sync_thread_running
    _sync_thread_running = False
    log.info("[accounts-sync] Daemon stop requested.")


def start_accounts_sync_daemon() -> threading.Thread:
    """
    Starts the background accounts/rates sync daemon.
    Non-blocking - safe to call from MainWindow.__init__.
    Runs one immediate sync cycle first, then repeats every hour.
    """
    global _sync_thread

    if _sync_thread and _sync_thread.is_alive():
        log.debug("[accounts-sync] Daemon already running.")
        return _sync_thread

    # Run one immediate sync in the daemon thread before entering the loop
    def _loop_with_immediate_first():
        # First cycle runs right away
        if _sync_lock.acquire(blocking=False):
            try:
                sync_accounts_and_rates()
            except Exception as e:
                log.error("[accounts-sync] Initial sync error: %s", e)
            finally:
                _sync_lock.release()
        # Then continue with regular interval
        _sync_loop()

    t = threading.Thread(
        target=_loop_with_immediate_first,
        daemon=True,
        name="AccountsSyncDaemon",
    )
    t.start()
    _sync_thread = t
    log.info("[accounts-sync] Daemon started.")
    return t


# =============================================================================
# DEBUG
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    print("Running one accounts + rates sync...")
    r = sync_accounts_and_rates()
    print(f"\nResult: {r['accounts']} GL accounts, {r['mops']} MOPs, {r['rates']} rate pair(s) synced.")
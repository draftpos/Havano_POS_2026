# =============================================================================
# services/accounts_sync_service.py
#
# Syncs two things from Frappe into local DB:
#   1. GL Accounts  → gl_accounts table
#      API: GET /api/method/havano_pos_integration.api.get_account
#
#   2. Exchange Rates → exchange_rates table
#      API: GET /api/method/erpnext.setup.utils.get_exchange_rate
#           ?from_currency=ZWG&to_currency=USD&transaction_date=YYYY-MM-DD
#
# Runs once on startup then every SYNC_INTERVAL seconds.
# Also callable on-demand: sync_accounts_and_rates()
# =============================================================================

from __future__ import annotations

import json
import logging
import time
import threading
import urllib.request
import urllib.error
import urllib.parse
from datetime import date

log = logging.getLogger("AccountsSync")

SYNC_INTERVAL   = 60 * 60   # 1 hour — rates don't change every minute
REQUEST_TIMEOUT = 30

_sync_lock:   threading.Lock          = threading.Lock()
_sync_thread: threading.Thread | None = None


# =============================================================================
# CREDENTIALS / HOST
# =============================================================================

def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        pass
    return "", ""

from services.site_config import get_host as _get_host

def _get_defaults() -> dict:
    try:
        from models.company_defaults import get_defaults
        return get_defaults() or {}
    except Exception:
        return {}


def _get(url: str, api_key: str, api_secret: str) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {api_key}:{api_secret}")
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
        return json.loads(r.read().decode())


# =============================================================================
# 1. SYNC GL ACCOUNTS
# =============================================================================

def sync_accounts(api_key: str, api_secret: str, host: str) -> int:
    """
    Fetches all GL accounts from Frappe and upserts them locally.
    Returns count of accounts synced.
    """
    print(f"[accounts] Syncing accounts from {host}..., api_key={api_key[:4]}..., api_secret={'*' * len(api_secret)}")
    url = f"{host}/api/method/havano_pos_integration.api.get_account"
    try:
        data     = _get(url, api_key, api_secret)
        accounts = data.get("message", [])
        if not accounts:
            log.info("[accounts] No accounts returned.")
            return 0
    except Exception as e:
        log.error("[accounts] Fetch failed: %s", e)
        return 0

    from models.gl_account import upsert_account
    count = 0
    for a in accounts:
        if not a.get("name"):
            continue
        try:
            upsert_account(a)
            count += 1
        except Exception as e:
            log.error("[accounts] Error upserting %s: %s", a.get("name"), e)

    log.info("[accounts] ✅ %d account(s) synced.", count)
    return count


# =============================================================================
# 2. SYNC EXCHANGE RATES
# =============================================================================

def _get_currencies_to_sync(company_currency: str) -> list[str]:
    """
    Returns list of non-base currencies found in gl_accounts.
    These are the currencies we need rates for.
    """
    try:
        from models.gl_account import get_all_accounts
        accounts = get_all_accounts()
        currencies = {
            a["account_currency"].upper()
            for a in accounts
            if a["account_currency"].upper() != company_currency.upper()
        }
        return list(currencies)
    except Exception:
        return []


def sync_exchange_rates(api_key: str, api_secret: str,
                        host: str, company_currency: str = "USD") -> int:
    """
    For each non-base currency found in gl_accounts, fetch today's
    exchange rate from Frappe and store it locally.
    Returns count of rates synced.
    """
    today      = date.today().isoformat()
    currencies = _get_currencies_to_sync(company_currency)

    if not currencies:
        log.info("[rates] No non-base currencies found in gl_accounts.")
        return 0

    from models.exchange_rate import upsert_rate
    count = 0

    for curr in currencies:
        # Fetch: curr → company_currency  (e.g. ZWG → USD)
        try:
            url = (
                f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
                f"?from_currency={urllib.parse.quote(curr)}"
                f"&to_currency={urllib.parse.quote(company_currency)}"
                f"&transaction_date={today}"
            )
            data = _get(url, api_key, api_secret)
            rate = float(data.get("message") or data.get("result") or 0)

            if rate > 0:
                upsert_rate(curr, company_currency, rate, today)
                # Also store reverse rate for convenience
                upsert_rate(company_currency, curr, round(1 / rate, 8), today)
                count += 1
                log.info("[rates] %s → %s = %.6f", curr, company_currency, rate)
            else:
                log.warning("[rates] Got zero/null rate for %s → %s",
                            curr, company_currency)

        except Exception as e:
            log.error("[rates] Failed for %s → %s: %s", curr, company_currency, e)

    log.info("[rates] ✅ %d rate(s) synced.", count)
    return count


# =============================================================================
# COMBINED SYNC
# =============================================================================

def sync_accounts_and_rates() -> dict:
    """Sync both accounts and rates in one call."""
    result = {"accounts": 0, "rates": 0}

    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("[accounts-sync] No credentials — skipping.")
        return result

    host             = _get_host()
    company_currency = _get_defaults().get("server_company_currency", "USD").strip().upper() or "USD"

    result["accounts"] = sync_accounts(api_key, api_secret, host)
    # Only sync rates after accounts are loaded (we need the currencies list)
    result["rates"]    = sync_exchange_rates(api_key, api_secret, host, company_currency)

    return result


# =============================================================================
# BACKGROUND DAEMON
# =============================================================================

def _sync_loop():
    log.info("[accounts-sync] Daemon started (interval=%dmin).", SYNC_INTERVAL // 60)
    while True:
        if _sync_lock.acquire(blocking=False):
            try:
                sync_accounts_and_rates()
            except Exception as e:
                log.error("[accounts-sync] Cycle error: %s", e)
            finally:
                _sync_lock.release()
        else:
            log.debug("[accounts-sync] Previous sync still running.")
        time.sleep(SYNC_INTERVAL)


def start_accounts_sync_daemon() -> threading.Thread:
    """Non-blocking — safe to call from MainWindow.__init__."""
    global _sync_thread
    if _sync_thread and _sync_thread.is_alive():
        return _sync_thread
    t = threading.Thread(target=_sync_loop, daemon=True, name="AccountsSyncDaemon")
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
    print(f"\nResult: {r['accounts']} accounts, {r['rates']} rates synced.")
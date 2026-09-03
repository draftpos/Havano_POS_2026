# =============================================================================
# services/saas_mop_rates.py
#
# SaaS Mode-of-Payment (MOP) exchange rate cache.
#
# Fetches from:
#   GET {host}/api/method/saas_api.www.api.get_account
#
# Response shape (from API):
#   {
#     "message": [
#       { "id": 1072, "name": "Cash",     "currency": "USD", "exchange_rate": 1.0,  ... },
#       { "id": 1656, "name": "Cash ZIG", "currency": "ZIG", "exchange_rate": 35.0, ... },
#       ...
#     ]
#   }
#
# Stores the full list to:
#   app_data/saas_mop_rates.json
#
# No DB schema changes required.
#
# Public API:
#   fetch_and_cache()          -> list[dict]  (fetches + saves to disk)
#   get_all_rates()            -> list[dict]  (loads from disk; falls back to fetch)
#   get_rate_for_mop(name)     -> float       (exchange_rate for a MOP name, default 1.0)
#   get_rate_for_currency(cur) -> float       (exchange_rate for a currency code, default 1.0)
#   get_mop_map()              -> dict        ({"Cash": {...}, "Cash ZIG": {...}, ...})
# =============================================================================

from __future__ import annotations

import json
import logging
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

log = logging.getLogger("saas_mop_rates")

POLL_INTERVAL_SECONDS = 180   # 3 minutes — aggressive live rate refresh

# ── Poller state (one thread per process) ────────────────────────────────────
import threading as _threading
_poller_lock    = _threading.Lock()
_poller_running = False
_poller_thread: _threading.Thread | None = None

# ── Path helpers ──────────────────────────────────────────────────────────────

def _app_data_dir() -> Path:
    """Returns the app_data directory, same logic as credentials.py."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys.executable).parent / "app_data"
    return Path(os.path.abspath(".")) / "app_data"


def _cache_path() -> Path:
    return _app_data_dir() / "saas_mop_rates.json"


# ── In-memory cache (process-lifetime) ───────────────────────────────────────

_mem_cache: list[dict] = []


# ── Credential helpers ────────────────────────────────────────────────────────

def _get_host_and_creds() -> tuple[str, str, str]:
    """Returns (host, api_key, api_secret) from the existing credentials service."""
    try:
        from services.credentials import get_all_credentials
        creds = get_all_credentials()
        api_key    = creds.get("api_key", "")
        api_secret = creds.get("api_secret", "")
    except Exception:
        api_key = api_secret = ""

    # host from sql_settings.json (same place the upload service reads it)
    host = "https://backoffice.havano.pro"
    try:
        settings_file = _app_data_dir() / "sql_settings.json"
        if settings_file.exists():
            data = json.loads(settings_file.read_text(encoding="utf-8"))
            h = (data.get("server_url") or data.get("host") or "").rstrip("/")
            if h:
                host = h
    except Exception:
        pass

    return host, api_key, api_secret


# ── Core fetch ────────────────────────────────────────────────────────────────

def fetch_and_cache(timeout: int = 15) -> list[dict]:
    """
    Calls the SaaS API, parses the MOP list, writes to disk, updates
    the in-memory cache, syncs the local modes_of_payment DB table,
    and returns the list.

    Safe to call at any point (login, background sync, on-demand).
    """
    global _mem_cache

    host, api_key, api_secret = _get_host_and_creds()
    url = f"{host}/api/method/saas_api.www.api.get_account"

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    from services.credentials import build_auth_header
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    auth_hdr = build_auth_header(api_key, api_secret)
    if auth_hdr:
        req.add_header("Authorization", auth_hdr)

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            pass
        log.warning("[saas_mop_rates] HTTP %s from %s: %s", e.code, url, body)
        return _mem_cache or _load_from_disk()
    except Exception as e:
        log.warning("[saas_mop_rates] Fetch failed (%s): %s", url, e)
        return _mem_cache or _load_from_disk()

    # Parse response
    message = raw.get("message", [])
    if not isinstance(message, list):
        log.warning("[saas_mop_rates] Unexpected response shape: %s", type(message))
        return _mem_cache or _load_from_disk()

    mops: list[dict] = []
    for entry in message:
        if not isinstance(entry, dict):
            continue
        mops.append({
            "id":            entry.get("id"),
            "name":          str(entry.get("name") or "").strip(),
            "account_name":  str(entry.get("account_name") or "").strip(),
            "type":          str(entry.get("type") or "Cash").strip(),
            "currency":      str(entry.get("currency") or "USD").upper().strip(),
            "currency_id":   entry.get("currency_id"),
            "exchange_rate": float(entry.get("exchange_rate") or 1.0),
            "rate":          float(entry.get("rate") or 1.0),
            "inverse_rate":  float(entry.get("inverse_rate") or 1.0),
            "symbol":        str(entry.get("symbol") or "").strip(),
        })

    # ── Save to disk (full replace — stale MOPs purged automatically) ─────────
    try:
        cache_path = _cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps({"mops": mops}, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        log.debug("[saas_mop_rates] Cached %d MOPs to %s", len(mops), cache_path)
    except Exception as e:
        log.warning("[saas_mop_rates] Could not write cache: %s", e)

    _mem_cache = mops

    # ── Sync to local modes_of_payment DB table (no schema changes) ──────────
    if mops:
        _sync_to_db(mops)

    return mops


def _sync_to_db(mops: list[dict]) -> None:
    """
    Upserts every MOP from the API into modes_of_payment (synced_from_api=1),
    then DELETEs any row that was previously API-synced but is no longer
    present in the latest payload.

    Uses only EXISTING columns — zero DB schema changes.
    """
    try:
        from database.db import get_connection
    except Exception as e:
        log.warning("[saas_mop_rates] DB import failed: %s", e)
        return

    api_names = {m["name"] for m in mops if m.get("name")}
    added: list[str]   = []
    updated: list[str] = []
    deleted: list[str] = []

    # ── 1. UPSERT each MOP from the API ──────────────────────────────────────
    for m in mops:
        name     = m["name"]
        currency = m["currency"]
        mop_type = m["type"]
        if not name:
            continue
        try:
            conn = get_connection()
            cur  = conn.cursor()
            cur.execute("SELECT id FROM modes_of_payment WHERE name = ?", (name,))
            row = cur.fetchone()
            conn.close()

            if row:
                conn2 = get_connection()
                cur2  = conn2.cursor()
                cur2.execute("""
                    UPDATE modes_of_payment
                    SET    account_currency = ?,
                           type             = ?,
                           mop_type         = ?,
                           synced_from_api  = 1,
                           enabled          = 1,
                           updated_at       = SYSDATETIME()
                    WHERE  name = ?
                """, (currency, mop_type, mop_type, name))
                conn2.commit()
                conn2.close()
                updated.append(name)
            else:
                conn3 = get_connection()
                cur3  = conn3.cursor()
                cur3.execute("""
                    INSERT INTO modes_of_payment
                        (name, type, mop_type, account_currency,
                         enabled, synced_from_api, display_order)
                    VALUES (?, ?, ?, ?, 1, 1, 0)
                """, (name, mop_type, mop_type, currency))
                conn3.commit()
                conn3.close()
                added.append(name)
        except Exception as e:
            log.warning("[saas_mop_rates] Upsert failed for '%s': %s", name, e)

    # ── 2. Write exchange rates into exchange_rates table ─────────────────────
    # The payment dialog calls models.exchange_rate.get_rate(currency, base_ccy).
    # exchange_rates was empty — populate it from the API payload so the dialog
    # gets the correct rate (e.g. ZIG→USD = 1/35 = 0.02857).
    base_ccy = "USD"
    try:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
        base_ccy = str(d.get("server_company_currency") or "USD").strip().upper()
    except Exception:
        pass

    rates_written: list[str] = []
    try:
        from models.exchange_rate import upsert_rate
        from datetime import date
        today = date.today().isoformat()

        for m in mops:
            currency     = (m.get("currency") or "").strip().upper()
            exchange_rate = float(m.get("exchange_rate") or 1.0)
            if not currency or currency == base_ccy or exchange_rate <= 0:
                continue

            # SaaS rate is "how many base units per 1 foreign unit" (e.g. ZIG→USD = 1/35)
            # exchange_rate from API = 35 means "1 USD = 35 ZIG"
            # So: ZIG→USD = 1/35, USD→ZIG = 35
            rate_foreign_to_base = round(1.0 / exchange_rate, 10)

            # foreign → base  (what payment_dialog uses)
            upsert_rate(currency, base_ccy, rate_foreign_to_base, today)
            # base → foreign  (useful for display / inverse lookups)
            upsert_rate(base_ccy, currency, exchange_rate, today)

            rates_written.append(f"{currency}->{base_ccy}={rate_foreign_to_base:.6f}")
            log.debug("[saas_mop_rates] Exchange rate: %s→%s=%.6f (inv=%.2f)",
                      currency, base_ccy, rate_foreign_to_base, exchange_rate)
    except Exception as e:
        log.warning("[saas_mop_rates] Exchange rate upsert error: %s", e)

    if rates_written:
        print(f"[saas_mop_rates] [FX] Exchange rates written: {', '.join(rates_written)}")

    # ── 3. DELETE stale API-synced rows no longer in the payload ─────────────
    try:
        conn4 = get_connection()
        cur4  = conn4.cursor()
        cur4.execute("SELECT name FROM modes_of_payment WHERE synced_from_api = 1")
        db_api_names = {row[0] for row in cur4.fetchall()}
        conn4.close()

        for name in (db_api_names - api_names):
            try:
                conn5 = get_connection()
                cur5  = conn5.cursor()
                cur5.execute(
                    "DELETE FROM modes_of_payment WHERE name = ? AND synced_from_api = 1",
                    (name,)
                )
                conn5.commit()
                conn5.close()
                deleted.append(name)
                log.info("[saas_mop_rates] Deleted stale MOP '%s' from local DB.", name)
            except Exception as e:
                log.warning("[saas_mop_rates] Delete failed for '%s': %s", name, e)
    except Exception as e:
        log.warning("[saas_mop_rates] Stale-check query failed: %s", e)

    # ── 4. Console summary ────────────────────────────────────────────────────
    parts = []
    if added:
        parts.append(f"[+] Added:   {added}")
    if updated:
        parts.append(f"[~] Updated: {updated}")
    if deleted:
        parts.append(f"[-] Deleted: {deleted}")

    if parts:
        print("[saas_mop_rates] DB sync:\n  " + "\n  ".join(parts))
        log.info("[saas_mop_rates] DB sync - added=%s updated=%s deleted=%s",
                 added, updated, deleted)
    else:
        log.debug("[saas_mop_rates] DB sync - no changes.")


# ── Disk loader ───────────────────────────────────────────────────────────────

def _load_from_disk() -> list[dict]:
    """Reads the JSON cache from disk. Returns [] if missing/corrupt."""
    global _mem_cache
    try:
        cache_path = _cache_path()
        if not cache_path.exists():
            return []
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        mops = data.get("mops", [])
        _mem_cache = mops
        return mops
    except Exception as e:
        log.warning("[saas_mop_rates] Could not read cache: %s", e)
        return []


# ── Public getters ────────────────────────────────────────────────────────────

def get_all_rates(auto_fetch: bool = False) -> list[dict]:
    """
    Returns the full MOP list.

    Priority:  in-memory cache  →  disk cache  →  (optional) live fetch
    Pass auto_fetch=True to trigger a live fetch when no cache is available.
    """
    if _mem_cache:
        return list(_mem_cache)
    mops = _load_from_disk()
    if mops:
        return mops
    if auto_fetch:
        return fetch_and_cache()
    return []


def get_mop_map() -> dict[str, dict]:
    """
    Returns a dict keyed by MOP name, e.g.:
      {
        "Cash":     {"currency": "USD", "exchange_rate": 1.0, ...},
        "Cash ZIG": {"currency": "ZIG", "exchange_rate": 35.0, ...},
      }
    """
    return {m["name"]: m for m in get_all_rates() if m.get("name")}


def get_rate_for_mop(name: str, default: float = 1.0) -> float:
    """
    Returns the exchange_rate for a given MOP name (case-insensitive).
    Falls back to `default` (1.0) if not found.

    Usage:
        rate = get_rate_for_mop("Cash ZIG")   # → 35.0
        rate = get_rate_for_mop("Cash")        # → 1.0
    """
    name_lower = (name or "").strip().lower()
    for m in get_all_rates():
        if m.get("name", "").lower() == name_lower:
            return float(m.get("exchange_rate") or default)
    return default


def get_rate_for_currency(currency_code: str, default: float = 1.0) -> float:
    """
    Returns the exchange_rate for a given currency code (e.g. "ZIG", "USD").
    If multiple MOPs share the same currency the first match wins.
    Falls back to `default` (1.0) if not found.

    Usage:
        rate = get_rate_for_currency("ZIG")   # → 35.0
        rate = get_rate_for_currency("USD")   # → 1.0
    """
    code = (currency_code or "").strip().upper()
    for m in get_all_rates():
        if m.get("currency", "").upper() == code:
            return float(m.get("exchange_rate") or default)
    return default


def get_symbol_for_currency(currency_code: str, default: str = "") -> str:
    """Returns the symbol string for a given currency code."""
    code = (currency_code or "").strip().upper()
    for m in get_all_rates():
        if m.get("currency", "").upper() == code:
            return m.get("symbol") or default
    return default



# ── Background poller (3-minute aggressive refresh) ───────────────────────────

def start_rate_poller() -> None:
    """
    Starts a permanent daemon thread that fetches MOP exchange rates from the
    SaaS API every POLL_INTERVAL_SECONDS (180 s = 3 minutes).

    Safe to call multiple times — only ONE poller thread will ever run per
    process.  Subsequent calls are no-ops if the poller is already running.

    Call this once after a successful SaaS login.
    """
    global _poller_running, _poller_thread

    with _poller_lock:
        if _poller_running and _poller_thread and _poller_thread.is_alive():
            log.debug("[saas_mop_rates] Poller already running — skipping.")
            return
        _poller_running = True

    def _poll_loop():
        global _poller_running
        log.info("[saas_mop_rates] Poller started (interval=%ds).", POLL_INTERVAL_SECONDS)

        while _poller_running:
            try:
                mops = fetch_and_cache()
                log.info(
                    "[saas_mop_rates] ✔ Rates refreshed — %d MOPs | %s",
                    len(mops),
                    ", ".join(
                        f"{m['name']}={m['exchange_rate']} {m['currency']}"
                        for m in mops if m.get("name")
                    )
                )
                print(
                    f"[saas_mop_rates] Rates updated: "
                    + ", ".join(
                        f"{m['name']}={m['exchange_rate']} {m['currency']}"
                        for m in mops if m.get("name")
                    )
                )
            except Exception as exc:
                log.warning("[saas_mop_rates] Poll cycle error: %s", exc)

            # Sleep in small increments so stop_rate_poller() responds fast
            elapsed = 0
            while _poller_running and elapsed < POLL_INTERVAL_SECONDS:
                import time as _t
                _t.sleep(1)
                elapsed += 1

        log.info("[saas_mop_rates] Poller stopped.")

    _poller_thread = _threading.Thread(
        target=_poll_loop,
        daemon=True,
        name="SaasMopRatesPoller"
    )
    _poller_thread.start()


def stop_rate_poller() -> None:
    """Signals the poller loop to exit gracefully (within ~1 s)."""
    global _poller_running
    _poller_running = False
    log.debug("[saas_mop_rates] Poller stop requested.")


def refresh_in_background() -> None:
    """
    Backward-compatible one-shot refresh.
    Also ensures the poller is running so future updates are automatic.
    """
    start_rate_poller()

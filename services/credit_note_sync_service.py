# =============================================================================
# services/credit_note_sync_service.py  —  Push local credit notes → Frappe
# =============================================================================
#
# MULTI-CURRENCY BEHAVIOUR
# ────────────────────────
# The return invoice currency mirrors the ORIGINAL sales invoice currency:
#
#   • All items in USD only          → _build_cn_payload_usd()
#   • All items in ZWD/ZIG only      → _build_cn_payload_local_currency("ZIG")
#   • Mixed (USD + ZWD/ZIG)          → _build_cn_payload_mixed_to_usd()
#
# Each builder is fully self-contained — they share NO branching logic.
# The dispatcher (_build_cn_payload) detects the currency once and calls
# exactly one builder.
#
# Frappe's conversion_rate = 1 / zwd_per_usd  (USD per 1 local-currency unit)
# so that Frappe can recover the USD base amount internally.
#
# Frappe Return Invoice:
#   POST /api/resource/Sales Invoice
#   with  is_return=1, return_against=<original_frappe_ref>, qty=-abs(qty)
# =============================================================================

from __future__ import annotations

import json
import logging
import time
import threading
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, date

log = logging.getLogger("CreditNoteSync")

SYNC_INTERVAL   = 60
REQUEST_TIMEOUT = 30
MAX_PER_MINUTE  = 20
INTER_PUSH_DELAY = 60 / MAX_PER_MINUTE

_LOCAL_CURRENCIES = {"ZWD", "ZIG", "zig", "ZWG", "zwg"}

_thread: threading.Thread | None = None
_lock   = threading.Lock()

_RATE_CACHE: dict[str, float] = {}


# =============================================================================
# CREDENTIALS / DEFAULTS / HOST
# =============================================================================

def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        pass
    try:
        from database.db import get_connection
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
        row = cur.fetchone(); conn.close()
        if row and row[0] and row[1]:
            return row[0], row[1]
    except Exception:
        pass
    import os
    return os.environ.get("HAVANO_API_KEY", ""), os.environ.get("HAVANO_API_SECRET", "")


def _get_defaults() -> dict:
    try:
        from models.company_defaults import get_defaults
        return get_defaults() or {}
    except Exception:
        return {}


def _get_host():
    """Get Frappe host URL using the same method as sync_customers"""
    try:
        from services.site_config import get_host as _gh
        return _gh()
    except Exception:
        # Fallback to database
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT TOP 1 server_api_host FROM company_defaults")
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                host = row[0].strip()
                if host and not host.startswith('http'):
                    host = 'https://' + host
                return host.rstrip('/')
        except Exception:
            pass
        return None
# =============================================================================
# EXCHANGE RATE HELPERS  (identical logic to pos_upload_service)
# =============================================================================

def _get_exchange_rate(
    from_currency: str,
    to_currency: str,
    transaction_date: str,
    api_key: str,
    api_secret: str,
    host: str,
) -> float:
    """
    Fetch live exchange rate from Frappe (from_currency → to_currency).
    Returns 1.0 for same currency.
    Falls back to local exchange_rate model, then 1.0 if all else fails.
    """
    if not from_currency or not to_currency:
        return 1.0
    if from_currency.upper() == to_currency.upper():
        return 1.0

    cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
    if cache_key in _RATE_CACHE:
        return _RATE_CACHE[cache_key]

    try:
        url = (
            f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
            f"?from_currency={urllib.parse.quote(from_currency)}"
            f"&to_currency={urllib.parse.quote(to_currency)}"
            f"&transaction_date={transaction_date}"
        )
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {api_key}:{api_secret}")
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
            data = json.loads(r.read().decode())
            rate = float(data.get("message") or data.get("result") or 0)
            if rate > 0:
                _RATE_CACHE[cache_key] = rate
                log.debug("Rate %s→%s on %s: %.6f",
                          from_currency, to_currency, transaction_date, rate)
                return rate
    except Exception as e:
        log.debug("Exchange rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

    try:
        from models.exchange_rate import get_rate
        rate = get_rate(from_currency, to_currency)
        if rate and rate > 0:
            _RATE_CACHE[cache_key] = float(rate)
            return float(rate)
    except Exception:
        pass

    return 1.0


def _resolve_zwd_per_usd(
    cn: dict,
    api_key: str,
    api_secret: str,
    host: str,
    local_currency: str,
    posting_date: str,
) -> float:
    """
    Resolve local-currency-per-USD (e.g. 30.0).

    Priority:
      1. Stored exchange_rate column on the credit note row
         - If > 1  → already local-per-USD  (e.g. 30)
         - If 0–1  → USD-per-local          (e.g. 0.0333) → invert
      2. Live Frappe: local → USD  (then invert)
      3. Live Frappe: USD → local  (direct)
      4. Fallback 1.0  (logged as warning)
    """
    stored = float(cn.get("exchange_rate") or 0)

    if stored > 1:
        return stored

    if 0 < stored < 1:
        return round(1.0 / stored, 8)

    usd_per_local = _get_exchange_rate(
        local_currency, "USD", posting_date, api_key, api_secret, host
    )
    if usd_per_local > 0 and usd_per_local != 1.0:
        return round(1.0 / usd_per_local, 8)

    local_per_usd = _get_exchange_rate(
        "USD", local_currency, posting_date, api_key, api_secret, host
    )
    if local_per_usd > 0 and local_per_usd != 1.0:
        return local_per_usd

    log.warning(
        "[cn-sync] Could not resolve exchange rate for %s on %s "
        "— defaulting to 1.0 (amounts may be wrong).",
        local_currency, posting_date,
    )
    return 1.0


# =============================================================================
# CURRENCY DETECTION  (mirrors pos_upload_service._detect_invoice_currency)
# =============================================================================

def _detect_cn_currency(cn: dict, items: list[dict]) -> str:
    """
    Determine the single invoice currency for this credit note.

    Uses the credit note's own currency field (which is copied from the
    original sale) plus each item's currency tag.

    Returns one of: "USD", "ZWD", "ZIG"
      • Any mixture → "USD"  (caller normalises to USD)
    """
    cn_currency = (cn.get("currency") or "").strip().upper()

    item_currencies: set[str] = set()
    for it in items:
        ic = (it.get("currency") or "").strip().upper()
        if ic:
            item_currencies.add(ic)

    observed: set[str] = set()
    if cn_currency:
        observed.add(cn_currency)
    observed.update(item_currencies)
    observed.discard("")

    if not observed:
        return "USD"
    if observed == {"ZWD"}:
        return "ZWD"
    if observed <= {"ZIG", "ZWG"}:           # treat ZWG as ZIG family
        return "ZIG"
    if observed == {"USD"}:
        return "USD"

    log.info(
        "[cn-sync] CN %s has mixed currencies %s — will normalise to USD.",
        cn.get("cn_number"), observed,
    )
    return "USD"   # signals "mixed" to the dispatcher


# =============================================================================
# POSTING DATE / TIME  (mirrors _parse_posting_datetime)
# =============================================================================

def _parse_posting_datetime(cn: dict) -> tuple[str, str]:
    """Return (posting_date, posting_time) from the credit note's created_at."""
    raw = cn.get("created_at") or ""
    if isinstance(raw, datetime):
        return raw.strftime("%Y-%m-%d"), raw.strftime("%H:%M:%S")
    s = str(raw).strip()
    posting_date = s[:10] if len(s) >= 10 else datetime.today().strftime("%Y-%m-%d")
    # Try to extract time portion (ISO: 2026-04-15 17:24:31.551...)
    if len(s) >= 19:
        posting_time = s[11:19]
    else:
        posting_time = datetime.now().strftime("%H:%M:%S")
    return posting_date, posting_time


# =============================================================================
# BASE PAYLOAD FIELDS  (mirrors _base_payload_fields)
# =============================================================================

def _base_cn_payload_fields(
    cn: dict,
    defaults: dict,
    posting_date: str,
    posting_time: str,
    currency: str,
    conversion_rate: float,
) -> dict:
    """
    Assemble the non-item fields shared by all three CN builders.
    Items and currency-specific values are injected by each builder.
    """
    company           = defaults.get("server_company",           "")
    warehouse         = defaults.get("server_warehouse",         "")
    cost_center       = defaults.get("server_cost_center",       "")
    taxes_and_charges = defaults.get("server_taxes_and_charges", "")
    walk_in           = (defaults.get("server_walk_in_customer", "").strip() or "Default")
    customer          = (cn.get("customer_name") or "").strip() or walk_in

    payload: dict = {
        "is_return":           1,
        "return_against":      cn["frappe_ref"],
        "customer":            customer,
        "posting_date":        posting_date,
        "posting_time":        posting_time,
        "set_posting_time":    1,
        "currency":            currency,
        "conversion_rate":     conversion_rate,
        "is_pos":              0,
        "update_stock":        0,
        "docstatus":           1,
        "custom_cn_reference": cn.get("cn_number", ""),
    }

    if company:           payload["company"]           = company
    if cost_center:       payload["cost_center"]       = cost_center
    if warehouse:         payload["set_warehouse"]     = warehouse
    if taxes_and_charges: payload["taxes_and_charges"] = taxes_and_charges

    return payload


# =============================================================================
# THREE INDEPENDENT PAYLOAD BUILDERS
# =============================================================================

def _build_cn_payload_usd(
    cn: dict,
    items: list[dict],
    defaults: dict,
) -> dict:
    """
    Build a Frappe return Sales Invoice payload for a PURE USD credit note.

    Rules:
      • currency        = "USD"
      • conversion_rate = 1.0
      • item rate       = price  (already in USD)
      • qty             = -abs(qty)  (Frappe return convention)
    """
    log.debug("[cn-sync] _build_cn_payload_usd  cn=%s", cn.get("cn_number"))

    posting_date, posting_time = _parse_posting_datetime(cn)
    cost_center = defaults.get("server_cost_center", "")

    frappe_items = []
    for item in items:
        item_code = (item.get("part_no") or "").strip()
        qty       = float(item.get("qty", 0))
        rate      = float(item.get("price") or 0)
        if not item_code or qty <= 0:
            continue
        row: dict = {
            "item_code": item_code,
            "qty":       -abs(qty),
            "rate":      rate,
            "uom":       (item.get("uom") or "Nos"),
        }
        if cost_center:
            row["cost_center"] = cost_center
        frappe_items.append(row)

    if not frappe_items:
        log.warning("[cn-sync] _build_cn_payload_usd  CN %s — no valid items.",
                    cn.get("cn_number"))
        return {}

    payload = _base_cn_payload_fields(
        cn, defaults, posting_date, posting_time,
        currency="USD", conversion_rate=1.0,
    )
    payload["items"] = frappe_items
    return payload


def _build_cn_payload_local_currency(
    cn: dict,
    items: list[dict],
    defaults: dict,
    local_currency: str,
    api_key: str,
    api_secret: str,
    host: str,
) -> dict:
    """
    Build a Frappe return Sales Invoice payload for a PURE local-currency
    credit note (all items in ZIG or ZWD).

    Rules:
      • currency        = local_currency  ("ZIG" or "ZWD")
      • conversion_rate = 1 / zwd_per_usd   (USD per 1 local unit)
      • item rate       = price  (already in local currency)
      • qty             = -abs(qty)
    """
    log.debug("[cn-sync] _build_cn_payload_local_currency  cn=%s  currency=%s",
              cn.get("cn_number"), local_currency)

    posting_date, posting_time = _parse_posting_datetime(cn)
    cost_center = defaults.get("server_cost_center", "")

    zwd_per_usd = _resolve_zwd_per_usd(
        cn, api_key, api_secret, host, local_currency, posting_date
    )
    frappe_conversion_rate = round(1.0 / zwd_per_usd, 8)

    log.debug(
        "[cn-sync] CN %s  %s_per_usd=%.6f  frappe_conversion_rate=%.8f",
        cn.get("cn_number"), local_currency, zwd_per_usd, frappe_conversion_rate,
    )

    frappe_items = []
    for item in items:
        item_code = (item.get("part_no") or "").strip()
        qty       = float(item.get("qty", 0))
        rate      = float(item.get("price") or 0)   # already in local currency
        if not item_code or qty <= 0:
            continue
        row: dict = {
            "item_code": item_code,
            "qty":       -abs(qty),
            "rate":      rate,
            "uom":       (item.get("uom") or "Nos"),
        }
        if cost_center:
            row["cost_center"] = cost_center
        frappe_items.append(row)

    if not frappe_items:
        log.warning("[cn-sync] _build_cn_payload_local_currency  CN %s — no valid items.",
                    cn.get("cn_number"))
        return {}

    payload = _base_cn_payload_fields(
        cn, defaults, posting_date, posting_time,
        currency=local_currency,
        conversion_rate=frappe_conversion_rate,
    )
    payload["items"] = frappe_items
    return payload


def _build_cn_payload_mixed_to_usd(
    cn: dict,
    items: list[dict],
    defaults: dict,
    api_key: str,
    api_secret: str,
    host: str,
) -> dict:
    """
    Build a Frappe return Sales Invoice payload for a MIXED-currency credit
    note (USD + ZIG/ZWD in the same transaction).

    Rules:
      • Normalise everything to USD
      • currency        = "USD"
      • conversion_rate = 1.0
      • item rate       = price_usd  (convert local items back to USD)
      • qty             = -abs(qty)
    """
    log.debug("[cn-sync] _build_cn_payload_mixed_to_usd  cn=%s — normalising to USD",
              cn.get("cn_number"))

    posting_date, posting_time = _parse_posting_datetime(cn)
    cost_center = defaults.get("server_cost_center", "")

    # Pre-resolve exchange rates for any local currencies in this CN
    local_currencies_seen: set[str] = set()
    for it in items:
        ic = (it.get("currency") or "").strip().upper()
        if ic in _LOCAL_CURRENCIES:
            local_currencies_seen.add(ic)

    rate_map: dict[str, float] = {}
    for lc in local_currencies_seen:
        rate_map[lc] = _resolve_zwd_per_usd(
            cn, api_key, api_secret, host, lc, posting_date
        )
        log.debug("[cn-sync] mixed  %s_per_usd=%.6f", lc, rate_map[lc])

    frappe_items = []
    for item in items:
        item_code     = (item.get("part_no") or "").strip()
        qty           = float(item.get("qty", 0))
        price_usd     = float(item.get("price") or 0)
        item_currency = (item.get("currency") or "USD").strip().upper()
        if not item_code or qty <= 0:
            continue

        # Convert local-currency items to USD
        if item_currency in _LOCAL_CURRENCIES and item_currency in rate_map:
            rate_usd = round(price_usd / rate_map[item_currency], 6)
        else:
            rate_usd = price_usd   # already USD

        row: dict = {
            "item_code": item_code,
            "qty":       -abs(qty),
            "rate":      rate_usd,
            "uom":       (item.get("uom") or "Nos"),
        }
        if cost_center:
            row["cost_center"] = cost_center
        frappe_items.append(row)

    if not frappe_items:
        log.warning("[cn-sync] _build_cn_payload_mixed_to_usd  CN %s — no valid items.",
                    cn.get("cn_number"))
        return {}

    payload = _base_cn_payload_fields(
        cn, defaults, posting_date, posting_time,
        currency="USD", conversion_rate=1.0,
    )
    payload["items"] = frappe_items
    return payload


# =============================================================================
# DISPATCHER  (mirrors pos_upload_service._build_payload)
# =============================================================================

def _build_cn_payload(
    cn: dict,
    items: list[dict],
    defaults: dict,
    api_key: str = "",
    api_secret: str = "",
    host: str = "",
) -> dict:
    """
    Detect the invoice currency and delegate to the appropriate builder.

    Only ONE builder is ever called per credit note — they are fully independent.

      "USD"        → _build_cn_payload_usd            (no exchange rate lookup)
      "ZIG"/"ZWD"  → _build_cn_payload_local_currency (rates resolved)
      mixed        → _build_cn_payload_mixed_to_usd   (normalise everything to USD)
    """
    invoice_currency = _detect_cn_currency(cn, items)

    # Pure local currency
    if invoice_currency in _LOCAL_CURRENCIES:
        return _build_cn_payload_local_currency(
            cn, items, defaults, invoice_currency, api_key, api_secret, host
        )

    if invoice_currency == "USD":
        # Determine whether it is genuinely pure-USD or was mixed→normalised
        cn_currency = (cn.get("currency") or "").strip().upper()
        item_currencies = {
            (it.get("currency") or "").strip().upper()
            for it in items
        }
        item_currencies.discard("")

        is_mixed = bool(item_currencies & _LOCAL_CURRENCIES) or (cn_currency in _LOCAL_CURRENCIES)

        if is_mixed:
            return _build_cn_payload_mixed_to_usd(
                cn, items, defaults, api_key, api_secret, host
            )
        else:
            return _build_cn_payload_usd(cn, items, defaults)

    # Fallback (should never be reached)
    log.error("[cn-sync] Unhandled currency '%s' for CN %s — falling back to USD builder.",
              invoice_currency, cn.get("cn_number"))
    return _build_cn_payload_usd(cn, items, defaults)


# =============================================================================
# PUSH ONE CREDIT NOTE
# =============================================================================

def _push_cn(
    cn: dict,
    api_key: str,
    api_secret: str,
    defaults: dict,
    host: str,
) -> str | bool:
    """Push ONE credit note return invoice to Frappe."""
    cn_num = cn.get("cn_number", str(cn["id"]))

    # Load items from DB
    try:
        from database.db import get_connection
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT part_no, product_name, qty, price, total,
                   tax_amount, tax_rate, tax_type, reason
            FROM credit_note_items
            WHERE credit_note_id = ?
        """, (cn["id"],))
        cols  = [d[0] for d in cur.description]
        items = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        log.error("[cn-sync] Failed to load items for CN %s: %s", cn_num, e)
        return False

    payload = _build_cn_payload(cn, items, defaults, api_key, api_secret, host)
    if not payload:
        log.warning("[cn-sync] CN %s — no valid items, skipping.", cn_num)
        return True   # treat as "done" so it doesn't retry forever

    try:
        body = json.dumps(payload, default=str).encode("utf-8")
    except Exception as e:
        log.error("[cn-sync] JSON serialisation failed for CN %s: %s", cn_num, e)
        return False

    req = urllib.request.Request(
        url=f"{host}/api/resource/Sales%20Invoice",
        data=body,
        method="POST",
        headers={
            "Content-Type":  "application/json",
            "Accept":        "application/json",
            "Authorization": f"token {api_key}:{api_secret}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            name = (json.loads(resp.read()).get("data") or {}).get("name", "")
            log.info("✅ CN %s → Frappe %s  (return_against=%s  currency=%s)",
                     cn_num, name, cn.get("frappe_ref"), payload.get("currency"))
            return name if name else True

    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8", errors="replace"))
            msg = (err.get("exception") or err.get("message") or
                   str(err.get("_server_messages", "")) or f"HTTP {e.code}")
        except Exception:
            msg = f"HTTP {e.code}"

        if e.code == 409:
            log.info("[cn-sync] CN %s already exists on Frappe (409).", cn_num)
            return True

        _PERM_SIGNALS = (
            "negativestockerror", "not marked as sales item",
            "is not a sales item", "return_against",
        )
        if e.code == 417 and any(p in msg.lower() for p in _PERM_SIGNALS):
            log.warning("[cn-sync] CN %s permanent error (won't retry): %s", cn_num, msg)
            return True

        log.error("❌ CN %s  HTTP %s: %s", cn_num, e.code, msg)

        try:
            # 1. Store raw error in credit_notes table
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE credit_notes SET sync_error = ? WHERE id = ?", (msg, cn["id"]))
            conn.commit()
            conn.close()

            # 2. Record to central sync errors
            from services.sync_errors_service import record_error
            record_error(
                "CN", cn_num, msg,
                customer=cn.get("customer_name", ""),
                amount=float(cn.get("total") or 0),
                error_code=f"HTTP {e.code}",
            )
        except Exception as db_e:
            log.warning("[cn-sync] Could not record sync error to DB: %s", db_e)

        return False

    except urllib.error.URLError as e:
        log.warning("[cn-sync] CN %s network error: %s", cn_num, e.reason)
        return False

    except (TimeoutError, OSError) as e:
        # Read timeout — the POST MAY have succeeded on Frappe but we lost the response.
        # DO NOT immediately return False (that would cause a retry → duplicate CN).
        # Instead: attempt a GET to check if a return invoice already exists.
        log.warning("[cn-sync] CN %s — read timeout. Checking if CN already exists on Frappe…", cn_num)
        frappe_ref = cn.get("frappe_ref", "")  # original invoice Frappe name
        if frappe_ref:
            try:
                check_url = (
                    f"{host}/api/resource/Sales%20Invoice"
                    f"?filters=[[\"Sales Invoice\",\"return_against\",\"=\",\"{frappe_ref}\"]]"
                    f"&fields=[\"name\"]&limit=5"
                )
                check_req = urllib.request.Request(
                    check_url,
                    headers={"Authorization": f"token {api_key}:{api_secret}", "Accept": "application/json"},
                )
                with urllib.request.urlopen(check_req, timeout=15) as check_resp:
                    data = json.loads(check_resp.read()).get("data", [])
                    if data:
                        found_name = data[0].get("name", "")
                        log.info("[cn-sync] CN %s already exists on Frappe as %s — marking synced.", cn_num, found_name)
                        return found_name if found_name else True  # treat as success
                    else:
                        log.info("[cn-sync] CN %s not found on Frappe after timeout — safe to retry.", cn_num)
                        return False
            except Exception as check_e:
                log.warning("[cn-sync] CN %s — could not verify on Frappe: %s. Will NOT retry to avoid duplicate.", cn_num, check_e)
                # Cannot confirm either way — mark as uncertain, do NOT retry automatically
                # Set a special status so it shows in the UI but doesn't auto-retry
                try:
                    from database.db import get_connection
                    _conn = get_connection()
                    _conn.execute(
                        "UPDATE credit_notes SET cn_status = 'sync_timeout' WHERE id = ?",
                        (cn["id"],)
                    )
                    _conn.commit(); _conn.close()
                except Exception: pass
                return True  # Return True so unlock_cn doesn't keep it in the retry loop
        return False

    except Exception as e:
        import traceback
        log.error("[cn-sync] CN %s unexpected: %s\n%s", cn_num, e, traceback.format_exc())
        return False


# =============================================================================
# PUBLIC ENTRY POINT
# =============================================================================

def push_unsynced_credit_notes(force: bool = False) -> dict:
    """Push all ready credit notes to Frappe as return Sales Invoices."""
    result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("[cn-sync] No API credentials — skipping sync cycle.")
        return result

    host     = _get_host()
    defaults = _get_defaults()

    try:
        from models.credit_note import get_pending_credit_notes, mark_cn_synced, try_lock_cn, unlock_cn, clear_stale_cn_locks
        pending = get_pending_credit_notes()
    except Exception as e:
        log.error("[cn-sync] DB error reading pending CNs: %s", e)
        return result

    result["total"] = len(pending)
    if not pending:
        log.debug("[cn-sync] No pending credit notes.")
        return result

    # STALE LOCK CLEANUP: mirror pos_upload_service pattern
    try:
        cleared = clear_stale_cn_locks()
        if cleared:
            log.debug("[cn-sync] Cleared %d stale CN locks.", cleared)
    except Exception:
        pass

    log.info("[cn-sync] Starting sync cycle — %d credit note(s) to push.", len(pending))

    for idx, cn in enumerate(pending):
        if idx > 0 and idx % MAX_PER_MINUTE == 0:
            log.info("[cn-sync] Rate-limit pause — waiting 60 s…")
            time.sleep(60)

        if not cn.get("frappe_ref"):
            log.debug("[cn-sync] CN %s has no frappe_ref yet — skipping.",
                      cn.get("cn_number"))
            result["skipped"] += 1
            continue

        # ATOMIC LOCK: Same pattern as try_lock_sale in pos_upload_service
        if not try_lock_cn(cn["id"]):
            log.debug("[cn-sync] Skipping CN %s — already being synced by another thread.",
                      cn.get("cn_number"))
            continue

        try:
            val = _push_cn(cn, api_key, api_secret, defaults, host)

            if val:
                frappe_cn_ref = val if isinstance(val, str) and val not in ("True",) else ""
                try:
                    mark_cn_synced(cn["id"], frappe_cn_ref)
                    result["pushed"] += 1
                except Exception as e:
                    log.error("[cn-sync] mark_cn_synced failed for CN %s: %s",
                               cn.get("cn_number"), e)
                    result["failed"] += 1

                # Link the refund payment entry
                if frappe_cn_ref:
                    try:
                        from services.cn_payment_entry_service import link_cn_payment_to_frappe
                        link_cn_payment_to_frappe(cn.get("cn_number", ""), frappe_cn_ref)
                    except Exception as lpe:
                        log.warning("[cn-sync] link payment failed for %s: %s",
                                    cn.get("cn_number"), lpe)
            else:
                result["failed"] += 1
        except Exception as e:
            log.error("[cn-sync] Sync loop error for CN %s: %s", cn.get("cn_number"), e)
            result["failed"] += 1
        finally:
            # RELENTLESS RETRY: Always release the lock so the CN can be retried
            unlock_cn(cn["id"])

        if idx < len(pending) - 1:
            time.sleep(INTER_PUSH_DELAY)

    log.info("[cn-sync] Done — ✅ %d pushed  ❌ %d failed  ⏭ %d skipped",
             result["pushed"], result["failed"], result["skipped"])
    return result


# =============================================================================
# BACKGROUND DAEMON  (mirrors pos_upload_service UploadWorker / start_upload_thread)
# =============================================================================

def _loop():
    log.info("[cn-sync] Daemon started (interval=%ds, max=%d/min).",
             SYNC_INTERVAL, MAX_PER_MINUTE)
    while True:
        if _lock.acquire(blocking=False):
            try:
                push_unsynced_credit_notes()
            except Exception as e:
                log.error("[cn-sync] Unhandled error in daemon: %s", e)
            finally:
                _lock.release()
        time.sleep(SYNC_INTERVAL)


try:
    from PySide6.QtCore import QObject, QThread

    class _CNSyncWorker(QObject):
        def run(self) -> None:
            log.info("[cn-sync] QThread worker started.")
            while True:
                try:
                    push_unsynced_credit_notes()
                except Exception as exc:
                    log.error("[cn-sync] Unhandled error: %s", exc)
                time.sleep(SYNC_INTERVAL)

    def start_credit_note_sync_daemon() -> QThread:
        """Call once from MainWindow.__init__ alongside the other daemons."""
        global _thread
        if _thread and _thread.isRunning():
            return _thread
        _thread = QThread()
        worker  = _CNSyncWorker()
        worker.moveToThread(_thread)
        _thread.started.connect(worker.run)
        _thread._worker = worker
        _thread.start()
        log.info("[cn-sync] QThread daemon started.")
        return _thread

except ImportError:
    def start_credit_note_sync_daemon() -> threading.Thread:   # type: ignore[misc]
        """Fallback plain-thread version when PySide6 is not available."""
        global _thread
        if _thread and _thread.is_alive():
            return _thread
        _thread = threading.Thread(target=_loop, daemon=True, name="CreditNoteSyncDaemon")
        _thread.start()
        log.info("[cn-sync] Thread daemon started.")
        return _thread
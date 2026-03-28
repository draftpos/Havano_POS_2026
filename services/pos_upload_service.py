# =============================================================================
# services/pos_upload_service.py  —  Push local POS sales → Frappe
# Rate-limited to 20 invoices/minute to stay within Frappe's limits.
# Sends as submitted (docstatus=1). Customer resolved dynamically — no hardcoding.
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

log = logging.getLogger("POSUpload")

UPLOAD_INTERVAL   = 60                      # seconds between full cycles
REQUEST_TIMEOUT   = 30
MAX_PER_MINUTE    = 20                      # Frappe rate limit guard
INTER_PUSH_DELAY  = 60 / MAX_PER_MINUTE    # 3 s between each push


# =============================================================================
# JSON ENCODER  —  handles datetime / date objects from the DB
# =============================================================================

class _DateTimeEncoder(json.JSONEncoder):
    """Converts datetime/date objects to ISO strings before JSON serialisation."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def _dumps(obj) -> str:
    """json.dumps with automatic datetime serialisation."""
    return json.dumps(obj, cls=_DateTimeEncoder)


# =============================================================================
# CREDENTIALS / DEFAULTS
# =============================================================================

def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        pass
    return "", ""


def _get_defaults() -> dict:
    try:
        from models.company_defaults import get_defaults
        return get_defaults() or {}
    except Exception:
        return {}


from services.site_config import get_host as _get_host

# =============================================================================
# PAYMENT METHOD MAP + ACCOUNT RESOLVER
# =============================================================================

_METHOD_MAP = {
    "CASH":     "Cash",
    "CARD":     "Credit Card",
    "C / CARD": "Credit Card",
    "EFTPOS":   "Credit Card",
    "CHECK":    "Cheque",
    "CHEQUE":   "Cheque",
    "MOBILE":   "Mobile Money",
    "CREDIT":   "Credit",
    "TRANSFER": "Bank Transfer",
}

# Cache: mode_of_payment name → GL account string (fetched once per session)
_MOP_ACCOUNT_CACHE: dict[str, str] = {}

# Cache: "FROM::TO::DATE" → exchange rate float
_RATE_CACHE: dict[str, float] = {}


def _get_exchange_rate(from_currency: str, to_currency: str,
                       transaction_date: str,
                       api_key: str, api_secret: str, host: str) -> float:
    """
    Fetch exchange rate from Frappe's built-in currency exchange API.
    Returns 1.0 if fetch fails.

    Endpoint:
        GET /api/method/erpnext.setup.utils.get_exchange_rate
            ?from_currency=ZWG&to_currency=USD&transaction_date=2026-03-20
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
                log.debug("Exchange rate %s→%s on %s: %.6f",
                          from_currency, to_currency, transaction_date, rate)
                return rate
    except Exception as e:
        log.debug("Exchange rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

    log.warning("Could not fetch exchange rate %s→%s — defaulting to 1.0.",
                from_currency, to_currency)
    return 1.0


def _get_mop_account(mop_name: str, company: str,
                     api_key: str, api_secret: str, host: str,
                     currency: str = "") -> str:
    """
    Returns the GL account for a Mode of Payment + Company + Currency combination.

    Resolution order:
        1. Session cache (keyed by mop::company::currency)
        2. Frappe MOP API — matches by company, then filters by account currency
        3. server_pos_account fallback in company_defaults
    """
    cache_key = f"{mop_name}::{company}::{currency}"
    if cache_key in _MOP_ACCOUNT_CACHE:
        return _MOP_ACCOUNT_CACHE[cache_key]

    try:
        url = (
            f"{host}/api/resource/Mode%20of%20Payment/{urllib.parse.quote(mop_name)}"
            f"?fields=[\"accounts\"]"
        )
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {api_key}:{api_secret}")
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
            data     = json.loads(r.read().decode())
            accounts = (data.get("data") or {}).get("accounts", [])

        company_accounts = [
            row for row in accounts
            if not company or row.get("company") == company
        ]

        matched_acct = ""
        if currency and company_accounts:
            for row in company_accounts:
                acct = row.get("default_account", "")
                if acct and currency.upper() in acct.upper():
                    matched_acct = acct
                    break

        if not matched_acct and company_accounts:
            matched_acct = company_accounts[0].get("default_account", "")

        if matched_acct:
            _MOP_ACCOUNT_CACHE[cache_key] = matched_acct
            log.debug("MOP account resolved: %s [%s] → %s", mop_name, currency, matched_acct)
            return matched_acct

    except Exception as e:
        log.debug("Could not fetch MOP account for '%s': %s", mop_name, e)

    fallback = _get_defaults().get("server_pos_account", "").strip()
    if fallback:
        _MOP_ACCOUNT_CACHE[cache_key] = fallback
        log.debug("MOP account fallback (company_defaults): %s", fallback)
        return fallback

    log.warning(
        "No GL account found for MOP '%s' (currency=%s). "
        "Configure accounts on the Mode of Payment in Frappe "
        "or set server_pos_account in company_defaults.",
        mop_name, currency or "any"
    )
    return ""


# =============================================================================
# BUILD PAYLOAD
# =============================================================================

def _safe_str(val) -> str:
    """Convert any value (including datetime) to a plain string."""
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return str(val) if val is not None else ""


def _build_payload(sale: dict, items: list[dict], defaults: dict,
                   api_key: str = "", api_secret: str = "") -> dict:
    company           = defaults.get("server_company",           "")
    warehouse         = defaults.get("server_warehouse",         "")
    cost_center       = defaults.get("server_cost_center",       "")
    taxes_and_charges = defaults.get("server_taxes_and_charges", "")
    walk_in           = defaults.get("server_walk_in_customer",  "").strip() or "default"
    host              = _get_host()

    customer = (sale.get("customer_name") or "").strip() or walk_in

    # ── posting_date: always a plain YYYY-MM-DD string ────────────────────────
    raw_date     = sale.get("invoice_date") or ""
    posting_date = _safe_str(raw_date) or datetime.today().strftime("%Y-%m-%d")

    # ── posting_time: always HH:MM:SS string ─────────────────────────────────
    raw_time = sale.get("time") or ""
    if isinstance(raw_time, datetime):
        posting_time = raw_time.strftime("%H:%M:%S")
    else:
        t = str(raw_time).strip()
        # Pad to HH:MM:SS if needed (e.g. "14:30" → "14:30:00")
        posting_time = (
            t if len(t) == 8
            else (t + ":00" if len(t) == 5
                  else datetime.now().strftime("%H:%M:%S"))
        )

    mode_of_payment = _METHOD_MAP.get(str(sale.get("method", "")).upper().strip(), "Cash")
    currency        = (sale.get("currency") or "USD").strip().upper()
    mop_account     = _get_mop_account(mode_of_payment, company, api_key, api_secret, host, currency)

    company_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"
    # Always fetch/compute conversion_rate — never omit it from the payload
    conversion_rate = (
        _get_exchange_rate(currency, company_currency, posting_date, api_key, api_secret, host)
        if currency != company_currency else 1.0
    )

    frappe_items = []
    for it in items:
        item_code = (it.get("part_no") or "").strip()
        qty       = float(it.get("qty",   0))
        rate      = float(it.get("price", 0))
        if not item_code or qty <= 0:
            continue
        row: dict = {
            "item_code": item_code,
            "qty":       qty,
            "rate":      rate,
            "uom":       (it.get("uom") or "Nos"),   # required by Frappe validation
        }
        if cost_center:
            row["cost_center"] = cost_center
        frappe_items.append(row)

    if not frappe_items:
        return {}

    payload: dict = {
        "customer":               customer,
        "posting_date":           posting_date,
        "posting_time":           posting_time,
        "set_posting_time":       1,            # tell Frappe to honour our time
        "currency":               currency,
        "conversion_rate":        conversion_rate,  # always present, same as mobile
        "is_pos":                 0,
        "update_stock":           1,            # match mobile — write stock ledger
        "docstatus":              1,            # submit directly, same as mobile
        "custom_sales_reference": _safe_str(sale.get("invoice_no", "")),
        "items":                  frappe_items,
    }

    if company:           payload["company"]           = company
    if cost_center:       payload["cost_center"]       = cost_center
    if warehouse:         payload["set_warehouse"]     = warehouse
    if taxes_and_charges: payload["taxes_and_charges"] = taxes_and_charges

    return payload


# =============================================================================
# PUSH ONE SALE
# =============================================================================

def _push_sale(sale: dict, api_key: str, api_secret: str,
               defaults: dict, host: str):
    """Returns Frappe doc name (str), True (permanent skip), or False (retry later)."""
    inv_no  = sale.get("invoice_no", str(sale["id"]))
    walk_in = defaults.get("dansohol", "").strip() or "default"

    try:
        from models.sale import get_sale_items
        items = get_sale_items(sale["id"])
    except Exception as e:
        log.error("Items fetch failed for %s: %s", inv_no, e)
        return False

    payload = _build_payload(sale, items, defaults, api_key, api_secret)
    if not payload:
        log.warning("Sale %s — no valid items, skipping (marked synced).", inv_no)
        return True

    url = f"{host}/api/resource/Sales%20Invoice"

    # First attempt with resolved customer; second attempt falls back to walk-in
    attempts = [payload]
    if payload["customer"] != walk_in:
        attempts.append({**payload, "customer": walk_in})

    _PERMANENT_ERRORS = (
        "negativestockerror",
        "not marked as sales item",
        "is not a sales item",
        "account is required",
    )

    # Keywords that indicate the customer record itself is bad → retry with walk-in
    _CUSTOMER_ERRORS = ("customer", "payment_terms", "nonetype", "none")

    for i, p in enumerate(attempts):
        try:
            body = _dumps(p).encode("utf-8")
        except Exception as e:
            log.error("JSON serialisation failed for sale %s: %s", inv_no, e)
            return False

        req = urllib.request.Request(
            url=url,
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
                name   = (json.loads(resp.read()).get("data") or {}).get("name", "")
                suffix = f" [walk-in fallback: {walk_in}]" if i > 0 else ""
                log.info("✅ %s → Frappe %s  customer=%s%s",
                         inv_no, name, p["customer"], suffix)
                return name if name else True

        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read().decode())
                msg = (err.get("exception") or err.get("message") or
                       str(err.get("_server_messages", "")) or f"HTTP {e.code}")
            except Exception:
                msg = f"HTTP {e.code}"

            # 409 — already exists, treat as success
            if e.code == 409:
                log.info("Sale %s already exists on Frappe (409) — marking synced.", inv_no)
                return True

            # Permanent data errors — stop retrying to avoid infinite loop
            if e.code == 417 and any(kw in msg.lower() for kw in _PERMANENT_ERRORS):
                log.warning(
                    "⚠️  Sale %s — permanent Frappe data error (marked synced to stop loop).\n  %s",
                    inv_no, msg,
                )
                return True

            # Customer/payment_terms error — retry with walk-in on first attempt
            if i == 0 and e.code in (403, 417, 500) and any(
                kw in msg.lower() for kw in _CUSTOMER_ERRORS
            ):
                log.warning("Sale %s — customer '%s' rejected (HTTP %s), retrying with walk-in…",
                            inv_no, p["customer"], e.code)
                continue

            log.error("❌ Sale %s  HTTP %s: %s", inv_no, e.code, msg)
            return False

        except urllib.error.URLError as e:
            log.warning("Network error pushing %s: %s", inv_no, e.reason)
            return False

        except Exception as e:
            log.error("Unexpected error pushing %s: %s", inv_no, e)
            return False

    return False


# =============================================================================
# PUBLIC — push all unsynced (rate-limited to MAX_PER_MINUTE)
# =============================================================================

def push_unsynced_sales() -> dict:
    result = {"pushed": 0, "failed": 0, "total": 0}

    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("No API credentials — skipping upload cycle.")
        return result

    host     = _get_host()
    defaults = _get_defaults()

    try:
        from models.sale import get_unsynced_sales, mark_synced_with_ref
        sales = get_unsynced_sales()
    except Exception as e:
        log.error("Could not read unsynced sales: %s", e)
        return result

    result["total"] = len(sales)
    if not sales:
        log.debug("No unsynced sales.")
        return result

    log.info("Pushing %d sale(s) to Frappe (max %d/min)…", len(sales), MAX_PER_MINUTE)

    for idx, sale in enumerate(sales):
        if idx > 0 and idx % MAX_PER_MINUTE == 0:
            log.info("Rate limit pause — waiting 60s before next batch…")
            time.sleep(60)

        result_val = _push_sale(sale, api_key, api_secret, defaults, host)
        if result_val:
            try:
                frappe_ref = result_val if isinstance(result_val, str) else ""
                mark_synced_with_ref(sale["id"], frappe_ref)
                result["pushed"] += 1
            except Exception as e:
                log.error("mark_synced failed for sale %s: %s", sale["id"], e)
                result["failed"] += 1
        else:
            result["failed"] += 1

        if idx < len(sales) - 1:
            time.sleep(INTER_PUSH_DELAY)

    log.info("Upload done — ✅ %d pushed  ❌ %d failed  (of %d)",
             result["pushed"], result["failed"], result["total"])
    return result


# =============================================================================
# QTHREAD WORKER
# =============================================================================

try:
    from PySide6.QtCore import QObject  # type: ignore

    class UploadWorker(QObject):
        def run(self) -> None:
            log.info("POS upload worker started (interval=%ds, max=%d/min).",
                     UPLOAD_INTERVAL, MAX_PER_MINUTE)
            while True:
                try:
                    push_unsynced_sales()
                except Exception as exc:
                    log.error("Unhandled error in upload worker: %s", exc)
                time.sleep(UPLOAD_INTERVAL)

except ImportError:
    class UploadWorker:              # type: ignore[no-redef]
        def run(self) -> None:
            pass


def start_upload_thread() -> object:
    """Start the upload background thread — call once from MainWindow.__init__."""
    try:
        from PySide6.QtCore import QThread  # type: ignore
        thread = QThread()
        worker = UploadWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        thread._worker = worker      # prevent GC
        thread.start()
        log.info("POS upload QThread started.")
        return thread
    except ImportError:
        def _loop():
            while True:
                try:
                    push_unsynced_sales()
                except Exception as exc:
                    log.error("Unhandled error: %s", exc)
                time.sleep(UPLOAD_INTERVAL)
        t = threading.Thread(target=_loop, daemon=True, name="POSUploadThread")
        t.start()
        return t
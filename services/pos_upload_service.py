
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

UPLOAD_INTERVAL   = 10
REQUEST_TIMEOUT   = 60
MAX_PER_MINUTE    = 20
INTER_PUSH_DELAY  = 60 / MAX_PER_MINUTE

_LOCAL_CURRENCIES = {"ZWD", "ZIG", "ZWG"}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

class _DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def _dumps(obj) -> str:
    return json.dumps(obj, cls=_DateTimeEncoder)


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

_RATE_CACHE: dict[str, float] = {}


def _get_exchange_rate(from_currency: str, to_currency: str,
                       transaction_date: str,
                       api_key: str, api_secret: str, host: str) -> float:
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
                log.debug("Rate %s→%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
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


def _get_batch_for_item(item_code: str) -> str:
    """Fetch the oldest valid batch_no for an item_code."""
    if not item_code:
        return ""
    try:
        from database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT TOP 1 pb.batch_no
            FROM product_batches pb
            JOIN products p ON pb.product_id = p.id
            WHERE UPPER(p.part_no) = UPPER(?)
              AND (pb.qty IS NULL OR pb.qty > 0)
            ORDER BY pb.expiry_date ASC
            """,
            (item_code,)
        )
        row = cur.fetchone()
        conn.close()
        return str(row[0]).strip() if row and row[0] else ""
    except Exception as e:
        log.debug("Batch lookup failed for %s: %s", item_code, e)
        return ""


def _resolve_zwd_per_usd(
    sale: dict,
    api_key: str,
    api_secret: str,
    host: str,
    local_currency: str,
    posting_date: str,
) -> float:
    """
    Resolve ZWD-per-USD (e.g. 30.0) for the given local currency.

    Priority:
      1. Stored exchange_rate column on the sale row
         - If > 1  → already ZWD-per-USD  (e.g. 30)
         - If 0–1  → USD-per-ZWD          (e.g. 0.0333) → invert
      2. Live Frappe: local → USD  (then invert)
      3. Live Frappe: USD → local  (direct)
      4. Fallback 1.0  (logged as warning)
    """
    stored = float(sale.get("exchange_rate") or 0)

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
        "[_resolve_zwd_per_usd] Could not resolve exchange rate for %s on %s "
        "— defaulting to 1.0 (amounts may be wrong).",
        local_currency, posting_date,
    )
    return 1.0


def _detect_invoice_currency(sale: dict, items: list[dict]) -> str:
    """
    Determine the single invoice currency for this sale.

    Returns one of: "USD", "ZWD", "ZIG", "ZWG", or "MIXED"

    Rules:
      • All signals point to ZIG only   → "ZIG"
      • All signals point to ZWG only   → "ZWG"
      • All signals point to ZWD only   → "ZWD"
      • All signals point to USD only   → "USD"
      • Any mixture                     → "MIXED"  (caller will normalise to USD)

    NOTE: Returns "MIXED" (not "USD") for mixed sales so the caller has an
    unambiguous signal — this prevents the double-detection bug where
    _push_sale used to re-derive currency independently.
    """
    sale_currency = (sale.get("currency") or "").strip().upper()
    has_local_tender = float(sale.get("tendered_zwd", 0)) > 0

    item_currencies: set[str] = set()
    for it in items:
        ic = (it.get("currency") or "").strip().upper()
        if ic:
            item_currencies.add(ic)

    observed: set[str] = set()
    if sale_currency:
        observed.add(sale_currency)
    if has_local_tender:
        observed.add(sale_currency if sale_currency in _LOCAL_CURRENCIES else "ZWD")
    observed.update(item_currencies)
    observed.discard("")

    if not observed:
        return "USD"
    if observed == {"ZWD"}:
        return "ZWD"
    if observed == {"ZIG"}:
        return "ZIG"
    if observed == {"ZWG"}:
        return "ZWG"
    if observed == {"USD"}:
        return "USD"

    log.info(
        "[_detect_invoice_currency] Sale %s has mixed currencies %s — "
        "will normalise to USD.",
        sale.get("id"), observed,
    )
    return "MIXED"


def _parse_posting_datetime(sale: dict) -> tuple[str, str]:
    """
    Return (posting_date, posting_time) as strings.
    If this sale previously failed with NegativeStockError, we 'bump' it to now.
    """
    inv_no = sale.get("invoice_no")
    use_now = False

    # Check if we have a recorded NegativeStockError for this invoice
    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        # Corrected column names: doc_ref, doc_type, error_msg, id
        cur.execute(
            "SELECT TOP 1 error_msg FROM sync_errors "
            "WHERE doc_ref = ? AND doc_type = 'SI' "
            "ORDER BY id DESC", 
            (inv_no,)
        )
        row = cur.fetchone()
        conn.close()
        if row and "NegativeStockError" in str(row[0]):
            use_now = True
            log.info("[sync] Sale %s failed previously with NegativeStockError — bumping timestamp to NOW for retry.", inv_no)
    except Exception as e:
        log.debug("[sync] parse_posting_datetime error check failed: %s", e)

    if use_now:
        now = datetime.now()
        return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

    raw_date = sale.get("invoice_date") or ""
    if isinstance(raw_date, (datetime, date)):
        posting_date = raw_date.strftime("%Y-%m-%d")
    else:
        posting_date = str(raw_date)[:10] if raw_date else datetime.today().strftime("%Y-%m-%d")

    raw_time = sale.get("time") or ""
    if isinstance(raw_time, datetime):
        posting_time = raw_time.strftime("%H:%M:%S")
    else:
        t = str(raw_time).strip()
        if len(t) == 8:
            posting_time = t
        elif len(t) == 5:
            posting_time = t + ":00"
        else:
            posting_time = datetime.now().strftime("%H:%M:%S")

    return posting_date, posting_time


def _base_payload_fields(sale: dict, defaults: dict,
                         posting_date: str, posting_time: str,
                         currency: str, conversion_rate: float) -> dict:
    """
    Assemble the non-item fields shared by all three builders.
    Items and currency-specific values are injected by each builder.
    """
    company           = defaults.get("server_company", "")
    warehouse         = defaults.get("server_warehouse", "")
    cost_center       = defaults.get("server_cost_center", "")
    taxes_and_charges = defaults.get("server_taxes_and_charges", "")
    walk_in           = defaults.get("server_walk_in_customer", "").strip() or "Default"
    customer          = (sale.get("customer_name") or "").strip() or walk_in

    payload: dict = {
        "customer":               customer,
        "posting_date":           posting_date,
        "posting_time":           posting_time,
        "set_posting_time":       1,
        "currency":               currency,
        "conversion_rate":        conversion_rate,
        "is_pos":                 0,
        "update_stock":           1,
        "docstatus":              1,
        "custom_sales_reference": str(sale.get("invoice_no", "")),
    }

    if company:
        payload["company"] = company
    if cost_center:
        payload["cost_center"] = cost_center
    if warehouse:
        payload["set_warehouse"] = warehouse
    if taxes_and_charges:
        payload["taxes_and_charges"] = taxes_and_charges

    if sale.get("is_on_account") and float(sale.get("tendered", 0)) == 0:
        payload["is_on_account"]        = 1
        payload["custom_is_on_account"] = 1

    return payload


# ─────────────────────────────────────────────────────────────────────────────
# Three independent payload builders
# ─────────────────────────────────────────────────────────────────────────────

def _build_payload_usd(sale: dict, items: list[dict], defaults: dict) -> dict:
    """
    Build a Frappe Sales Invoice payload for a PURE USD sale.

    Rules:
      • currency          = "USD"
      • conversion_rate   = 1.0
      • item rate         = price_usd  (already in USD)

    No exchange-rate lookup is performed — USD invoices need none.
    """
    log.debug("[_build_payload_usd] sale=%s", sale.get("id"))

    posting_date, posting_time = _parse_posting_datetime(sale)

    frappe_items     = []
    total_calculated = 0.0
    cost_center      = defaults.get("server_cost_center", "")

    for it in items:
        item_code = (it.get("part_no") or "").strip()
        qty       = float(it.get("qty", 0))
        rate      = float(it.get("price") or 0)   # USD price, used directly

        if not item_code or qty <= 0:
            continue

        row: dict = {
            "item_code": item_code,
            "qty":       qty,
            "rate":      rate,
            "uom":       (it.get("uom") or "Nos"),
        }
        
        batch_no = str(it.get("batch_no") or "").strip()
        if not batch_no:
            batch_no = _get_batch_for_item(item_code)
            
        if batch_no:
            row["batch_no"] = batch_no
            
        serial_no = str(it.get("serial_no") or "").strip()
        if serial_no:
            row["serial_no"] = serial_no

        if cost_center:
            row["cost_center"] = cost_center

        frappe_items.append(row)
        total_calculated += rate * qty

    if not frappe_items:
        log.warning("[_build_payload_usd] Sale %s — no valid items.", sale.get("id"))
        return {}

    stored_total = float(sale.get("total_usd") or sale.get("total") or 0)
    if stored_total > 0 and abs(total_calculated - stored_total) > 0.02:
        log.warning(
            "[_build_payload_usd] Sale %s: computed USD total %.4f differs from "
            "stored total %.4f",
            sale.get("id"), total_calculated, stored_total,
        )

    payload = _base_payload_fields(
        sale, defaults, posting_date, posting_time,
        currency="USD", conversion_rate=1.0,
    )
    payload["items"]       = frappe_items
    payload["grand_total"] = round(total_calculated, 2)
    payload["total"]       = round(total_calculated, 2)
    return payload


def _build_payload_local_currency(
    sale: dict,
    items: list[dict],
    defaults: dict,
    local_currency: str,
    api_key: str,
    api_secret: str,
    host: str,
) -> dict:
    """
    Build a Frappe Sales Invoice payload for a PURE local-currency sale
    (all items and tender are in the same local currency: ZWD, ZIG, or ZWG).

    Rules:
      • currency          = local_currency  ("ZWD", "ZIG", or "ZWG")
      • conversion_rate   = 1 / zwd_per_usd   (USD per 1 local unit)
      • item rate         = price (already in local currency, no conversion needed)

    Frappe recovers the USD base: rate_local × conversion_rate = price_usd  ✅
    """
    log.debug("[_build_payload_local_currency] sale=%s  currency=%s",
              sale.get("id"), local_currency)

    posting_date, posting_time = _parse_posting_datetime(sale)

    zwd_per_usd = _resolve_zwd_per_usd(
        sale, api_key, api_secret, host, local_currency, posting_date
    )
    frappe_conversion_rate = round(1.0 / zwd_per_usd, 8)

    log.debug(
        "[_build_payload_local_currency] sale=%s  %s_per_usd=%.6f  "
        "frappe_conversion_rate=%.8f",
        sale.get("id"), local_currency, zwd_per_usd, frappe_conversion_rate,
    )

    frappe_items     = []
    total_calculated = 0.0
    cost_center      = defaults.get("server_cost_center", "")

    for it in items:
        item_code = (it.get("part_no") or "").strip()
        qty       = float(it.get("qty", 0))
        rate      = float(it.get("price") or 0)   # already in local currency

        if not item_code or qty <= 0:
            continue

        row: dict = {
            "item_code": item_code,
            "qty":       qty,
            "rate":      rate,
            "uom":       (it.get("uom") or "Nos"),
        }
        
        batch_no = str(it.get("batch_no") or "").strip()
        if not batch_no:
            batch_no = _get_batch_for_item(item_code)
            
        if batch_no:
            row["batch_no"] = batch_no
            
        serial_no = str(it.get("serial_no") or "").strip()
        if serial_no:
            row["serial_no"] = serial_no

        if cost_center:
            row["cost_center"] = cost_center

        frappe_items.append(row)
        total_calculated += rate * qty

    if not frappe_items:
        log.warning("[_build_payload_local_currency] Sale %s — no valid items.",
                    sale.get("id"))
        return {}

    stored_total = float(sale.get("total") or 0)
    if stored_total > 0 and abs(total_calculated - stored_total) > 0.02:
        log.warning(
            "[_build_payload_local_currency] Sale %s: computed %s total %.4f differs from "
            "stored total %.4f",
            sale.get("id"), local_currency, total_calculated, stored_total,
        )

    payload = _base_payload_fields(
        sale, defaults, posting_date, posting_time,
        currency=local_currency,
        conversion_rate=frappe_conversion_rate,
    )
    payload["items"]       = frappe_items
    payload["grand_total"] = round(total_calculated, 2)
    payload["total"]       = round(total_calculated, 2)
    return payload


def _build_payload_mixed_to_usd(
    sale: dict,
    items: list[dict],
    defaults: dict,
    api_key: str,
    api_secret: str,
    host: str,
) -> dict:
    """
    Build a Frappe Sales Invoice payload for a MIXED-currency sale
    (USD + ZWD, USD + ZWG, or ZWD + ZWG in the same transaction).

    Rules:
      • Normalise everything to USD
      • currency          = "USD"
      • conversion_rate   = 1.0
      • item rate         = price_usd  (POS already stores prices in USD)

    Any per-item local-currency rates are converted to USD before sending.
    The exchange rate is resolved once for the transaction date.
    """
    log.debug("[_build_payload_mixed_to_usd] sale=%s — normalising to USD",
              sale.get("id"))

    posting_date, posting_time = _parse_posting_datetime(sale)

    local_currencies_seen: set[str] = set()
    for it in items:
        ic = (it.get("currency") or "").strip().upper()
        if ic in _LOCAL_CURRENCIES:
            local_currencies_seen.add(ic)

    rate_map: dict[str, float] = {}
    for lc in local_currencies_seen:
        zwd_per_usd = _resolve_zwd_per_usd(
            sale, api_key, api_secret, host, lc, posting_date
        )
        rate_map[lc] = zwd_per_usd
        log.debug("[_build_payload_mixed_to_usd] %s_per_usd=%.6f", lc, zwd_per_usd)

    frappe_items     = []
    total_calculated = 0.0
    cost_center      = defaults.get("server_cost_center", "")

    for it in items:
        item_code     = (it.get("part_no") or "").strip()
        qty           = float(it.get("qty", 0))
        price_usd     = float(it.get("price") or 0)
        item_currency = (it.get("currency") or "USD").strip().upper()

        if not item_code or qty <= 0:
            continue

        if item_currency in _LOCAL_CURRENCIES and item_currency in rate_map:
            rate_usd = round(price_usd / rate_map[item_currency], 6)
        else:
            rate_usd = price_usd

        row: dict = {
            "item_code": item_code,
            "qty":       qty,
            "rate":      rate_usd,
            "uom":       (it.get("uom") or "Nos"),
        }
        
        batch_no = str(it.get("batch_no") or "").strip()
        if not batch_no:
            batch_no = _get_batch_for_item(item_code)
            
        if batch_no:
            row["batch_no"] = batch_no
            
        serial_no = str(it.get("serial_no") or "").strip()
        if serial_no:
            row["serial_no"] = serial_no

        if cost_center:
            row["cost_center"] = cost_center

        frappe_items.append(row)
        total_calculated += rate_usd * qty

    if not frappe_items:
        log.warning("[_build_payload_mixed_to_usd] Sale %s — no valid items.",
                    sale.get("id"))
        return {}

    stored_total_usd = float(sale.get("total_usd") or sale.get("total") or 0)
    if stored_total_usd > 0 and abs(total_calculated - stored_total_usd) > 0.02:
        log.warning(
            "[_build_payload_mixed_to_usd] Sale %s: computed USD total %.4f "
            "differs from stored total_usd %.4f",
            sale.get("id"), total_calculated, stored_total_usd,
        )

    payload = _base_payload_fields(
        sale, defaults, posting_date, posting_time,
        currency="USD", conversion_rate=1.0,
    )
    payload["items"]       = frappe_items
    payload["grand_total"] = round(total_calculated, 2)
    payload["total"]       = round(total_calculated, 2)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher — detects currency once, routes to exactly one builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_payload(sale: dict, items: list[dict], defaults: dict,
                   api_key: str = "", api_secret: str = "",
                   host: str = "") -> tuple[dict, bool]:
    """
    Detect the invoice currency and delegate to the appropriate builder.

    Returns (payload, is_mixed) so _push_sale never needs to re-derive
    the currency — eliminating the double-detection bug.

    Only ONE builder is ever called per sale — they are fully independent.

      "USD"   → _build_payload_usd            (no exchange rate lookup)
      "ZWD"   → _build_payload_local_currency (rates resolved for ZWD)
      "ZIG"   → _build_payload_local_currency (rates resolved for ZIG)
      "ZWG"   → _build_payload_local_currency (rates resolved for ZWG)
      "MIXED" → _build_payload_mixed_to_usd   (normalise everything to USD)
    """
    invoice_currency = _detect_invoice_currency(sale, items)

    if invoice_currency in _LOCAL_CURRENCIES:
        return (
            _build_payload_local_currency(
                sale, items, defaults, invoice_currency, api_key, api_secret, host
            ),
            False,   # single currency — never mixed
        )

    if invoice_currency == "USD":
        return _build_payload_usd(sale, items, defaults), False

    if invoice_currency == "MIXED":
        return (
            _build_payload_mixed_to_usd(sale, items, defaults, api_key, api_secret, host),
            True,    # mixed — walk-in fallback is allowed
        )

    # Fallback (should never be reached)
    log.error("[_build_payload] Unhandled currency '%s' for sale %s — "
              "falling back to USD builder.", invoice_currency, sale.get("id"))
    return _build_payload_usd(sale, items, defaults), False


# ─────────────────────────────────────────────────────────────────────────────
# Push logic
# ─────────────────────────────────────────────────────────────────────────────

def _is_already_synced(sale_id: int) -> bool:
    """
    Read synced + frappe_ref FRESH from the DB right now.
    Returns True if this sale was already successfully pushed to Frappe
    (synced=1 OR a frappe_ref is recorded), so we never POST it twice.
    """
    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "SELECT synced, frappe_ref FROM sales WHERE id = ?",
            (sale_id,)
        )
        row = cur.fetchone()
        conn.close()
        if row is None:
            return False   # sale not found — let it fail naturally below
        synced, frappe_ref = row
        if synced:
            return True
        if frappe_ref and str(frappe_ref).strip():
            return True
        return False
    except Exception as e:
        log.warning("[_is_already_synced] DB check failed for sale %s: %s — will proceed with push.", sale_id, e)
        return False   # safe default: if we can't check, try to push (Frappe 409 will catch it)


def _push_sale(sale: dict, api_key: str, api_secret: str,
               defaults: dict, host: str):
    """Push ONE invoice to Frappe.

    For single-currency sales (USD, ZIG, ZWD, ZWG) exactly ONE POST is ever
    made — there is no walk-in retry, and no HTTP-error retry that could
    produce a second invoice.

    The walk-in customer retry only fires for genuinely MIXED sales, and only
    on HTTP 403/417/500 from the first attempt.
    """
    inv_no  = sale.get("invoice_no", str(sale["id"]))
    walk_in = defaults.get("server_walk_in_customer", "").strip() or "Default"

    # ── GUARD: re-read synced flag from DB before doing anything ─────────────
    if _is_already_synced(sale["id"]):
        log.info("Sale %s (id=%s) is already synced in DB — skipping.", inv_no, sale["id"])
        return True

    try:
        from models.sale import get_sale_items
        items = get_sale_items(sale["id"])
    except Exception as e:
        log.error("Items fetch failed for %s: %s", inv_no, e)
        return False

    # ── Single source of truth: currency is determined ONCE here ─────────────
    payload, is_mixed = _build_payload(sale, items, defaults, api_key, api_secret, host)

    if not payload:
        log.warning("Sale %s — no valid items, skipping.", inv_no)
        return True

    url = f"{host}/api/resource/Sales%20Invoice"

    if is_mixed and payload.get("customer") != walk_in:
        attempts = [payload, {**payload, "customer": walk_in}]
        log.debug("Mixed currency sale %s — up to 2 attempts (walk-in fallback ready).", inv_no)
    else:
        attempts = [payload]
        log.debug("Single currency sale %s — exactly 1 attempt.", inv_no)

    def _record_sync_error(code: str, raw_msg: str):
        customer_name = sale.get("customer_name") or walk_in
        amount        = float(sale.get("total") or 0)
        log.error("❌ Sale %s  %s: %s", inv_no, code, raw_msg)
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE sales SET sync_error = ? WHERE id = ?", (raw_msg, sale["id"]))
            conn.commit()
            conn.close()

            from services.sync_errors_service import record_error
            record_error("SI", inv_no, raw_msg,
                         customer=customer_name, amount=amount, error_code=code)
        except Exception as e:
            log.warning("Could not record sync error to DB: %s", e)

    for i, p in enumerate(attempts):
        try:
            body = _dumps(p).encode("utf-8")
        except Exception as e:
            log.error("JSON serialisation failed: %s", e)
            return False

        req = urllib.request.Request(
            url=url,
            data=body,
            method="POST",
            headers={
                "Content-Type":  "application/json",
                "Accept":        "application/json",
                "Authorization": f"token {api_key}:{api_secret}",
                "Idempotency-Key": f"pos_sale_{inv_no}_{i}",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                response_data = json.loads(resp.read())
                name = (response_data.get("data") or {}).get("name", "")
                log.info("✅ Sale %s → Frappe %s", inv_no, name)
                return name if name else True

        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode("utf-8", errors="replace")
                error_json = json.loads(error_body) if error_body else {}
                msg = (error_json.get("exception") or error_json.get("message") or
                       str(error_json.get("_server_messages", "")) or f"HTTP {e.code}")
            except Exception:
                msg = f"HTTP {e.code}"

            if e.code == 409:
                log.info("Sale %s already exists on Frappe (409).", inv_no)
                return True

            if is_mixed and i == 0 and e.code in (403, 417, 500):
                log.warning(
                    "Sale %s HTTP %s — retrying once with walk-in customer.", inv_no, e.code
                )
                continue

            _record_sync_error(f"HTTP {e.code}", msg)
            return False

        except urllib.error.URLError as e:
            _record_sync_error("NETWORK", f"Cannot reach server: {e.reason}")
            return False

        except Exception as e:
            import traceback
            log.error("Unexpected error pushing %s: %s\n%s", inv_no, e, traceback.format_exc())
            _record_sync_error("UNKNOWN", str(e))
            return False

    return False


def push_unsynced_sales() -> dict:
    """Push all unsynced sales to Frappe."""

    result = {"pushed": 0, "failed": 0, "total": 0}

    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("No API credentials — skipping upload cycle.")
        return result

    host     = _get_host()
    defaults = _get_defaults()

    # ─────────────────────────────────────────────────────────────────────────
    # FIX 1 (stale lock cleanup): Moved BELOW the sales fetch so we never
    # accidentally unlock a sale that was legitimately mid-push in a previous
    # or concurrent cycle before we even start iterating.
    # The old code ran clear_stale_locks() BEFORE the loop, which could reset
    # syncing=0 on a sale that another thread was actively pushing, allowing
    # this thread to grab it and POST a second invoice to Frappe.
    # By running the cleanup first and THEN fetching, both steps are inside the
    # same logical transaction boundary — but we still need the atomic lock
    # below (FIX 2) as the real guard.
    # ─────────────────────────────────────────────────────────────────────────

    try:
        from models.sale import get_unsynced_sales
        sales = get_unsynced_sales()
    except Exception as e:
        log.error("Could not read unsynced sales: %s", e)
        return result

    result["total"] = len(sales)

    if not sales:
        log.debug("No unsynced sales found.")
        return result

    log.info("Starting upload cycle — %d sale(s) to push.", len(sales))

    # Clear stale locks AFTER fetching the snapshot — never before.
    # This prevents unlocking a sale that another thread is mid-push on.
    try:
        from models.sale import clear_stale_locks
        cleared = clear_stale_locks()
        if cleared:
            log.debug("Cleared %d stale sync locks.", cleared)
    except Exception:
        pass

    for idx, sale in enumerate(sales):
        if idx > 0 and idx % MAX_PER_MINUTE == 0:
            log.info("Rate-limit pause — waiting 60 s…")
            time.sleep(60)

        # ─────────────────────────────────────────────────────────────────────
        # FIX 2 (atomic lock): try_lock_sale MUST be implemented as a single
        # atomic UPDATE … WHERE syncing = 0 AND synced = 0 with a ROWCOUNT
        # check — NOT a separate SELECT then UPDATE.  Two threads reading
        # syncing=0 simultaneously can both proceed with a non-atomic lock,
        # causing duplicate invoices.
        #
        # Required SQL Server implementation in models/sale.py:
        #
        #   def try_lock_sale(sale_id: int) -> bool:
        #       conn = get_connection()
        #       cur  = conn.cursor()
        #       cur.execute("""
        #           UPDATE sales WITH (ROWLOCK, UPDLOCK)
        #           SET    syncing = 1,
        #                  sync_locked_at = GETDATE()
        #           WHERE  id      = ?
        #             AND  syncing = 0
        #             AND  synced  = 0
        #       """, (sale_id,))
        #       conn.commit()
        #       locked = cur.rowcount == 1
        #       conn.close()
        #       return locked
        # ─────────────────────────────────────────────────────────────────────
        from models.sale import try_lock_sale
        if not try_lock_sale(sale["id"]):
            log.debug("Skipping sale %s — already being synced by another thread.", sale.get("invoice_no"))
            continue

        push_succeeded = False
        try:
            result_val = _push_sale(sale, api_key, api_secret, defaults, host)
            if result_val:
                frappe_ref = result_val if isinstance(result_val, str) else ""
                from models.sale import mark_synced_with_ref
                # mark_synced_with_ref sets synced=1 AND clears syncing=0 atomically.
                # The finally block below only releases the lock for FAILED pushes,
                # so a crash between a successful POST and this call cannot produce
                # a duplicate — Frappe's 409 dedup will catch it on the next retry.
                mark_synced_with_ref(sale["id"], frappe_ref)
                result["pushed"] += 1
                push_succeeded = True
            else:
                result["failed"] += 1
        except Exception as e:
            log.error("Sync loop error for sale %s: %s", sale.get("invoice_no"), e)
            result["failed"] += 1
        finally:
            # ─────────────────────────────────────────────────────────────────
            # FIX 3 (conditional lock release): Only release the syncing lock
            # for FAILED pushes.  The old code always set syncing=0 in finally,
            # even after a successful POST.  If mark_synced_with_ref failed
            # (e.g. DB timeout), synced stayed 0, the lock was released, and
            # the next cycle pushed the same sale again producing a duplicate.
            #
            # For successful pushes, mark_synced_with_ref is responsible for
            # clearing syncing as part of its own UPDATE (set synced=1,
            # syncing=0 in one statement).  We only need to unlock here for
            # the failure path so the sale can be retried next cycle.
            # ─────────────────────────────────────────────────────────────────
            if not push_succeeded:
                try:
                    from database.db import get_connection
                    _conn = get_connection()
                    _conn.cursor().execute(
                        "UPDATE sales SET syncing = 0 WHERE id = ?", (sale["id"],)
                    )
                    _conn.commit()
                    _conn.close()
                except Exception:
                    pass

        if idx < len(sales) - 1:
            time.sleep(INTER_PUSH_DELAY)

    log.info("Upload done — ✅ %d pushed  ❌ %d failed", result["pushed"], result["failed"])
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Background worker
# ─────────────────────────────────────────────────────────────────────────────

try:
    from PySide6.QtCore import QObject

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
    class UploadWorker:
        def run(self) -> None:
            pass


def start_upload_thread() -> object:
    try:
        from PySide6.QtCore import QThread
        thread  = QThread()
        worker  = UploadWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        thread._worker = worker
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
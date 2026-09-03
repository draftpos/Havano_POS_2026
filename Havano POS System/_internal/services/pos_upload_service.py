
from __future__ import annotations

import json
import logging
import time
import threading
import urllib.parse
from services.network_utils import safe_urlopen
from datetime import datetime, date

log = logging.getLogger("POSUpload")

UPLOAD_INTERVAL   = 300       # 5 minutes
REQUEST_TIMEOUT   = 60
MAX_PER_MINUTE    = 20
INTER_PUSH_DELAY  = 60 / MAX_PER_MINUTE

_LOCAL_CURRENCIES = {"ZWD", "ZIG", "ZWG"}
_upload_thread_running = False


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
    Fetch live exchange rate from Frappe (from_currency -> to_currency).
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
        with safe_urlopen(req, timeout=REQUEST_TIMEOUT) as r:
            data = json.loads(r.read().decode())
            rate = float(data.get("message") or data.get("result") or 0)
            if rate > 0:
                _RATE_CACHE[cache_key] = rate
                log.debug("Rate %s->%s on %s: %.6f", from_currency, to_currency, transaction_date, rate)
                return rate
    except Exception as e:
        log.debug("Exchange rate fetch failed (%s->%s): %s", from_currency, to_currency, e)

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
         - If > 1  -> already ZWD-per-USD  (e.g. 30)
         - If 0–1  -> USD-per-ZWD          (e.g. 0.0333) -> invert
      2. Live Frappe: local -> USD  (then invert)
      3. Live Frappe: USD -> local  (direct)
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
        "- defaulting to 1.0 (amounts may be wrong).",
        local_currency, posting_date,
    )
    return 1.0


def _detect_invoice_currency(sale: dict, items: list[dict]) -> str:
    """
    Determine the single invoice currency for this sale.

    Returns one of: "USD", "ZWD", "ZIG", "ZWG", or "MIXED"

    Rules:
      • All signals point to ZIG only   -> "ZIG"
      • All signals point to ZWG only   -> "ZWG"
      • All signals point to ZWD only   -> "ZWD"
      • All signals point to USD only   -> "USD"
      • Any mixture                     -> "MIXED"  (caller will normalise to USD)

    NOTE: Returns "MIXED" (not "USD") for mixed sales so the caller has an
    unambiguous signal - this prevents the double-detection bug where
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
        "[_detect_invoice_currency] Sale %s has mixed currencies %s - "
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
            log.info("[sync] Sale %s failed previously with NegativeStockError - bumping timestamp to NOW for retry.", inv_no)
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


def _resolve_waiter_frappe_user(waiter_name: str) -> str:
    if not waiter_name:
        return ""
    try:
        from database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT TOP 1 frappe_user, email, username FROM users WHERE username = ? OR full_name = ?", (waiter_name, waiter_name))
        row = cur.fetchone()
        conn.close()
        if row:
            f_user, email, uname = row
            if f_user and str(f_user).strip():
                return str(f_user).strip()
            if email and str(email).strip():
                return str(email).strip()
            if uname and str(uname).strip():
                return str(uname).strip()
    except Exception:
        pass
    return waiter_name

_TAX_ACCOUNT_MAP_CACHE = {}

def _fetch_tax_account_map(host: str, api_key: str, api_secret: str, company: str) -> dict:
    global _TAX_ACCOUNT_MAP_CACHE
    if company in _TAX_ACCOUNT_MAP_CACHE:
        return _TAX_ACCOUNT_MAP_CACHE[company]

    try:
        filters = [["account_type", "=", "Tax"]]
        if company:
            filters.append(["company", "=", company])
            
        filters_str = json.dumps(filters)
        fields = json.dumps(["name", "account_name"])
        url = f"{host}/api/resource/Account?filters={urllib.parse.quote(filters_str)}&fields={urllib.parse.quote(fields)}&limit_page_length=0"
        
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {api_key}:{api_secret}")
        with safe_urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            accounts = data.get("data", [])
            
            result = {}
            for acc in accounts:
                aname = (acc.get("account_name") or "").strip().upper()
                name = (acc.get("name") or "").strip()
                if aname and name:
                    result[aname] = name
            
            _TAX_ACCOUNT_MAP_CACHE[company] = result
            return result
    except Exception as e:
        log.error("Failed to fetch tax accounts from ERPNext for company %s: %s", company, e)
        return {}

def _resolve_tax_account_head(category: str, tax_accounts: dict) -> str | None:
    if not tax_accounts:
        return None
        
    cat = (category or "VAT").strip().upper()
    
    if "VAT" in cat:
        if "VAT" in tax_accounts: return tax_accounts["VAT"]
        for k, v in tax_accounts.items():
            if "VAT" in k: return v
            
    if "DUTIES" in cat:
        if "DUTIES AND TAXES" in tax_accounts: return tax_accounts["DUTIES AND TAXES"]
        for k, v in tax_accounts.items():
            if "DUTIES" in k: return v
            
    if cat in tax_accounts:
        return tax_accounts[cat]
        
    return None

def _build_erpnext_tax_lines(sale: dict, items: list[dict], defaults: dict, host: str, api_key: str, api_secret: str) -> list[dict]:
    item_codes = [it.get("part_no") for it in items if it.get("part_no")]
    if not item_codes:
        return []
        
    try:
        from database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        
        placeholders = ",".join("?" * len(item_codes))
        cur.execute(f"SELECT part_no, tax_category, minimum_net_rate FROM product_taxes WHERE part_no IN ({placeholders})", tuple(item_codes))
        rows = cur.fetchall()
        conn.close()
        
        selected_vat_rate = None
        selected_cat = None
        has_tax = False
        
        for r in rows:
            cat = str(r[1] or "").upper()
            rate = float(r[2] or 0.0)
            
            if "VAT" in cat:
                has_tax = True
                selected_cat = "VAT"
                r_val = rate if rate > 0 else 15.0
                if selected_vat_rate is None or r_val > selected_vat_rate:
                    selected_vat_rate = r_val
            elif "DUTIES" in cat:
                has_tax = True
                if not selected_cat: selected_cat = "Duties and Taxes"
                if rate > 0:
                    if selected_vat_rate is None or rate > selected_vat_rate:
                        selected_vat_rate = rate
            elif rate > 0:
                has_tax = True
                if not selected_cat: selected_cat = cat
                
        tax_amount = float(sale.get("tax_amount") or 0.0)
        if not has_tax and tax_amount > 0:
            has_tax = True
            selected_vat_rate = 15.0
            
        if not has_tax:
            return []
            
        vat_rate = selected_vat_rate if selected_vat_rate is not None else 15.0
        
        company = defaults.get("server_company", "")
        tax_map = _fetch_tax_account_map(host, api_key, api_secret, company)
        account_head = _resolve_tax_account_head(selected_cat, tax_map)
        
        if not account_head:
            log.warning("No matching tax account head found for %s, skipping tax line.", selected_cat)
            return []
            
        return [{
            "charge_type": "On Net Total",
            "account_head": account_head,
            "rate": vat_rate,
            "description": selected_cat or "VAT",
            "cost_center": defaults.get("server_cost_center", ""),
            "included_in_print_rate": 1
        }]
    except Exception as e:
        log.error("Error building ERPNext tax lines: %s", e)
        return []

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
    walk_in           = defaults.get("server_walk_in_customer", "").strip() or "Cash Customer"
    customer          = (sale.get("customer_name") or "").strip()
    if not customer or customer.lower() in ("walk-in customer", "walk-in"):
        customer = walk_in

    waiter = str(sale.get("waiter_name") or "").strip()
    cashier = str(sale.get("cashier_name") or "").strip()
    frappe_waiter = _resolve_waiter_frappe_user(waiter)
    frappe_cashier = _resolve_waiter_frappe_user(cashier)

    terminal_id = str(defaults.get("server_terminal_id") or "").strip()
    shop_id     = str(defaults.get("server_shop_id") or "").strip()
    
    print(f"\n[DEBUG UPLOAD] retrieved server_terminal_id = '{terminal_id}'")
    print(f"[DEBUG UPLOAD] retrieved server_shop_id = '{shop_id}'")
    
    payload: dict = {
        "customer":               customer,
        "posting_date":           posting_date,
        "posting_time":           posting_time,
        "set_posting_time":       1,
        "currency":               currency,
        "conversion_rate":        conversion_rate,
        "is_pos":                 1 if terminal_id else 0,
        "update_stock":           1,
        "docstatus":              1,
        "is_return":              1 if (sale.get("receipt_type") in ("Credit Note", "Refund") or float(sale.get("total") or 0) < 0) else 0,
        "reference_number": str(sale.get("invoice_no", "")),
        "custom_waiter":          frappe_waiter,
        "pos_cashier":            frappe_waiter if frappe_waiter else frappe_cashier,
        "custom_verification_code":      str(sale.get("fiscal_verification_code") or ""),
    }

    if terminal_id:
        # We also pass shop_id or pos_profile as a fallback if needed
        payload["pos_profile"] = shop_id if shop_id else "Terminal 1"

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

    try:
        from services.credentials import get_system_mode
        if get_system_mode() == "saas":
            # Strip out all Frappe-specific fields to match exact SaaS payload
            keys_to_remove = ["is_pos", "is_return", "custom_waiter", "pos_cashier", 
                              "custom_verification_code", "taxes_and_charges", 
                              "is_on_account", "custom_is_on_account", "pos_profile", "terminal_id"]
            for k in keys_to_remove:
                if k in payload:
                    del payload[k]
            
            # Map cashier and owner specifically for SaaS mode
            saas_user = frappe_waiter if frappe_waiter else frappe_cashier
            payload["cashier"] = saas_user
            payload["owner"] = saas_user
            
            import json
            try:
                from database.db import get_connection
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    "SELECT mode_of_payment, paid_amount, currency, source_exchange_rate "
                    "FROM payment_entries WHERE sale_invoice_no = ?",
                    (sale.get("invoice_no"),)
                )
                rows = cur.fetchall()
                conn.close()
                frappe_payments = []
                
                if rows:
                    for r in rows:
                        mop, p_amt, p_curr, exch_rate = r
                        val = float(p_amt or 0)
                        if val > 0:
                            frappe_payments.append({
                                "payment_method": str(mop or "Cash"),
                                "amount": val,
                                "base_amount": val,
                                "currency": str(p_curr or currency),
                                "exchange_rate": float(exch_rate or 1.0),
                                "reference": None
                            })
                
                # Fallback if no splits were recorded, just map the main method
                if not frappe_payments:
                    val = float(sale.get("total", 0))
                    if val > 0:
                        frappe_payments.append({
                            "mode_of_payment": sale.get("method", "Cash"),
                            "payment_method": sale.get("method", "Cash"),
                            "amount": val,
                            "base_amount": val,
                            "currency": currency,
                            "exchange_rate": 1.0,
                            "reference": None
                        })
                
                if frappe_payments:
                    payload["payments"] = frappe_payments
                    # Map the default one to payload root too
                    payload["payment_method"] = frappe_payments[0]["payment_method"]
            except Exception as e:
                log.warning("Could not append saas payments for %s: %s", sale.get("id"), e)
    except Exception:
        pass

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

    No exchange-rate lookup is performed - USD invoices need none.
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
        l_disc    = float(it.get("discount") or 0) # Percentage

        if not item_code or qty <= 0:
            continue

        row: dict = {
            "item_code": item_code,
            "qty":       qty,
            "rate":      rate,
            "uom":       (it.get("uom") or "Nos"),
            "discount_percentage": l_disc,
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
        total_calculated += (rate * qty) * (1.0 - l_disc / 100.0)

    if not frappe_items:
        log.warning("[_build_payload_usd] Sale %s - no valid items.", sale.get("id"))
        return {}

    # Header-level discount
    da = float(sale.get("discount_amount") or 0)
    total_calculated -= da

    stored_total = float(sale.get("total_usd") or sale.get("total") or 0)
    if stored_total > 0 and abs(total_calculated - stored_total) > 0.05:
        log.warning(
            "[_build_payload_usd] Sale %s: computed net USD total %.4f differs from "
            "stored total %.4f (Line discs + Global disc applied)",
            sale.get("id"), total_calculated, stored_total,
        )

    payload = _base_payload_fields(
        sale, defaults, posting_date, posting_time,
        currency="USD", conversion_rate=1.0,
    )
    payload["items"]       = frappe_items
    # In Frappe, we send the gross total of items for grand_total if we apply 
    # discount_amount at the header, BUT if we want to match stored_total, 
    # let's see. Actually, Frappe recalculates it. 
    # Forcing grand_total to the net amount is safer for matching local DB.
    payload["grand_total"] = round(total_calculated, 2)
    payload["total"]       = round(total_calculated, 2)

    if da > 0:
        payload["discount_amount"]   = da
        payload["apply_discount_on"] = "Grand Total"

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

    Frappe recovers the USD base: rate_local × conversion_rate = price_usd  [OK]
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
        l_disc    = float(it.get("discount") or 0)

        if not item_code or qty <= 0:
            continue

        row: dict = {
            "item_code": item_code,
            "qty":       qty,
            "rate":      rate,
            "uom":       (it.get("uom") or "Nos"),
            "discount_percentage": l_disc,
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
        total_calculated += (rate * qty) * (1.0 - l_disc / 100.0)

    if not frappe_items:
        log.warning("[_build_payload_local_currency] Sale %s - no valid items.",
                    sale.get("id"))
        return {}

    # Header-level discount (in local currency)
    da_usd = float(sale.get("discount_amount") or 0)
    da_local = 0.0
    if da_usd > 0:
        da_local = round(da_usd * zwd_per_usd, 2)
        total_calculated -= da_local

    stored_total = float(sale.get("total") or 0)
    if stored_total > 0 and abs(total_calculated - stored_total) > 0.05:
        log.warning(
            "[_build_payload_local_currency] Sale %s: computed %s net total %.4f differs from "
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

    if da_local > 0:
        payload["discount_amount"]   = da_local
        payload["apply_discount_on"] = "Grand Total"

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
    log.debug("[_build_payload_mixed_to_usd] sale=%s - normalising to USD",
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
        l_disc        = float(it.get("discount") or 0)

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
            "discount_percentage": l_disc,
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
        total_calculated += (rate_usd * qty) * (1.0 - l_disc / 100.0)

    if not frappe_items:
        log.warning("[_build_payload_mixed_to_usd] Sale %s - no valid items.",
                    sale.get("id"))
        return {}

    # Header-level discount
    da = float(sale.get("discount_amount") or 0)
    total_calculated -= da

    stored_total_usd = float(sale.get("total_usd") or sale.get("total") or 0)
    if stored_total_usd > 0 and abs(total_calculated - stored_total_usd) > 0.05:
        log.warning(
            "[_build_payload_mixed_to_usd] Sale %s: computed net USD total %.4f "
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

    if da > 0:
        payload["discount_amount"]   = da
        payload["apply_discount_on"] = "Grand Total"

    return payload


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher - detects currency once, routes to exactly one builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_payload(sale: dict, items: list[dict], defaults: dict,
                   api_key: str = "", api_secret: str = "",
                   host: str = "") -> tuple[dict, bool]:
    """
    Detect the invoice currency and delegate to the appropriate builder.

    Returns (payload, is_mixed) so _push_sale never needs to re-derive
    the currency - eliminating the double-detection bug.

    Only ONE builder is ever called per sale - they are fully independent.

      "USD"   -> _build_payload_usd            (no exchange rate lookup)
      "ZWD"   -> _build_payload_local_currency (rates resolved for ZWD)
      "ZIG"   -> _build_payload_local_currency (rates resolved for ZIG)
      "ZWG"   -> _build_payload_local_currency (rates resolved for ZWG)
      "MIXED" -> _build_payload_mixed_to_usd   (normalise everything to USD)
    """
    invoice_currency = _detect_invoice_currency(sale, items)

    if invoice_currency in _LOCAL_CURRENCIES:
        payload = _build_payload_local_currency(
            sale, items, defaults, invoice_currency, api_key, api_secret, host
        )
        is_mixed = False
    elif invoice_currency == "USD":
        payload = _build_payload_usd(sale, items, defaults)
        is_mixed = False
    elif invoice_currency == "MIXED":
        payload = _build_payload_mixed_to_usd(sale, items, defaults, api_key, api_secret, host)
        is_mixed = True
    else:
        log.error("[_build_payload] Unhandled currency '%s' for sale %s - "
                  "falling back to USD builder.", invoice_currency, sale.get("id"))
        payload = _build_payload_usd(sale, items, defaults)
        is_mixed = False

    # Attach dynamic tax lines just like the Flutter app
    tax_lines = _build_erpnext_tax_lines(sale, items, defaults, host, api_key, api_secret)
    if tax_lines:
        payload["taxes"] = tax_lines
        # Remove the template so Frappe doesn't conflict
        if "taxes_and_charges" in payload:
            del payload["taxes_and_charges"]

    return payload, is_mixed


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
            return False   # sale not found - let it fail naturally below
        synced, frappe_ref = row
        if synced:
            return True
        if frappe_ref and str(frappe_ref).strip():
            return True
        return False
    except Exception as e:
        log.warning("[_is_already_synced] DB check failed for sale %s: %s - will proceed with push.", sale_id, e)
        return False   # safe default: if we can't check, try to push (Frappe 409 will catch it)


def _push_sale(sale: dict, api_key: str, api_secret: str,
               defaults: dict, host: str):
    """Push ONE invoice to Frappe.

    For single-currency sales (USD, ZIG, ZWD, ZWG) exactly ONE POST is ever
    made - there is no walk-in retry, and no HTTP-error retry that could
    produce a second invoice.

    The walk-in customer retry only fires for genuinely MIXED sales, and only
    on HTTP 403/417/500 from the first attempt.
    """
    inv_no  = sale.get("invoice_no", str(sale["id"]))
    walk_in = defaults.get("server_walk_in_customer", "").strip() or "Cash Customer"

    # ── GUARD: re-read synced flag from DB before doing anything ─────────────
    if _is_already_synced(sale["id"]):
        log.info("Sale %s (id=%s) is already synced in DB - skipping.", inv_no, sale["id"])
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
        log.warning("Sale %s - no valid items, skipping.", inv_no)
        return True

    url = f"{host}/api/resource/Sales%20Invoice"

    if is_mixed and payload.get("customer") != walk_in:
        attempts = [payload, {**payload, "customer": walk_in}]
        log.debug("Mixed currency sale %s - up to 2 attempts (walk-in fallback ready).", inv_no)
    else:
        attempts = [payload]
        log.debug("Single currency sale %s - exactly 1 attempt.", inv_no)

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
        log.info(f"\n============================================================")
        log.info(f"[FRAPPE UPLOAD] Payload for {inv_no}:")
        log.info(f"{_dumps(p)}")
        log.info(f"============================================================\n")
        
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
            with safe_urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                response_data = json.loads(resp.read().decode())
                name = (response_data.get("data") or {}).get("name", "")
                log.info("[OK] Sale %s -> Frappe %s", inv_no, name)
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
                    "Sale %s HTTP %s - retrying once with walk-in customer.", inv_no, e.code
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

    from services.credentials import get_system_mode
    if get_system_mode() == "odoo":
        return result
        
    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("No API credentials - skipping upload cycle.")
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
    # same logical transaction boundary - but we still need the atomic lock
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

    log.info("Starting upload cycle - %d sale(s) to push.", len(sales))

    # Clear stale locks AFTER fetching the snapshot - never before.
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
            log.info("Rate-limit pause - waiting 60 s…")
            time.sleep(60)

        # ─────────────────────────────────────────────────────────────────────
        # FIX 2 (atomic lock): try_lock_sale MUST be implemented as a single
        # atomic UPDATE … WHERE syncing = 0 AND synced = 0 with a ROWCOUNT
        # check - NOT a separate SELECT then UPDATE.  Two threads reading
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
            log.debug("Skipping sale %s - already being synced by another thread.", sale.get("invoice_no"))
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
                # a duplicate - Frappe's 409 dedup will catch it on the next retry.
                mark_synced_with_ref(sale["id"], frappe_ref)
                try:
                    from services.sync_errors_service import resolve
                    resolve("SI", sale.get("invoice_no", str(sale["id"])))
                except Exception:
                    pass
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

    log.info("Upload done - [OK] %d pushed  ❌ %d failed", result["pushed"], result["failed"])
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Background worker
# ─────────────────────────────────────────────────────────────────────────────

try:
    # pyrefly: ignore [missing-import]
    from PySide6.QtCore import QObject

    class UploadWorker(QObject):
        def __init__(self):
            super().__init__()
            self._running = True

        def stop(self):
            self._running = False

        def run(self) -> None:
            log.info("POS upload worker started (interval=%ds, max=%d/min).",
                     UPLOAD_INTERVAL, MAX_PER_MINUTE)
            while self._running:
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
    global _upload_thread_running
    _upload_thread_running = True
    def _loop():
        global _upload_thread_running
        while _upload_thread_running:
            try:
                push_unsynced_sales()
            except Exception as exc:
                log.error("Unhandled error in upload worker: %s", exc)
            time.sleep(UPLOAD_INTERVAL)
    t = threading.Thread(target=_loop, daemon=True, name="POSUploadThread")
    t.start()
    log.info("POS upload daemon thread started.")
    return {"thread": t, "worker": None}

def stop_upload_thread():
    global _upload_thread_running
    _upload_thread_running = False
    log.info("POS upload daemon stop requested.")
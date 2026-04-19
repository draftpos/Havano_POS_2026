from __future__ import annotations

import json
import logging
import time
import threading
import urllib.request
import urllib.error
from datetime import date

log = logging.getLogger("PaymentEntry")

SYNC_INTERVAL   = 15
REQUEST_TIMEOUT = 30

_RATE_CACHE: dict[str, float] = {}


def _get_exchange_rate(from_currency: str, to_currency: str,
                       transaction_date: str,
                       api_key: str, api_secret: str, host: str) -> float:
    if not from_currency or from_currency.upper() == to_currency.upper():
        return 1.0

    cache_key = f"{from_currency.upper()}::{to_currency.upper()}::{transaction_date}"
    if cache_key in _RATE_CACHE:
        return _RATE_CACHE[cache_key]

    try:
        import urllib.parse
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
        log.debug("Rate fetch failed (%s→%s): %s", from_currency, to_currency, e)

    return 0.0


_sync_lock: threading.Lock = threading.Lock()
_sync_thread: threading.Thread | None = None


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


def _get_gl_account_currency(gl_account_name: str, fallback: str = "USD") -> str:
    if not gl_account_name:
        return fallback
    try:
        from models.gl_account import get_account_by_name
        acct = get_account_by_name(gl_account_name)
        if acct:
            return (acct.get("account_currency") or fallback).upper()
    except Exception:
        pass
    return fallback


def _resolve_mop(raw_method: str, gl_account: str, currency: str) -> tuple[str, str]:
    """
    🔴 FIX: ALWAYS use the raw_method as the MOP name - DO NOT merge by GL account!
    This ensures that "Bank Accounts ZWD" and "CBZ ZWD" remain as separate methods.
    """
    from database.db import get_connection, fetchone_dict
    
    if not raw_method:
        raw_method = "Cash"
    
    log.info(f"[_resolve_mop] raw_method={raw_method}, gl_account={gl_account}, currency={currency}")
    
    # 🔴 FIX: DO NOT merge by GL account - use raw_method as-is
    # This prevents "Bank Accounts ZWD" and "CBZ ZWD" from being merged
    # into the same MOP just because they share a GL account.
    
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Try exact name match first
        cur.execute(
            "SELECT name, gl_account FROM modes_of_payment WHERE name = ?",
            (raw_method,)
        )
        row = fetchone_dict(cur)
        if row and row.get("gl_account"):
            log.info(f"[_resolve_mop] Found exact match: {row['name']} -> GL: {row['gl_account']}")
            return row["name"], row["gl_account"]
        
        # Try by currency if no exact match
        if currency:
            cur.execute("""
                SELECT name, gl_account FROM modes_of_payment 
                WHERE account_currency = ? AND gl_account IS NOT NULL AND gl_account != ''
            """, (currency.upper(),))
            cur.execute("""
                        SELECT name, gl_account FROM modes_of_payment 
                        WHERE name = ? AND account_currency = ?'
                        """), (raw_method, currency.upper())
            rows = cur.dict(cur)
            if row:
                return row["name"], row["gl_account"]
                # Return the FIRST matching by currency, but keep original method name
                
                 # 🔴 FIX: Keep original method name!
        
    except Exception as e:
        log.error(f"[_resolve_mop] Error: {e}")
    finally:
        conn.close()
    
    # Fallback - use raw_method as-is
    log.info(f"[_resolve_mop] Fallback: using raw_method='{raw_method}', gl_account='{gl_account}'")
    return raw_method, gl_account


def _resolve_amounts(sale: dict, override_rate: float = None) -> dict:
    _defaults = _get_defaults()
    base_currency = _defaults.get("server_company_currency", "USD").strip().upper() or "USD"
    currency = (sale.get("currency") or base_currency).strip().upper()
    
    amount = float(sale.get("paid_amount") or sale.get("total") or 0)
    
    if override_rate is not None:
        exch_rate = float(override_rate)
    elif currency == "USD":
        exch_rate = 1.0
    else:
        exch_rate = float(sale.get("exchange_rate") or 0)
        if exch_rate <= 0:
            try:
                from models.exchange_rate import get_rate
                rate = get_rate(currency, "USD")
                if rate and rate > 0:
                    exch_rate = float(rate)
                else:
                    inv = get_rate("USD", currency)
                    if inv and inv > 0:
                        exch_rate = 1.0 / float(inv)
            except Exception:
                exch_rate = 1.0
    
    if currency == "USD":
        amount_usd = amount
    else:
        amount_usd = round(amount * exch_rate, 4)
    
    amount_zwd = amount if currency in ("ZWD", "ZWG") else 0.0
    amount_zwg = amount if currency == "ZWG" else 0.0
    
    log.debug("[resolve_amounts] %s %.4f -> USD %.4f (rate=%.6f)", 
              currency, amount, amount_usd, exch_rate)
    
    return {
        "currency": currency,
        "amount": amount,
        "amount_usd": amount_usd,
        "amount_zwd": amount_zwd,
        "amount_zwg": amount_zwg,
        "exchange_rate": exch_rate,
        "received_amount": amount_usd,
    }


def create_payment_entry(sale: dict, override_rate: float = None,
                         override_account: str = None,
                         _is_split: bool = False) -> int | None:
    """
    🔴 FIX: ALWAYS create payment entry - NO duplicate check!
    """
    from database.db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    
    raw_method = str(sale.get("method") or "Cash").strip()
    _defaults = _get_defaults()
    _base_curr = _defaults.get("server_company_currency", "USD").strip().upper()
    
    log.info(f"[create_PE] ========== START ==========")
    log.info(f"[create_PE] sale_id={sale.get('id')}")
    log.info(f"[create_PE] raw_method={raw_method}")
    log.info(f"[create_PE] currency={sale.get('currency')}")
    log.info(f"[create_PE] paid_amount={sale.get('paid_amount')}")
    log.info(f"[create_PE] gl_account from sale: {sale.get('gl_account')}")
    log.info(f"[create_PE] override_account: {override_account}")
    
    resolved = _resolve_amounts(sale, override_rate)
    currency = resolved["currency"]
    amount = resolved["amount"]
    amount_usd = resolved["amount_usd"]
    amount_zwd = resolved["amount_zwd"]
    amount_zwg = resolved["amount_zwg"]
    exch_rate = resolved["exchange_rate"]
    received_amount = resolved["received_amount"]
    
    gl_hint = (override_account or sale.get("gl_account") or sale.get("paid_to") or "").strip()
    mop_name, gl_account = _resolve_mop(raw_method, gl_hint, currency)
    
    log.info(f"[create_PE] Resolved mop_name={mop_name}, gl_account={gl_account}")
    
    # 🔴🔴🔴 NO DUPLICATE CHECK - ALWAYS CREATE 🔴🔴🔴
    # Previously this would skip creating payment entries if a payment
    # with the same mode_of_payment already existed.
    # Now we ALWAYS create the payment entry.
    
    _walk_in = _defaults.get("server_walk_in_customer", "").strip() or "Default"
    customer = (sale.get("customer_name") or "").strip() or _walk_in
    inv_no = sale.get("invoice_no", "")
    inv_date = sale.get("invoice_date") or date.today().isoformat()
    
    try:
        cur.execute("""
            INSERT INTO payment_entries (
                sale_id, sale_invoice_no, frappe_invoice_ref,
                party, party_name,
                paid_amount, received_amount, source_exchange_rate,
                paid_to_account_currency, currency,
                paid_to, mode_of_payment,
                reference_no, reference_date,
                remarks, synced,
                amount_usd, amount_zwd, amount_zwg, exchange_rate
            ) OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
        """, (
            sale["id"], inv_no,
            sale.get("frappe_ref") or None,
            customer, customer,
            amount, received_amount, exch_rate,
            currency, currency,
            gl_account or None,
            mop_name,
            inv_no, inv_date,
            f"POS Payment — {mop_name}",
            amount_usd, amount_zwd, amount_zwg, exch_rate
        ))
        
        new_id = int(cur.fetchone()[0])
        conn.commit()
        conn.close()
        
        log.info(f"[create_PE] ✅✅✅ Created PE {new_id}: {mop_name} - {amount} {currency} (USD={amount_usd})")
        return new_id
        
    except Exception as e:
        log.error(f"[create_PE] ❌ Database error: {e}")
        conn.rollback()
        conn.close()
        return None


def create_split_payment_entries(sale: dict, splits: list[dict]) -> list[int]:
    """Creates payment entries for each split leg - NO duplicate checks."""
    ids = []
    _defaults = _get_defaults()
    _base_curr = _defaults.get("server_company_currency", "USD").strip().upper()
    
    log.info(f"[create_split_PE] ========== START ==========")
    log.info(f"[create_split_PE] Sale ID: {sale.get('id')}")
    log.info(f"[create_split_PE] Total splits received: {len(splits)}")
    
    for idx, split in enumerate(splits):
        log.info(f"[create_split_PE] --- Split {idx+1}/{len(splits)} ---")
        log.info(f"[create_split_PE] Split data: {split}")
        
        currency = (split.get("currency") or _base_curr).strip().upper()
        amount = float(split.get("paid_amount") or split.get("base_value") or 0)
        
        if amount <= 0:
            log.info(f"[create_split_PE] Split {idx+1}: Skipping zero amount")
            continue
        
        method = (split.get("method") or split.get("mode") or "Cash").strip()
        gl_account = (split.get("gl_account") or split.get("paid_to") or "").strip()
        rate = float(split.get("exchange_rate") or split.get("rate") or 1.0)
        
        log.info(f"[create_split_PE] method={method}, amount={amount}, currency={currency}, gl_account={gl_account}, rate={rate}")
        
        split_sale = dict(sale)
        split_sale["currency"] = currency
        split_sale["paid_amount"] = amount
        split_sale["total"] = amount
        split_sale["method"] = method
        split_sale["exchange_rate"] = rate
        split_sale["gl_account"] = gl_account
        split_sale.pop("tendered", None)
        
        new_id = create_payment_entry(
            split_sale,
            override_rate=rate,
            override_account=gl_account,
            _is_split=True,
        )
        if new_id:
            ids.append(new_id)
            log.info(f"[create_split_PE] ✅ Created PE {new_id} for {method}")
        else:
            log.warning(f"[create_split_PE] ❌ Failed to create PE for {method}")
    
    log.info(f"[create_split_PE] ========== END ==========")
    log.info(f"[create_split_PE] Created {len(ids)} out of {len(splits)} payment entries")
    return ids


def get_unsynced_payment_entries() -> list[dict]:
    from database.db import get_connection, fetchall_dicts
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT pe.*, s.frappe_ref AS sale_frappe_ref
        FROM payment_entries pe
        LEFT JOIN sales s ON s.id = pe.sale_id
        WHERE pe.synced = 0
          AND (pe.sync_attempts IS NULL OR pe.sync_attempts < 20)
          AND (pe.payment_type IS NULL OR pe.payment_type = 'Receive')
          AND (pe.frappe_invoice_ref IS NOT NULL
               OR s.frappe_ref IS NOT NULL)
        ORDER BY ISNULL(pe.sync_attempts, 0) ASC, pe.id DESC
    """)
    rows = fetchall_dicts(cur)
    conn.close()
    return rows


def get_payment_entries_by_sale(sale_id: int) -> list[dict]:
    from database.db import get_connection, fetchall_dicts
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM payment_entries WHERE sale_id = ? ORDER BY id
    """, (sale_id,))
    rows = fetchall_dicts(cur)
    conn.close()
    return rows


def mark_payment_synced(pe_id: int, frappe_payment_ref: str = "") -> None:
    from database.db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
        (frappe_payment_ref or None, pe_id)
    )
    cur.execute("""
        UPDATE sales SET payment_entry_ref=?, payment_synced=1
        WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
    """, (frappe_payment_ref or None, pe_id))
    conn.commit()
    conn.close()


def refresh_frappe_refs() -> int:
    from database.db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE pe
        SET pe.frappe_invoice_ref = s.frappe_ref
        FROM payment_entries pe
        JOIN sales s ON s.id = pe.sale_id
        WHERE pe.synced = 0
          AND (pe.frappe_invoice_ref IS NULL OR pe.frappe_invoice_ref = '')
          AND s.frappe_ref IS NOT NULL AND s.frappe_ref != ''
    """)
    count = cur.rowcount
    conn.commit()
    conn.close()
    return count


def _build_payload(pe: dict, defaults: dict,
                   api_key: str, api_secret: str, host: str) -> dict:
    company = defaults.get("server_company", "")
    base_currency = defaults.get("server_company_currency", "USD").strip().upper() or "USD"

    currency = (pe.get("currency") or pe.get("paid_to_account_currency") or base_currency).upper()
    stored_amount_usd = float(pe.get("amount_usd") or 0)
    native_amount = float(pe.get("paid_amount") or 0)

    exch_rate = float(pe.get("exchange_rate") or pe.get("source_exchange_rate") or 0)
    if exch_rate <= 0:
        exch_rate = 1.0

    if currency in ("ZWD", "ZWG") and exch_rate > 1:
        exch_rate = 1.0 / exch_rate

    if stored_amount_usd > 0:
        amount_usd = stored_amount_usd
    elif currency == "USD":
        amount_usd = native_amount
    else:
        amount_usd = round(native_amount * exch_rate, 4)

    frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
    stored_mop = (pe.get("mode_of_payment") or "").strip()
    paid_to = (pe.get("paid_to") or "").strip()
    mop_name, gl_account = _resolve_mop(stored_mop, paid_to, currency)
    paid_to_currency = _get_gl_account_currency(gl_account, fallback=base_currency)

    _walk_in = defaults.get("server_walk_in_customer", "").strip() or "Default"
    _WALK_IN_ALIASES = {"walk-in", "walk in", "walkin", ""}
    raw_party = (pe.get("party") or "").strip()
    party = _walk_in if raw_party.lower() in _WALK_IN_ALIASES else raw_party or _walk_in

    if currency in ("ZWD", "ZWG"):
        zwd_per_usd = round(1.0 / exch_rate, 8)
        if stored_amount_usd > 0:
            usd_amount = stored_amount_usd
        elif native_amount > 0 and exch_rate < 1:
            usd_amount = round(native_amount * exch_rate, 4)
        else:
            usd_amount = native_amount
        zwd_amount = round(usd_amount / exch_rate, 2)
        paid_amount_for_frappe = usd_amount
        received_amount_for_frappe = zwd_amount
        target_exch_rate = zwd_per_usd
        source_exch_rate = 1.0
    else:
        paid_amount_for_frappe = amount_usd
        received_amount_for_frappe = amount_usd
        target_exch_rate = 1.0
        source_exch_rate = 1.0

    log.info(
        "[build_payload] PE id=%d MOP='%s' GL='%s' currency=%s native=%.4f USD=%.4f paid_frappe=%.4f received_frappe=%.4f",
        pe.get("id", 0), mop_name, gl_account, currency, native_amount, amount_usd,
        paid_amount_for_frappe, received_amount_for_frappe
    )

    payload = {
        "doctype": "Payment Entry",
        "payment_type": "Receive",
        "party_type": "Customer",
        "party": party,
        "party_name": party,
        "paid_from_account_currency": base_currency,
        "paid_to_account_currency": paid_to_currency,
        "paid_amount": paid_amount_for_frappe,
        "received_amount": received_amount_for_frappe,
        "source_exchange_rate": source_exch_rate,
        "target_exchange_rate": target_exch_rate,
        "mode_of_payment": mop_name,
        "reference_no": pe.get("reference_no") or pe.get("sale_invoice_no", ""),
        "reference_date": (
            pe.get("reference_date").isoformat()
            if hasattr(pe.get("reference_date"), "isoformat")
            else pe.get("reference_date") or date.today().isoformat()
        ),
        "remarks": pe.get("remarks") or f"POS Payment — {mop_name}",
        "docstatus": 1,
    }

    if gl_account:
        payload["paid_to"] = gl_account
    if company:
        payload["company"] = company
    if frappe_inv:
        payload["references"] = [{
            "reference_doctype": "Sales Invoice",
            "reference_name": frappe_inv,
            "allocated_amount": paid_amount_for_frappe,
        }]
    print(payload)
    return payload


def _push_payment_entry(pe: dict, api_key: str, api_secret: str,
                        defaults: dict, host: str) -> str | None:
    pe_id = pe["id"]
    inv_no = pe.get("sale_invoice_no", str(pe_id))
    
    frappe_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "").strip()
    if not frappe_inv:
        log.warning("Payment %d — Sales Invoice not yet on Frappe, skipping.", pe_id)
        return None
    
    payload = _build_payload(pe, defaults, api_key, api_secret, host)
    log.info("Pushing PE %d: %s %.2f %s", pe_id, inv_no, float(pe.get("paid_amount", 0)), pe.get("currency", ""))
    
    url = f"{host}/api/resource/Payment%20Entry"
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload, default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o)).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"token {api_key}:{api_secret}",
        },
    )
    
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            name = (data.get("data") or {}).get("name", "")
            log.info("✅ PE %d → Frappe %s", pe_id, name)
            return name or "SYNCED"
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            msg = (err.get("exception") or err.get("message") or
                   str(err.get("_server_messages", "")) or f"HTTP {e.code}")
        except Exception:
            msg = f"HTTP {e.code}"
        if e.code == 409:
            log.info("PE %d already on Frappe (409)", pe_id)
            return "DUPLICATE"
        if e.code == 417 and ("already been fully paid" in msg.lower() or "already paid" in msg.lower()):
            log.info("PE %d — invoice already paid", pe_id)
            return "ALREADY_PAID"
        log.error("FAIL PE %d HTTP %s: %s", pe_id, e.code, msg[:200])
        _increment_sync_attempt(pe_id, f"HTTP {e.code}: {msg[:200]}")
        return None
    except Exception as e:
        log.error("Unexpected error pushing PE %d: %s", pe_id, e)
        _increment_sync_attempt(pe_id, str(e))
        return None


def _increment_sync_attempt(pe_id: int, error_msg: str):
    try:
        from database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE payment_entries 
            SET sync_attempts = ISNULL(sync_attempts, 0) + 1,
                last_error = ?
            WHERE id = ?
        """, (str(error_msg)[:500], pe_id))
        conn.commit()
        conn.close()
    except Exception as ex:
        log.debug("Failed to increment sync attempt: %s", ex)


def push_unsynced_payment_entries() -> dict:
    result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}
    
    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("No credentials — skipping payment entry sync.")
        return result
    
    host = _get_host()
    defaults = _get_defaults()
    
    updated = refresh_frappe_refs()
    if updated:
        log.info("Refreshed frappe_invoice_ref on %d PE(s).", updated)
    
    entries = get_unsynced_payment_entries()
    result["total"] = len(entries)
    
    if not entries:
        log.debug("No unsynced payment entries.")
        return result
    
    log.info("Pushing %d payment entry(ies) to Frappe…", len(entries))
    
    prev_inv = None
    for pe in entries:
        this_inv = (pe.get("frappe_invoice_ref") or pe.get("sale_frappe_ref") or "")
        if this_inv and this_inv == prev_inv:
            time.sleep(2.0)
        elif prev_inv is not None:
            time.sleep(0.5)
        prev_inv = this_inv
        
        frappe_name = _push_payment_entry(pe, api_key, api_secret, defaults, host)
        if frappe_name:
            mark_payment_synced(pe["id"], frappe_name)
            result["pushed"] += 1
        else:
            result["failed"] += 1
    
    log.info("Payment sync done — ✅ %d pushed ❌ %d failed", result["pushed"], result["failed"])
    return result


def _sync_loop():
    log.info("Payment entry sync daemon started (interval=%ds).", SYNC_INTERVAL)
    while True:
        if _sync_lock.acquire(blocking=False):
            try:
                push_unsynced_payment_entries()
            except Exception as e:
                log.error("Payment sync cycle error: %s", e)
            finally:
                _sync_lock.release()
        else:
            log.debug("Previous payment sync still running — skipping.")
        time.sleep(SYNC_INTERVAL)


def start_payment_sync_daemon() -> threading.Thread:
    global _sync_thread
    if _sync_thread and _sync_thread.is_alive():
        return _sync_thread
    t = threading.Thread(target=_sync_loop, daemon=True, name="PaymentSyncDaemon")
    t.start()
    _sync_thread = t
    log.info("Payment entry sync daemon started.")
    return t


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    print("Running one payment entry sync cycle...")
    r = push_unsynced_payment_entries()
    print(f"\nResult: {r['pushed']} pushed, {r['failed']} failed, {r['skipped']} skipped (of {r['total']} total)")
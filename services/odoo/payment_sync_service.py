import json
import logging
import time
import threading
import urllib.request
import urllib.error
from datetime import date

from services.credentials import get_all_credentials, get_system_mode
from services.odoo.sync_service import _get_host, get_defaults
from services.network_utils import safe_urlopen
from database.db import get_connection, fetchall_dicts

log = logging.getLogger("OdooPaymentSync")

SYNC_INTERVAL = 20
REQUEST_TIMEOUT = 60

_sync_lock = threading.Lock()
_sync_thread = None

def get_unsynced_payment_entries() -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT pe.*, s.frappe_ref AS sale_frappe_ref, s.odoo_invoice_id, s.customer_name
        FROM payment_entries pe
        LEFT JOIN sales s ON s.id = pe.sale_id
        WHERE pe.synced = 0
          AND (pe.sync_attempts IS NULL OR pe.sync_attempts < 60)
          AND (
                s.odoo_invoice_id IS NOT NULL
             OR (s.frappe_ref IS NOT NULL AND s.frappe_ref <> '' AND s.frappe_ref <> 'ODOO-SYNCED')
          )
        ORDER BY ISNULL(pe.sync_attempts, 0) ASC, pe.id DESC
    """)
    rows = fetchall_dicts(cur)
    conn.close()
    return rows

def mark_payment_synced(pe_id: int, odoo_payment_ref: str = "") -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE payment_entries SET synced=1, frappe_payment_ref=? WHERE id=?",
        (odoo_payment_ref or None, pe_id)
    )
    cur.execute("""
        UPDATE sales SET payment_entry_ref=?, payment_synced=1
        WHERE id = (SELECT sale_id FROM payment_entries WHERE id=?)
    """, (odoo_payment_ref or None, pe_id))
    conn.commit()
    conn.close()

def _increment_sync_attempt(pe_id: int, error_msg: str):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE payment_entries
            SET sync_attempts   = ISNULL(sync_attempts, 0) + 1,
                last_error      = ?,
                sync_error      = ?,
                last_attempt_at = GETDATE()
            WHERE id = ?
        """, (str(error_msg)[:500], str(error_msg), pe_id))
        conn.commit()
        conn.close()
    except Exception as ex:
        log.debug("Failed to increment sync attempt: %s", ex)

def _push_payment_entry(pe: dict, sid: str, host: str) -> str | None:
    pe_id = pe["id"]

    # Prefer the integer sale_order_id; fall back to the Odoo sale order name (frappe_ref)
    invoice_id   = pe.get("odoo_invoice_id")
    sale_ref_name = pe.get("sale_frappe_ref") or ""

    if not invoice_id and not sale_ref_name:
        log.warning("Payment %d - no Odoo reference, skipping.", pe_id)
        return None

    native_amount     = float(pe.get("paid_amount") or 0)
    stored_amount_usd = float(pe.get("amount_usd") or 0)
    amount_to_pay     = stored_amount_usd if stored_amount_usd > 0 else native_amount
    method = (pe.get("mode_of_payment") or "cash").lower()

    if "bank" in method:
        odoo_method = "Bank"
    elif "ecocash" in method or "mobile" in method:
        odoo_method = "Bank" # Defaulting to bank for mobile money unless a specific journal exists
    else:
        odoo_method = "Cash"

    p_date = pe.get("reference_date")
    if hasattr(p_date, "isoformat"):
        p_date = p_date.isoformat()
    elif not p_date:
        p_date = date.today().isoformat()
    else:
        p_date = str(p_date)

    # Build payload for saas_api Payment Entry
    payload = {
        "party": pe.get("customer_name") or "Default Customer",
        "paid_amount": amount_to_pay,
        "received_amount": amount_to_pay,
        "reference_no": pe.get("reference_no") or pe.get("sale_invoice_no") or f"POS-PAY-{int(time.time())}",
        "reference_date": p_date,
        "remarks": f"Payment for {sale_ref_name or pe.get('sale_invoice_no')} via POS",
        "docstatus": 1,
        "paid_to": odoo_method
    }
    
    if sale_ref_name:
        payload["references"] = [{"reference_doctype": "Sales Invoice", "reference_name": sale_ref_name}]

    log.info("Pushing PE %d: ref=%s / id=%s  amount=%.2f", pe_id, sale_ref_name, invoice_id, amount_to_pay)

    url = f"{host.rstrip('/')}/api/resource/Payment%20Entry"
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": sid,
        },
    )

    try:
        with safe_urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            if "error" not in data:
                name = (data.get("data") or {}).get("name", "ODOO-SYNCED")
                log.info("[OK] PE %d -> Odoo %s", pe_id, name)
                return name
            else:
                msg = data.get("error") or "Unknown error"
                log.error("FAIL PE %d Odoo Error: %s", pe_id, msg)
                _increment_sync_attempt(pe_id, msg)
                return None

    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            msg = err.get("error") or err.get("message") or f"HTTP {e.code}"
        except Exception:
            msg = f"HTTP {e.code}"
        
        log.error("FAIL PE %d HTTP %s: %s", pe_id, e.code, msg[:200])
        _increment_sync_attempt(pe_id, f"HTTP {e.code}: {msg[:200]}")
        return None

    except urllib.error.URLError as e:
        log.warning("Network error pushing PE %d: %s", pe_id, e.reason)
        _increment_sync_attempt(pe_id, f"Network: {e.reason}")
        return None

    except Exception as e:
        log.error("Unexpected error pushing PE %d: %s", pe_id, e)
        _increment_sync_attempt(pe_id, str(e))
        return None


def push_unsynced_payment_entries_odoo() -> dict:
    result = {"pushed": 0, "failed": 0, "skipped": 0, "total": 0}

    if get_system_mode() != "odoo":
        return result

    defaults = get_defaults() or {}
    if defaults.get("work_offline") == "1":
        return result

    sid = defaults.get("odoo_token") or get_all_credentials().get("odoo_token")
    if not sid:
        log.warning("No Odoo token - skipping payment entry sync.")
        return result

    host = defaults.get("server_api_host") or _get_host()
    
    entries = get_unsynced_payment_entries()
    result["total"] = len(entries)

    if not entries:
        return result

    log.info("Pushing %d payment entry(ies) to Odoo…", len(entries))

    for pe in entries:
        odoo_name = _push_payment_entry(pe, sid, host)
        if odoo_name:
            mark_payment_synced(pe["id"], odoo_name)
            result["pushed"] += 1
        elif odoo_name is None:
            result["skipped"] += 1
        else:
            result["failed"] += 1
        time.sleep(1)

    log.info("Odoo Payment sync done - [OK] %d pushed  ❌ %d failed  ⏭ %d skipped",
             result["pushed"], result["failed"], result["skipped"])
    return result

def _sync_loop():
    log.info("Odoo Payment sync daemon started (interval=%ds).", SYNC_INTERVAL)
    while True:
        if _sync_lock.acquire(blocking=False):
            try:
                push_unsynced_payment_entries_odoo()
            except Exception as e:
                log.error("Odoo Payment sync cycle error: %s", e)
            finally:
                _sync_lock.release()
        time.sleep(SYNC_INTERVAL)

def start_odoo_payment_sync_daemon() -> threading.Thread:
    global _sync_thread
    if _sync_thread and _sync_thread.is_alive():
        return _sync_thread
    t = threading.Thread(target=_sync_loop, daemon=True, name="OdooPaymentSync")
    t.start()
    _sync_thread = t
    log.info("Odoo Payment entry sync daemon started.")
    return t

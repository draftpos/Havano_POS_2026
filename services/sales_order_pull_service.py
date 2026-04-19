from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

log = logging.getLogger("SalesOrderPull")

REQUEST_TIMEOUT = 30
SYNC_INTERVAL   = 300          # 5 minutes — same cadence as quotation pull

_sync_lock  = threading.Lock()
_sync_thread: threading.Thread | None = None


# ---------------------------------------------------------------------------
# Credentials / host / defaults
# ---------------------------------------------------------------------------

def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        return "", ""


def _get_host() -> str:
    from services.site_config import get_host
    return get_host()


def _auth_headers(api_key: str, api_secret: str) -> dict:
    return {
        "Authorization": f"token {api_key}:{api_secret}",
        "Accept":        "application/json",
    }


# ---------------------------------------------------------------------------
# Frappe API
# ---------------------------------------------------------------------------

def _http_get_json(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode() or "{}")


_DOCTYPE_PATH = "Sales%20Order"   # the doctype's URL segment — space must be encoded


def _list_order_names(host: str, headers: dict) -> list[str]:
    """List every Sales Order name (submitted OR draft) the API user can see."""
    fields = urllib.parse.quote('["name"]', safe="")
    url = (f"{host}/api/resource/{_DOCTYPE_PATH}"
           f"?fields={fields}&limit_page_length=0")
    try:
        data = _http_get_json(url, headers)
    except urllib.error.HTTPError as e:
        log.error("[SO pull] list HTTP %s: %s", e.code, e.reason)
        return []
    except Exception as e:
        log.error("[SO pull] list failed: %s", e)
        return []
    return [r.get("name") for r in (data.get("data") or []) if r.get("name")]


def _fetch_order_doc(host: str, headers: dict, name: str) -> dict | None:
    """GET a single Sales Order doc so we get the items child table."""
    encoded = urllib.parse.quote(name, safe="")
    url = f"{host}/api/resource/{_DOCTYPE_PATH}/{encoded}"
    try:
        data = _http_get_json(url, headers)
        return data.get("data") or None
    except Exception as e:
        log.warning("[SO pull] fetch '%s' failed: %s", name, e)
        return None


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

_FRAPPE_DOCSTATUS_TO_STATUS = {
    0: "Draft",
    1: "Submitted",
    2: "Cancelled",
}


def _upsert_order(cur, doc: dict) -> int | None:
    """Insert or update a sales_order row + its items. Returns the local id."""
    frappe_name    = str(doc.get("name") or "").strip()
    if not frappe_name:
        return None

    customer_name  = doc.get("customer") or ""
    company        = doc.get("company")  or ""
    order_date     = str(doc.get("transaction_date") or "")[:10]
    delivery_date  = str(doc.get("delivery_date")    or "")[:10]
    total          = float(doc.get("grand_total")  or 0)
    advance_paid   = float(doc.get("advance_paid") or 0)
    balance_due    = round(max(total - advance_paid, 0.0), 4)
    frappe_status  = (doc.get("status") or "").strip()
    docstatus      = int(doc.get("docstatus") or 0)
    # Prefer the Frappe status string; fall back to docstatus mapping
    status = frappe_status or _FRAPPE_DOCSTATUS_TO_STATUS.get(docstatus, "Draft")

    # Match on frappe_ref (authoritative) or fall back to order_no for pre-sync rows
    cur.execute(
        "SELECT id FROM sales_order WHERE frappe_ref = ? OR order_no = ?",
        (frappe_name, frappe_name),
    )
    row = cur.fetchone()

    if row:
        order_id = int(row[0])
        cur.execute("""
            UPDATE sales_order
            SET    order_no       = ?,
                   customer_name  = ?,
                   company        = ?,
                   order_date     = ?,
                   delivery_date  = ?,
                   total          = ?,
                   deposit_amount = ?,
                   balance_due    = ?,
                   status         = ?,
                   synced         = 1,
                   frappe_ref     = ?
            WHERE  id = ?
        """, (frappe_name, customer_name, company,
              order_date, delivery_date,
              total, advance_paid, balance_due,
              status, frappe_name, order_id))
    else:
        cur.execute("""
            INSERT INTO sales_order (
                order_no, customer_name, company,
                order_date, delivery_date,
                total, deposit_amount, balance_due,
                status, synced, frappe_ref, created_at
            )
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (frappe_name, customer_name, company,
              order_date, delivery_date,
              total, advance_paid, balance_due,
              status, frappe_name,
              datetime.now().isoformat(timespec="seconds")))
        order_id = int(cur.fetchone()[0])

    # Replace items — simpler than diffing
    cur.execute("DELETE FROM sales_order_item WHERE sales_order_id = ?", (order_id,))
    for row_idx, it in enumerate(doc.get("items") or []):
        code = str(it.get("item_code") or "").strip()
        if not code:
            continue
        qty    = float(it.get("qty")    or 0)
        rate   = float(it.get("rate")   or 0)
        amount = float(it.get("amount") or round(qty * rate, 4))
        cur.execute("""
            INSERT INTO sales_order_item (
                sales_order_id, item_code, item_name, qty, rate, amount, warehouse
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (order_id,
              code,
              it.get("item_name") or code,
              qty, rate, amount,
              it.get("warehouse") or ""))
    return order_id


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def pull_sales_orders_from_frappe() -> dict:
    """Fetch every Sales Order from Frappe and upsert into the local DB.
    Returns a small summary dict so callers can log/inspect the run."""
    result = {"scanned": 0, "updated": 0, "errors": 0}

    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("[SO pull] no credentials — skipping.")
        return result

    host    = _get_host()
    headers = _auth_headers(api_key, api_secret)

    names = _list_order_names(host, headers)
    result["scanned"] = len(names)
    if not names:
        log.info("[SO pull] no Sales Orders returned.")
        return result

    from database.db import get_connection
    from models.sales_order import ensure_tables
    ensure_tables()

    conn = get_connection()
    cur  = conn.cursor()
    try:
        for n in names:
            doc = _fetch_order_doc(host, headers, n)
            if not doc:
                result["errors"] += 1
                continue
            try:
                order_id = _upsert_order(cur, doc)
                if order_id:
                    result["updated"] += 1
            except Exception as e:
                result["errors"] += 1
                log.warning("[SO pull] upsert '%s' failed: %s", n, e)
        conn.commit()
    finally:
        conn.close()

    log.info("[SO pull] scanned=%d  updated=%d  errors=%d",
             result["scanned"], result["updated"], result["errors"])
    return result


# ---------------------------------------------------------------------------
# Background daemon
# ---------------------------------------------------------------------------

def _sync_loop():
    log.info("Sales Order pull daemon started (interval=%ds).", SYNC_INTERVAL)
    while True:
        if _sync_lock.acquire(blocking=False):
            try:
                pull_sales_orders_from_frappe()
            except Exception as e:
                log.error("[SO pull] cycle error: %s", e)
            finally:
                _sync_lock.release()
        else:
            log.debug("[SO pull] previous cycle still running — skipping.")
        time.sleep(SYNC_INTERVAL)


def start_sales_order_pull_daemon() -> threading.Thread:
    global _sync_thread
    if _sync_thread and _sync_thread.is_alive():
        return _sync_thread
    t = threading.Thread(target=_sync_loop, daemon=True, name="SalesOrderPullDaemon")
    t.start()
    _sync_thread = t
    return t


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    r = pull_sales_orders_from_frappe()
    print(f"Sales Order pull — scanned={r['scanned']} updated={r['updated']} errors={r['errors']}")

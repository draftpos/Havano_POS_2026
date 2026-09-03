# =============================================================================
# services/invoice_sync_service.py
# (credentials delegated to services.credentials)
# =============================================================================

from __future__ import annotations

import json
import logging
import time
import threading
import urllib.request
import urllib.error

log = logging.getLogger("InvoiceSync")

SYNC_INTERVAL   = 10 * 60
PAGE_SIZE       = 100
REQUEST_TIMEOUT = 30

_sync_lock:   threading.Lock          = threading.Lock()
_sync_thread: threading.Thread | None = None


def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        pass
    return "", ""


from services.site_config import get_host as _get_host


def _fetch_frappe_invoices(api_key: str, api_secret: str, host: str) -> list[dict]:
    invoices: list[dict] = []
    page = 1
    while True:
        url = (
            f"{host}/api/method/havano_pos_integration.api.get_sales_invoice"
            f"?page={page}&limit={PAGE_SIZE}"
        )
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"token {api_key}:{api_secret}")
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
                data = json.loads(r.read().decode())
            msg         = data.get("message", {})
            page_items  = msg.get("invoices", []) if isinstance(msg, dict) else (msg or [])
            total_pages = msg.get("total_pages", 1) if isinstance(msg, dict) else 1
            if not page_items and isinstance(msg, list):
                page_items = msg
        except Exception as e:
            log.error("[invoice-sync] Page %d fetch failed: %s", page, e)
            break
        invoices.extend(page_items)
        log.debug("[invoice-sync] Page %d/%d — %d invoices", page, total_pages, len(page_items))
        if page >= total_pages or len(page_items) < PAGE_SIZE:
            break
        page += 1
    return invoices


def _get_local_invoice_map() -> dict[str, int]:
    try:
        from database.db import get_connection
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT id, invoice_no FROM sales WHERE invoice_no != ''")
        rows = cur.fetchall(); conn.close()
        return {row[1]: row[0] for row in rows if row[1]}
    except Exception as e:
        log.error("[invoice-sync] Could not read local invoice map: %s", e)
        return {}


def sync_invoices_from_frappe() -> dict:
    result = {"matched": 0, "unmatched": 0, "already_set": 0, "errors": 0, "total_frappe": 0}

    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("[invoice-sync] No credentials — skipping.")
        return result

    host = _get_host()
    frappe_invoices = _fetch_frappe_invoices(api_key, api_secret, host)
    result["total_frappe"] = len(frappe_invoices)

    if not frappe_invoices:
        log.info("[invoice-sync] No invoices returned from Frappe.")
        return result

    local_map = _get_local_invoice_map()

    try:
        from database.db import get_connection
        conn = get_connection(); cur = conn.cursor()
    except Exception as e:
        log.error("[invoice-sync] DB connection failed: %s", e)
        return result

    for inv in frappe_invoices:
        frappe_name  = (inv.get("name") or "").strip()
        local_inv_no = (inv.get("custom_sales_reference") or "").strip()

        if not frappe_name or not local_inv_no:
            result["unmatched"] += 1
            continue

        sale_id = local_map.get(local_inv_no)
        if not sale_id:
            result["unmatched"] += 1
            log.debug("[invoice-sync] No local match for Frappe ref '%s'", local_inv_no)
            continue

        try:
            cur.execute("SELECT frappe_ref, synced FROM sales WHERE id = ?", (sale_id,))
            row = cur.fetchone()
            if row and row[0] == frappe_name and row[1] == 1:
                result["already_set"] += 1
                continue
            cur.execute("""
                UPDATE sales SET frappe_ref = ?, synced = 1 WHERE id = ?
            """, (frappe_name, sale_id))
            result["matched"] += 1
            log.info("[invoice-sync] ✅ Local %s → Frappe %s", local_inv_no, frappe_name)
        except Exception as e:
            log.error("[invoice-sync] Error updating sale %s: %s", sale_id, e)
            result["errors"] += 1

    conn.commit()
    conn.close()

    log.info(
        "[invoice-sync] Done — %d matched, %d already set, %d unmatched, %d errors (of %d)",
        result["matched"], result["already_set"], result["unmatched"],
        result["errors"], result["total_frappe"],
    )
    return result


def _sync_loop():
    log.info("[invoice-sync] Daemon started (interval=%ds).", SYNC_INTERVAL)
    while True:
        if _sync_lock.acquire(blocking=False):
            try:
                sync_invoices_from_frappe()
            except Exception as e:
                log.error("[invoice-sync] Cycle error: %s", e)
            finally:
                _sync_lock.release()
        else:
            log.debug("[invoice-sync] Previous sync still running — skipping.")
        time.sleep(SYNC_INTERVAL)


def start_invoice_sync_daemon() -> threading.Thread:
    global _sync_thread
    if _sync_thread and _sync_thread.is_alive():
        return _sync_thread
    t = threading.Thread(target=_sync_loop, daemon=True, name="InvoiceSyncDaemon")
    t.start()
    _sync_thread = t
    log.info("[invoice-sync] Daemon thread started.")
    return t


if __name__ == "__main__":
    import logging as _l
    _l.basicConfig(level=_l.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    r = sync_invoices_from_frappe()
    print(f"matched={r['matched']} already_set={r['already_set']} unmatched={r['unmatched']} errors={r['errors']}")
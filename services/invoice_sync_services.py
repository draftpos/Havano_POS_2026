# =============================================================================
# services/invoice_sync_service.py
#
#  Pulls Sales Invoices from Frappe and updates local sales records with the
#  authoritative Frappe document name (frappe_ref).
#
#  Matching logic:
#    Frappe invoice field  →  Local sales field
#    custom_sales_reference  →  invoice_no
#
#  What gets written back:
#    frappe_ref   — the Frappe document name (e.g. ACC-SINV-2026-00565)
#    synced = 1   — marks the sale as synced if Frappe has it
#
#  Runs every SYNC_INTERVAL seconds in a daemon thread.
#  Also callable on-demand via sync_invoices_from_frappe().
# =============================================================================

from __future__ import annotations

import json
import logging
import time
import threading
import urllib.request
import urllib.error

log = logging.getLogger("InvoiceSync")

SYNC_INTERVAL   = 10 * 60   # 10 minutes
PAGE_SIZE       = 100
REQUEST_TIMEOUT = 30

_sync_lock:   threading.Lock          = threading.Lock()
_sync_thread: threading.Thread | None = None


# =============================================================================
# CREDENTIALS / HOST
# =============================================================================

def _get_credentials() -> tuple[str, str]:
    try:
        from services.auth_service import get_session
        s = get_session()
        if s.get("api_key") and s.get("api_secret"):
            return s["api_key"], s["api_secret"]
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


def _get_host() -> str:
    try:
        from models.company_defaults import get_defaults
        host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
        if host:
            return host
    except Exception:
        pass
    return "https://apk.havano.cloud"


# =============================================================================
# FETCH FRAPPE INVOICES (paginated)
# =============================================================================

def _fetch_frappe_invoices(api_key: str, api_secret: str, host: str) -> list[dict]:
    """
    Fetches all Sales Invoices from Frappe via the custom endpoint.
    Returns list of dicts with at minimum: name, custom_sales_reference
    """
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

            # Fallback: some endpoints return a flat list directly
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


# =============================================================================
# CORE SYNC LOGIC
# =============================================================================

def _get_local_invoice_map() -> dict[str, int]:
    """
    Returns {invoice_no: sale_id} for all local sales.
    Used to match Frappe's custom_sales_reference back to a local sale.
    """
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
    """
    Main sync function.
    - Fetches all Frappe Sales Invoices
    - Matches each to a local sale via custom_sales_reference → invoice_no
    - Updates frappe_ref and synced=1 on matched local sales
    Returns summary dict.
    """
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

    local_map = _get_local_invoice_map()  # {invoice_no → sale_id}

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
            # Invoice created directly in Frappe — no local counterpart
            result["unmatched"] += 1
            continue

        sale_id = local_map.get(local_inv_no)
        if not sale_id:
            # Frappe invoice references a local invoice_no we don't have
            result["unmatched"] += 1
            log.debug("[invoice-sync] No local match for Frappe ref '%s'", local_inv_no)
            continue

        try:
            # Check if already set to the same value (skip unnecessary writes)
            cur.execute("SELECT frappe_ref, synced FROM sales WHERE id = ?", (sale_id,))
            row = cur.fetchone()
            if row and row[0] == frappe_name and row[1] == 1:
                result["already_set"] += 1
                continue

            # Update frappe_ref and mark synced
            cur.execute("""
                UPDATE sales
                SET frappe_ref = ?, synced = 1
                WHERE id = ?
            """, (frappe_name, sale_id))
            result["matched"] += 1
            log.info("[invoice-sync] ✅ Local %s → Frappe %s", local_inv_no, frappe_name)

        except Exception as e:
            log.error("[invoice-sync] Error updating sale %s: %s", sale_id, e)
            result["errors"] += 1

    conn.commit()
    conn.close()

    log.info(
        "[invoice-sync] Done — %d matched, %d already set, %d unmatched, "
        "%d errors (of %d Frappe invoices)",
        result["matched"], result["already_set"], result["unmatched"],
        result["errors"], result["total_frappe"],
    )
    return result


# =============================================================================
# BACKGROUND DAEMON THREAD
# =============================================================================

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
    """
    Start the Frappe → Local invoice reference sync daemon.
    Non-blocking — safe to call from MainWindow.__init__.
    """
    global _sync_thread
    if _sync_thread and _sync_thread.is_alive():
        return _sync_thread
    t = threading.Thread(target=_sync_loop, daemon=True, name="InvoiceSyncDaemon")
    t.start()
    _sync_thread = t
    log.info("[invoice-sync] Daemon thread started.")
    return t


# =============================================================================
# DEBUG
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    print("Running one invoice sync cycle...")
    r = sync_invoices_from_frappe()
    print(
        f"\nResult: {r['matched']} matched, {r['already_set']} already set, "
        f"{r['unmatched']} unmatched, {r['errors']} errors "
        f"(of {r['total_frappe']} Frappe invoices)"
    )
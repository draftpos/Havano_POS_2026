# =============================================================================
# services/sales_sync_service.py
#
# Sales Invoice Sync — pulls remote invoices into the local DB every 60 seconds.
#
# TWO modes:
#   1.  In-process QThread  →  call start_sales_sync_thread() from main.py
#                              on app startup.  No Windows service install needed.
#   2.  Windows Service     →  install/start/stop/remove/debug via pywin32
#       py services\sales_sync_service.py install
#       py services\sales_sync_service.py start
#       py services\sales_sync_service.py stop
#       py services\sales_sync_service.py remove
#       py services\sales_sync_service.py debug      ← runs in console, Ctrl-C to stop
#
# Dependencies:
#   pip install pywin32          (Windows service mode only)
#   pip install pyodbc           (already in project)
# =============================================================================

from __future__ import annotations

import logging
import os
import sys
import time
import threading
from datetime import datetime

import requests

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SalesSync] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("SalesSync")

# ── Config ───────────────────────────────────────────────────────────────────
SYNC_INTERVAL_SECONDS = 60          # run every 1 minute
PAGE_SIZE             = 20          # invoices per fetch
API_URL               = (
    "https://apk.havano.cloud/api/method/"
    "havano_pos_integration.api.get_sales_invoice"
)

# Items whose name contains these keywords are TAX rows — skip for sale_items
TAX_KEYWORDS = ("tax", "vat", "levy", "duty", "charge")


# =============================================================================
# HELPERS
# =============================================================================

def _is_tax_item(item_name: str) -> bool:
    """Return True if the item is a tax/levy line that should not be stored."""
    return any(kw in item_name.lower() for kw in TAX_KEYWORDS)


def _get_credentials() -> tuple[str, str]:
    """
    Read api_key / api_secret.
    Priority: 1) live auth session  2) company_defaults DB  3) env vars.
    Reading from the session means credentials are available immediately
    after login without any DB round-trip or timing issues.
    """
    # 1 — live in-memory session (set by auth_service at login, always fresh)
    try:
        from services.auth_service import get_session
        s = get_session()
        if s.get("api_key") and s.get("api_secret"):
            return s["api_key"], s["api_secret"]
    except Exception as exc:
        log.debug("Could not read from auth session: %s", exc)

    # 2 — company_defaults table (persists across restarts)
    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "SELECT api_key, api_secret FROM company_defaults WHERE id = 1"
        )
        row = cur.fetchone()
        conn.close()
        if row and row[0] and row[1]:
            return row[0], row[1]
    except Exception as exc:
        log.debug("Could not read credentials from DB: %s", exc)

    # 3 — environment variables (useful for Windows service / headless mode)
    api_key    = os.environ.get("HAVANO_API_KEY",    "")
    api_secret = os.environ.get("HAVANO_API_SECRET", "")
    return api_key, api_secret


def _auth_header(api_key: str, api_secret: str) -> dict:
    return {"Authorization": f"token {api_key}:{api_secret}"}


# =============================================================================
# DB UPSERT  (no duplicates — match on invoice_no)
# =============================================================================

def _upsert_invoices(invoices: list[dict]) -> tuple[int, int]:
    """
    Insert-or-update invoices fetched from the API.
    Returns (inserted, updated) counts.
    """
    try:
        from database.db import get_connection
    except ImportError:
        log.error("Cannot import database.db — make sure PYTHONPATH is set.")
        return 0, 0

    inserted = updated = 0

    try:
        conn = get_connection()
        cur  = conn.cursor()
    except Exception as exc:
        log.error("DB connection failed: %s", exc)
        return 0, 0

    try:
        for inv in invoices:
            invoice_no   = inv.get("name", "")
            customer     = inv.get("customer_name", inv.get("customer", ""))
            company      = inv.get("company", "")
            grand_total  = float(inv.get("grand_total", inv.get("total", 0)) or 0)
            posting_date = inv.get("posting_date", "")
            posting_time = inv.get("posting_time", "")
            total_qty    = float(inv.get("total_qty", 0) or 0)

            # Build created_at datetime string for display
            try:
                # posting_time may have fractional seconds  e.g. "9:55:0.6157"
                pt = posting_time.split(".")[0]    # strip microseconds
                created_at = f"{posting_date} {pt}"
            except Exception:
                created_at = posting_date

            # ── Check existence ───────────────────────────────────────────
            cur.execute(
                "SELECT id FROM sales WHERE invoice_no = ?", (invoice_no,)
            )
            existing = cur.fetchone()

            if existing:
                # UPDATE header
                cur.execute("""
                    UPDATE sales
                    SET    customer_name = ?,
                           company_name  = ?,
                           total         = ?,
                           subtotal      = ?,
                           total_items   = ?,
                           invoice_date  = ?,
                           synced        = 1
                    WHERE  invoice_no = ?
                """, (
                    customer, company,
                    grand_total, grand_total,
                    total_qty,
                    posting_date,
                    invoice_no,
                ))
                sale_id = existing[0]

                # Replace items: delete old, re-insert new
                cur.execute("DELETE FROM sale_items WHERE sale_id = ?", (sale_id,))
                _insert_items(cur, sale_id, inv.get("items", []))
                updated += 1

            else:
                # INSERT header
                cur.execute("""
                    INSERT INTO sales (
                        invoice_no, invoice_date, customer_name, company_name,
                        total, subtotal, total_items,
                        tendered, method, currency,
                        cashier_id, cashier_name, customer_contact,
                        kot, receipt_type, footer,
                        total_vat, discount_amount, change_amount,
                        synced, created_at, invoice_number
                    ) VALUES (
                        ?, ?, ?, ?,
                        ?, ?, ?,
                        0, 'API', 'USD',
                        NULL, '', '',
                        '', 'Invoice', '',
                        0, 0, 0,
                        1, ?, 0
                    )
                """, (
                    invoice_no, posting_date, customer, company,
                    grand_total, grand_total, total_qty,
                    created_at,
                ))

                # Get the newly inserted id
                cur.execute("SELECT @@IDENTITY")
                sale_id = int(cur.fetchone()[0])

                _insert_items(cur, sale_id, inv.get("items", []))
                inserted += 1

        conn.commit()
    except Exception as exc:
        log.error("Upsert error: %s", exc)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return inserted, updated


def _insert_items(cur, sale_id: int, items: list[dict]) -> None:
    """Insert sale_items rows, skipping pure tax lines."""
    for item in items:
        name = item.get("item_name", "")
        if _is_tax_item(name):
            continue

        qty   = float(item.get("qty",    0) or 0)
        price = float(item.get("rate",   0) or 0)
        total = float(item.get("amount", 0) or 0)

        cur.execute("""
            INSERT INTO sale_items (
                sale_id, product_name, qty, price, total,
                part_no, discount, tax, tax_type, tax_rate, tax_amount, remarks
            ) VALUES (
                ?, ?, ?, ?, ?,
                '', 0, '', '', 0, 0, ''
            )
        """, (sale_id, name, qty, price, total))


# =============================================================================
# SYNC LOGIC
# =============================================================================

def run_sync_once() -> None:
    """Fetch up to PAGE_SIZE invoices and upsert them."""
    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("No API credentials — skipping sync cycle.")
        return

    headers = _auth_header(api_key, api_secret)
    params  = {"limit": PAGE_SIZE}

    try:
        resp = requests.get(API_URL, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        log.warning("API request failed: %s", exc)
        return
    except ValueError as exc:
        log.warning("Invalid JSON from API: %s", exc)
        return

    invoices = data.get("message", [])
    if not isinstance(invoices, list):
        log.warning("Unexpected API response shape.")
        return

    if not invoices:
        log.debug("No invoices returned this cycle.")
        return

    inserted, updated = _upsert_invoices(invoices)
    log.info(
        "Sync complete — %d new, %d updated (of %d received)",
        inserted, updated, len(invoices),
    )


# =============================================================================
# MODE 1 — QThread (auto-start when app launches)
# =============================================================================

def start_sales_sync_thread() -> object:
    """
    Start the sync loop in a background QThread.
    Call this from main.py after the QApplication is created:

        from services.sales_sync_service import start_sales_sync_thread
        _sales_sync_worker = start_sales_sync_thread()   # keep reference alive

    Returns the QThread object (keep a reference so it isn't GC'd).
    """
    try:
        from PySide6.QtCore import QThread, Signal, QObject  # type: ignore

        class _Worker(QObject):
            def run(self) -> None:
                log.info("Sales sync thread started (interval=%ds).", SYNC_INTERVAL_SECONDS)
                while True:
                    try:
                        run_sync_once()
                    except Exception as exc:
                        log.error("Unhandled error in sync: %s", exc)
                    time.sleep(SYNC_INTERVAL_SECONDS)

        thread = QThread()
        worker = _Worker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        thread.start()
        log.info("Sales sync QThread started.")
        # Keep both alive so GC doesn't collect them
        thread._worker = worker
        return thread

    except ImportError:
        # Fallback: plain daemon thread (no PySide6 available)
        log.info("PySide6 not available — using daemon thread instead.")
        return _start_daemon_thread()


def _start_daemon_thread() -> threading.Thread:
    """Plain-Python daemon thread fallback."""
    def _loop():
        log.info("Sales sync daemon thread started (interval=%ds).", SYNC_INTERVAL_SECONDS)
        while True:
            try:
                run_sync_once()
            except Exception as exc:
                log.error("Unhandled error in sync: %s", exc)
            time.sleep(SYNC_INTERVAL_SECONDS)

    t = threading.Thread(target=_loop, daemon=True, name="SalesSyncThread")
    t.start()
    return t


# =============================================================================
# MODE 2 — Windows Service (pywin32)
# =============================================================================

try:
    import win32serviceutil   # type: ignore
    import win32service       # type: ignore
    import win32event         # type: ignore
    import servicemanager     # type: ignore

    class SalesSyncWindowsService(win32serviceutil.ServiceFramework):
        _svc_name_        = "HavanoSalesSyncService"
        _svc_display_name_= "Havano POS — Sales Sync Service"
        _svc_description_ = (
            "Pulls sales invoices from the Havano cloud API every 60 seconds "
            "and upserts them into the local SQL Server database."
        )

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)
            self._running    = True

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self._running = False
            win32event.SetEvent(self._stop_event)

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )
            log.info("Windows service starting.")
            self._run_loop()

        def _run_loop(self):
            while self._running:
                try:
                    run_sync_once()
                except Exception as exc:
                    log.error("Unhandled error in service loop: %s", exc)

                # Wait SYNC_INTERVAL_SECONDS or until stop signal
                result = win32event.WaitForSingleObject(
                    self._stop_event,
                    SYNC_INTERVAL_SECONDS * 1000,   # milliseconds
                )
                if result == win32event.WAIT_OBJECT_0:
                    break

            log.info("Windows service stopped.")

    _WIN32_AVAILABLE = True

except ImportError:
    _WIN32_AVAILABLE = False


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Add project root to path so database/services can be imported
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        # ── Debug mode: run sync loop in console ──────────────────────────
        print("[debug] Running sync loop. Press Ctrl-C to stop.")
        while True:
            try:
                run_sync_once()
            except KeyboardInterrupt:
                print("\n[debug] Stopped.")
                break
            except Exception as exc:
                log.error("Error: %s", exc)
            time.sleep(SYNC_INTERVAL_SECONDS)

    elif _WIN32_AVAILABLE:
        # ── Windows service install/start/stop/remove ─────────────────────
        win32serviceutil.HandleCommandLine(SalesSyncWindowsService)

    else:
        print("pywin32 is not installed.")
        print("To install: pip install pywin32")
        print("To run a debug loop: py services\\sales_sync_service.py debug")
        sys.exit(1)
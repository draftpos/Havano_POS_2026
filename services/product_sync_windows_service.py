# # =============================================================================
# # services/product_sync_windows_service.py
# #
# #  Windows Service that keeps the local product catalogue in sync with
# #  apk.havano.cloud every N minutes without requiring a user to be logged in.
# #
# #  REQUIREMENTS
# #  ────────────
# #  pip install pywin32
# #
# #  INSTALL / MANAGE
# #  ────────────────
# #  # Install (run as Administrator):
# #  python services\product_sync_windows_service.py install
# #
# #  # Start / Stop / Remove:
# #  python services\product_sync_windows_service.py start
# #  python services\product_sync_windows_service.py stop
# #  python services\product_sync_windows_service.py remove
# #
# #  # Run interactively for testing (no install needed):
# #  python services\product_sync_windows_service.py debug
# #
# #  CREDENTIALS
# #  ──────────
# #  The service reads api_key and api_secret from the company_defaults table
# #  (saved there on the last successful online login).  If they are missing,
# #  the service logs a warning and skips the sync cycle.
# # =============================================================================

# import sys
# import os
# import time
# import logging
# import servicemanager
# import win32event
# import win32service
# import win32serviceutil

# # ── Make sure the project root is on the path ────────────────────────────────
# _HERE = os.path.dirname(os.path.abspath(__file__))
# _ROOT = os.path.dirname(_HERE)   # one level up from services/
# if _ROOT not in sys.path:
#     sys.path.insert(0, _ROOT)

# # ── Logging to Windows Event Log + a rotating file ───────────────────────────
# _LOG_PATH = os.path.join(_ROOT, "logs", "product_sync_service.log")
# os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)

# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s  [%(levelname)s]  %(message)s",
#     handlers=[
#         logging.FileHandler(_LOG_PATH, encoding="utf-8"),
#         logging.StreamHandler(sys.stdout),
#     ],
# )
# log = logging.getLogger("ProductSyncService")

# # ── How often to sync (seconds) ──────────────────────────────────────────────
# SYNC_INTERVAL_SECONDS = 5 * 60   # 5 minutes — change as needed


# # =============================================================================
# # SERVICE CLASS
# # =============================================================================
# class ProductSyncService(win32serviceutil.ServiceFramework):
#     _svc_name_        = "HavanoProductSync"
#     _svc_display_name_ = "Havano POS — Product Sync Service"
#     _svc_description_  = (
#         "Periodically syncs product catalogue from apk.havano.cloud "
#         "into the local SQL Server database."
#     )

#     def __init__(self, args):
#         win32serviceutil.ServiceFramework.__init__(self, args)
#         self._stop_event = win32event.CreateEvent(None, 0, 0, None)
#         self._running    = True

#     # ── SCM callbacks ─────────────────────────────────────────────────────────
#     def SvcStop(self):
#         log.info("Stop signal received.")
#         self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
#         self._running = False
#         win32event.SetEvent(self._stop_event)

#     def SvcDoRun(self):
#         servicemanager.LogMsg(
#             servicemanager.EVENTLOG_INFORMATION_TYPE,
#             servicemanager.PYS_SERVICE_STARTED,
#             (self._svc_name_, ""),
#         )
#         log.info("Havano Product Sync Service started.")
#         self._main_loop()

#     # ── Main loop ─────────────────────────────────────────────────────────────
#     def _main_loop(self):
#         log.info(f"Sync interval: {SYNC_INTERVAL_SECONDS}s  "
#                  f"({SYNC_INTERVAL_SECONDS // 60} min)")

#         # Run immediately on startup, then on interval
#         self._run_sync()

#         while self._running:
#             # Wait for stop signal or next interval
#             rc = win32event.WaitForSingleObject(
#                 self._stop_event,
#                 SYNC_INTERVAL_SECONDS * 1000   # milliseconds
#             )
#             if rc == win32event.WAIT_OBJECT_0:
#                 break   # stop was signalled
#             if self._running:
#                 self._run_sync()

#         log.info("Havano Product Sync Service stopped.")

#     # ── Single sync run ───────────────────────────────────────────────────────
#     def _run_sync(self):
#         log.info("─── Starting product sync ───")
#         try:
#             api_key, api_secret = _load_credentials()
#         except Exception as e:
#             log.warning(f"Could not load credentials: {e}  — skipping cycle.")
#             return

#         if not api_key or not api_secret:
#             log.warning(
#                 "No API credentials in company_defaults. "
#                 "Login online at least once to populate them."
#             )
#             return

#         try:
#             from services.sync_service import sync_products, format_sync_result
#             result = sync_products(api_key=api_key, api_secret=api_secret)
#             log.info(format_sync_result(result))
#             if result.get("errors"):
#                 for err in result["errors"][:5]:
#                     log.warning(f"  Sync error: {err}")
#         except Exception as e:
#             log.error(f"Sync failed with exception: {e}", exc_info=True)


# # =============================================================================
# # CREDENTIAL LOADER
# # =============================================================================

# def _load_credentials() -> tuple[str, str]:
#     """
#     Reads api_key / api_secret saved by auth_service into company_defaults.
#     Falls back to environment variables HAVANO_API_KEY / HAVANO_API_SECRET.
#     """
#     # 1. Try environment variables first (useful for Docker / CI)
#     env_key    = os.environ.get("HAVANO_API_KEY", "").strip()
#     env_secret = os.environ.get("HAVANO_API_SECRET", "").strip()
#     if env_key and env_secret:
#         return env_key, env_secret

#     # 2. Try company_defaults table
#     try:
#         from models.company_defaults import get_defaults
#         defaults   = get_defaults()
#         api_key    = str(defaults.get("api_key")    or "").strip()
#         api_secret = str(defaults.get("api_secret") or "").strip()
#         return api_key, api_secret
#     except Exception as e:
#         raise RuntimeError(f"company_defaults unavailable: {e}")


# # =============================================================================
# # DEBUG / INTERACTIVE MODE
# # =============================================================================

# def _run_debug():
#     """
#     Runs one sync cycle in the foreground — useful for testing without
#     installing the service.  Reads credentials the same way the service does.
#     """
#     log.info("=== DEBUG MODE — running one sync cycle ===")
#     try:
#         api_key, api_secret = _load_credentials()
#     except Exception as e:
#         log.error(f"Credential error: {e}")
#         sys.exit(1)

#     if not api_key or not api_secret:
#         log.error(
#             "No credentials found. "
#             "Set HAVANO_API_KEY / HAVANO_API_SECRET env vars, "
#             "or login online first to populate company_defaults."
#         )
#         sys.exit(1)

#     from services.sync_service import sync_products, format_sync_result
#     result = sync_products(api_key=api_key, api_secret=api_secret)
#     print("\n" + format_sync_result(result))
#     if result.get("errors"):
#         print("\nErrors:")
#         for e in result["errors"]:
#             print(f"  • {e}")


# # =============================================================================
# # ENTRY POINT
# # =============================================================================

# if __name__ == "__main__":
#     if len(sys.argv) == 2 and sys.argv[1].lower() == "debug":
#         _run_debug()
#     else:
#         win32serviceutil.HandleCommandLine(ProductSyncService)

# =============================================================================
# services/product_sync_windows_service.py
#
#  Windows Service — keeps local product catalogue in sync with Frappe.
#
#  KEY BEHAVIOURS
#  ──────────────
#  • Non-blocking: sync runs in a daemon thread so login/UI is never held up.
#  • Smart diff: fetches all remote part_no values first, then only pulls
#    records that are NEW or have changed (compares by part_no).
#  • Pagination: 500 records per page to avoid overwhelming Frappe.
#  • Credentials: reads from company_defaults (set at login) or env vars.
#
#  INSTALL / MANAGE  (run as Administrator)
#  ────────────────────────────────────────
#  python services\product_sync_windows_service.py install
#  python services\product_sync_windows_service.py start
#  python services\product_sync_windows_service.py stop
#  python services\product_sync_windows_service.py remove
#  python services\product_sync_windows_service.py debug   ← test without install
# =============================================================================

# from __future__ import annotations

# import sys
# import os
# import time
# import json
# import logging
# import threading
# import urllib.request
# import urllib.error

# # ── Project root on path ─────────────────────────────────────────────────────
# _HERE = os.path.dirname(os.path.abspath(__file__))
# _ROOT = os.path.dirname(_HERE)
# if _ROOT not in sys.path:
#     sys.path.insert(0, _ROOT)

# # ── Logging ──────────────────────────────────────────────────────────────────
# _LOG_PATH = os.path.join(_ROOT, "logs", "product_sync_service.log")
# os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)

# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s  [%(levelname)s]  %(message)s",
#     handlers=[
#         logging.FileHandler(_LOG_PATH, encoding="utf-8"),
#         logging.StreamHandler(sys.stdout),
#     ],
# )
# log = logging.getLogger("ProductSyncService")

# # ── Config ───────────────────────────────────────────────────────────────────
# SYNC_INTERVAL = 5 * 60      # seconds between cycles
# PAGE_SIZE     = 500          # records per Frappe page request
# REQUEST_TIMEOUT = 30


# # =============================================================================
# # CREDENTIALS / HOST
# # =============================================================================

# def _load_credentials() -> tuple[str, str]:
#     env_key    = os.environ.get("HAVANO_API_KEY",    "").strip()
#     env_secret = os.environ.get("HAVANO_API_SECRET", "").strip()
#     if env_key and env_secret:
#         return env_key, env_secret
#     try:
#         from models.company_defaults import get_defaults
#         d = get_defaults() or {}
#         return str(d.get("api_key") or "").strip(), str(d.get("api_secret") or "").strip()
#     except Exception as e:
#         raise RuntimeError(f"company_defaults unavailable: {e}")


# def _get_host() -> str:
#     try:
#         from models.company_defaults import get_defaults
#         host = (get_defaults() or {}).get("server_api_host", "").strip().rstrip("/")
#         if host:
#             return host
#     except Exception:
#         pass
#     return "https://apk.havano.cloud"


# # =============================================================================
# # FETCH HELPERS
# # =============================================================================

# def _get(url: str, api_key: str, api_secret: str) -> dict:
#     """Single authenticated GET → parsed JSON dict."""
#     req = urllib.request.Request(url)
#     req.add_header("Authorization", f"token {api_key}:{api_secret}")
#     with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
#         return json.loads(r.read().decode())


# def _fetch_all_pages(api_key: str, api_secret: str, host: str) -> list[dict]:
#     """
#     Pages through the Frappe products endpoint (PAGE_SIZE per page).
#     Returns the full list of raw product dicts from the API.
#     """
#     products: list[dict] = []
#     page = 1

#     while True:
#         url = (
#             f"{host}/api/method/havano_pos_integration.api.get_products"
#             f"?page={page}&limit={PAGE_SIZE}"
#         )
#         log.info("[sync] Fetching page %d (limit=%d)…", page, PAGE_SIZE)

#         try:
#             data       = _get(url, api_key, api_secret)
#             msg        = data.get("message", {})
#             page_items = msg.get("products", []) if isinstance(msg, dict) else (msg or [])
#             total_pages = msg.get("total_pages", 1) if isinstance(msg, dict) else 1
#         except Exception as e:
#             log.error("[sync] Page %d fetch failed: %s", page, e)
#             break

#         products.extend(page_items)
#         log.info("[sync]   %d products on page %d/%d", len(page_items), page, total_pages)

#         if page >= total_pages or len(page_items) < PAGE_SIZE:
#             break
#         page += 1

#     return products


# # =============================================================================
# # CORE SYNC LOGIC
# # =============================================================================

# def _get_local_part_nos() -> set[str]:
#     """Return a set of all part_no values already in the local DB."""
#     try:
#         from database.db import get_connection
#         conn = get_connection()
#         cur  = conn.cursor()
#         cur.execute("SELECT part_no FROM products")
#         rows = cur.fetchall()
#         conn.close()
#         return {r[0].strip().upper() for r in rows if r[0]}
#     except Exception as e:
#         log.error("Could not read local part_nos: %s", e)
#         return set()


# def sync_products_smart(api_key: str, api_secret: str) -> dict:
#     """
#     1. Fetch all remote products (paginated, PAGE_SIZE per page).
#     2. Compare part_no against local DB.
#     3. INSERT new ones, UPDATE existing ones (price / stock / name).
#     Returns a result summary dict.
#     """
#     result = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0, "total_api": 0}

#     remote = _fetch_all_pages(api_key, api_secret, _get_host())
#     result["total_api"] = len(remote)

#     if not remote:
#         log.info("[sync] No products returned from API.")
#         return result

#     local_part_nos = _get_local_part_nos()

#     try:
#         from database.db import get_connection
#         conn = get_connection()
#         cur  = conn.cursor()
#     except Exception as e:
#         log.error("DB connection failed: %s", e)
#         return result

#     for p in remote:
#         part_no = str(p.get("item_code") or p.get("part_no") or "").strip().upper()
#         name    = str(p.get("item_name") or p.get("name") or "").strip()
#         price   = float(p.get("standard_rate") or p.get("price") or 0)
#         stock   = int(float(p.get("actual_qty") or p.get("stock") or 0))
#         category = str(p.get("item_group") or p.get("category") or "").strip()

#         if not part_no:
#             result["skipped"] += 1
#             continue

#         try:
#             if part_no in local_part_nos:
#                 # UPDATE — only fields that can change from Frappe
#                 cur.execute("""
#                     UPDATE products
#                     SET name=?, price=?, stock=?, category=?
#                     WHERE part_no=?
#                 """, (name, price, stock, category, part_no))
#                 result["updated"] += 1
#             else:
#                 # INSERT — new product
#                 cur.execute("""
#                     INSERT INTO products (part_no, name, price, stock, category)
#                     VALUES (?, ?, ?, ?, ?)
#                 """, (part_no, name, price, stock, category))
#                 local_part_nos.add(part_no)   # prevent duplicate inserts in same run
#                 result["inserted"] += 1

#         except Exception as e:
#             log.error("Error processing product '%s': %s", part_no, e)
#             result["errors"] += 1

#     conn.commit()
#     conn.close()

#     log.info(
#         "[sync] ✅ Done — %d inserted, %d updated, %d skipped, %d errors  (%d total API records)",
#         result["inserted"], result["updated"], result["skipped"],
#         result["errors"], result["total_api"],
#     )
#     return result


# # =============================================================================
# # BACKGROUND SYNC THREAD  (non-blocking — login is never held up)
# # =============================================================================

# _sync_lock   = threading.Lock()     # prevents overlapping sync runs
# _sync_thread: threading.Thread | None = None


# def _sync_loop():
#     """Daemon thread: sync immediately on start, then every SYNC_INTERVAL seconds."""
#     log.info("Product sync daemon thread started (interval=%ds, page_size=%d).",
#              SYNC_INTERVAL, PAGE_SIZE)
#     while True:
#         if _sync_lock.acquire(blocking=False):
#             try:
#                 api_key, api_secret = _load_credentials()
#                 if api_key and api_secret:
#                     sync_products_smart(api_key, api_secret)
#                 else:
#                     log.warning("[sync] No credentials — skipping cycle.")
#             except Exception as e:
#                 log.error("[sync] Cycle error: %s", e)
#             finally:
#                 _sync_lock.release()
#         else:
#             log.info("[sync] Previous sync still running — skipping cycle.")

#         time.sleep(SYNC_INTERVAL)


# def start_sync_daemon() -> threading.Thread:
#     """
#     Start the background sync daemon.
#     Safe to call from MainWindow.__init__ — returns immediately, never blocks login.
#     """
#     global _sync_thread
#     if _sync_thread and _sync_thread.is_alive():
#         return _sync_thread
#     t = threading.Thread(target=_sync_loop, daemon=True, name="ProductSyncDaemon")
#     t.start()
#     _sync_thread = t
#     return t


# # =============================================================================
# # WINDOWS SERVICE CLASS
# # =============================================================================

# try:
#     import servicemanager
#     import win32event
#     import win32service
#     import win32serviceutil

#     class ProductSyncService(win32serviceutil.ServiceFramework):
#         _svc_name_         = "HavanoProductSync"
#         _svc_display_name_ = "Havano POS — Product Sync Service"
#         _svc_description_  = (
#             "Periodically syncs product catalogue from apk.havano.cloud "
#             "into the local SQL Server database (PAGE_SIZE=500, smart diff)."
#         )

#         def __init__(self, args):
#             win32serviceutil.ServiceFramework.__init__(self, args)
#             self._stop_event = win32event.CreateEvent(None, 0, 0, None)
#             self._running    = True

#         def SvcStop(self):
#             log.info("Stop signal received.")
#             self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
#             self._running = False
#             win32event.SetEvent(self._stop_event)

#         def SvcDoRun(self):
#             servicemanager.LogMsg(
#                 servicemanager.EVENTLOG_INFORMATION_TYPE,
#                 servicemanager.PYS_SERVICE_STARTED,
#                 (self._svc_name_, ""),
#             )
#             log.info("Havano Product Sync Service started.")
#             self._main_loop()

#         def _main_loop(self):
#             log.info("Sync interval: %ds (%d min)  page_size: %d",
#                      SYNC_INTERVAL, SYNC_INTERVAL // 60, PAGE_SIZE)
#             self._run_sync()   # run immediately on startup

#             while self._running:
#                 rc = win32event.WaitForSingleObject(
#                     self._stop_event, SYNC_INTERVAL * 1000
#                 )
#                 if rc == win32event.WAIT_OBJECT_0:
#                     break
#                 if self._running:
#                     self._run_sync()

#             log.info("Havano Product Sync Service stopped.")

#         def _run_sync(self):
#             if not _sync_lock.acquire(blocking=False):
#                 log.info("[sync] Previous sync still running — skipping.")
#                 return
#             try:
#                 api_key, api_secret = _load_credentials()
#                 if api_key and api_secret:
#                     sync_products_smart(api_key, api_secret)
#                 else:
#                     log.warning("[sync] No credentials — skipping cycle.")
#             except Exception as e:
#                 log.error("[sync] Cycle error: %s", e, exc_info=True)
#             finally:
#                 _sync_lock.release()

# except ImportError:
#     # pywin32 not installed — service class unavailable, daemon thread still works
#     log.debug("pywin32 not available — Windows Service class disabled.")
#     ProductSyncService = None  # type: ignore


# # =============================================================================
# # DEBUG / INTERACTIVE
# # =============================================================================

# def _run_debug():
#     log.info("=== DEBUG MODE — one sync cycle ===")
#     try:
#         api_key, api_secret = _load_credentials()
#     except Exception as e:
#         log.error("Credential error: %s", e); sys.exit(1)

#     if not api_key or not api_secret:
#         log.error("No credentials found. Login online first or set env vars.")
#         sys.exit(1)

#     result = sync_products_smart(api_key, api_secret)
#     print(
#         f"\nResult: {result['inserted']} inserted, {result['updated']} updated, "
#         f"{result['skipped']} skipped, {result['errors']} errors "
#         f"(of {result['total_api']} API records)"
#     )


# # =============================================================================
# # ENTRY POINT
# # =============================================================================

# if __name__ == "__main__":
#     if len(sys.argv) == 2 and sys.argv[1].lower() == "debug":
#         _run_debug()
#     elif ProductSyncService:
#         win32serviceutil.HandleCommandLine(ProductSyncService)
#     else:
#         log.error("pywin32 not installed. Run 'pip install pywin32' to use as a Windows Service.")


# =============================================================================
# services/product_sync_windows_service.py
#
#  Syncs products from Frappe → local SQL Server.
#
#  ACTUAL API RESPONSE SHAPE (confirmed from payload):
#  {
#    "message": {
#      "products": [
#        {
#          "itemcode":        "013308",
#          "itemname":        "vatproduct2",
#          "groupname":       "All Item Groups",
#          "maintainstock":   1,
#          "is_sales_item":   1,
#          "simple_code":     "026739" | null,
#          "warehouses":      [{"warehouse": "Stores - AT", "qtyOnHand": 0.0}],
#          "prices":          [{"priceName": "Standard Selling", "price": 1.0, "type": "selling"}],
#          ...
#        }
#      ],
#      "pagination": {
#        "current_page": 1,
#        "total_pages":  7,
#        "has_next_page": true,
#        "next_page":     2
#      }
#    }
#  }
#
#  INSTALL / MANAGE  (run as Administrator)
#  ────────────────────────────────────────
#  python services\product_sync_windows_service.py install
#  python services\product_sync_windows_service.py start
#  python services\product_sync_windows_service.py stop
#  python services\product_sync_windows_service.py remove
#  python services\product_sync_windows_service.py debug
# =============================================================================

from __future__ import annotations

import sys
import os
import time
import json
import logging
import threading
import urllib.request
import urllib.error

# ── Project root on path ─────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ── Logging ──────────────────────────────────────────────────────────────────
_LOG_PATH = os.path.join(_ROOT, "logs", "product_sync_service.log")
os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    handlers=[
        logging.FileHandler(_LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("ProductSyncService")

# ── Config ───────────────────────────────────────────────────────────────────
SYNC_INTERVAL   = 5 * 60   # seconds between cycles
PAGE_SIZE       = 500       # records per Frappe page request
REQUEST_TIMEOUT = 30


# =============================================================================
# CREDENTIALS / HOST
# =============================================================================

def _load_credentials() -> tuple[str, str]:
    env_key    = os.environ.get("HAVANO_API_KEY",    "").strip()
    env_secret = os.environ.get("HAVANO_API_SECRET", "").strip()
    if env_key and env_secret:
        return env_key, env_secret
    try:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
        return str(d.get("api_key") or "").strip(), str(d.get("api_secret") or "").strip()
    except Exception as e:
        raise RuntimeError(f"company_defaults unavailable: {e}")


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
# FETCH
# =============================================================================

def _get(url: str, api_key: str, api_secret: str) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {api_key}:{api_secret}")
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
        return json.loads(r.read().decode())


def _fetch_all_pages(api_key: str, api_secret: str, host: str) -> list[dict]:
    """Pages through the API using the real pagination structure."""
    products: list[dict] = []
    page = 1

    while True:
        url = (
            f"{host}/api/method/havano_pos_integration.api.get_products"
            f"?page={page}&limit={PAGE_SIZE}"
        )
        log.info("[sync] Fetching page %d (limit=%d)...", page, PAGE_SIZE)

        try:
            data       = _get(url, api_key, api_secret)
            msg        = data.get("message", {})
            page_items = msg.get("products", []) if isinstance(msg, dict) else []
            pagination = msg.get("pagination", {}) if isinstance(msg, dict) else {}
            total_pages = pagination.get("total_pages", 1)
            has_next    = pagination.get("has_next_page", False)
        except Exception as e:
            log.error("[sync] Page %d fetch failed: %s", page, e)
            break

        products.extend(page_items)
        log.info("[sync]   %d products on page %d/%d", len(page_items), page, total_pages)

        if not has_next:
            break
        page += 1

    return products


# =============================================================================
# FIELD EXTRACTORS  (maps real API field names → local values)
# =============================================================================

def _extract_selling_price(prices: list) -> float:
    """Find the Standard Selling price from the prices array."""
    for p in (prices or []):
        if str(p.get("type", "")).lower() == "selling":
            return float(p.get("price") or 0)
    return 0.0


def _extract_stock(warehouses: list) -> int:
    """Sum qtyOnHand across all warehouses."""
    total = 0.0
    for w in (warehouses or []):
        total += float(w.get("qtyOnHand") or 0)
    return int(total)


def _parse_product(p: dict) -> dict | None:
    """
    Maps the real API product object to a clean local dict.
    Returns None if the product should be skipped.
    """
    # Real field names from API
    part_no  = str(p.get("itemcode") or "").strip().upper()
    name     = str(p.get("itemname") or "").strip()
    category = str(p.get("groupname") or "").strip()
    price    = _extract_selling_price(p.get("prices", []))
    stock    = _extract_stock(p.get("warehouses", []))

    # is_sales_item filter — skip if explicitly 0
    is_sales = p.get("is_sales_item")
    if is_sales is not None and str(is_sales).strip() in ("0", "false", "False", "no"):
        log.debug("[sync] Skipped (not sales item): %s - %s", part_no, name)
        return None

    if not part_no:
        return None

    return {
        "part_no":  part_no,
        "name":     name,
        "category": category,
        "price":    price,
        "stock":    stock,
    }


# =============================================================================
# CORE SYNC
# =============================================================================

def _get_local_part_nos() -> set[str]:
    try:
        from database.db import get_connection
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT part_no FROM products")
        rows = cur.fetchall(); conn.close()
        return {r[0].strip().upper() for r in rows if r[0]}
    except Exception as e:
        log.error("Could not read local part_nos: %s", e)
        return set()


def sync_products_smart(api_key: str, api_secret: str) -> dict:
    result = {
        "inserted": 0, "updated": 0,
        "skipped_no_code": 0,
        "skipped_not_sales": 0,
        "errors": 0, "total_api": 0,
    }

    remote_raw = _fetch_all_pages(api_key, api_secret, _get_host())
    result["total_api"] = len(remote_raw)

    if not remote_raw:
        log.info("[sync] No products returned from API.")
        return result

    # Parse and filter
    remote = []
    for p in remote_raw:
        parsed = _parse_product(p)
        if parsed is None:
            # distinguish skipped reason
            part_no = str(p.get("itemcode") or "").strip()
            if not part_no:
                result["skipped_no_code"] += 1
            else:
                result["skipped_not_sales"] += 1
        else:
            remote.append(parsed)

    local_part_nos = _get_local_part_nos()

    try:
        from database.db import get_connection
        conn = get_connection(); cur = conn.cursor()
    except Exception as e:
        log.error("DB connection failed: %s", e)
        return result

    for p in remote:
        try:
            if p["part_no"] in local_part_nos:
                cur.execute("""
                    UPDATE products
                    SET name=?, price=?, stock=?, category=?
                    WHERE part_no=?
                """, (p["name"], p["price"], p["stock"], p["category"], p["part_no"]))
                result["updated"] += 1
            else:
                cur.execute("""
                    INSERT INTO products (part_no, name, price, stock, category)
                    VALUES (?, ?, ?, ?, ?)
                """, (p["part_no"], p["name"], p["price"], p["stock"], p["category"]))
                local_part_nos.add(p["part_no"])
                result["inserted"] += 1
        except Exception as e:
            log.error("Error processing product '%s': %s", p["part_no"], e)
            result["errors"] += 1

    conn.commit()
    conn.close()

    log.info(
        "[sync] Done -- %d inserted, %d updated, %d skipped (no code), "
        "%d skipped (not sales item), %d errors  (%d total API records)",
        result["inserted"], result["updated"], result["skipped_no_code"],
        result["skipped_not_sales"], result["errors"], result["total_api"],
    )
    return result


# =============================================================================
# BACKGROUND DAEMON THREAD  (non-blocking)
# =============================================================================

_sync_lock:   threading.Lock           = threading.Lock()
_sync_thread: threading.Thread | None = None


def _sync_loop():
    log.info("Product sync daemon started (interval=%ds, page_size=%d).",
             SYNC_INTERVAL, PAGE_SIZE)
    while True:
        if _sync_lock.acquire(blocking=False):
            try:
                api_key, api_secret = _load_credentials()
                if api_key and api_secret:
                    sync_products_smart(api_key, api_secret)
                else:
                    log.warning("[sync] No credentials -- skipping cycle.")
            except Exception as e:
                log.error("[sync] Cycle error: %s", e)
            finally:
                _sync_lock.release()
        else:
            log.info("[sync] Previous sync still running -- skipping cycle.")
        time.sleep(SYNC_INTERVAL)


def start_sync_daemon() -> threading.Thread:
    """Non-blocking — safe to call from MainWindow.__init__."""
    global _sync_thread
    if _sync_thread and _sync_thread.is_alive():
        return _sync_thread
    t = threading.Thread(target=_sync_loop, daemon=True, name="ProductSyncDaemon")
    t.start()
    _sync_thread = t
    return t


# =============================================================================
# WINDOWS SERVICE CLASS
# =============================================================================

try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    class ProductSyncService(win32serviceutil.ServiceFramework):
        _svc_name_         = "HavanoProductSync"
        _svc_display_name_ = "Havano POS -- Product Sync Service"
        _svc_description_  = (
            "Periodically syncs product catalogue from apk.havano.cloud "
            "into the local SQL Server database. Skips non-sales items."
        )

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)
            self._running    = True

        def SvcStop(self):
            log.info("Stop signal received.")
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self._running = False
            win32event.SetEvent(self._stop_event)

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )
            log.info("Havano Product Sync Service started.")
            self._main_loop()

        def _main_loop(self):
            log.info("Sync interval: %ds (%d min)  page_size: %d",
                     SYNC_INTERVAL, SYNC_INTERVAL // 60, PAGE_SIZE)
            self._run_sync()
            while self._running:
                rc = win32event.WaitForSingleObject(self._stop_event, SYNC_INTERVAL * 1000)
                if rc == win32event.WAIT_OBJECT_0:
                    break
                if self._running:
                    self._run_sync()
            log.info("Havano Product Sync Service stopped.")

        def _run_sync(self):
            if not _sync_lock.acquire(blocking=False):
                log.info("[sync] Previous sync still running -- skipping.")
                return
            try:
                api_key, api_secret = _load_credentials()
                if api_key and api_secret:
                    sync_products_smart(api_key, api_secret)
                else:
                    log.warning("[sync] No credentials -- skipping cycle.")
            except Exception as e:
                log.error("[sync] Cycle error: %s", e, exc_info=True)
            finally:
                _sync_lock.release()

except ImportError:
    log.debug("pywin32 not available -- Windows Service class disabled.")
    ProductSyncService = None  # type: ignore


# =============================================================================
# DEBUG / INTERACTIVE
# =============================================================================

def _run_debug():
    log.info("=== DEBUG MODE -- one sync cycle ===")
    try:
        api_key, api_secret = _load_credentials()
    except Exception as e:
        log.error("Credential error: %s", e); sys.exit(1)

    if not api_key or not api_secret:
        log.error("No credentials found. Login online first or set env vars.")
        sys.exit(1)

    result = sync_products_smart(api_key, api_secret)
    print(
        f"\nResult: {result['inserted']} inserted, {result['updated']} updated, "
        f"{result['skipped_no_code']} skipped (no code), "
        f"{result['skipped_not_sales']} skipped (not sales item), "
        f"{result['errors']} errors  (of {result['total_api']} API records)"
    )


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1].lower() == "debug":
        _run_debug()
    elif ProductSyncService:
        win32serviceutil.HandleCommandLine(ProductSyncService)
    else:
        log.error("pywin32 not installed. Run 'pip install pywin32' to use as a Windows Service.")
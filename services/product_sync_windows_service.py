
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
    env_key    = os.environ.get("e0608e091360182",    "").strip()
    env_secret = os.environ.get("45851f2c3cd4213", "").strip()
    if env_key and env_secret:
        return env_key, env_secret
    try:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
        return str(d.get("api_key") or "").strip(), str(d.get("api_secret") or "").strip()
    except Exception as e:
        raise RuntimeError(f"company_defaults unavailable: {e}")


from services.site_config import get_host as _get_host

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
            print("MSG:", msg)
            page_items = msg.get("products", []) if isinstance(msg, dict) else []
            print("PAGE ITEMS:", page_items)
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

def _extract_selling_price(prices: list, stock_uom: str = "Nos") -> float:
    """
    Find the best selling price from the prices array.
    Priority:
      1. Standard Selling for the stock UOM (e.g. Nos, Kg)
      2. Any Standard Selling price
      3. Any selling type price
    """
    selling = [p for p in (prices or []) if str(p.get("type", "")).lower() == "selling"]
    if not selling:
        return 0.0
    # 1. Match stock UOM exactly
    for p in selling:
        if str(p.get("uom") or "").strip().lower() == stock_uom.strip().lower():
            return float(p.get("price") or 0)
    # 2. priceName contains Standard Selling
    for p in selling:
        if "standard selling" in str(p.get("priceName") or "").lower():
            return float(p.get("price") or 0)
    # 3. First selling price
    return float(selling[0].get("price") or 0)


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
    part_no   = str(p.get("itemcode") or "").strip().upper()
    name      = str(p.get("itemname") or "").strip()
    stock_uom = str((p.get("uom") or {}).get("stock_uom") or "Nos").strip()
    price     = _extract_selling_price(p.get("prices", []), stock_uom)

    # #29 — strip Frappe parent/root group names so only real leaf groups
    # appear in the POS category bar.  "All Item Groups" is the Frappe root
    # node (is_group=1); items assigned there haven't been categorised yet.
    # Any name in this set is treated as "uncategorised" (stored as "").
    _ROOT_GROUPS = {
        "all item groups",
        "all",
    }
    raw_group = str(p.get("groupname") or "").strip()
    category  = "" if raw_group.lower() in _ROOT_GROUPS else raw_group

    if raw_group and raw_group.lower() in _ROOT_GROUPS:
        log.debug("[sync] %s — groupname '%s' is a root group, stored as uncategorised.",
                  part_no, raw_group)

    stock     = _extract_stock(p.get("warehouses", []))

    # is_sales_item filter — only sync items explicitly marked as sales items
    # If the field is missing or falsy, skip to be safe
    is_sales = p.get("is_sales_item")
    if not is_sales or str(is_sales).strip() in ("0", "false", "False", "no"):
        log.debug("[sync] Skipped (not sales item): %s - %s", part_no, name)
        return None

    if not part_no:
        return None

    # Build UOM prices list — all selling prices with their UOM
    raw_prices = p.get("prices", [])
    uom_prices = []
    seen_uoms  = set()
    for rp in raw_prices:
        if str(rp.get("type", "")).lower() != "selling":
            continue
        uom_name = str(rp.get("uom") or "Nos").strip()
        rp_price = float(rp.get("price") or 0)
        if uom_name not in seen_uoms and rp_price > 0:
            uom_prices.append({"uom": uom_name, "price": rp_price})
            seen_uoms.add(uom_name)

    return {
        "part_no":    part_no,
        "name":       name,
        "category":   category,
        "price":      price,
        "stock":      stock,
        "uom_prices": uom_prices,   # list of {uom, price} for picker dialog
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
        "root_group_stripped": 0,   # products whose groupname was a root/parent
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
            part_no = str(p.get("itemcode") or "").strip()
            if not part_no:
                result["skipped_no_code"] += 1
            else:
                result["skipped_not_sales"] += 1
        else:
            # Count products that had a root group stripped
            raw_group = str(p.get("groupname") or "").strip()
            if raw_group.lower() in {"all item groups", "all"} and parsed["category"] == "":
                result["root_group_stripped"] += 1
            remote.append(parsed)

    # Build set of part_nos that ARE valid sales items from this sync
    valid_sales_part_nos = {p["part_no"] for p in remote}

    # Build set of part_nos that were explicitly rejected as non-sales items
    non_sales_part_nos = set()
    for p in remote_raw:
        part_no = str(p.get("itemcode") or "").strip().upper()
        is_sales = p.get("is_sales_item")
        if part_no and (not is_sales or str(is_sales).strip() in ("0", "false", "False", "no")):
            non_sales_part_nos.add(part_no)

    local_part_nos = _get_local_part_nos()

    try:
        from database.db import get_connection
        conn = get_connection(); cur = conn.cursor()
    except Exception as e:
        log.error("DB connection failed: %s", e)
        return result

    # Deactivate any local products that Frappe says are not sales items
    deactivated = 0
    for part_no in non_sales_part_nos:
        if part_no in local_part_nos:
            cur.execute("UPDATE products SET active=0 WHERE part_no=?", (part_no,))
            deactivated += 1
    if deactivated:
        log.info("[sync] Deactivated %d non-sales items in local DB.", deactivated)

    # Ensure product_uom_prices table exists
    try:
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = 'product_uom_prices'
            )
            CREATE TABLE product_uom_prices (
                id       INT           IDENTITY(1,1) PRIMARY KEY,
                part_no  NVARCHAR(50)  NOT NULL,
                uom      NVARCHAR(40)  NOT NULL,
                price    DECIMAL(12,2) NOT NULL DEFAULT 0,
                CONSTRAINT UQ_product_uom UNIQUE (part_no, uom)
            )
        """)
    except Exception as e:
        log.warning("[sync] Could not create product_uom_prices: %s", e)

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

            # Upsert UOM prices
            for up in (p.get("uom_prices") or []):
                try:
                    cur.execute("""
                        MERGE product_uom_prices AS target
                        USING (SELECT ? AS part_no, ? AS uom) AS src
                            ON target.part_no = src.part_no
                           AND target.uom     = src.uom
                        WHEN MATCHED THEN
                            UPDATE SET price = ?
                        WHEN NOT MATCHED THEN
                            INSERT (part_no, uom, price) VALUES (?, ?, ?);
                    """, (p["part_no"], up["uom"], up["price"],
                          p["part_no"], up["uom"], up["price"]))
                except Exception:
                    pass

        except Exception as e:
            log.error("Error processing product '%s': %s", p["part_no"], e)
            result["errors"] += 1

    conn.commit()
    conn.close()

    log.info(
        "[sync] Done -- %d inserted, %d updated, %d skipped (no code), "
        "%d skipped (not sales item), %d root-group stripped → uncategorised, "
        "%d errors  (%d total API records)",
        result["inserted"], result["updated"], result["skipped_no_code"],
        result["skipped_not_sales"], result["root_group_stripped"],
        result["errors"], result["total_api"],
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
            "Periodically syncs product catalogue from  "
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
        f"{result['root_group_stripped']} root-group stripped → uncategorised, "
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
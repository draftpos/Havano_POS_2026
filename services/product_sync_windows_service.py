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
        logging.StreamHandler(open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)),
    ],
)
log = logging.getLogger("ProductSyncService")

# ── Config ───────────────────────────────────────────────────────────────────
SYNC_INTERVAL   = 1 * 60   # 1 minute (Aggressive Sync)
PAGE_SIZE       = 500       # records per Frappe page request
REQUEST_TIMEOUT = 30


# =============================================================================
# CREDENTIALS / HOST
# =============================================================================

def _load_credentials() -> tuple[str, str]:
    """
    Load credentials with correct fallback chain:
      1. In-memory session (fastest — covers mid-session calls)
      2. DB read — queries MIN(id) so it works regardless of the actual id value
      3. Environment variables (CI / headless fallback)
    """

    # ── 1. In-memory session ─────────────────────────────────────────────────
    try:
        from services.credentials import get_credentials
        api_key, api_secret = get_credentials()
        if api_key and api_secret:
            log.debug("Credentials loaded from credentials module")
            return api_key, api_secret
    except Exception as e:
        log.warning("Could not load from credentials module: %s", e)

    # ── 2. Direct DB read using MIN(id) — fixes WHERE id=1 bug ──────────────
    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("""
            SELECT api_key, api_secret
            FROM   company_defaults
            WHERE  id = (SELECT MIN(id) FROM company_defaults)
        """)
        row = cur.fetchone()
        conn.close()
        if row:
            k = str(row[0] or "").strip()
            s = str(row[1] or "").strip()
            if k and s:
                log.debug("Credentials loaded directly from DB (MIN id): %s...", k[:8])
                return k, s
            else:
                log.warning("api_key/api_secret columns exist but are empty in DB — "
                            "login with username+password once to populate them.")
    except Exception as e:
        log.error("DB credential read failed: %s", e)

    # ── 3. Environment variables ─────────────────────────────────────────────
    env_key    = os.environ.get("HAVANO_API_KEY",    "").strip()
    env_secret = os.environ.get("HAVANO_API_SECRET", "").strip()
    if env_key and env_secret:
        log.debug("Credentials loaded from environment variables")
        return env_key, env_secret

    log.error("No credentials found — login via the POS app or set "
              "HAVANO_API_KEY / HAVANO_API_SECRET environment variables.")
    return "", ""


def _get_host() -> str:
    # Primary: read api_url from sql_settings.json (always present)
    try:
        from database.db import get_api_url
        host = get_api_url()
        if host:
            return host
    except Exception as e:
        log.warning("Could not read api_url from sql_settings: %s", e)

    # Fallback: try site_config module
    try:
        from services.site_config import get_host
        return get_host()
    except Exception:
        pass

    # Last resort: try server_api_host column in DB
    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("""
            SELECT server_api_host
            FROM   company_defaults
            WHERE  id = (SELECT MIN(id) FROM company_defaults)
        """)
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            host = str(row[0]).strip().rstrip("/")
            if host:
                return host
    except Exception:
        pass

    return "https://erp1193.havano.cloud"


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
            data        = _get(url, api_key, api_secret)
            msg         = data.get("message", {})
            page_items  = msg.get("products", []) if isinstance(msg, dict) else []
            pagination  = msg.get("pagination", {}) if isinstance(msg, dict) else {}
            total_pages = pagination.get("total_pages", 1)
            has_next    = pagination.get("has_next_page", False)

            # TAX DEBUG: log a sample raw product on first page
            if page == 1 and page_items:
                sample       = page_items[0]
                sample_taxes = sample.get("taxes", [])
                log.info(
                    "[TAX FIELD DEBUG] Sample product '%s' taxes raw: %s",
                    sample.get("itemcode", "?"),
                    json.dumps(sample_taxes, default=str),
                )

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
# FIELD EXTRACTORS
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
    for p in selling:
        if str(p.get("uom") or "").strip().lower() == stock_uom.strip().lower():
            return float(p.get("price") or 0)
    for p in selling:
        if "standard selling" in str(p.get("priceName") or "").lower():
            return float(p.get("price") or 0)
    return float(selling[0].get("price") or 0)


def _extract_stock(warehouses: list) -> int:
    """Sum qtyOnHand across all warehouses."""
    total = 0.0
    for w in (warehouses or []):
        total += float(w.get("qtyOnHand") or 0)
    return int(total)


def _extract_tax_info(taxes: list, part_no: str = "") -> dict | None:
    """
    Extract tax information from the taxes array.

    Tries all common field names for the rate so we never silently get 0.
    Infers tax_category from item_tax_template when the category field is blank.
    Applies a 15.5% VAT fallback when rate is still 0 for a VAT category item.
    """
    if not taxes:
        log.debug("[TAX] %s — no taxes array, will default to ZERO RATED", part_no)
        return None

    tax = taxes[0]

    # Log the raw tax object for every product
    log.info("[TAX RAW] %s -> %s", part_no or "?", json.dumps(tax, default=str))

    # Try every common field name for the rate; take first non-zero value
    tax_rate = (
        float(tax.get("tax_rate")        or 0)
        or float(tax.get("rate")             or 0)
        or float(tax.get("minimum_net_rate") or 0)
        or float(tax.get("maximum_net_rate") or 0)
    )

    tax_category      = str(tax.get("tax_category")      or "").strip()
    item_tax_template = str(tax.get("item_tax_template") or "").strip()

    # Infer category from template name when blank
    if not tax_category:
        tmpl_upper = item_tax_template.upper()
        if "VAT" in tmpl_upper:
            tax_category = "VAT"
            log.debug("[TAX] %s — inferred category=VAT from template '%s'",
                      part_no, item_tax_template)
        elif "EXEMPT" in tmpl_upper:
            tax_category = "EXEMPT"
            log.debug("[TAX] %s — inferred category=EXEMPT from template '%s'",
                      part_no, item_tax_template)
        elif "ZERO" in tmpl_upper:
            tax_category = "ZERO RATED"
            log.debug("[TAX] %s — inferred category=ZERO RATED from template '%s'",
                      part_no, item_tax_template)

    # VAT rate fallback (15.5%) when rate is still 0
    if tax_rate == 0 and tax_category.upper() == "VAT":
        tax_rate = 15.5
        log.debug("[TAX] %s — rate was 0 for VAT category, defaulted to 15.5", part_no)

    log.info(
        "[TAX RESOLVED] %s -> rate=%.4f  category='%s'  template='%s'",
        part_no or "?", tax_rate, tax_category, item_tax_template,
    )

    return {
        "tax_rate":          tax_rate,
        "tax_category":      tax_category,
        "item_tax_template": item_tax_template,
    }


def _parse_product(p: dict) -> dict | None:
    """
    Maps the real API product object to a clean local dict including tax info.
    Returns None if the product should be skipped.
    """
    part_no   = str(p.get("itemcode") or "").strip().upper()
    name      = str(p.get("itemname") or "").strip()
    stock_uom = str((p.get("uom") or {}).get("stock_uom") or "Nos").strip()
    price     = _extract_selling_price(p.get("prices", []), stock_uom)

    _ROOT_GROUPS = {"all item groups", "all"}
    raw_group = str(p.get("groupname") or "").strip()
    category  = "" if raw_group.lower() in _ROOT_GROUPS else raw_group

    if raw_group and raw_group.lower() in _ROOT_GROUPS:
        log.debug("[sync] %s — groupname '%s' is a root group, stored as uncategorised.",
                  part_no, raw_group)

    stock = _extract_stock(p.get("warehouses", []))

    taxes    = p.get("taxes", [])
    tax_info = _extract_tax_info(taxes, part_no=part_no)

    # is_sales_item filter
    is_sales = p.get("is_sales_item")
    if not is_sales or str(is_sales).strip() in ("0", "false", "False", "no"):
        log.debug("[sync] Skipped (not sales item): %s - %s", part_no, name)
        return None

    if not part_no:
        return None

    # Build UOM prices list
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

    result = {
        "part_no":    part_no,
        "name":       name,
        "category":   category,
        "price":      price,
        "stock":      stock,
        "uom_prices": uom_prices,
    }

    if tax_info:
        result["tax_rate"]          = tax_info["tax_rate"]
        result["tax_type"]          = tax_info["tax_category"] if tax_info["tax_category"] else "VAT"
        result["item_tax_template"] = tax_info["item_tax_template"]
    else:
        result["tax_rate"]          = 0.0
        result["tax_type"]          = "ZERO RATED"
        result["item_tax_template"] = ""
        log.debug("[TAX] %s — no tax_info returned, defaulting to ZERO RATED", part_no)

    return result


# =============================================================================
# CORE SYNC
# =============================================================================

def _get_local_part_nos() -> set[str]:
    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("SELECT part_no FROM products")
        rows = cur.fetchall()
        conn.close()
        return {r[0].strip().upper() for r in rows if r[0]}
    except Exception as e:
        log.error("Could not read local part_nos: %s", e)
        return set()


def _ensure_schema(cur) -> None:
    """
    Make sure all required tables and columns exist before we start writing.
    Safe to call every sync cycle — all DDL is guarded with IF NOT EXISTS.
    """

    # product_uom_prices table
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

    # product_taxes table
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'product_taxes'
        )
        CREATE TABLE product_taxes (
            id                INT           IDENTITY(1,1) PRIMARY KEY,
            part_no           NVARCHAR(50)  NOT NULL,
            item_tax_template NVARCHAR(100),
            tax_category      NVARCHAR(50),
            valid_from        DATE,
            minimum_net_rate  DECIMAL(8,4),
            maximum_net_rate  DECIMAL(8,4),
            created_at        DATETIME2     DEFAULT SYSDATETIME(),
            updated_at        DATETIME2     DEFAULT SYSDATETIME(),
            CONSTRAINT UQ_product_taxes UNIQUE (part_no, tax_category)
        )
    """)

    # tax_rate column on products
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'tax_rate'
        )
        ALTER TABLE products ADD tax_rate DECIMAL(8,4) DEFAULT 0
    """)

    # tax_type column on products
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'tax_type'
        )
        ALTER TABLE products ADD tax_type NVARCHAR(50) DEFAULT 'VAT'
    """)

    # item_tax_template column on products (so we store the Frappe template name too)
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'item_tax_template'
        )
        ALTER TABLE products ADD item_tax_template NVARCHAR(100) DEFAULT ''
    """)


def sync_products_smart(api_key: str, api_secret: str) -> dict:
    result = {
        "inserted":            0,
        "updated":             0,
        "skipped_no_code":     0,
        "skipped_not_sales":   0,
        "root_group_stripped": 0,
        "taxes_updated":       0,
        "errors":              0,
        "total_api":           0,
    }

    host       = _get_host()
    remote_raw = _fetch_all_pages(api_key, api_secret, host)
    result["total_api"] = len(remote_raw)

    if not remote_raw:
        log.info("[sync] No products returned from API.")
        return result

    # ── Parse and filter ─────────────────────────────────────────────────────
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
            raw_group = str(p.get("groupname") or "").strip()
            if raw_group.lower() in {"all item groups", "all"} and parsed["category"] == "":
                result["root_group_stripped"] += 1
            remote.append(parsed)

    # Build set of part_nos explicitly rejected as non-sales items
    non_sales_part_nos: set[str] = set()
    for p in remote_raw:
        part_no  = str(p.get("itemcode") or "").strip().upper()
        is_sales = p.get("is_sales_item")
        if part_no and (not is_sales or str(is_sales).strip() in ("0", "false", "False", "no")):
            non_sales_part_nos.add(part_no)

    local_part_nos = _get_local_part_nos()

    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
    except Exception as e:
        log.error("DB connection failed: %s", e)
        return result

    # ── Ensure schema ────────────────────────────────────────────────────────
    try:
        _ensure_schema(cur)
        conn.commit()
    except Exception as e:
        log.warning("[sync] Schema check failed: %s", e)

    # ── Deactivate non-sales items ───────────────────────────────────────────
    deactivated = 0
    for part_no in non_sales_part_nos:
        if part_no in local_part_nos:
            try:
                cur.execute("UPDATE products SET active=0 WHERE part_no=?", (part_no,))
                deactivated += 1
            except Exception:
                pass
    if deactivated:
        log.info("[sync] Deactivated %d non-sales items in local DB.", deactivated)

    # ── Upsert each product ──────────────────────────────────────────────────
    for p in remote:
        try:
            tax_rate          = p.get("tax_rate",          0)
            tax_type          = p.get("tax_type",          "VAT")
            item_tax_template = p.get("item_tax_template", "")

            if p["part_no"] in local_part_nos:
                cur.execute("""
                    UPDATE products
                    SET    name              = ?,
                           price             = ?,
                           stock             = ?,
                           category          = ?,
                           tax_rate          = ?,
                           tax_type          = ?,
                           item_tax_template = ?
                    WHERE  part_no = ?
                """, (
                    p["name"], p["price"], p["stock"], p["category"],
                    tax_rate, tax_type, item_tax_template,
                    p["part_no"],
                ))
                result["updated"] += 1
                log.debug("[sync] Updated: %s  tax_rate=%.4f  tax_type=%s",
                          p["part_no"], tax_rate, tax_type)
            else:
                cur.execute("""
                    INSERT INTO products
                        (part_no, name, price, stock, category,
                         tax_rate, tax_type, item_tax_template)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p["part_no"], p["name"], p["price"], p["stock"], p["category"],
                    tax_rate, tax_type, item_tax_template,
                ))
                local_part_nos.add(p["part_no"])
                result["inserted"] += 1
                log.debug("[sync] Inserted: %s  tax_rate=%.4f  tax_type=%s",
                          p["part_no"], tax_rate, tax_type)

            # ── Upsert UOM prices ────────────────────────────────────────────
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
                    """, (
                        p["part_no"], up["uom"], up["price"],
                        p["part_no"], up["uom"], up["price"],
                    ))
                except Exception as e:
                    log.warning("Error upserting UOM price for %s/%s: %s",
                                p["part_no"], up.get("uom"), e)

            # ── Upsert product_taxes ─────────────────────────────────────────
            # Always write the tax record — even ZERO RATED items should have
            # a row so downstream code never has to guess.
            try:
                cur.execute("""
                    MERGE product_taxes AS target
                    USING (SELECT ? AS part_no, ? AS tax_category) AS src
                        ON target.part_no      = src.part_no
                       AND target.tax_category = src.tax_category
                    WHEN MATCHED THEN
                        UPDATE SET
                            item_tax_template = ?,
                            minimum_net_rate  = ?,
                            maximum_net_rate  = ?,
                            updated_at        = SYSDATETIME()
                    WHEN NOT MATCHED THEN
                        INSERT (part_no, tax_category, item_tax_template,
                                minimum_net_rate, maximum_net_rate)
                        VALUES (?, ?, ?, ?, ?);
                """, (
                    p["part_no"], tax_type,
                    item_tax_template, tax_rate, tax_rate,
                    p["part_no"], tax_type, item_tax_template, tax_rate, tax_rate,
                ))
                result["taxes_updated"] += 1
                log.debug("[sync] Tax upserted: %s  rate=%.4f  type=%s",
                          p["part_no"], tax_rate, tax_type)
            except Exception as e:
                log.warning("Error upserting tax for %s: %s", p["part_no"], e)

        except Exception as e:
            log.error("Error processing product '%s': %s", p["part_no"], e)
            result["errors"] += 1

    conn.commit()
    conn.close()

    log.info(
        "[sync] Done -- %d inserted, %d updated, %d skipped (no code), "
        "%d skipped (not sales item), %d root-group stripped -> uncategorised, "
        "%d taxes updated, %d errors  (%d total API records)",
        result["inserted"], result["updated"], result["skipped_no_code"],
        result["skipped_not_sales"], result["root_group_stripped"],
        result["taxes_updated"], result["errors"], result["total_api"],
    )
    return result


# =============================================================================
# BACKGROUND DAEMON THREAD
# =============================================================================

_sync_lock:   threading.Lock          = threading.Lock()
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
            "Periodically syncs product catalogue from Frappe "
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
        log.error("Credential error: %s", e)
        sys.exit(1)

    if not api_key or not api_secret:
        log.error("No credentials found. Login via the POS app first, or set "
                  "HAVANO_API_KEY / HAVANO_API_SECRET environment variables.")
        sys.exit(1)

    result = sync_products_smart(api_key, api_secret)
    print(
        f"\nResult: {result['inserted']} inserted, {result['updated']} updated, "
        f"{result['skipped_no_code']} skipped (no code), "
        f"{result['skipped_not_sales']} skipped (not sales item), "
        f"{result['root_group_stripped']} root-group stripped -> uncategorised, "
        f"{result['taxes_updated']} taxes updated, "
        f"{result['errors']} errors  (of {result['total_api']} API records)"
    )
    print(
        f"\nCheck logs at: {_LOG_PATH}"
        f"\nSearch for '[TAX RAW]'        to see raw API tax objects."
        f"\nSearch for '[TAX RESOLVED]'   to see what was actually saved."
        f"\nSearch for '[TAX FIELD DEBUG]' for the first-page sample."
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
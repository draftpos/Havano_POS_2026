# =============================================================================
# services/sync_service.py
# Product + GL Account + Mode of Payment + Exchange Rate + Tax Sync
# =============================================================================
#
# MERGE NOTES
# ───────────
# Tax logic is now taken entirely from product_sync_windows_service.py:
#   • _extract_tax_info()   — uses maximum_net_rate as the authoritative rate
#   • _parse_product()      — maps raw API → clean dict with full tax fields
#   • _ensure_schema()      — creates product_taxes with the correct columns
#   • _upsert_product_taxes — MERGE on (part_no, tax_category) with full cols
#
# Every section is wrapped in try/except so a single failure never crashes
# login or the background SyncWorker loop.
# =============================================================================

import json
import logging
import time as _time
import urllib.error
import urllib.parse
import urllib.request

from database.db import get_connection, fetchone_dict
from services.site_config import get_host as _get_host

log = logging.getLogger("SyncService")

API_BASE_URL      = _get_host()
PRODUCTS_ENDPOINT = f"{API_BASE_URL}/api/method/havano_pos_integration.api.get_products"
PAGE_SIZE         = 100
MAX_PAGES         = 200

# Background-sync intervals
PRODUCT_SYNC_INTERVAL_SECONDS = 15   # aggressive product sync
GL_MOP_SYNC_INTERVAL_SECONDS  = 600  # GL / MOP / exchange rates every 10 min


# =============================================================================
# PUBLIC — called on login and by SyncWorker
# =============================================================================

def _has_local_products() -> bool:
    """Returning-user detection: do we already have a catalogue on disk?

    When True, the login flow should NOT block on a full inline sync —
    the BackgroundSyncWorker (started from login_dialog._accept_user)
    will refresh products, taxes, GL, MOP, and exchange rates without
    making the cashier wait at the login screen. False means first-time
    setup: the POS grid would be empty until sync completes, so we fall
    back to the blocking inline path.
    """
    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM products")
        n = int(cur.fetchone()[0] or 0)
        conn.close()
        return n > 0
    except Exception as e:
        log.debug("_has_local_products check failed: %s", e)
        return False


def sync_from_login_response(login_data: dict) -> dict:
    token_string = login_data.get("token_string", "")
    api_key = api_secret = ""
    if token_string and ":" in token_string:
        api_key, api_secret = token_string.split(":", 1)

    # ------------------------------------------------------------------
    # Fast path: returning user, products already cached locally.
    # Defer every heavy sync to the BackgroundSyncWorker so login opens
    # the POS immediately. The background worker runs users + products +
    # taxes (+ GL/MOP/rates via its SyncWorker) in the same order.
    # ------------------------------------------------------------------
    if _has_local_products():
        log.info("[sync_login] products exist locally — skipping inline "
                 "sync, background worker will handle refresh")
        return {
            "inserted":                0,
            "updated":                  0,
            "products_synced":          0,
            "gl_accounts_synced":       0,
            "modes_of_payment_synced":  0,
            "exchange_rates_synced":    0,
            "doctors_synced":           0,
            "dosages_synced":           0,
            "skipped_inline":           True,
        }

    # ------------------------------------------------------------------
    # First-time install path (no local products yet) — the POS grid is
    # unusable until a catalogue is populated, so we block login on the
    # full sync. Login dialog paints a "First-time setup" notice before
    # spawning the LoginWorker when this branch is about to fire.
    # ------------------------------------------------------------------
    # 1. Products (always first)
    # ------------------------------------------------------------------
    result = sync_products(api_key=api_key, api_secret=api_secret)

    # ------------------------------------------------------------------
    # 2. GL accounts + MOP — must commit before exchange-rate sync so
    #    that get_all_accounts() actually finds currencies.
    # ------------------------------------------------------------------
    try:
        from models.company_defaults import get_defaults
        company = (get_defaults() or {}).get("server_company", "")
        host    = _get_host()

        gl_count  = sync_gl_accounts(api_key, api_secret, host, company)
        mop_count = sync_modes_of_payment(api_key, api_secret, host, company)

        # ------------------------------------------------------------------
        # 3. Exchange rates — AFTER GL accounts so currencies are present.
        # ------------------------------------------------------------------
        rate_count = sync_exchange_rates(
            api_key, api_secret, host,
            _force=True,
        )

        result["gl_accounts_synced"]      = gl_count
        result["modes_of_payment_synced"] = mop_count
        result["exchange_rates_synced"]   = rate_count

        log.info(
            "[sync_login] GL=%d  MOP=%d  Rates=%d",
            gl_count, mop_count, rate_count,
        )

    except Exception as e:
        log.warning("GL/MOP/rates sync during login failed: %s", e)
        result["gl_accounts_synced"]      = 0
        result["modes_of_payment_synced"] = 0
        result["exchange_rates_synced"]   = 0

    # ------------------------------------------------------------------
    # 4. Pharmacy reference data — best-effort, never blocks login.
    # ------------------------------------------------------------------
    try:
        from services.doctor_sync_service import sync_doctors
        from services.dosage_sync_service import sync_dosages
        doc_res = sync_doctors()
        dos_res = sync_dosages()
        result["doctors_synced"] = doc_res.get("synced", 0)
        result["dosages_synced"] = dos_res.get("synced", 0)
        print(
            f"[sync] ✅ Doctors synced: {result['doctors_synced']} | "
            f"Dosages synced: {result['dosages_synced']}"
        )
    except Exception as e:
        log.warning("Doctor/Dosage sync during login failed: %s", e)
        result["doctors_synced"] = 0
        result["dosages_synced"] = 0

    try:
        from services.doctor_push_service import push_unsynced_doctors
        doc_push = push_unsynced_doctors() or {}
        result["doctors_pushed"]      = int(doc_push.get("pushed", 0))
        result["doctors_push_errors"] = int(doc_push.get("errors", 0))
        print(
            f"[sync] ✅ Doctors pushed: {result['doctors_pushed']} "
            f"(errors: {result['doctors_push_errors']})"
        )
    except Exception as e:
        log.warning("Doctor push during login failed: %s", e)
        result["doctors_pushed"]      = 0
        result["doctors_push_errors"] = 0

    try:
        from services.dosage_push_service import push_unsynced_dosages
        dos_push = push_unsynced_dosages() or {}
        result["dosages_pushed"]       = int(dos_push.get("pushed", 0))
        result["dosages_push_errors"]  = int(dos_push.get("errors", 0))
        print(
            f"[sync] ✅ Dosages pushed: {result['dosages_pushed']} "
            f"(errors: {result['dosages_push_errors']})"
        )
    except Exception as e:
        log.warning("Dosage push during login failed: %s", e)
        result["dosages_pushed"]      = 0
        result["dosages_push_errors"] = 0

    return result


# =============================================================================
# SCHEMA HELPERS
# =============================================================================

def _ensure_product_schema(cur) -> None:
    """
    Creates / migrates all product-related tables and columns.
    Safe to call every sync cycle — all DDL is guarded with IF NOT EXISTS.
    """

    # ── product_uom_prices ─────────────────────────────────────────────
    try:
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = 'product_uom_prices'
            )
            CREATE TABLE product_uom_prices (
                id      INT           IDENTITY(1,1) PRIMARY KEY,
                part_no NVARCHAR(50)  NOT NULL,
                uom     NVARCHAR(40)  NOT NULL,
                price   DECIMAL(12,2) NOT NULL DEFAULT 0,
                CONSTRAINT UQ_product_uom UNIQUE (part_no, uom)
            )
        """)
    except Exception as e:
        log.warning("[schema] product_uom_prices: %s", e)

    # ── product_taxes — full schema matching product_sync_windows_service ─
    try:
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
    except Exception as e:
        log.warning("[schema] product_taxes: %s", e)

    # ── products — add tax columns if this is an older DB ─────────────
    for col, definition in (
        ("tax_rate",          "DECIMAL(8,4) DEFAULT 0"),
        ("tax_type",          "NVARCHAR(50) DEFAULT 'VAT'"),
        ("item_tax_template", "NVARCHAR(100) DEFAULT ''"),
    ):
        try:
            cur.execute(f"""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'products' AND COLUMN_NAME = '{col}'
                )
                ALTER TABLE products ADD {col} {definition}
            """)
        except Exception as e:
            log.warning("[schema] products.%s: %s", col, e)

# =============================================================================
# TAX EXTRACTION  (ported from product_sync_windows_service.py)
# =============================================================================

_ROOT_GROUPS = {"all item groups", "all"}


def _extract_tax_info(taxes: list, part_no: str = "") -> dict | None:
    """
    Extract tax information from the taxes array.

    Uses `maximum_net_rate` as the single authoritative rate — same as the
    Android/Flutter POS client.  No hardcoded VAT fallback: if Frappe sends
    0, the rate is 0.  Fix upstream rather than papering over it.
    """
    if not taxes:
        log.debug("[TAX] %s — no taxes array, will default to ZERO RATED", part_no)
        return None

    tax = taxes[0]
    log.info("[TAX RAW] %s -> %s", part_no or "?", json.dumps(tax, default=str))

    tax_rate          = float(tax.get("maximum_net_rate") or 0)
    tax_category      = str(tax.get("tax_category")      or "").strip()
    item_tax_template = str(tax.get("item_tax_template") or "").strip()

    # Infer category from template name when blank
    if not tax_category:
        tmpl_upper = item_tax_template.upper()
        if "VAT" in tmpl_upper:
            tax_category = "VAT"
        elif "EXEMPT" in tmpl_upper:
            tax_category = "EXEMPT"
        elif "ZERO" in tmpl_upper:
            tax_category = "ZERO RATED"
        if tax_category:
            log.debug(
                "[TAX] %s — inferred category=%s from template '%s'",
                part_no, tax_category, item_tax_template,
            )

    log.info(
        "[TAX RESOLVED] %s -> rate=%.4f  category='%s'  template='%s'",
        part_no or "?", tax_rate, tax_category, item_tax_template,
    )
    return {
        "tax_rate":          tax_rate,
        "tax_category":      tax_category,
        "item_tax_template": item_tax_template,
    }


def _extract_selling_price(prices: list, stock_uom: str = "Nos") -> float:
    """
    Best selling price from the prices array.
    Priority:
      1. Selling price that matches the stock UOM
      2. Any 'Standard Selling' price list entry
      3. First selling-type entry
    """
    selling = [p for p in (prices or []) if str(p.get("type", "")).lower() == "selling"]
    if not selling:
        return 0.0
    for p in selling:
        if str(p.get("uom") or "").strip().lower() == stock_uom.strip().lower():
            try:
                return float(p.get("price") or 0)
            except (TypeError, ValueError):
                pass
    for p in selling:
        if "standard selling" in str(p.get("priceName") or "").lower():
            try:
                return float(p.get("price") or 0)
            except (TypeError, ValueError):
                pass
    try:
        return float(selling[0].get("price") or 0)
    except (TypeError, ValueError):
        return 0.0


def _get_company_warehouse() -> str:
    """
    Retrieve the company's default warehouse from company defaults.
    
    Returns:
        Warehouse name or empty string if not found
    """
    try:
        from models.company_defaults import get_defaults
        defaults = get_defaults() or {}
        warehouse = defaults.get("server_warehouse", "").strip()
        if warehouse:
            log.debug(f"[STOCK] Using company warehouse: {warehouse}")
            return warehouse
        else:
            log.debug("[STOCK] No company warehouse configured")
            return ""
    except Exception as e:
        log.warning(f"[STOCK] Failed to get company warehouse: {e}")
        return ""


def _extract_stock(warehouses: list) -> float:
    """
    Sum qtyOnHand ONLY for the company's configured warehouse.
    
    If no company warehouse is configured, falls back to summing all warehouses.
    """
    target_warehouse = _get_company_warehouse()
    
    if not warehouses:
        return 0.0
    
    # If no target warehouse specified, sum all (fallback behavior)
    if not target_warehouse:
        total = 0.0
        for w in warehouses:
            try:
                total = 0
            except (TypeError, ValueError):
                pass
        return total
    
    # Filter for the specific warehouse
    target_warehouse_upper = target_warehouse.strip().upper()
    for w in warehouses:
        warehouse_name = str(w.get("warehouse") or "").strip().upper()
        if warehouse_name == target_warehouse_upper:
            try:
                qty = float(w.get("qtyOnHand") or 0)
                log.debug(f"[STOCK] Found stock for warehouse '{target_warehouse}': {qty}")
                return qty
            except (TypeError, ValueError):
                return 0.0
    
    # Warehouse not found in the list
    log.debug(f"[STOCK] Warehouse '{target_warehouse}' not found in product warehouses")
    return 0.0


def _parse_product(p: dict) -> dict | None:
    """
    Maps a raw API product dict → clean local dict with full tax fields.
    Stock is filtered by the company's default warehouse.
    Returns None if the product must be skipped.
    """
    part_no   = str(p.get("itemcode") or "").strip().upper()
    name      = _clean_text(str(p.get("itemname") or "")).strip()[:255]
    stock_uom = str((p.get("uom") or {}).get("stock_uom") or "Nos").strip()

    raw_group = str(p.get("groupname") or "").strip()
    category  = "" if raw_group.lower() in _ROOT_GROUPS else raw_group[:100]

    price = _extract_selling_price(p.get("prices") or [], stock_uom)
    stock = _extract_stock(p.get("warehouses") or [])

    # Tax — full extraction using maximum_net_rate
    tax_info = _extract_tax_info(p.get("taxes") or [], part_no=part_no)

    if not part_no:
        return None

    # UOM prices (selling only, positive price, deduplicated)
    uom_prices = []
    seen_uoms: set = set()
    for rp in (p.get("prices") or []):
        if str(rp.get("type", "")).lower() != "selling":
            continue
        uom_name  = str(rp.get("uom") or "Nos").strip()
        rp_price  = 0.0
        try:
            rp_price = float(rp.get("price") or 0)
        except (TypeError, ValueError):
            pass
        if uom_name and rp_price > 0 and uom_name not in seen_uoms:
            uom_prices.append({"uom": uom_name, "price": rp_price})
            seen_uoms.add(uom_name)

    result = {
        "part_no":             part_no,
        "name":                name or part_no,
        "category":            category,
        "price":               price,
        "stock":               stock,
        "uom":                 stock_uom,
        "uom_prices":          uom_prices,
        "is_pharmacy_product": 1 if p.get("is_pharmacy_product") else 0,
        "batches":             p.get("batches") or [],
    }

    # Kitchen-printer routing flags (custom_is_order_item_1..6 → order_1..6)
    for i in range(1, 7):
        result[f"order_{i}"] = 1 if p.get(f"custom_is_order_item_{i}") else 0

    if tax_info:
        result["tax_rate"]          = tax_info["tax_rate"]
        result["tax_type"]          = tax_info["tax_category"] or "VAT"
        result["item_tax_template"] = tax_info["item_tax_template"]
    else:
        result["tax_rate"]          = 0.0
        result["tax_type"]          = "ZERO RATED"
        result["item_tax_template"] = ""
        log.debug("[TAX] %s — no tax_info, defaulting to ZERO RATED", part_no)

    # Log stock info for debugging
    warehouse = _get_company_warehouse()
    if warehouse:
        log.debug(f"[STOCK] {part_no} — warehouse={warehouse}, qty={stock}")
    else:
        log.debug(f"[STOCK] {part_no} — no warehouse filter, qty={stock}")

    return result

# =============================================================================
# PRODUCT SYNC  (full rewrite using _parse_product for correct taxes)
# =============================================================================

import json
import logging
import math
import time as _time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
 
from database.db import get_connection
from services.site_config import get_host as _get_host
 
log = logging.getLogger("SyncService")
 
API_BASE_URL      = _get_host()
PRODUCTS_ENDPOINT = f"{API_BASE_URL}/api/method/havano_pos_integration.api.get_products"
 
PAGE_SIZE            = 100    # items per API page
MAX_PAGES            = 500    # absolute safety cap — raise if catalog ever exceeds 50 000
MAX_RETRIES          = 3      # per-page retry attempts before skipping
RETRY_BACKOFF_BASE   = 2.0    # seconds; doubles each retry (2s, 4s, 8s)
PARALLEL_WORKERS     = 4      # concurrent HTTP threads — keep ≤ 8 to avoid server throttle
PROGRESS_EVERY       = 50     # print progress counter every N products upserted
REQUEST_TIMEOUT      = 30     # seconds per HTTP request
 
 
# =============================================================================
# INTERNAL: single-page fetch with retry
# =============================================================================
 
def _fetch_page(page_num: int, headers: dict) -> tuple[int, list, dict | None]:
    """
    Fetch one page from the products API.
 
    Returns:
        (page_num, products_list, pagination_dict | None)
 
    Raises:
        RuntimeError if all retries are exhausted.
    """
    url = f"{PRODUCTS_ENDPOINT}?page={page_num}&limit={PAGE_SIZE}"
    last_error = None
 
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                payload   = json.loads(resp.read().decode())
                message   = payload.get("message") or {}
                products  = message.get("products") or []
                paginator = message.get("pagination") or {}
                return page_num, products, paginator
 
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()[:200]
            except Exception:
                pass
            last_error = f"HTTP {e.code}: {body}"
            log.warning("[sync] Page %d attempt %d/%d → %s", page_num, attempt, MAX_RETRIES, last_error)
 
        except Exception as e:
            last_error = str(e)
            log.warning("[sync] Page %d attempt %d/%d → %s", page_num, attempt, MAX_RETRIES, last_error)
 
        if attempt < MAX_RETRIES:
            wait = RETRY_BACKOFF_BASE ** attempt
            log.debug("[sync] Backing off %.1fs before retry", wait)
            _time.sleep(wait)
 
    raise RuntimeError(f"Page {page_num} failed after {MAX_RETRIES} attempts: {last_error}")
 
 
# =============================================================================
# INTERNAL: discover total page count from page-1 response
# =============================================================================
 
def _resolve_total_pages(paginator: dict, products_on_page: int) -> int:
    """
    Use multiple signals from the pagination dict to determine how many pages
    to fetch.  Falls back gracefully when any field is absent or zero.
 
    Priority:
      1. total_count / PAGE_SIZE  (most reliable — pure arithmetic)
      2. total_pages field        (only if sensibly > 0)
      3. has_next_page heuristic  (only as a minimum floor)
      4. 1                        (last resort — we at least have page 1)
    """
    total_count = int(paginator.get("total_count") or 0)
    total_pages = int(paginator.get("total_pages") or 0)
    has_next    = bool(paginator.get("has_next_page"))
 
    # Signal 1: arithmetic is king
    if total_count > 0:
        computed = math.ceil(total_count / PAGE_SIZE)
        log.info(
            "[sync] total_count=%d → computed %d page(s) @ %d per page",
            total_count, computed, PAGE_SIZE,
        )
        return computed
 
    # Signal 2: total_pages field (trust only if sane)
    if total_pages > 0:
        log.info("[sync] Using total_pages=%d from API", total_pages)
        return total_pages
 
    # Signal 3: has_next_page says at least one more page exists
    if has_next:
        log.warning(
            "[sync] No total_count or total_pages in response — "
            "falling back to sequential scan (has_next_page=True)"
        )
        return MAX_PAGES  # Will break early when a page returns 0 products
 
    # Signal 4: nothing useful — we only have page 1
    log.warning(
        "[sync] Cannot determine page count from API response "
        "(paginator=%s). Assuming single page.", paginator
    )
    return 1
 
 
# =============================================================================
# PUBLIC: sync_products  (drop-in replacement)
# =============================================================================
 
def sync_products(api_key: str = "", api_secret: str = "",
                  page: int = None) -> dict:
    """
    Fetches ALL products from Frappe using parallel, retrying HTTP requests,
    parses them with _parse_product(), and upserts them into SQL Server.
 
    Improvements over the original:
      • Pagination driven by total_count arithmetic, not fragile boolean flags.
      • Each page retried up to MAX_RETRIES times before being skipped.
      • Pages fetched in parallel batches of PARALLEL_WORKERS threads.
      • A failed middle page never aborts the rest of the sync.
    """
    result = {
        "products_synced":   0,
        "products_inserted": 0,
        "products_updated":  0,
        "skipped":           0,
        "total_api":         0,
        "pages_fetched":     0,
        "pages_failed":      0,
        "errors":            [],
    }
 
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if api_key and api_secret:
        headers["Authorization"] = f"token {api_key}:{api_secret}"
 
    # ── Step 1: Fetch page 1 to learn the total page count ────────────
    print(f"[sync] Fetching page 1 to determine catalog size…", flush=True)
    try:
        _, p1_products, p1_paginator = _fetch_page(1, headers)
    except RuntimeError as e:
        result["errors"].append(f"Page 1 fetch failed: {e}")
        log.error("[sync] Cannot start sync — page 1 unreachable: %s", e)
        return result
 
    if not p1_products:
        result["errors"].append("API returned 0 products on page 1.")
        log.error("[sync] No products on page 1. Response paginator: %s", p1_paginator)
        return result
 
    result["total_api"]    = int(p1_paginator.get("total_count") or 0)
    result["pages_fetched"] += 1
 
    # Log tax field sample
    sample = p1_products[0]
    log.info(
        "[TAX FIELD DEBUG] Sample '%s' taxes raw: %s",
        sample.get("itemcode", "?"),
        json.dumps(sample.get("taxes", []), default=str),
    )
 
    if page is not None:
        # Caller requested a single specific page only
        all_raw = p1_products if page == 1 else []
        if page != 1:
            try:
                _, all_raw, _ = _fetch_page(page, headers)
                result["pages_fetched"] += 1
            except RuntimeError as e:
                result["errors"].append(str(e))
                return result
    else:
        # ── Step 2: Determine remaining pages ─────────────────────────
        total_pages = _resolve_total_pages(p1_paginator, len(p1_products))
        remaining   = list(range(2, total_pages + 1))
 
        print(
            f"[sync] Catalog: {result['total_api']} products across "
            f"{total_pages} page(s). Fetching {len(remaining)} remaining "
            f"page(s) with {PARALLEL_WORKERS} parallel workers…",
            flush=True,
        )
 
        all_raw: list = list(p1_products)
 
        # ── Step 3: Parallel fetch of remaining pages ──────────────────
        if remaining:
            # Group into batches so we don't open MAX_PAGES threads at once
            def _batched(lst, n):
                for i in range(0, len(lst), n):
                    yield lst[i : i + n]
 
            for batch in _batched(remaining, PARALLEL_WORKERS * 2):
                with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as pool:
                    futures = {
                        pool.submit(_fetch_page, pg, headers): pg
                        for pg in batch
                    }
                    for future in as_completed(futures):
                        pg = futures[future]
                        try:
                            _, products, _ = future.result()
                            if products:
                                all_raw.extend(products)
                                result["pages_fetched"] += 1
                                print(
                                    f"[sync]   ✔ Page {pg}: "
                                    f"{len(products)} products "
                                    f"(running total: {len(all_raw)})",
                                    flush=True,
                                )
                            else:
                                # Empty page beyond the last real page — normal at tail
                                log.debug("[sync] Page %d returned 0 products (tail)", pg)
                        except RuntimeError as e:
                            result["pages_failed"] += 1
                            err_msg = str(e)
                            result["errors"].append(err_msg)
                            log.error("[sync] %s — skipping page, continuing sync", err_msg)
                            print(f"[sync]   ✘ {err_msg} — skipping", flush=True)
 
    if not all_raw:
        result["errors"].append("No products collected after all page fetches.")
        return result
 
    print(
        f"[sync] All pages fetched. Total raw products: {len(all_raw)} "
        f"({result['pages_fetched']} pages OK, {result['pages_failed']} failed)",
        flush=True,
    )
 
    # ── Step 4: Open DB and upsert ────────────────────────────────────
    try:
        conn = get_connection()
        cur  = conn.cursor()
    except Exception as e:
        result["errors"].append(f"DB connection failed: {e}")
        log.error("[sync] DB connection failed: %s", e)
        return result
 
    try:
        _ensure_product_schema(cur)
        conn.commit()
    except Exception as e:
        log.warning("[sync] Schema ensure failed: %s", e)
 
    try:
        cur.execute("SELECT part_no FROM products")
        local_part_nos = {r[0].strip().upper() for r in (cur.fetchall() or []) if r[0]}
    except Exception as e:
        log.warning("[sync] Could not load local part_nos: %s", e)
        local_part_nos = set()
 
    for idx, raw in enumerate(all_raw, start=1):
        part_no_raw = str(raw.get("itemcode") or "").strip()
        if not part_no_raw:
            result["skipped"] += 1
            continue
 
        # Live progress counter (not every product to avoid log flood)
        if idx % PROGRESS_EVERY == 0 or idx == len(all_raw):
            print(
                f"[sync] Upserting {idx}/{len(all_raw)} "
                f"({result['products_inserted']} new, "
                f"{result['products_updated']} updated)…",
                flush=True,
            )
 
        try:
            parsed = _parse_product(raw)
            if parsed is None:
                result["skipped"] += 1
                continue
 
            inserted = _upsert_parsed_product(cur, conn, parsed, local_part_nos)
            result["products_synced"] += 1
            if inserted:
                result["products_inserted"] += 1
            else:
                result["products_updated"] += 1
 
        except Exception as e:
            result["skipped"] += 1
            err_msg = f"{part_no_raw}: {e}"
            result["errors"].append(err_msg)
            log.error("[sync] Error processing %s: %s", part_no_raw, e)
 
    try:
        conn.commit()
    except Exception as e:
        log.warning("[sync] Final commit failed: %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass
 
    print(
        f"[sync] ✅ Done — "
        f"{result['products_inserted']} inserted, "
        f"{result['products_updated']} updated, "
        f"{result['skipped']} skipped, "
        f"{result['pages_failed']} page(s) failed "
        f"({result['pages_fetched']} pages fetched of "
        f"{result['total_api']} total API records)",
        flush=True,
    )
    return result
 
 


def _upsert_parsed_product(cur, conn, p: dict, local_part_nos: set) -> bool:
    """
    Upsert one fully-parsed product dict (from _parse_product) to the DB.
    Returns True if a new row was inserted, False if updated.

    Handles: products row, UOM prices, product_taxes, batches.
    Each sub-section is individually try/excepted so a batch failure
    doesn't roll back the product row.
    """
    part_no           = p["part_no"]
    tax_rate          = p.get("tax_rate",          0.0)
    tax_type          = p.get("tax_type",          "VAT")
    item_tax_template = p.get("item_tax_template", "")
    is_pharm          = p.get("is_pharmacy_product", 0)
    order_flags       = tuple(int(p.get(f"order_{i}", 0) or 0) for i in range(1, 7))

    is_new = part_no not in local_part_nos

    # ── INSERT or UPDATE products row ──────────────────────────────────
    try:
        if is_new:
            cur.execute(
                """
                INSERT INTO products
                    (part_no, name, price, stock, category,
                     uom, conversion_factor,
                     tax_rate, tax_type, item_tax_template,
                     is_pharmacy_product,
                     order_1, order_2, order_3, order_4, order_5, order_6)
                VALUES (?, ?, ?, ?, ?, ?, 1.0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    part_no, p["name"], p["price"], p["stock"], p["category"],
                    p.get("uom", "Nos"),
                    tax_rate, tax_type, item_tax_template,
                    is_pharm,
                    *order_flags,
                ),
            )
            local_part_nos.add(part_no)
            log.debug(
                "[sync] Inserted: %s  tax_rate=%.4f  tax_type=%s  orders=%s",
                part_no, tax_rate, tax_type, order_flags,
            )
        else:
            cur.execute(
                """
                UPDATE products
                SET name                = ?,
                    price               = ?,
                    stock               = ?,
                    category            = CASE WHEN ? <> '' THEN ? ELSE category END,
                    uom                 = ?,
                    tax_rate            = ?,
                    tax_type            = ?,
                    item_tax_template   = ?,
                    is_pharmacy_product = ?,
                    order_1 = ?, order_2 = ?, order_3 = ?,
                    order_4 = ?, order_5 = ?, order_6 = ?
                WHERE part_no = ?
                """,
                (
                    p["name"], p["price"], p["stock"],
                    p["category"], p["category"],
                    p.get("uom", "Nos"),
                    tax_rate, tax_type, item_tax_template,
                    is_pharm,
                    *order_flags,
                    part_no,
                ),
            )
            log.debug(
                "[sync] Updated: %s  tax_rate=%.4f  tax_type=%s  orders=%s",
                part_no, tax_rate, tax_type, order_flags,
            )
        conn.commit()
    except Exception as e:
        log.error("[sync] INSERT/UPDATE failed for %s: %s", part_no, e)
        raise  # Let caller count this as an error

    # ── UOM prices ─────────────────────────────────────────────────────
    for up in (p.get("uom_prices") or []):
        try:
            cur.execute(
                """
                MERGE product_uom_prices AS target
                USING (SELECT ? AS part_no, ? AS uom) AS src
                    ON target.part_no = src.part_no
                   AND target.uom     = src.uom
                WHEN MATCHED THEN
                    UPDATE SET price = ?
                WHEN NOT MATCHED THEN
                    INSERT (part_no, uom, price) VALUES (?, ?, ?);
                """,
                (
                    part_no, up["uom"], up["price"],
                    part_no, up["uom"], up["price"],
                ),
            )
        except Exception as e:
            log.warning("[sync] UOM price MERGE failed for %s/%s: %s", part_no, up.get("uom"), e)
    try:
        conn.commit()
    except Exception as e:
        log.warning("[sync] UOM prices commit failed for %s: %s", part_no, e)

    # ── product_taxes — MERGE on (part_no, tax_category) ──────────────
    #    Always write a row even for ZERO RATED so downstream code never
    #    has to guess.
    try:
        cur.execute(
            """
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
            """,
            (
                part_no, tax_type,
                item_tax_template, tax_rate, tax_rate,
                part_no, tax_type, item_tax_template, tax_rate, tax_rate,
            ),
        )
        conn.commit()
        log.debug("[TAX] Upserted: %s  rate=%.4f  type=%s", part_no, tax_rate, tax_type)
    except Exception as e:
        log.warning("[sync] product_taxes MERGE failed for %s: %s", part_no, e)

    # ── Batches — DELETE + re-INSERT ───────────────────────────────────
    batches = p.get("batches") or []
    try:
        cur.execute(
            "DELETE FROM product_batches "
            "WHERE product_id IN (SELECT id FROM products WHERE part_no = ?)",
            (part_no,),
        )
        for b in batches:
            bn = (b.get("batch_no") or "").strip()
            if not bn:
                continue
            try:
                cur.execute(
                    """
                    INSERT INTO product_batches
                        (product_id, batch_no, expiry_date, qty, synced)
                    SELECT id, ?, ?, ?, 1 FROM products WHERE part_no = ?
                    """,
                    (bn, b.get("expiry_date"), float(b.get("qty") or 0), part_no),
                )
            except Exception as be:
                log.warning("[sync] Batch INSERT failed for %s/%s: %s", part_no, bn, be)
        conn.commit()
        if batches:
            log.debug("[sync] %s — %d batch(es) synced", part_no, len(batches))
    except Exception as e:
        log.warning("[sync] Batch upsert failed for %s: %s", part_no, e)

    return is_new


# =============================================================================
# GL ACCOUNT SYNC
# =============================================================================

def sync_gl_accounts(api_key: str, api_secret: str,
                     host: str, company: str) -> int:
    """
    Fetches Cash and Bank accounts from Frappe Chart of Accounts.
    Makes two separate requests (one per account type).
    """
    from models.gl_account import upsert_account

    account_types_to_sync = ["Cash", "Bank"]
    all_accounts: list = []

    for account_type in account_types_to_sync:
        fields = json.dumps([
            "name", "account_name", "account_number",
            "company", "parent_account", "account_type", "account_currency",
            "is_group",
        ])
        filters = json.dumps([
            ["company",      "=", company],
            ["account_type", "=", account_type],
        ])
        url = (
            f"{host}/api/resource/Account"
            f"?fields={urllib.parse.quote(fields)}"
            f"&filters={urllib.parse.quote(filters)}"
            f"&limit_page_length=500"
        )
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {api_key}:{api_secret}")

        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                accounts = json.loads(r.read().decode()).get("data", [])
                all_accounts.extend(accounts)
                log.debug("Fetched %d %s accounts", len(accounts), account_type)
        except Exception as e:
            log.warning("Failed to fetch %s accounts: %s", account_type, e)

    count = 0
    for acct in all_accounts:
        try:
            upsert_account({
                "name":             acct.get("name", ""),
                "account_name":     acct.get("account_name", ""),
                "account_number":   acct.get("account_number"),
                "company":          acct.get("company", company),
                "parent_account":   acct.get("parent_account", ""),
                "account_type":     acct.get("account_type", ""),
                "account_currency": acct.get("account_currency", "USD"),
            })
            count += 1
        except Exception as e:
            log.warning("Failed to upsert GL account '%s': %s", acct.get("name"), e)

    log.info("GL accounts synced (Cash/Bank only): %d", count)
    print(f"[sync] ✅ GL accounts synced (Cash/Bank only): {count}")
    return count


# =============================================================================
# EXCHANGE RATE SYNC
# =============================================================================

def sync_exchange_rates(api_key: str, api_secret: str,
                        host: str, _force: bool = False) -> int:
    """
    For each non-base currency found in gl_accounts, fetches today's
    exchange rate from Frappe and stores BOTH directions locally:
      - curr → base  (e.g. ZWG → USD)
      - base → curr  (e.g. USD → ZWG)

    _force=True skips the early-exit guard so that a fresh login always
    attempts the sync even if currencies were just written this session.

    Returns count of currency pairs successfully synced.
    """
    import urllib.parse as _up
    from datetime import date as _date
    from models.exchange_rate import upsert_rate

    # ── Resolve base currency ──────────────────────────────────────────
    base_curr = "USD"
    try:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
        base_curr = (d.get("server_company_currency") or "USD").strip().upper() or "USD"
    except Exception as e:
        log.warning("[rates] Could not load base currency, defaulting to USD: %s", e)

    # ── Collect non-base currencies from gl_accounts ───────────────────
    try:
        from models.gl_account import get_all_accounts
        accounts = get_all_accounts() or []
    except Exception as e:
        log.warning("[rates] Could not load GL accounts for rate sync: %s", e)
        return 0

    currencies = {
        (a.get("account_currency") or "").strip().upper()
        for a in accounts
        if (a.get("account_currency") or "").strip().upper() not in ("", base_curr)
    }

    if not currencies:
        if _force:
            log.warning(
                "[rates] _force=True but STILL no non-base currencies found in "
                "gl_accounts (base=%s, total accounts=%d). "
                "GL account sync may have returned 0 rows — check GL sync logs.",
                base_curr, len(accounts),
            )
            print(
                f"[sync] ⚠  No non-base currencies in GL accounts "
                f"(base={base_curr}, accounts={len(accounts)}) — rate sync skipped."
            )
        else:
            log.info("[rates] No non-base currencies found — skipping rate sync.")
        return 0

    today  = _date.today().isoformat()
    count  = 0
    errors = 0

    for curr in sorted(currencies):
        try:
            url = (
                f"{host}/api/method/erpnext.setup.utils.get_exchange_rate"
                f"?from_currency={_up.quote(curr)}"
                f"&to_currency={_up.quote(base_curr)}"
                f"&transaction_date={today}"
            )
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"token {api_key}:{api_secret}")

            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode())

            rate_raw = data.get("message") or data.get("result") or 0
            try:
                rate = float(rate_raw)
            except (TypeError, ValueError):
                rate = 0.0

            if rate > 0:
                upsert_rate(curr, base_curr, rate, today)
                upsert_rate(base_curr, curr, round(1.0 / rate, 8), today)
                count += 1
                log.info(
                    "[rates] %s → %s = %.8f  |  %s → %s = %.8f",
                    curr, base_curr, rate,
                    base_curr, curr, 1.0 / rate,
                )
                print(
                    f"[sync] ✅ Rate synced: 1 {curr} = {rate:.8f} {base_curr}  "
                    f"(1 {base_curr} = {1.0 / rate:,.4f} {curr})"
                )
            else:
                errors += 1
                log.warning(
                    "[rates] Zero/null rate returned for %s → %s (raw=%r)",
                    curr, base_curr, rate_raw,
                )
                print(f"[sync] ⚠  No rate returned for {curr} → {base_curr} (raw={rate_raw!r})")

        except urllib.error.HTTPError as e:
            errors += 1
            body = ""
            try:
                body = e.read().decode()[:300]
            except Exception:
                pass
            log.error(
                "[rates] HTTP %d fetching rate for %s → %s: %s",
                e.code, curr, base_curr, body,
            )
            print(f"[sync] ❌ HTTP {e.code} fetching rate for {curr} → {base_curr}: {body}")

        except Exception as e:
            errors += 1
            log.error("[rates] Failed to fetch rate for %s → %s: %s", curr, base_curr, e)
            print(f"[sync] ❌ Rate fetch failed for {curr} → {base_curr}: {e}")

    log.info(
        "[rates] ✅ %d exchange rate pair(s) synced, %d error(s) (base=%s).",
        count, errors, base_curr,
    )
    print(f"[sync] ✅ Exchange rates: {count} synced, {errors} failed (base={base_curr})")
    return count


# =============================================================================
# MODE OF PAYMENT SYNC
# =============================================================================

def sync_modes_of_payment(api_key: str, api_secret: str,
                           host: str, company: str) -> int:
    from models.gl_account import upsert_mop

    url = (
        f"{host}/api/method/saas_api.www.api.get_modes_of_payment"
        f"?company={urllib.parse.quote(company or '')}"
    )
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {api_key}:{api_secret}")

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.loads(r.read().decode())
    except Exception as e:
        log.warning("MOP list fetch failed: %s", e)
        return 0

    msg      = payload.get("message") or payload
    mop_list = (msg or {}).get("data") or []

    count = 0
    for mop in mop_list:
        mop_name = (mop.get("name") or "").strip()
        if not mop_name:
            continue
        try:
            currency = (mop.get("account_currency") or "USD").strip().upper() or "USD"
            upsert_mop({
                "name":             mop_name,
                "mop_type":         mop.get("type") or "Cash",
                "company":          mop.get("company") or company,
                "gl_account":       mop.get("default_account") or "",
                "account_currency": currency,
            })
            log.debug(
                "MOP synced: %s → %s (%s)",
                mop_name, mop.get("default_account", ""), currency,
            )
            count += 1
        except Exception as e:
            log.warning("Failed to upsert MOP '%s': %s", mop_name, e)

    log.info("Modes of Payment synced: %d", count)
    print(f"[sync] ✅ Modes of Payment synced: {count}")
    return count


# =============================================================================
# TEXT / LOCK HELPERS
# =============================================================================

def _clean_text(text: str) -> str:
    if not text:
        return ""
    return (
        text
        .replace("&amp;",  "&")
        .replace("&lt;",   "<")
        .replace("&gt;",   ">")
        .replace("&quot;", '"')
        .replace("&#39;",  "'")
        .strip()
    )


def _dump_lock_info(cur, table_name: str) -> None:
    """Diagnostic helper — logs active locks on table_name."""
    try:
        cur.execute("SET LOCK_TIMEOUT -1")
        cur.execute(
            """
            SELECT
              tl.request_session_id   AS sid,
              tl.resource_type        AS res_type,
              tl.request_mode         AS mode,
              tl.request_status       AS status,
              es.login_name,
              es.program_name,
              es.host_name
            FROM sys.dm_tran_locks tl
            JOIN sys.dm_exec_sessions es
              ON tl.request_session_id = es.session_id
            WHERE tl.resource_type = 'OBJECT'
              AND tl.resource_associated_entity_id = OBJECT_ID(?)
            """,
            (table_name,),
        )
        rows = cur.fetchall() or []
        print(f"[sync]     ↳ locks on {table_name}: {len(rows)} row(s)", flush=True)
        for r in rows:
            print(
                f"[sync]       sid={r.sid} mode={r.mode} "
                f"status={r.status} login={r.login_name!r} "
                f"prog={r.program_name!r} host={r.host_name!r}",
                flush=True,
            )
        cur.execute(
            """
            SELECT DISTINCT
              r.session_id     AS sid,
              r.status,
              r.command,
              r.wait_type,
              r.blocking_session_id AS blocker,
              SUBSTRING(t.text, 1, 200) AS sql_text
            FROM sys.dm_exec_requests r
            OUTER APPLY sys.dm_exec_sql_text(r.sql_handle) t
            WHERE r.session_id IN (
              SELECT request_session_id FROM sys.dm_tran_locks
              WHERE resource_associated_entity_id = OBJECT_ID(?)
            )
            """,
            (table_name,),
        )
        reqs = cur.fetchall() or []
        for r in reqs:
            print(
                f"[sync]       sid={r.sid} status={r.status!r} "
                f"cmd={r.command!r} wait={r.wait_type!r} "
                f"blocker={r.blocker} sql={r.sql_text!r}",
                flush=True,
            )
    except Exception as _le:
        print(f"[sync]     ↳ could not query lock info: {_le}", flush=True)


# =============================================================================
# UI HELPER
# =============================================================================

def format_sync_result(result: dict) -> str:
    if not result:
        return "No sync performed."
    if "error" in result and not result.get("products_synced"):
        return f"❌ Sync failed: {result['error']}"
    lines = [
        f"✅ Sync complete  ({result.get('total_api', 0)} products on server)",
        f"   • {result.get('products_inserted', 0)} new products added",
        f"   • {result.get('products_updated',  0)} products updated",
    ]
    if result.get("skipped"):
        lines.append(f"   • {result['skipped']} skipped")
    if result.get("gl_accounts_synced") is not None:
        lines.append(f"   • {result['gl_accounts_synced']} GL accounts synced")
    if result.get("modes_of_payment_synced") is not None:
        lines.append(f"   • {result['modes_of_payment_synced']} modes of payment synced")
    if result.get("exchange_rates_synced") is not None:
        lines.append(f"   • {result['exchange_rates_synced']} exchange rate(s) synced")
    if result.get("errors"):
        lines.append(f"   ⚠  {result['errors'][0]}")
    return "\n".join(lines)


# =============================================================================
# SyncWorker — background QThread daemon
# =============================================================================

try:
    from PySide6.QtCore import QObject  # type: ignore

    class SyncWorker(QObject):
        """
        Background daemon that keeps products, stock, GL accounts, MOP and
        exchange rates in sync with Frappe.

        Product / tax / batch loop  : every PRODUCT_SYNC_INTERVAL_SECONDS
        GL + MOP + rates loop       : every GL_MOP_SYNC_INTERVAL_SECONDS
        """

        def run(self) -> None:
            import subprocess
            import sys
            import os

            log.info(
                "[sync] SyncWorker started (product_interval=%ds, gl_interval=%ds)",
                PRODUCT_SYNC_INTERVAL_SECONDS, GL_MOP_SYNC_INTERVAL_SECONDS,
            )

            last_gl_sync = 0.0

            while True:
                try:
                    # ── 1. Product + tax sync via windows-service script ──
                    _here  = os.path.dirname(os.path.abspath(__file__))
                    script = os.path.join(_here, "product_sync_windows_service.py")

                    if not os.path.exists(script):
                        log.error(
                            "[sync] Cannot find product_sync_windows_service.py at %s",
                            script,
                        )
                    else:
                        try:
                            subprocess.run(
                                [sys.executable, script, "debug"],
                                capture_output=True,
                                text=True,
                                timeout=120,
                                cwd=_here,
                            )
                        except subprocess.TimeoutExpired:
                            log.error("[sync] product+tax sync timed out after 120 s")
                        except Exception as e:
                            log.error("[sync] product+tax sync error: %s", e)

                    # ── 2. GL + MOP + exchange rates (less frequent) ──────
                    now = _time.time()
                    if now - last_gl_sync > GL_MOP_SYNC_INTERVAL_SECONDS:
                        try:
                            from services.credentials import get_credentials
                            from models.company_defaults import get_defaults

                            api_key, api_secret = get_credentials()
                            host    = _get_host()
                            company = (get_defaults() or {}).get("server_company", "")

                            if api_key and api_secret:
                                gl_count   = sync_gl_accounts(api_key, api_secret, host, company)
                                mop_count  = sync_modes_of_payment(api_key, api_secret, host, company)
                                rate_count = sync_exchange_rates(
                                    api_key, api_secret, host, _force=True
                                )
                                last_gl_sync = now
                                log.info(
                                    "[sync] Periodic GL/MOP/Rates sync complete: "
                                    "GL=%d MOP=%d Rates=%d",
                                    gl_count, mop_count, rate_count,
                                )
                            else:
                                log.warning(
                                    "[sync] Skipping periodic GL/MOP/Rates sync — "
                                    "no credentials available."
                                )
                        except Exception as e:
                            log.error("[sync] GL/MOP/rates sync error: %s", e)

                    # ── 3. Retry failed sale uploads ──────────────────────
                    try:
                        from services.pos_upload_service import push_unsynced_sales
                        push_unsynced_sales()
                    except Exception as e:
                        log.error("[sync] Auto-recovery upload trigger failed: %s", e)

                except Exception as e:
                    log.error("[sync] Unexpected error in SyncWorker loop: %s", e)

                _time.sleep(PRODUCT_SYNC_INTERVAL_SECONDS)

except ImportError:
    class SyncWorker:          # type: ignore[no-redef]
        """Stub used when PySide6 is unavailable."""
        def run(self) -> None:
            pass


# =============================================================================
# Backwards-compat credential shim
# =============================================================================

def _read_credentials() -> tuple:
    import os
    try:
        from services.credentials import get_credentials
        k, s = get_credentials()
        if k and s:
            return k, s
    except Exception:
        pass
    return (
        os.environ.get("HAVANO_API_KEY",    ""),
        os.environ.get("HAVANO_API_SECRET", ""),
    )
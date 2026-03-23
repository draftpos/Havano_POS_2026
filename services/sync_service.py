# # =============================================================================
# # services/sync_service.py  —  Product Sync  (new /api/get_products endpoint)
# #
# #  NEW API shape  (message.products[]):
# #  {
# #    "itemcode":        "026739",
# #    "itemname":        "Standard Chair",
# #    "groupname":       "All Item Groups",
# #    "maintainstock":   1,
# #    "warehouses":      [{"warehouse": "Stores - AT", "qtyOnHand": 0}],
# #    "default warehouse":"Stores - AT",
# #    "prices":          [{"priceName": "Standard Selling", "price": 25.0,
# #                         "uom": "Nos", "type": "selling"}, ...],
# #    "taxes":           [{"tax_category": "VAT", ...}],
# #    "simple_code":     "026739",
# #    "is_sales_item":   1,
# #    "uom":             {"stock_uom": "Nos", "conversions": [...]},
# #    "food_and_tourism_tax": 0, "food_tax": 0, "tourism_tax": 0,
# #    "cummulative":     0
# #  }
# # =============================================================================

# import urllib.request
# import urllib.error
# import json

# from database.db import get_connection, fetchone_dict

# from services.site_config import get_host as _site_get_host
# API_BASE_URL      = _site_get_host()
# PRODUCTS_ENDPOINT = f"{_site_get_host()}/api/method/havano_pos_integration.api.get_products"
# PAGE_SIZE        = 100          # request up to 100 per page
# MAX_PAGES        = 200          # safety cap


# # =============================================================================
# # PUBLIC — called by auth_service on login
# # =============================================================================

# def sync_from_login_response(login_data: dict) -> dict:
#     """
#     Entry point called by auth_service immediately after a successful online
#     login. Reads api_key/api_secret from the login data and fetches ALL
#     products from the paginated endpoint, then upserts them locally.
#     """
#     token_string = login_data.get("token_string", "")
#     api_key = api_secret = ""
#     if token_string and ":" in token_string:
#         api_key, api_secret = token_string.split(":", 1)

#     return sync_products(api_key=api_key, api_secret=api_secret)


# # =============================================================================
# # PUBLIC — can also be called on demand (e.g. from a background service)
# # =============================================================================

# def sync_products(api_key: str = "", api_secret: str = "",
#                   page: int = None) -> dict:
#     """
#     Fetches all products from the Havano API (handles pagination automatically)
#     and upserts them into the local products table.

#     Pass page=N to sync only one specific page (used by the Windows service).

#     Returns:
#         {
#             "products_synced":   int,
#             "products_inserted": int,
#             "products_updated":  int,
#             "skipped":           int,
#             "total_api":         int,   # total_count from API pagination
#             "pages_fetched":     int,
#             "errors":            list[str],
#         }
#     """
#     result = {
#         "products_synced":   0,
#         "products_inserted": 0,
#         "products_updated":  0,
#         "skipped":           0,
#         "total_api":         0,
#         "pages_fetched":     0,
#         "errors":            [],
#     }

#     headers = {"Accept": "application/json", "Content-Type": "application/json"}
#     if api_key and api_secret:
#         headers["Authorization"] = f"token {api_key}:{api_secret}"

#     if page is not None:
#         # Single-page mode
#         pages_to_fetch = [page]
#     else:
#         # Full sync — discover page count from first response, then loop
#         pages_to_fetch = None   # determined after first fetch

#     current_page = 1
#     while True:
#         url = f"{PRODUCTS_ENDPOINT}?page={current_page}&limit={PAGE_SIZE}"
#         print(f"[sync] Fetching page {current_page}: {url}")

#         try:
#             req = urllib.request.Request(url, headers=headers)
#             with urllib.request.urlopen(req, timeout=30) as resp:
#                 payload = json.loads(resp.read().decode())
#         except urllib.error.HTTPError as e:
#             body = ""
#             try:
#                 body = e.read().decode()[:200]
#             except Exception:
#                 pass
#             result["errors"].append(f"HTTP {e.code} on page {current_page}: {body}")
#             break
#         except Exception as e:
#             result["errors"].append(f"Network error on page {current_page}: {e}")
#             break

#         # ── Parse response ────────────────────────────────────────────────────
#         message    = payload.get("message") or {}
#         products   = message.get("products") or []
#         pagination = message.get("pagination") or {}

#         if not products:
#             if current_page == 1:
#                 result["errors"].append(
#                     f"API returned 0 products on page 1. "
#                     f"Response keys: {list(payload.keys())}. "
#                     f"message keys: {list(message.keys()) if isinstance(message, dict) else type(message).__name__}"
#                 )
#             break   # no more data

#         result["pages_fetched"] += 1
#         result["total_api"] = int(pagination.get("total_count") or 0)
#         total_pages = int(pagination.get("total_pages") or 1)
#         has_next    = bool(pagination.get("has_next_page"))

#         print(f"[sync]   {len(products)} products on page {current_page}/{total_pages}")

#         # ── Upsert this page ──────────────────────────────────────────────────
#         for raw in products:
#             item_code = str(raw.get("itemcode") or "").strip()
#             if not item_code:
#                 result["skipped"] += 1
#                 continue
#             try:
#                 inserted = _upsert_product(raw)
#                 result["products_synced"] += 1
#                 if inserted:
#                     result["products_inserted"] += 1
#                 else:
#                     result["products_updated"] += 1
#             except Exception as e:
#                 result["skipped"] += 1
#                 err_msg = f"{item_code}: {e}"
#                 result["errors"].append(err_msg)
#                 if result["skipped"] <= 5:
#                     print(f"[sync] ❌ {err_msg}")

#         # ── Pagination control ────────────────────────────────────────────────
#         if page is not None:
#             break   # single-page mode requested
#         if not has_next or current_page >= total_pages or current_page >= MAX_PAGES:
#             break
#         current_page += 1

#     print(
#         f"[sync] ✅ Done — "
#         f"{result['products_inserted']} inserted, "
#         f"{result['products_updated']} updated, "
#         f"{result['skipped']} skipped "
#         f"({result['pages_fetched']} page(s) fetched of {result['total_api']} total API records)"
#     )
#     return result


# # =============================================================================
# # PRIVATE — upsert one product from the new API shape
# # =============================================================================

# def _upsert_product(raw: dict) -> bool:
#     """
#     Maps the new API product shape to the local products table and
#     upserts by part_no = itemcode.

#     PRICE RULE: always use the "Standard Selling" price.
#     If the server sends a non-zero selling price, use it.
#     If the server sends 0, keep whatever the cashier has set locally.

#     Returns True = inserted (new), False = updated (existing).
#     """
#     part_no = str(raw.get("itemcode") or "").strip().upper()
#     name    = _clean_text(str(raw.get("itemname") or part_no))[:255]
#     group   = str(raw.get("groupname") or "")[:100]
#     uom     = str((raw.get("uom") or {}).get("stock_uom") or "Nos").strip()
#     simple  = str(raw.get("simple_code") or "").strip()

#     # ── Stock: sum qtyOnHand across all warehouses ────────────────────────────
#     stock = 0.0
#     for wh in (raw.get("warehouses") or []):
#         try:
#             stock += float(wh.get("qtyOnHand") or 0)
#         except (TypeError, ValueError):
#             pass

#     # ── Price: prefer "Standard Selling" type ────────────────────────────────
#     server_price = 0.0
#     for p in (raw.get("prices") or []):
#         if str(p.get("type") or "").lower() == "selling":
#             try:
#                 v = float(p.get("price") or 0)
#                 if v > server_price:
#                     server_price = v     # take highest selling price
#             except (TypeError, ValueError):
#                 pass

#     # ── Tax category (first tax entry wins) ───────────────────────────────────
#     tax_category = ""
#     for t in (raw.get("taxes") or []):
#         tc = str(t.get("tax_category") or "").strip()
#         if tc:
#             tax_category = tc
#             break

#     # ── Category: map from item_group_name ───────────────────────────────────
#     category = group if group not in ("All Item Groups", "") else ""

#     conn = get_connection()
#     cur  = conn.cursor()
#     try:
#         cur.execute(
#             "SELECT id, price FROM products WHERE part_no = ?",
#             (part_no,)
#         )
#         existing = fetchone_dict(cur)

#         if existing:
#             local_price = float(existing.get("price") or 0)
#             new_price   = server_price if server_price > 0 else local_price

#             cur.execute("""
#                 UPDATE products
#                 SET name         = ?,
#                     stock        = ?,
#                     uom          = ?,
#                     price        = ?,
#                     category     = CASE WHEN ? <> '' THEN ? ELSE category END
#                 WHERE part_no = ?
#             """, (name, stock, uom, new_price, category, category, part_no))
#             conn.commit()
#             return False  # updated

#         else:
#             cur.execute("""
#                 INSERT INTO products
#                     (part_no, name, price, stock, category,
#                      uom, conversion_factor,
#                      order_1, order_2, order_3, order_4, order_5, order_6)
#                 VALUES (?, ?, ?, ?, ?, ?, 1.0, 0, 0, 0, 0, 0, 0)
#             """, (part_no, name, server_price, stock, category, uom))
#             conn.commit()
#             return True   # inserted

#     finally:
#         conn.close()

#     # ── Upsert UOM prices ─────────────────────────────────────────────────────
#     _upsert_uom_prices(part_no, raw)


# def _upsert_uom_prices(part_no: str, raw: dict) -> None:
#     """Populate product_uom_prices from all selling prices in API response."""
#     uom_prices = []
#     seen = set()
#     for p in (raw.get("prices") or []):
#         if str(p.get("type") or "").lower() != "selling":
#             continue
#         uom_name = str(p.get("uom") or "Nos").strip()
#         price    = float(p.get("price") or 0)
#         if uom_name not in seen and price > 0:
#             uom_prices.append((uom_name, price))
#             seen.add(uom_name)

#     if not uom_prices:
#         return

#     try:
#         conn = get_connection(); cur = conn.cursor()
#         # Ensure table exists
#         cur.execute("""
#             IF NOT EXISTS (
#                 SELECT 1 FROM INFORMATION_SCHEMA.TABLES
#                 WHERE TABLE_NAME = 'product_uom_prices'
#             )
#             CREATE TABLE product_uom_prices (
#                 id      INT           IDENTITY(1,1) PRIMARY KEY,
#                 part_no NVARCHAR(50)  NOT NULL,
#                 uom     NVARCHAR(40)  NOT NULL,
#                 price   DECIMAL(12,2) NOT NULL DEFAULT 0,
#                 CONSTRAINT UQ_product_uom UNIQUE (part_no, uom)
#             )
#         """)
#         for uom_name, price in uom_prices:
#             cur.execute("""
#                 MERGE product_uom_prices AS target
#                 USING (SELECT ? AS part_no, ? AS uom) AS src
#                     ON target.part_no = src.part_no
#                    AND target.uom     = src.uom
#                 WHEN MATCHED THEN
#                     UPDATE SET price = ?
#                 WHEN NOT MATCHED THEN
#                     INSERT (part_no, uom, price) VALUES (?, ?, ?);
#             """, (part_no, uom_name, price, part_no, uom_name, price))
#         conn.commit(); conn.close()
#     except Exception as e:
#         pass   # never block main sync for UOM failures


# # =============================================================================
# # PRIVATE — helpers
# # =============================================================================

# def _clean_text(text: str) -> str:
#     if not text:
#         return ""
#     return (
#         text
#         .replace("&amp;",  "&")
#         .replace("&lt;",   "<")
#         .replace("&gt;",   ">")
#         .replace("&quot;", '"')
#         .replace("&#39;",  "'")
#         .strip()
#     )


# # =============================================================================
# # UI helper — readable summary
# # =============================================================================

# def format_sync_result(result: dict) -> str:
#     if not result:
#         return "No sync performed."
#     if "error" in result and not result.get("products_synced"):
#         return f"❌ Sync failed: {result['error']}"
#     lines = [
#         f"✅ Sync complete  ({result.get('total_api', 0)} products on server)",
#         f"   • {result.get('products_inserted', 0)} new products added",
#         f"   • {result.get('products_updated',  0)} products updated",
#     ]
#     if result.get("skipped"):
#         lines.append(f"   • {result['skipped']} skipped")
#     if result.get("errors"):
#         lines.append(f"   ⚠  {result['errors'][0]}")
#     return "\n".join(lines)


# # =============================================================================
# # QObject worker — used by main_window.py to run product sync in a QThread
# # =============================================================================

# PRODUCT_SYNC_INTERVAL_SECONDS = 300   # 5 minutes

# import time as _time

# try:
#     from PySide6.QtCore import QObject  # type: ignore

#     class SyncWorker(QObject):
#         """
#         Drop-in QObject that main_window.py moves onto a QThread.

#         Usage (already in main_window.py):
#             thread = QThread()
#             worker = SyncWorker()
#             worker.moveToThread(thread)
#             thread.started.connect(worker.run)
#             thread.start()

#         On each cycle it reads api_key/api_secret from company_defaults,
#         then calls sync_products() and logs the result.
#         """

#         def run(self) -> None:
#             import logging
#             log = logging.getLogger("ProductSync")
#             log.info(
#                 "Product sync worker started (interval=%ds).",
#                 PRODUCT_SYNC_INTERVAL_SECONDS,
#             )
#             _time.sleep(10)   # wait for save_defaults to commit after login
#             while True:
#                 try:
#                     api_key, api_secret = _read_credentials()
#                     if api_key and api_secret:
#                         result = sync_products(api_key=api_key, api_secret=api_secret)
#                         log.info(
#                             "Product sync — %d inserted, %d updated, %d skipped.",
#                             result.get("products_inserted", 0),
#                             result.get("products_updated",  0),
#                             result.get("skipped", 0),
#                         )
#                     else:
#                         log.debug("No API credentials — skipping product sync cycle.")
#                 except Exception as exc:
#                     import logging as _logging
#                     _logging.getLogger("ProductSync").error(
#                         "Unhandled error in product sync: %s", exc
#                     )
#                 _time.sleep(PRODUCT_SYNC_INTERVAL_SECONDS)

# except ImportError:
#     # PySide6 not available (e.g. running as a plain script / Windows service).
#     # Provide a no-op stub so the import in main_window.py doesn't crash.
#     class SyncWorker:          # type: ignore[no-redef]
#         """Stub used when PySide6 is unavailable."""
#         def run(self) -> None:
#             pass


# def _read_credentials() -> tuple:
#     """
#     Read api_key / api_secret.
#     Priority: 1) live auth session  2) company_defaults DB  3) env vars.
#     """
#     import os
#     # 1 — live in-memory session (always available right after login)
#     try:
#         from services.auth_service import get_session
#         s = get_session()
#         if s.get("api_key") and s.get("api_secret"):
#             return s["api_key"], s["api_secret"]
#     except Exception:
#         pass

#     # 2 — company_defaults table (survives app restarts)
#     try:
#         from database.db import get_connection
#         conn = get_connection()
#         cur  = conn.cursor()
#         cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
#         row = cur.fetchone()
#         conn.close()
#         if row and row[0] and row[1]:
#             return row[0], row[1]
#     except Exception:
#         pass

#     # 3 — environment variables
#     return (
#         os.environ.get("HAVANO_API_KEY",    ""),
#         os.environ.get("HAVANO_API_SECRET", ""),
#     )

# =============================================================================
# services/sync_service.py  —  Product Sync  (new /api/get_products endpoint)
#
#  NEW API shape  (message.products[]):
#  {
#    "itemcode":        "026739",
#    "itemname":        "Standard Chair",
#    "groupname":       "All Item Groups",
#    "maintainstock":   1,
#    "warehouses":      [{"warehouse": "Stores - AT", "qtyOnHand": 0}],
#    "default warehouse":"Stores - AT",
#    "prices":          [{"priceName": "Standard Selling", "price": 25.0,
#                         "uom": "Nos", "type": "selling"}, ...],
#    "taxes":           [{"tax_category": "VAT", ...}],
#    "simple_code":     "026739",
#    "is_sales_item":   1,
#    "uom":             {"stock_uom": "Nos", "conversions": [...]},
#    "food_and_tourism_tax": 0, "food_tax": 0, "tourism_tax": 0,
#    "cummulative":     0
#  }
# =============================================================================

import urllib.request
import urllib.error
import json

from database.db import get_connection, fetchone_dict

API_BASE_URL     = "https://apk.havano.cloud"
PRODUCTS_ENDPOINT = f"{API_BASE_URL}/api/method/havano_pos_integration.api.get_products"
PAGE_SIZE        = 100          # request up to 100 per page
MAX_PAGES        = 200          # safety cap


# =============================================================================
# PUBLIC — called by auth_service on login
# =============================================================================

def sync_from_login_response(login_data: dict) -> dict:
    """
    Entry point called by auth_service immediately after a successful online
    login. Reads api_key/api_secret from the login data and fetches ALL
    products from the paginated endpoint, then upserts them locally.
    """
    token_string = login_data.get("token_string", "")
    api_key = api_secret = ""
    if token_string and ":" in token_string:
        api_key, api_secret = token_string.split(":", 1)

    return sync_products(api_key=api_key, api_secret=api_secret)


# =============================================================================
# PUBLIC — can also be called on demand (e.g. from a background service)
# =============================================================================

def sync_products(api_key: str = "", api_secret: str = "",
                  page: int = None) -> dict:
    """
    Fetches all products from the Havano API (handles pagination automatically)
    and upserts them into the local products table.

    Pass page=N to sync only one specific page (used by the Windows service).

    Returns:
        {
            "products_synced":   int,
            "products_inserted": int,
            "products_updated":  int,
            "skipped":           int,
            "total_api":         int,   # total_count from API pagination
            "pages_fetched":     int,
            "errors":            list[str],
        }
    """
    result = {
        "products_synced":   0,
        "products_inserted": 0,
        "products_updated":  0,
        "skipped":           0,
        "total_api":         0,
        "pages_fetched":     0,
        "errors":            [],
    }

    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if api_key and api_secret:
        headers["Authorization"] = f"token {api_key}:{api_secret}"

    if page is not None:
        # Single-page mode
        pages_to_fetch = [page]
    else:
        # Full sync — discover page count from first response, then loop
        pages_to_fetch = None   # determined after first fetch

    current_page = 1
    while True:
        url = f"{PRODUCTS_ENDPOINT}?page={current_page}&limit={PAGE_SIZE}"
        print(f"[sync] Fetching page {current_page}: {url}")

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()[:200]
            except Exception:
                pass
            result["errors"].append(f"HTTP {e.code} on page {current_page}: {body}")
            break
        except Exception as e:
            result["errors"].append(f"Network error on page {current_page}: {e}")
            break

        # ── Parse response ────────────────────────────────────────────────────
        message    = payload.get("message") or {}
        products   = message.get("products") or []
        pagination = message.get("pagination") or {}

        if not products:
            if current_page == 1:
                result["errors"].append(
                    f"API returned 0 products on page 1. "
                    f"Response keys: {list(payload.keys())}. "
                    f"message keys: {list(message.keys()) if isinstance(message, dict) else type(message).__name__}"
                )
            break   # no more data

        result["pages_fetched"] += 1
        result["total_api"] = int(pagination.get("total_count") or 0)
        total_pages = int(pagination.get("total_pages") or 1)
        has_next    = bool(pagination.get("has_next_page"))

        print(f"[sync]   {len(products)} products on page {current_page}/{total_pages}")

        # ── Upsert this page ──────────────────────────────────────────────────
        for raw in products:
            item_code = str(raw.get("itemcode") or "").strip()
            if not item_code:
                result["skipped"] += 1
                continue
            try:
                inserted = _upsert_product(raw)
                result["products_synced"] += 1
                if inserted:
                    result["products_inserted"] += 1
                else:
                    result["products_updated"] += 1
            except Exception as e:
                result["skipped"] += 1
                err_msg = f"{item_code}: {e}"
                result["errors"].append(err_msg)
                if result["skipped"] <= 5:
                    print(f"[sync] ❌ {err_msg}")

        # ── Pagination control ────────────────────────────────────────────────
        if page is not None:
            break   # single-page mode requested
        if not has_next or current_page >= total_pages or current_page >= MAX_PAGES:
            break
        current_page += 1

    print(
        f"[sync] ✅ Done — "
        f"{result['products_inserted']} inserted, "
        f"{result['products_updated']} updated, "
        f"{result['skipped']} skipped "
        f"({result['pages_fetched']} page(s) fetched of {result['total_api']} total API records)"
    )
    return result


# =============================================================================
# PRIVATE — upsert one product from the new API shape
# =============================================================================

def _upsert_product(raw: dict) -> bool:
    """
    Maps the new API product shape to the local products table and
    upserts by part_no = itemcode.

    PRICE RULE: always use the "Standard Selling" price.
    If the server sends a non-zero selling price, use it.
    If the server sends 0, keep whatever the cashier has set locally.

    Returns True = inserted (new), False = updated (existing).
    """
    part_no = str(raw.get("itemcode") or "").strip().upper()
    name    = _clean_text(str(raw.get("itemname") or part_no))[:255]
    group   = str(raw.get("groupname") or "")[:100]
    uom     = str((raw.get("uom") or {}).get("stock_uom") or "Nos").strip()
    simple  = str(raw.get("simple_code") or "").strip()

    # ── Stock: sum qtyOnHand across all warehouses ────────────────────────────
    stock = 0.0
    for wh in (raw.get("warehouses") or []):
        try:
            stock += float(wh.get("qtyOnHand") or 0)
        except (TypeError, ValueError):
            pass

    # ── Price: prefer "Standard Selling" type ────────────────────────────────
    server_price = 0.0
    for p in (raw.get("prices") or []):
        if str(p.get("type") or "").lower() == "selling":
            try:
                v = float(p.get("price") or 0)
                if v > server_price:
                    server_price = v     # take highest selling price
            except (TypeError, ValueError):
                pass

    # ── Tax category (first tax entry wins) ───────────────────────────────────
    tax_category = ""
    for t in (raw.get("taxes") or []):
        tc = str(t.get("tax_category") or "").strip()
        if tc:
            tax_category = tc
            break

    # ── Category: map from item_group_name ───────────────────────────────────
    category = group if group not in ("All Item Groups", "") else ""

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            "SELECT id, price FROM products WHERE part_no = ?",
            (part_no,)
        )
        existing = fetchone_dict(cur)

        if existing:
            local_price = float(existing.get("price") or 0)
            new_price   = server_price if server_price > 0 else local_price

            cur.execute("""
                UPDATE products
                SET name         = ?,
                    stock        = ?,
                    uom          = ?,
                    price        = ?,
                    category     = CASE WHEN ? <> '' THEN ? ELSE category END
                WHERE part_no = ?
            """, (name, stock, uom, new_price, category, category, part_no))
            conn.commit()
            _upsert_uom_prices(cur, part_no, raw.get("prices") or [])
            conn.commit()
            return False  # updated

        else:
            cur.execute("""
                INSERT INTO products
                    (part_no, name, price, stock, category,
                     uom, conversion_factor,
                     order_1, order_2, order_3, order_4, order_5, order_6)
                VALUES (?, ?, ?, ?, ?, ?, 1.0, 0, 0, 0, 0, 0, 0)
            """, (part_no, name, server_price, stock, category, uom))
            conn.commit()
            _upsert_uom_prices(cur, part_no, raw.get("prices") or [])
            conn.commit()
            return True   # inserted

    finally:
        conn.close()


def _upsert_uom_prices(cur, part_no: str, prices: list) -> None:
    """Upsert all selling UOM prices for a product into product_uom_prices."""
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
    except Exception:
        pass

    seen = set()
    for p in prices:
        if str(p.get("type") or "").lower() != "selling":
            continue
        uom_name = str(p.get("uom") or "Nos").strip()
        uom_price = float(p.get("price") or 0)
        if not uom_name or uom_price <= 0 or uom_name in seen:
            continue
        seen.add(uom_name)
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
            """, (part_no, uom_name, uom_price,
                  part_no, uom_name, uom_price))
        except Exception:
            pass


# =============================================================================
# PRIVATE — helpers
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


# =============================================================================
# UI helper — readable summary
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
    if result.get("errors"):
        lines.append(f"   ⚠  {result['errors'][0]}")
    return "\n".join(lines)


# =============================================================================
# QObject worker — used by main_window.py to run product sync in a QThread
# =============================================================================

PRODUCT_SYNC_INTERVAL_SECONDS = 300   # 5 minutes

import time as _time

try:
    from PySide6.QtCore import QObject  # type: ignore

    class SyncWorker(QObject):
        """
        Drop-in QObject that main_window.py moves onto a QThread.

        Usage (already in main_window.py):
            thread = QThread()
            worker = SyncWorker()
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            thread.start()

        On each cycle it reads api_key/api_secret from company_defaults,
        then calls sync_products() and logs the result.
        """

        def run(self) -> None:
            import logging
            log = logging.getLogger("ProductSync")
            log.info(
                "Product sync worker started (interval=%ds).",
                PRODUCT_SYNC_INTERVAL_SECONDS,
            )
            _time.sleep(10)   # wait for save_defaults to commit after login
            while True:
                try:
                    api_key, api_secret = _read_credentials()
                    if api_key and api_secret:
                        result = sync_products(api_key=api_key, api_secret=api_secret)
                        log.info(
                            "Product sync — %d inserted, %d updated, %d skipped.",
                            result.get("products_inserted", 0),
                            result.get("products_updated",  0),
                            result.get("skipped", 0),
                        )
                    else:
                        log.debug("No API credentials — skipping product sync cycle.")
                except Exception as exc:
                    import logging as _logging
                    _logging.getLogger("ProductSync").error(
                        "Unhandled error in product sync: %s", exc
                    )
                _time.sleep(PRODUCT_SYNC_INTERVAL_SECONDS)

except ImportError:
    # PySide6 not available (e.g. running as a plain script / Windows service).
    # Provide a no-op stub so the import in main_window.py doesn't crash.
    class SyncWorker:          # type: ignore[no-redef]
        """Stub used when PySide6 is unavailable."""
        def run(self) -> None:
            pass


def _read_credentials() -> tuple:
    """
    Read api_key / api_secret.
    Priority: 1) live auth session  2) company_defaults DB  3) env vars.
    """
    import os
    # 1 — live in-memory session (always available right after login)
    try:
        from services.auth_service import get_session
        s = get_session()
        if s.get("api_key") and s.get("api_secret"):
            return s["api_key"], s["api_secret"]
    except Exception:
        pass

    # 2 — company_defaults table (survives app restarts)
    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("SELECT api_key, api_secret FROM company_defaults WHERE id = 1")
        row = cur.fetchone()
        conn.close()
        if row and row[0] and row[1]:
            return row[0], row[1]
    except Exception:
        pass

    # 3 — environment variables
    return (
        os.environ.get("HAVANO_API_KEY",    ""),
        os.environ.get("HAVANO_API_SECRET", ""),
    )
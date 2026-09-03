# =============================================================================
# services/odoo/sync_service.py
# Odoo-specific Data Synchronization Service (Consolidated)
# =============================================================================

import json
import logging
import math
import time as _time
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
# pyrefly: ignore [missing-import]
from PySide6.QtCore import QThread

from database.db import get_connection, fetchall_dicts
from services.network_utils import safe_urlopen
from services.credentials import get_all_credentials
from models.company_defaults import get_defaults
from services.site_config import get_host as _get_host
from services.odoo.doctor_sync_service import sync_doctors_odoo
from services.odoo.dosage_sync_service import sync_dosages_odoo
from services.odoo.user_sync_service import sync_users_odoo
log = logging.getLogger("OdooSync")

# Settings
PAGE_SIZE            = 100
MAX_PAGES            = 500
MAX_RETRIES          = 3
RETRY_BACKOFF_BASE   = 2.0
PARALLEL_WORKERS     = 4
REQUEST_TIMEOUT      = 60

# =============================================================================
# PUBLIC ENTRY POINTS
# =============================================================================

def sync_all_odoo():
    """Primary entry point for periodic background sync."""
    defaults = get_defaults() or {}
    # FORCED ONLINE: Ignore work_offline setting so dosages can sync!
    # if defaults.get("work_offline") == "1":
    #    print("[OdooSync] Skipping background sync because 'work_offline' is enabled!", flush=True)
    #    return

    log.info("[OdooSync] Starting background sync cycle...")
    try:
        sync_dosages_odoo() # Moved to top for instant feedback!
        sync_products_odoo()
        sync_product_uoms_odoo()
        sync_customers_odoo()
        sync_users_odoo()
        sync_doctors_odoo()
        sync_price_lists_odoo()
        sync_payment_methods_odoo()
        push_unsynced_customers_odoo()
        push_unsynced_sales_odoo()
        push_unsynced_bundles_odoo()
        log.info("[OdooSync] Background sync cycle complete.")
    except Exception as e:
        log.error(f"[OdooSync] Cycle failed: {e}")

def sync_from_login_response(login_data: dict) -> dict:
    """
    Called after a successful login to perform initial data setup.
    Blocks the UI to ensure products/customers are ready for first-time users.
    """
    log.info("[OdooSync] Starting initial sync from login...")
    result = {
        "products_synced": 0,
        "customers_synced": 0,
        "price_lists_synced": 0,
        "payment_methods_synced": 0,
    }
    
    try:
        # Sync essential data first
        res_p = sync_products_odoo()
        result["products_synced"] = res_p.get("products_synced", 0)
        
        sync_customers_odoo()
        sync_users_odoo()
        sync_doctors_odoo()
        sync_dosages_odoo()
        sync_price_lists_odoo()
        sync_payment_methods_odoo()
        
        log.info("[OdooSync] Initial sync complete.")
    except Exception as e:
        log.error(f"[OdooSync] Initial sync failed: {e}")
        
    return result

# =============================================================================
# WORKER THREAD
# =============================================================================

class SyncWorker(QThread):
    """
    Background thread that periodically refreshes Odoo data.
    """
    def run(self):
        log.info("[OdooSyncWorker] Thread started.")
        while not self.isInterruptionRequested():
            try:
                sync_all_odoo()
            except Exception as e:
                log.error(f"[OdooSyncWorker] Error in loop: {e}")
            
            # Wait 60 seconds before next cycle (or as configured)
            for _ in range(60):
                if self.isInterruptionRequested(): break
                _time.sleep(1)
        log.info("[OdooSyncWorker] Thread stopped.")

# =============================================================================
# PRODUCT SYNC
# =============================================================================

def sync_products_odoo() -> dict:
    creds = get_all_credentials()
    if creds.get("system_mode") != "odoo":
        return {}

    defaults = get_defaults() or {}
    host = defaults.get("server_api_host") or _get_host()
    api_key = defaults.get("odoo_token") or creds.get("odoo_token")

    if not host or not api_key:
        log.warning("[OdooSync] Missing host or api_key, skipping product sync.")
        return {}

    url = f"{host.rstrip('/')}/saas_api/get_products"
    headers = {
        "User-Agent": "PostmanRuntime/7.54.0",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Authorization": api_key
    }

    # Odoo API expects db parameter in JSON body
    db_name = defaults.get("server_database", "")
    body = json.dumps({"db": db_name}).encode('utf-8')

    items = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            req.method = "POST"
            with safe_urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                raw_data = response.read().decode()
                data = json.loads(raw_data)

            # In /saas_api/get_products, the payload can be {"message": [...]} or {"message": {"products": [...]}}
            log.warning(f"[OdooSync] Products API Response keys: {list(data.keys())}")
            
            if "message" in data:
                log.warning(f"[OdooSync] type of message: {type(data['message'])}")
                if isinstance(data["message"], list):
                    items = data["message"]
                    log.warning(f"[OdooSync] Found {len(items)} products in list!")
                    break  # success
                elif isinstance(data["message"], dict):
                    items = data["message"].get("products") or []
                    log.warning(f"[OdooSync] Found {len(items)} products in dict!")
                    break  # success

            if not data.get("success", True):
                log.warning(f"[OdooSync] API success=false (attempt {attempt}): {data.get('message')}")
                _time.sleep(RETRY_BACKOFF_BASE ** attempt)
                continue
            else:
                # Fallback just in case
                items = data.get("user", {}).get("warehouse_items") or \
                        data.get("data", {}).get("items") or \
                        data.get("items") or []
                log.warning(f"[OdooSync] Used fallback extraction, found {len(items)} items")
                break
        except Exception as e:
            log.warning(f"[OdooSync] Fetch failed (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                _time.sleep(RETRY_BACKOFF_BASE ** attempt)

    if items:
        _upsert_products(items)
        try:
            from services.stock_cache import init_stock_cache
            init_stock_cache()
            log.info("[OdooSync] Stock cache refreshed after product sync")
        except Exception as e:
            log.warning(f"[OdooSync] Failed to refresh stock cache: {e}")
        return {"products_synced": len(items)}
    
    return {}

def _upsert_products(items: list[dict]):
    defaults = get_defaults() or {}
    target_warehouse = defaults.get("server_warehouse", "").strip().upper()
    price_list_id = defaults.get("default_price_list_id")

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT part_no FROM products")
        local_part_nos = {row[0].strip().upper() for row in cur.fetchall() if row[0]}

        # Cache price list name
        price_list_name = "Standard Selling"  # Fallback so products always show up
        if price_list_id:
            cur.execute("SELECT name FROM price_lists WHERE id = ?", (price_list_id,))
            pl_row = cur.fetchone()
            if pl_row and pl_row[0]: 
                price_list_name = pl_row[0]

        for item in items:
            # Determine if this item has variants
            variants_list = item.get("variants") or []
            variant_count = len(variants_list)
            
            # If variant_count > 1, this is a template product!
            has_vars = 1 if variant_count > 1 else 0
            is_tmpl = 1 if variant_count > 1 else 0
            
            parent_part_no = str(item.get("itemcode") or item.get("item_code") or item.get("default_code") or "").strip().upper()
            if not parent_part_no: parent_part_no = f"ODOO-{item.get('id')}"

            name = str(item.get("itemname") or item.get("item_name") or item.get("name") or "").strip()
            if not name: continue

            price = float(item.get("list_price") or item.get("val_price") or 0.0)
            # Try to read price from prices array if available
            prices_arr = item.get("prices") or []
            price = 0.0
            for p in prices_arr:
                if p.get("priceName") == "Standard Selling" or p.get("type") == "selling":
                    price = float(p.get("price") or 0.0)
                    break
            
            # Stock Logic
            stock = float(item.get("qty_available") or 0.0)
            warehouse_stock = item.get("warehouses") or item.get("warehouse_stock") or []
            
            # If no target_warehouse is specified, find the default warehouse or sum positive stock
            if not target_warehouse and warehouse_stock:
                default_wh = str(item.get("default warehouse") or "").strip().upper()
                for ws in warehouse_stock:
                    ws_qty = float(ws.get("qtyOnHand") if ws.get("qtyOnHand") is not None else ws.get("available") or ws.get("qty_available") or 0.0)
                    wh_name = str(ws.get("warehouse") or ws.get("warehouse_name") or ws.get("warehouse_code") or "").strip().upper()
                    if default_wh and wh_name == default_wh:
                        stock = ws_qty
                        break
                    elif not default_wh and ws_qty > 0 and "ADJUSTMENT" not in wh_name and "CUSTOMER" not in wh_name:
                        stock += ws_qty

            if target_warehouse and warehouse_stock:
                for ws in warehouse_stock:
                    wh_name = str(ws.get("warehouse") or ws.get("warehouse_name") or ws.get("warehouse_code") or "").strip().upper()
                    if wh_name == target_warehouse:
                        stock = float(ws.get("qtyOnHand") if ws.get("qtyOnHand") is not None else ws.get("available") or ws.get("qty_available") or 0.0)
                        break

            # Metadata
            category = str(item.get("groupname") or item.get("category") or "").strip()[:100]
            
            # UOM Extraction
            uom = str(item.get("uom_name") or "").strip()
            if not uom and item.get("prices") and len(item.get("prices")) > 0:
                uom = str(item.get("prices")[0].get("uom") or "").strip()
            if not uom:
                avail_uoms = item.get("available_uoms") or []
                for au in avail_uoms:
                    if au.get("is_default"):
                        uom = str(au.get("name") or "").strip()
                        break
                if not uom and avail_uoms:
                    uom = str(avail_uoms[0].get("name") or "").strip()
            if not uom:
                uom = "Units"
                
            active = 1 if item.get("active", True) else 0
            is_pharmacy = 1 if item.get("is_pharmacy_product") or item.get("is_pharmacy") else 0
            order_flags = [1 if item.get(f"custom_is_order_item_{i}") else 0 for i in range(1, 7)]

            # Taxes
            taxes = item.get("taxes") or []
            tax_rate = sum(float(t.get("amount") or 0) for t in taxes)
            tax_type = str(taxes[0].get("name") or "VAT").strip() if taxes else "VAT"

            # Bundle Extraction
            is_bundle = 1 if item.get("is_product_bundle") else 0
            expand_bundle = 1 if item.get("expand_bundle_in_so", True) else 0
            bundle_sale = float(item.get("bundle_sale_total") or 0.0)
            bundle_cost = float(item.get("bundle_cost_total") or 0.0)
            bundle_override = 1 if item.get("bundle_price_overridden") else 0
            bundle_lines_json = json.dumps(item.get("bundle_lines") or []) if is_bundle else None

            # Pharmacy Metadata Extraction (Stuffed into Attributes JSON)
            parent_attrs = []
            if is_pharmacy:
                req_rx = 1 if item.get("requires_prescription") else 0
                dosage_str = str(item.get("dosage") or "").strip()
                if req_rx:
                    parent_attrs.append({"attribute": "requires_prescription", "attribute_value": "1"})
                if dosage_str:
                    parent_attrs.append({"attribute": "default_dosage", "attribute_value": dosage_str})
            
            parent_attrs_json = json.dumps(parent_attrs)

            hs_code = str(item.get("hscode") or item.get("hs_code") or "").strip()

            # Upsert the template/parent row
            parent_odoo_id = item.get("id")
            parent_lots = item.get("batches") or item.get("lots") or item.get("lots_serials") or []
            _upsert_single_product(
                cur, local_part_nos, parent_part_no, name, price, stock, category, uom,
                tax_rate, tax_type, active, is_pharmacy, order_flags,
                is_template=is_tmpl, has_variants=has_vars, variant_of=None, attributes=parent_attrs_json,
                prices_list=prices_arr, lots=parent_lots,
                is_bundle=is_bundle, expand_bundle=expand_bundle, bundle_sale=bundle_sale,
                bundle_cost=bundle_cost, bundle_override=bundle_override, bundle_lines_json=bundle_lines_json,
                odoo_id=parent_odoo_id, hs_code=hs_code
            )

            # If there are nested variants, upsert each child variant product!
            if variant_count > 1:
                for var in variants_list:
                    var_id = var.get("id")
                    var_code = str(var.get("default_code") or "").strip().upper()
                    if not var_code:
                        var_code = f"{parent_part_no}-{var_id}"
                    
                    # Variant name usually appends attributes
                    var_name = name
                    odoo_attrs = var.get("attributes") or []
                    attr_names = [f"{a.get('attribute_name')}: {a.get('value_name')}" for a in odoo_attrs if a.get("value_name")]
                    if attr_names:
                        var_name = f"{name} ({', '.join(attr_names)})"

                    var_price = float(var.get("lst_price") or var.get("val_price") or price)
                    var_stock = float(var.get("qtyOnHand") if var.get("qtyOnHand") is not None else var.get("qty_available") or 0.0)
                    var_active = 1 if var.get("active", True) else 0
                    var_hs_code = str(var.get("hscode") or var.get("hs_code") or hs_code).strip()
                    
                    # Try to get variant UOM, fallback to parent
                    var_uom = str(var.get("uom_name") or uom).strip()
                    if not var.get("uom_name"):
                        var_avail_uoms = var.get("available_uoms") or []
                        for au in var_avail_uoms:
                            if au.get("is_default"):
                                var_uom = str(au.get("name") or "").strip()
                                break
                    if not var_uom:
                        var_uom = uom
                    
                    # Format attributes list for VariantPickerDialog
                    local_attrs = [{"attribute": a.get("attribute_name"), "attribute_value": a.get("value_name")} for a in odoo_attrs]
                    local_attrs.extend(parent_attrs)  # Append pharmacy metadata
                    attrs_json = json.dumps(local_attrs)
                    
                    var_is_bundle = 1 if var.get("is_product_bundle") else is_bundle
                    var_expand_bundle = 1 if var.get("expand_bundle_in_so", True) else expand_bundle
                    var_bundle_sale = float(var.get("bundle_sale_total") or bundle_sale)
                    var_bundle_cost = float(var.get("bundle_cost_total") or bundle_cost)
                    var_bundle_override = 1 if var.get("bundle_price_overridden") else bundle_override
                    var_bundle_lines_json = json.dumps(var.get("bundle_lines") or []) if var_is_bundle else bundle_lines_json

                    # Upsert child variant product
                    _upsert_single_product(
                        cur, local_part_nos, var_code, var_name, var_price, var_stock, category, var_uom,
                        tax_rate, tax_type, var_active, is_pharmacy, order_flags,
                        is_template=0, has_variants=0, variant_of=parent_part_no, attributes=attrs_json,
                        prices_list=prices_arr, lots=var.get("batches") or var.get("lots") or var.get("lots_serials") or parent_lots,
                        is_bundle=var_is_bundle, expand_bundle=var_expand_bundle, bundle_sale=var_bundle_sale,
                        bundle_cost=var_bundle_cost, bundle_override=var_bundle_override, bundle_lines_json=var_bundle_lines_json,
                        odoo_id=var_id, hs_code=var_hs_code
                    )

        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"[OdooSync] DB error in products: {e}")
    finally:
        conn.close()

def _upsert_single_product(cur, local_part_nos: set[str], part_no: str, name: str, base_price: float, stock: float,
                           category: str, uom: str, tax_rate: float, tax_type: str, active: int, is_pharmacy: int,
                           order_flags: list[int], is_template: int, has_variants: int, variant_of: str | None,
                           attributes: str, prices_list: list, lots: list,
                           is_bundle: int = 0, expand_bundle: int = 1, bundle_sale: float = 0.0,
                           bundle_cost: float = 0.0, bundle_override: int = 0, bundle_lines_json: str = None,
                           odoo_id: int | None = None, hs_code: str = ""):
    # Upsert products table
    if part_no in local_part_nos:
        cur.execute("""
            UPDATE products SET
                name = ?, price = ?, stock = ?, category = ?, uom = ?,
                tax_rate = ?, tax_type = ?, hs_code = ?, active = ?, is_pharmacy_product = ?,
                order_1 = ?, order_2 = ?, order_3 = ?, order_4 = ?, order_5 = ?, order_6 = ?,
                is_template = ?, has_variants = ?, variant_of = ?, attributes = ?,
                is_product_bundle = ?, expand_bundle_in_so = ?, bundle_sale_total = ?,
                bundle_cost_total = ?, bundle_price_overridden = ?,
                bundle_lines = CASE WHEN sync_status = 'pending' THEN bundle_lines ELSE ? END,
                odoo_id = COALESCE(?, odoo_id)
            WHERE part_no = ?
        """, (name, base_price, stock, category, uom, tax_rate, tax_type, hs_code, active, is_pharmacy, *order_flags,
              is_template, has_variants, variant_of, attributes,
              is_bundle, expand_bundle, bundle_sale, bundle_cost, bundle_override,
              bundle_lines_json, odoo_id, part_no))
    else:
        cur.execute("""
            INSERT INTO products (
                part_no, name, price, stock, category, uom,
                tax_rate, tax_type, hs_code, active, is_pharmacy_product,
                order_1, order_2, order_3, order_4, order_5, order_6,
                is_template, has_variants, variant_of, attributes,
                is_product_bundle, expand_bundle_in_so, bundle_sale_total,
                bundle_cost_total, bundle_price_overridden, bundle_lines, odoo_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (part_no, name, base_price, stock, category, uom, tax_rate, tax_type, hs_code, active, is_pharmacy, *order_flags,
              is_template, has_variants, variant_of, attributes,
              is_bundle, expand_bundle, bundle_sale, bundle_cost, bundle_override,
              bundle_lines_json, odoo_id))
        local_part_nos.add(part_no)

    # item_prices upsert
    if prices_list:
        for p in prices_list:
            pl_name = str(p.get("priceName") or p.get("price_list_name") or "Standard Selling").strip()
            pl_price = float(p.get("price") or base_price)
            pl_uom = str(p.get("uom") or uom).strip()
            pl_type = str(p.get("type") or "selling").strip()
            cur.execute("""
                IF EXISTS (SELECT 1 FROM item_prices WHERE part_no = ? AND price_list = ? AND uom = ?)
                    UPDATE item_prices SET price = ?, price_type = ?, updated_at = GETDATE() WHERE part_no = ? AND price_list = ? AND uom = ?
                ELSE
                    INSERT INTO item_prices (part_no, price_list, price_type, price, uom) VALUES (?, ?, ?, ?, ?)
            """, (part_no, pl_name, pl_uom, pl_price, pl_type, part_no, pl_name, pl_uom, part_no, pl_name, pl_type, pl_price, pl_uom))

        # Odoo customers often default to a price list literally named "Default".
        # Ensure base product prices are available under "Default" as well so they don't ring up as $0.00.
        cur.execute("""
            IF EXISTS (SELECT 1 FROM item_prices WHERE part_no = ? AND price_list = 'Default' AND uom = ?)
                UPDATE item_prices SET price = ?, updated_at = GETDATE() WHERE part_no = ? AND price_list = 'Default' AND uom = ?
            ELSE
                INSERT INTO item_prices (part_no, price_list, price_type, price, uom) VALUES (?, 'Default', 'selling', ?, ?)
        """, (part_no, uom, base_price, part_no, uom, part_no, base_price, uom))

    # product_batches upsert
    if lots:
        cur.execute("SELECT id FROM products WHERE part_no = ?", (part_no,))
        pid_row = cur.fetchone()
        if pid_row:
            pid = pid_row[0]
            cur.execute("DELETE FROM product_batches WHERE product_id = ?", (pid,))
            for lot in lots:
                lot_name = str(lot.get("lot_name") or lot.get("name") or lot.get("batch_no") or "")
                exp_date = lot.get("expiration_date") or lot.get("expiry_date")
                lot_qty = float(lot.get("qty") or lot.get("quantity") or 0.0)
                cur.execute("""
                    INSERT INTO product_batches (product_id, batch_no, expiry_date, qty, synced)
                    VALUES (?, ?, ?, ?, 1)
                """, (pid, lot_name, exp_date, lot_qty))

# =============================================================================
# PRODUCT UOM SYNC (separate step with retry)
# =============================================================================

def sync_product_uoms_odoo():
    """
    Separate UOM sync - fetches the products endpoint and extracts
    available_uoms for products with allow_multi_uom=True.
    Skips the base UOM (already stored on the product row) and only
    stores additional pack sizes with a meaningful fixed_price.
    Includes retry logic for resilience.
    """
    creds = get_all_credentials()
    if creds.get("system_mode") != "odoo":
        return

    # Odoo saas_api currently does not implement a get_uoms endpoint
    return

    defaults = get_defaults() or {}
    host = defaults.get("server_api_host") or _get_host()
    api_key = defaults.get("odoo_token") or creds.get("odoo_token")

    if not host or not api_key:
        return

    url = f"{host.rstrip('/')}/api/v1/products/"
    headers = {
        "User-Agent": "PostmanRuntime/7.54.0",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "X-API-Key": api_key
    }

    # Retry loop
    items = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with safe_urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                data = json.loads(response.read().decode())

            if not data.get("success"):
                log.warning(f"[OdooSync:UOM] API success=false (attempt {attempt})")
                _time.sleep(RETRY_BACKOFF_BASE ** attempt)
                continue

            items = data.get("user", {}).get("warehouse_items") or \
                    data.get("data", {}).get("items") or \
                    data.get("items") or []
            break  # success
        except Exception as e:
            # Handle IncompleteRead by attempting to use partial data already buffered
            import http.client as _http_client
            if isinstance(e, _http_client.IncompleteRead) and e.partial:
                log.warning(
                    f"[OdooSync:UOM] IncompleteRead on attempt {attempt} - "
                    f"using {len(e.partial)} partial bytes"
                )
                try:
                    data = json.loads(e.partial.decode())
                    items = (
                        data.get("user", {}).get("warehouse_items")
                        or data.get("data", {}).get("items")
                        or data.get("items")
                        or []
                    )
                    if items:
                        break  # partial data is usable
                except Exception:
                    pass
            log.warning(f"[OdooSync:UOM] Fetch failed (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                _time.sleep(RETRY_BACKOFF_BASE ** attempt)

    if not items:
        return

    _upsert_product_uoms(items)


def _upsert_product_uoms(items: list[dict]):
    """
    For each product with allow_multi_uom=True, store its additional
    UOM pack sizes in product_uom_prices.
    Skips the product's base UOM (already on the products row) and
    only stores UOMs with a meaningful fixed_price > 0.
    """
    conn = get_connection()
    cur = conn.cursor()
    uom_count = 0

    try:
        for item in items:
            part_no = str(item.get("item_code") or item.get("default_code") or "").strip().upper()
            if not part_no:
                part_no = f"ODOO-{item.get('id')}"

            base_uom = str(item.get("uom_name") or "").strip().upper()
            available_uoms = item.get("available_uoms") or []
            
            if not base_uom:
                for au in available_uoms:
                    if au.get("is_default"):
                        base_uom = str(au.get("name") or "").strip().upper()
                        break

            for uom_item in available_uoms:
                uom_name = str(uom_item.get("name") or "").strip()
                uom_price = float(uom_item.get("price") or uom_item.get("fixed_price") or 0.0)

                # Skip: no name, zero price, or it's the base UOM
                if not uom_name or uom_price <= 0:
                    continue
                if uom_name.strip().upper() == base_uom:
                    continue

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
                    """, (part_no, uom_name, uom_price, part_no, uom_name, uom_price))
                    uom_count += 1
                except Exception as e:
                    log.warning(f"[OdooSync:UOM] MERGE failed {part_no}/{uom_name}: {e}")

        conn.commit()
        if uom_count:
            log.info(f"[OdooSync:UOM] Synced {uom_count} alternative UOM prices")
    except Exception as e:
        conn.rollback()
        log.error(f"[OdooSync:UOM] DB error: {e}")
    finally:
        conn.close()

# =============================================================================
# CUSTOMER SYNC
# =============================================================================

def sync_customers_odoo():
    creds = get_all_credentials()
    if creds.get("system_mode") != "odoo": return

    defaults = get_defaults() or {}
    host = defaults.get("server_api_host") or _get_host()
    api_key = defaults.get("odoo_token") or creds.get("odoo_token")

    if not host or not api_key: return

    url = f"{host.rstrip('/')}/saas_api/get_customers"
    try:
        db_name = defaults.get("server_database", "")
        body = json.dumps({"db": db_name}).encode('utf-8')
        
        req = urllib.request.Request(url, data=body)
        req.add_header("Authorization", api_key)
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "PostmanRuntime/7.54.0")
        req.method = "POST"

        with safe_urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode())
        
        # /saas_api/get_customers payload is usually in {"message": [...]}
        customers = data.get("message", [])
        if isinstance(customers, list) and customers:
            _upsert_customers(customers)
        elif not data.get("success", True):
            log.error(f"[OdooSync] Customer sync API error: {data.get('message')}")
    except Exception as e:
        log.error(f"[OdooSync] Customer sync failed: {e}")

def _upsert_customers(items: list[dict]):
    from models.customer import _ensure_price_list_id
    defaults = get_defaults() or {}
    conn = get_connection(); cur = conn.cursor()
    
    try:
        # Helper for required IDs
        def find_id(table, search_name):
            if not search_name: return None
            cur.execute(f"SELECT id FROM {table} WHERE name = ?", (search_name.strip(),))
            row = cur.fetchone()
            if not row:
                cur.execute(f"SELECT TOP 1 id FROM {table} ORDER BY id ASC")
                row = cur.fetchone()
            return row[0] if row else None

        group_id = find_id("customer_groups", "Individual")
        wh_id    = find_id("warehouses", defaults.get("server_warehouse"))
        cc_id    = find_id("cost_centers", defaults.get("server_cost_center"))

        for item in items:
            name = str(item.get("display_name") or item.get("name") or "").strip()
            if not name: continue
            
            c_type = "Company" if item.get("is_company") else "Individual"
            email  = str(item.get("email") or "").strip()
            phone  = str(item.get("mobile") or item.get("phone") or "").strip()
            pl_name = item.get("property_product_pricelist_name")
            if not pl_name or str(pl_name).lower() == "false":
                pl_id = defaults.get("default_price_list_id")
            else:
                pl_id = _ensure_price_list_id(cur, pl_name)

            cur.execute("""
                MERGE customers AS target
                USING (SELECT ? AS customer_name) AS src ON target.customer_name = src.customer_name
                WHEN MATCHED THEN
                    UPDATE SET customer_type = ?, custom_telephone_number = ?, custom_email_address = ?,
                               default_price_list_id = ISNULL(?, target.default_price_list_id), frappe_synced = 1
                WHEN NOT MATCHED THEN
                    INSERT (customer_name, customer_type, customer_group_id, custom_telephone_number, 
                            custom_email_address, custom_warehouse_id, custom_cost_center_id, 
                            default_price_list_id, outstanding_amount, balance, laybye_balance, frappe_synced)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 1);
            """, (name, c_type, phone, email, pl_id, name, c_type, group_id, phone, email, wh_id, cc_id, pl_id))
            
        conn.commit()
    except Exception as e:
        conn.rollback(); log.error(f"[OdooSync] DB error in customers: {e}")
    finally:
        conn.close()

# =============================================================================
# PRICE LIST SYNC
# =============================================================================

def sync_price_lists_odoo():
    creds = get_all_credentials(); defaults = get_defaults() or {}
    if creds.get("system_mode") != "odoo": return
    
    host = defaults.get("server_api_host") or _get_host()
    api_key = defaults.get("odoo_token") or creds.get("odoo_token")
    if not host or not api_key: return

    url = f"{host.rstrip('/')}/api/resource/Price%20List"
    try:
        req = urllib.request.Request(url)
        req.add_header("Authorization", api_key)
        req.add_header("Content-Type", "application/json")
        with safe_urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode())
            
        items = data.get("data", [])
        if isinstance(items, list) and items:
            for pl_summary in items:
                _upsert_price_list(pl_summary)
            log.info(f"[OdooSync] Synced {len(items)} PriceLists from saas_api")
    except Exception as e:
        log.warning(f"[OdooSync] saas_api Price Lists unavailable: {e}")

def _upsert_price_list(pl_data: dict):
    name = pl_data.get("name", "Unknown"); rules = pl_data.get("rules", [])
    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM price_lists WHERE name = ?", (name,))
        if not cur.fetchone():
            cur.execute("INSERT INTO price_lists (name, selling) VALUES (?, 1)", (name,))
        
        for rule in rules:
            product_id = rule.get("product_id")
            price = float(rule.get("price") or 0); uom = rule.get("uom_name", "Units")
            if product_id:
                cur.execute("SELECT part_no FROM products WHERE part_no = ? OR part_no = ?", 
                           (str(product_id), f"ODOO-{product_id}"))
                p_row = cur.fetchone()
                if p_row:
                    part_no = p_row[0]
                    cur.execute("""
                        IF EXISTS (SELECT 1 FROM item_prices WHERE part_no = ? AND price_list = ? AND uom = ?)
                        UPDATE item_prices SET price = ?, updated_at = SYSDATETIME()
                        WHERE part_no = ? AND price_list = ? AND uom = ?
                        ELSE
                        INSERT INTO item_prices (part_no, price_list, uom, price, price_type)
                        VALUES (?, ?, ?, ?, 'selling')
                    """, (part_no, name, uom, price, part_no, name, uom, part_no, name, uom, price))
        conn.commit()
    except Exception as e:
        conn.rollback(); log.error(f"[OdooSync] PL upsert error: {e}")
    finally: conn.close()

# =============================================================================
# PAYMENT METHOD SYNC
# =============================================================================

def sync_payment_methods_odoo():
    creds = get_all_credentials(); defaults = get_defaults() or {}
    if creds.get("system_mode") != "odoo": return
    host = defaults.get("server_api_host") or _get_host()
    api_key = defaults.get("odoo_token") or creds.get("odoo_token")
    if not host or not api_key: return

    lines_synced = False

    # 1. Sync Payment Methods from /api/method/saas_api.www.api.get_account
    url = f"{host.rstrip('/')}/api/method/saas_api.www.api.get_account"
    try:
        req = urllib.request.Request(url)
        req.add_header("Authorization", api_key)
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "PostmanRuntime/7.54.0")

        with safe_urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode())
        
        # Payload is in {"message": [...]}
        items = data.get("message", [])
        if isinstance(items, list) and items:
            # Map accounts to payment_methods structure
            mapped_items = []
            for item in items:
                mapped_items.append({
                    "name": item.get("name"),
                    "code": item.get("account_name"),
                    "payment_type": "inbound"  # Mock it as inbound so it gets added
                })
            
            _upsert_payment_methods(mapped_items)
            log.info(f"[OdooSync] Synced {len(mapped_items)} payment methods (accounts) from saas_api")
            _populate_mop_from_payment_methods(mapped_items)
        elif not data.get("success", True):
            log.warning(f"[OdooSync] get_account API error: {data.get('message')}")
    except Exception as e:
        log.warning(f"[OdooSync] saas_api get_account unavailable: {e}")

def _upsert_payment_method_lines(items: list[dict]):
    conn = get_connection(); cur = conn.cursor()
    try:
        for item in items:
            if item.get("payment_type") != "inbound": continue
            name = str(item.get("display_name") or item.get("name") or "").strip()
            if not name: continue
            j_type = str(item.get("journal_type") or "General").capitalize()
            j_name = str(item.get("journal_name") or "").strip()
            currency = str(item.get("journal_currency_name") or "USD").strip().upper() or "USD"

            cur.execute("""
                MERGE modes_of_payment AS target
                USING (SELECT ? AS name) AS src ON target.name = src.name
                WHEN MATCHED THEN
                    UPDATE SET type = ?, mop_type = ?, gl_account = ?, account_currency = ?, updated_at = SYSDATETIME()
                WHEN NOT MATCHED THEN
                    INSERT (name, type, mop_type, gl_account, gl_account_name, account_currency, synced_from_api, enabled)
                    VALUES (?, ?, ?, ?, ?, ?, 1, 1);
            """, (name, j_type, j_type, j_name, currency, name, j_type, j_type, j_name, j_name, currency))
        conn.commit()
    except Exception as e:
        conn.rollback(); log.error(f"[OdooSync] MOP (lines) upsert error: {e}")
    finally:
        conn.close()

def _upsert_payment_methods(items: list[dict]):
    conn = get_connection(); cur = conn.cursor()
    try:
        for item in items:
            p_id = item.get("id")
            name = str(item.get("name") or "").strip()
            code = str(item.get("code") or "").strip()
            p_type = str(item.get("payment_type") or "inbound").strip()
            if p_id is None or not name: continue

            cur.execute("""
                MERGE payment_methods AS target
                USING (SELECT ? AS id) AS src ON target.id = src.id
                WHEN MATCHED THEN
                    UPDATE SET name = ?, code = ?, payment_type = ?
                WHEN NOT MATCHED THEN
                    INSERT (id, name, code, payment_type)
                    VALUES (?, ?, ?, ?);
            """, (p_id, name, code, p_type, p_id, name, code, p_type))
        conn.commit()
    except Exception as e:
        conn.rollback(); log.error(f"[OdooSync] Payment Methods upsert error: {e}")
    finally: conn.close()

def _populate_mop_from_payment_methods(items: list[dict]):
    """
    Fallback: when /api/v1/payment-method-lines is unavailable (404),
    populate modes_of_payment from the /api/v1/payment-methods response
    so the Payment Dialog always has usable entries.
    """
    conn = get_connection(); cur = conn.cursor()
    try:
        for item in items:
            if str(item.get("payment_type") or "").strip() != "inbound":
                continue
            name = str(item.get("name") or "").strip()
            code = str(item.get("code") or "").strip()
            if not name:
                continue

            # Infer journal type from code
            code_lower = code.lower()
            if "cash" in code_lower:
                j_type = "Cash"
            elif "bank" in code_lower or "manual" in code_lower:
                j_type = "Bank"
            else:
                j_type = "General"

            cur.execute("""
                MERGE modes_of_payment AS target
                USING (SELECT ? AS name) AS src ON target.name = src.name
                WHEN MATCHED THEN
                    UPDATE SET type = ?, mop_type = ?, updated_at = SYSDATETIME()
                WHEN NOT MATCHED THEN
                    INSERT (name, type, mop_type, gl_account, gl_account_name,
                            account_currency, synced_from_api, enabled)
                    VALUES (?, ?, ?, ?, ?, 'USD', 1, 1);
            """, (name, j_type, j_type,
                  name, j_type, j_type, name, name))
        conn.commit()
        log.info(f"[OdooSync] Fallback: populated modes_of_payment from {len(items)} payment methods")
    except Exception as e:
        conn.rollback()
        log.error(f"[OdooSync] Fallback MOP populate error: {e}")
    finally:
        conn.close()

# =============================================================================
# SALE UPLOAD
# =============================================================================
# BUNDLE SYNC PUSH
# =============================================================================
def _get_local_odoo_id(cur, part_no: str) -> str | None:
    """
    Read the stored Odoo integer ID for a product from the local DB.
    Returns it as a string, or None if not set.
    """
    try:
        cur.execute("SELECT odoo_id FROM products WHERE part_no = ?", (part_no,))
        row = cur.fetchone()
        if row and row[0] is not None:
            return str(row[0])
    except Exception as e:
        log.debug(f"[OdooSync] _get_local_odoo_id({part_no}): {e}")
    return None


def push_unsynced_bundles_odoo():
    creds = get_all_credentials(); defaults = get_defaults() or {}
    if creds.get("system_mode") != "odoo" or defaults.get("work_offline") == "1": return

    host = defaults.get("server_api_host") or _get_host()
    api_key = defaults.get("odoo_token") or creds.get("odoo_token")
    if not host or not api_key: return

    conn = get_connection(); cur = conn.cursor()
    try:
        # Try to include odoo_id (available after migration); fall back gracefully
        # if the column doesn't exist yet on this database instance.
        try:
            cur.execute(
                "SELECT part_no, name, price, bundle_lines, odoo_id "
                "FROM products WHERE is_product_bundle = 1 AND sync_status = 'pending'"
            )
        except Exception:
            cur.execute(
                "SELECT part_no, name, price, bundle_lines "
                "FROM products WHERE is_product_bundle = 1 AND sync_status = 'pending'"
            )
        bundles = fetchall_dicts(cur)

        for bundle in bundles:
            try:
                part_no = bundle["part_no"]

                # ── Step 1: Resolve the Odoo integer ID for the parent product ─
                # Prefer the locally-cached odoo_id written during product sync.
                bundle_product_id: str | None = (
                    str(bundle["odoo_id"]) if bundle.get("odoo_id") else None
                )

                if not bundle_product_id:
                    # Not yet synced FROM Odoo - try to CREATE it there now.
                    parent_payload = {
                        "name": bundle["name"],
                        "default_code": part_no,
                        "is_product_bundle": True,
                        "list_price": float(bundle["price"] or 0),
                        "sale_ok": True,
                        "expand_bundle_in_so": False
                    }
                    url_parent = f"{host.rstrip('/')}/api/v1/products/"
                    req_parent = urllib.request.Request(
                        url_parent,
                        data=json.dumps(parent_payload).encode(),
                        method="POST",
                        headers={"Content-Type": "application/json", "X-API-Key": api_key, "Accept": "*/*"}
                    )
                    try:
                        with safe_urlopen(req_parent, timeout=15) as r1:
                            res1 = json.loads(r1.read().decode())
                            if res1.get("data") and res1["data"].get("id"):
                                bundle_product_id = str(res1["data"]["id"])
                            elif res1.get("id"):
                                bundle_product_id = str(res1["id"])
                        # Cache the newly-minted Odoo ID locally
                        if bundle_product_id:
                            cur.execute(
                                "UPDATE products SET odoo_id = ? WHERE part_no = ?",
                                (int(bundle_product_id), part_no)
                            )
                            conn.commit()
                    except urllib.error.HTTPError as he:
                        if he.code != 400:
                            raise he
                        # 400 = product already exists on Odoo.
                        # Try to extract the existing product's ID from the error body.
                        try:
                            err_body = he.read().decode()
                            err_data = json.loads(err_body)
                            # Odoo sometimes returns the existing record under data.id
                            existing_id = (
                                (err_data.get("data") or {}).get("id")
                                or err_data.get("id")
                            )
                            if existing_id:
                                bundle_product_id = str(existing_id)
                                cur.execute(
                                    "UPDATE products SET odoo_id = ? WHERE part_no = ?",
                                    (int(bundle_product_id), part_no)
                                )
                                conn.commit()
                                log.info(f"[OdooSync] Resolved existing Odoo ID {bundle_product_id} for bundle {part_no} from 400 body")
                            else:
                                log.debug(f"[OdooSync] 400 body for {part_no}: {err_body[:300]}")
                        except Exception:
                            pass

                        if not bundle_product_id:
                            # Cannot recover yet - waiting for product sync to populate
                            # odoo_id. 
                            log.warning(
                                f"[OdooSync] Bundle {part_no}: odoo_id not yet stored "
                                f"locally (exists on Odoo) - will resolve after next product sync"
                            )
                            continue

                if not bundle_product_id:
                    log.error(f"[OdooSync] No Odoo product ID resolved for bundle {part_no} - skipping")
                    continue

                # ── Step 2: Build bundle lines, resolving each item's Odoo ID ─
                lines_json_str = bundle.get("bundle_lines") or "[]"
                try:
                    local_lines = json.loads(lines_json_str)
                except Exception:
                    local_lines = []

                lines_payload = []
                skip_bundle = False
                for ln in local_lines:
                    # Support both current and legacy key names for the item code
                    item_code = (
                        str(ln.get("item_code") or ln.get("product_code") or
                            ln.get("code") or ln.get("part_no") or "")
                    ).strip()
                    if not item_code:
                        continue

                    # Prefer the cached Odoo integer ID for this line item
                    line_odoo_id = _get_local_odoo_id(cur, item_code)
                    if line_odoo_id:
                        product_id_val = int(line_odoo_id)
                    else:
                        # Fallback: send the part_no string
                        product_id_val = item_code
                        log.debug(
                            f"[OdooSync] Bundle {part_no}: line item {item_code} "
                            f"has no cached odoo_id, sending part_no as fallback"
                        )

                    lines_payload.append({
                        "product_id": product_id_val,
                        "quantity": float(ln.get("quantity") or 1),
                        "uom_id": 1,
                        "cost_price": 0.0,
                        "sale_price": float(ln.get("rate") or ln.get("sale_price") or 0.0)
                    })

                if not lines_payload:
                    # Log the actual keys present so we can diagnose key-name mismatches
                    sample_keys = [list(ln.keys()) for ln in local_lines[:3]] if local_lines else []
                    msg = f"No valid lines mapped. bundle_lines has {len(local_lines)} item(s), sample keys: {sample_keys}"
                    log.warning(f"[OdooSync] Bundle {part_no} - skipping push. {msg}")
                    
                    try:
                        cur.execute("UPDATE products SET sync_status = 'failed', sync_error = ? WHERE part_no = ?", (msg[:1000], part_no))
                    except Exception:
                        cur.execute("UPDATE products SET sync_status = 'failed' WHERE part_no = ?", (part_no,))
                    conn.commit()
                    continue

                total_list_price = sum(ln["quantity"] * ln["sale_price"] for ln in lines_payload)
                bundle_lines_data = {
                    "list_price": total_list_price,
                    "expand_bundle_in_so": False,
                    "lines": lines_payload
                }

                url_lines = f"{host.rstrip('/')}/api/v1/products/{bundle_product_id}/bundle"
                req_lines = urllib.request.Request(
                    url_lines,
                    data=json.dumps(bundle_lines_data).encode(),
                    method="POST",
                    headers={"Content-Type": "application/json", "X-API-Key": api_key, "Accept": "*/*"}
                )
                with safe_urlopen(req_lines, timeout=15) as r2:
                    res2 = json.loads(r2.read().decode())

                if res2.get("success") or res2.get("data"):
                    cur.execute("UPDATE products SET sync_status = 'synced' WHERE part_no = ?", (part_no,))
                    conn.commit()
                    log.info(f"[OdooSync] [OK] Bundle {part_no} synced to Odoo ID {bundle_product_id}")
                else:
                    log.error(f"[OdooSync] Failed to sync lines for bundle {part_no}: {res2}")

            except urllib.error.HTTPError as lines_err:
                # Read the full error body so we can distinguish validation
                # failures (unrecoverable) from transient server errors.
                try:
                    body = lines_err.read().decode()
                except Exception:
                    body = ""

                error_msg = ""
                try:
                    err_data = json.loads(body)
                    error_msg = (
                        err_data.get("message")
                        or err_data.get("error")
                        or ""
                    )
                except Exception:
                    error_msg = body[:300]

                log.error(
                    f"[OdooSync] Bundle push error on {bundle['part_no']}: "
                    f"HTTP {lines_err.code} - {body[:400]}"
                )

                # Validation failures (400) with a clear message are unrecoverable
                # until the user fixes the bundle data - mark as 'failed' so
                # we stop hammering the API every 60 seconds.
                if lines_err.code == 400 and error_msg:
                    try:
                        cur.execute(
                            "UPDATE products SET sync_status = 'failed', sync_error = ? "
                            "WHERE part_no = ?",
                            (error_msg[:1000], bundle['part_no'])
                        )
                    except Exception:
                        # sync_error column not migrated yet - status-only fallback
                        cur.execute(
                            "UPDATE products SET sync_status = 'failed' WHERE part_no = ?",
                            (bundle['part_no'],)
                        )
                    conn.commit()
                    log.warning(
                        f"[OdooSync] Bundle {bundle['part_no']} marked as failed: {error_msg}"
                    )

            except Exception as item_err:
                log.error(f"[OdooSync] Bundle push error on {bundle['part_no']}: {item_err}")

    except Exception as e:
        log.error(f"[OdooSync] Push bundles error: {e}")
    finally:
        conn.close()

# =============================================================================

def push_unsynced_sales_odoo():
    creds = get_all_credentials(); defaults = get_defaults() or {}
    if creds.get("system_mode") != "odoo" or defaults.get("work_offline") == "1": return
    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("SELECT id, invoice_no, customer_name, total, method FROM sales WHERE synced = 0 AND (syncing IS NULL OR syncing = 0)")
        for sale in fetchall_dicts(cur):
            _push_sale(sale, cur, conn)
    except Exception as e: log.error(f"[OdooSync] Push sales error: {e}")
    finally: conn.close()

def _push_sale(sale, cur, conn):
    sid = sale["id"]; cur.execute("UPDATE sales SET syncing = 1 WHERE id = ?", (sid,)); conn.commit()
    try:
        cur.execute("SELECT part_no, qty, price FROM sale_items WHERE sale_id = ?", (sid,))
        lines = []
        for it in cur.fetchall():
            p_no = str(it[0]).strip()
            # Resolve Odoo integer product ID from the local DB first (most reliable)
            odoo_pid = None
            try:
                cur2_conn = get_connection()
                c2 = cur2_conn.cursor()
                c2.execute("SELECT odoo_id FROM products WHERE part_no = ?", (p_no,))
                row = c2.fetchone()
                cur2_conn.close()
                if row and row[0]:
                    odoo_pid = int(row[0])
            except Exception:
                pass

            item_code = str(odoo_pid) if odoo_pid is not None else p_no

            lines.append({
                "item_code": item_code,
                "qty": float(it[1]),
                "price": float(it[2])
            })

        defaults = get_defaults() or {}
        host = defaults.get("server_api_host") or _get_host()
        api_key = defaults.get("odoo_token") or get_all_credentials().get("odoo_token")
        db_name = defaults.get("server_database", "")

        def _post(url, payload):
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(), method="POST",
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            )
            try:
                with safe_urlopen(req, timeout=30) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                err_body = e.read().decode()
                log.error(f"[OdooSync] HTTPError {e.code} on {url}: {err_body[:300]}")
                return {"success": False, "message": f"HTTP {e.code}: {err_body[:300]}"}

        sales_payload = {
            "customer": sale["customer_name"] or "Cash Customer",
            "lines": lines,
        }
        if db_name:
            sales_payload["db"] = db_name

        url = f"{host.rstrip('/')}/saas_api/make_sale"
        res = _post(url, sales_payload)
        log.info(f"[OdooSync] /saas_api/make_sale response for {sale['invoice_no']}: {res}")
        print(f"[OdooSync] /make_sale response: {res}")

        error_msg = res.get("error")
        if error_msg or not res.get("sale_order_id"):
            msg = error_msg or "Failed to create sale order"
            log.error(f"[OdooSync] Sale {sale['invoice_no']} - SO creation failed: {msg}")
            cur.execute("UPDATE sales SET syncing=0, sync_error=? WHERE id=?", (str(msg), sid))
            conn.commit()
            return

        so_id = res.get("sale_order_id")
        so_name = res.get("sale_order_name") or res.get("data", {}).get("name") or "ODOO-SYNCED"

        log.info(
            f"[OdooSync] Sale {sale['invoice_no']} -> SO={so_name}({so_id}) synced successfully via saas_api"
        )

        cur.execute(
            "UPDATE sales SET synced=1, syncing=0, frappe_ref=?, odoo_invoice_id=? WHERE id=?",
            (str(so_name), so_id, sid)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        try:
            cur.execute("UPDATE sales SET syncing=0, sync_error=? WHERE id=?", (str(e), sid))
            conn.commit()
        except Exception:
            pass
        log.error(f"[OdooSync] Push sale {sale['invoice_no']} failed: {e}")
        import traceback; traceback.print_exc()

# =============================================================================
# PUSH UNSYNCED CUSTOMERS ODOO
# =============================================================================

def push_unsynced_customers_odoo():
    creds = get_all_credentials(); defaults = get_defaults() or {}
    if creds.get("system_mode") != "odoo" or defaults.get("work_offline") == "1": return

    host = defaults.get("server_api_host") or _get_host()
    api_key = defaults.get("odoo_token") or creds.get("odoo_token")
    if not host or not api_key: return

    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, customer_name, customer_type, custom_telephone_number, 
                   custom_email_address, custom_city, custom_house_no, custom_trade_name
            FROM customers WHERE frappe_synced = 0
        """)
        customers = fetchall_dicts(cur)

        db_name = defaults.get("server_database", "")

        for c in customers:
            customer_id = c["id"]
            name = c["customer_name"]

            payload = {
                "name": name,
                "is_company": c.get("customer_type") == "Company",
                "phone": c.get("custom_telephone_number") or "",
                "mobile": c.get("custom_telephone_number") or "",
                "email": c.get("custom_email_address") or "",
                "city": c.get("custom_city") or "",
                "street": c.get("custom_house_no") or "",
                "vat": c.get("custom_trade_name") or "",
                "customer_rank": 1
            }
            if db_name:
                payload["db"] = db_name

            # Try saas_api directly
            url = f"{host.rstrip('/')}/saas_api/create_customer"
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(), method="POST"
            )
            req.add_header("Authorization", api_key)
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "PostmanRuntime/7.54.0")
            
            try:
                with safe_urlopen(req, timeout=15) as r:
                    res = json.loads(r.read().decode())
                
                if res.get("success") or res.get("data") or res.get("message"):
                    cur.execute("UPDATE customers SET frappe_synced = 1 WHERE id = ?", (customer_id,))
                    conn.commit()
                    log.info(f"[OdooSync] [OK] Customer {name} synced to Odoo via saas_api")
                else:
                    log.error(f"[OdooSync] Failed to push customer {name}: {res}")
            except urllib.error.HTTPError as e:
                err_body = e.read().decode(errors='replace')
                log.error(f"[OdooSync] Failed to push customer {name}: HTTP {e.code} - {err_body[:300]}")
            except Exception as e:
                log.error(f"[OdooSync] Failed to push customer {name}: {e}")

    except Exception as e:
        log.error(f"[OdooSync] Push customers error: {e}")
    finally:
        conn.close()

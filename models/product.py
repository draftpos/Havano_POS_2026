# =============================================================================
# models/product.py  -  SQL Server version (Updated with UOM & Conversion)
# =============================================================================

from database.db import get_connection, fetchall_dicts, fetchone_dict

_ORDER_COLS = [f"order_{i}" for i in range(1, 7)]
_ORDER_SEL  = ", ".join(_ORDER_COLS)   # order_1, order_2, … order_6

# Added uom and conversion_factor to the standard selection
# is_pharmacy_product is wrapped in COALESCE so pre-migration rows still work
# is_template / has_variants / variant_of / attributes come from task 3 (variants).
# All four are COALESCE'd so the SELECT never blows up on a DB that hasn't
# migrated yet (fresh installs pick them up via setup_database.py).
def _get_base_select(warehouse_id: int = None) -> str:
    stock_expr = "p.stock"
    if warehouse_id:
        stock_expr = "COALESCE(pws.stock, 0) AS stock"
    
    return (
        f"p.id, p.part_no, p.name, p.description, p.price, {stock_expr}, p.category, p.image_path, p.uom, p.conversion_factor, "
        "COALESCE(p.is_pharmacy_product, 0) AS is_pharmacy_product, "
        "COALESCE(p.is_butchery_product, 0) AS is_butchery_product, "
        "COALESCE(p.track_stock, 1)         AS track_stock, "
        "COALESCE(p.is_template, 0)         AS is_template, "
        "COALESCE(p.has_variants, 0)        AS has_variants, "
        "p.variant_of, "
        "p.attributes, "
        "COALESCE(p.is_product_bundle, 0)   AS is_product_bundle, "
        "COALESCE(p.expand_bundle_in_so, 1) AS expand_bundle_in_so, "
        "p.bundle_sale_total, p.bundle_cost_total, "
        "COALESCE(p.bundle_price_overridden, 0) AS bundle_price_overridden, "
        "p.bundle_lines, p.cost_price, p.reorder_level, p.hs_code, "
        "p.tax_type, p.tax_rate, "
        f"p.{_ORDER_SEL.replace(', ', ', p.')}"
    )

def _get_base_join(warehouse_id: int = None) -> str:
    joins = []
    if warehouse_id:
        joins.append(f"LEFT JOIN product_warehouse_stock pws ON p.id = pws.product_id AND pws.warehouse_id = {int(warehouse_id)}")
    return "\n".join(joins)


def _apply_prices(products_list: list[dict], price_list_name: str = None) -> list[dict]:
    if not products_list:
        return products_list
    target_pl = (price_list_name or "Standard Selling").strip()
    try:
        from database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT part_no, uom, price FROM item_prices WHERE price_list = ? AND price_type = 'selling'", (target_pl,))
        price_map = {(r[0], r[1]): float(r[2]) for r in cur.fetchall()}
        if target_pl != "Standard Selling":
            cur.execute("SELECT part_no, uom, price FROM item_prices WHERE price_list = 'Standard Selling' AND price_type = 'selling'")
            fallback_map = {(r[0], r[1]): float(r[2]) for r in cur.fetchall()}
            for k, v in fallback_map.items():
                if k not in price_map:
                    price_map[k] = v
        conn.close()
        for p in products_list:
            key = (p.get("part_no"), p.get("uom"))
            if key in price_map and price_map[key] > 0:
                p["price"] = price_map[key]
    except Exception as e:
        print(f"[_apply_prices] Error: {e}")
    return products_list


# =============================================================================
# READ
# =============================================================================

# When include_variants=False (default), variant rows are hidden from the
# grid - only templates and standalone items appear. Cashiers reach variants
# via the variant-picker dialog launched on tapping a template.
_HIDE_VARIANTS = " AND (p.variant_of IS NULL OR p.variant_of = '')"


def _get_warehouse_filter(warehouse_id: int = None, only_in_stock: bool = False) -> str:
    if not warehouse_id:
        return ""
    filter_clause = (
        f" AND (pws.product_id IS NOT NULL "
        f"OR NOT EXISTS (SELECT 1 FROM product_warehouse_stock WHERE warehouse_id = {int(warehouse_id)}))"
    )
    if only_in_stock:
        filter_clause += " AND (COALESCE(p.track_stock, 1) = 0 OR COALESCE(pws.stock, 0) > 0)"
    return filter_clause


def get_all_products(include_variants: bool = False, warehouse_id: int = None, only_in_stock: bool = False, price_list_name: str = None) -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    
    where = "WHERE (p.active = 1 OR p.active IS NULL)"
    if not include_variants:
        where += f" {_HIDE_VARIANTS}"
    where += _get_warehouse_filter(warehouse_id, only_in_stock)
    
    cur.execute(f"SELECT {_get_base_select(warehouse_id)} FROM products p {_get_base_join(warehouse_id)} {where} ORDER BY p.id DESC")
    rows = fetchall_dicts(cur)
    conn.close()
    products = [_to_dict(r, warehouse_id) for r in rows]
    return _apply_prices(products, price_list_name=price_list_name)



def get_products_by_category(category: str, include_variants: bool = False, warehouse_id: int = None, only_in_stock: bool = False, price_list_name: str = None) -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    tail = "" if include_variants else _HIDE_VARIANTS
    wh_filter = _get_warehouse_filter(warehouse_id, only_in_stock)
    cur.execute(f"""
        SELECT {_get_base_select(warehouse_id)}
        FROM products p
        {_get_base_join(warehouse_id)}
        WHERE (p.active = 1 OR p.active IS NULL) AND p.category = ? {tail} {wh_filter}
        ORDER BY p.id DESC
    """, (category,))
    rows = fetchall_dicts(cur)
    conn.close()
    return _apply_prices([_to_dict(r, warehouse_id) for r in rows], price_list_name=price_list_name)



def get_categories() -> list[str]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT DISTINCT category FROM (
            SELECT category FROM products WHERE category IS NOT NULL AND category != ''
            UNION
            SELECT name as category FROM item_groups WHERE name IS NOT NULL AND name != ''
        ) AS t
        ORDER BY category
    """)
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def search_products(query: str, warehouse_id: int = None, only_in_stock: bool = False, limit: int = 30, min_len: int = 3, price_list_name: str = None) -> list[dict]:
    query_clean = query.strip()
    if len(query_clean) < min_len:
        return []

    like = f"%{query_clean}%"
    prefix_like = f"{query_clean}%"
    conn = get_connection()
    cur  = conn.cursor()
    wh_filter = _get_warehouse_filter(warehouse_id, only_in_stock)
    
    cur.execute(f"""
        SELECT TOP {limit} {_get_base_select(warehouse_id)}
        FROM products p
        {_get_base_join(warehouse_id)}
        WHERE (p.active = 1 OR p.active IS NULL) AND (
           p.part_no LIKE ? 
           OR p.name LIKE ?
           OR p.part_no IN (SELECT part_no FROM product_barcodes WHERE barcode LIKE ?)
        ) {wh_filter}
        ORDER BY 
            CASE WHEN p.part_no LIKE ? THEN 1 WHEN p.name LIKE ? THEN 2 ELSE 3 END,
            p.id DESC
    """, (like, like, like, prefix_like, prefix_like))
    rows = fetchall_dicts(cur)
    conn.close()
    products = [_to_dict(r, warehouse_id) for r in rows]
    return _apply_prices(products, price_list_name=price_list_name)



def get_product_by_id(product_id: int, warehouse_id: int = None, price_list_name: str = None) -> dict | None:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(f"SELECT {_get_base_select(warehouse_id)} FROM products p {_get_base_join(warehouse_id)} WHERE p.id = ?", (product_id,))
    row = fetchone_dict(cur)
    conn.close()
    if not row:
        return None
    res = _to_dict(row, warehouse_id)
    return _apply_prices([res], price_list_name=price_list_name)[0] if row else None



def get_product_by_part_no(part_no: str, warehouse_id: int = None, price_list_name: str = None) -> dict | None:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(f"SELECT {_get_base_select(warehouse_id)} FROM products p {_get_base_join(warehouse_id)} WHERE p.part_no = ?", (part_no,))
    row = fetchone_dict(cur)
    if not row:
        # Fallback: check alternative barcodes table
        cur.execute(f"""
            SELECT {_get_base_select(warehouse_id)}
            FROM products p
            {_get_base_join(warehouse_id)}
            WHERE p.part_no = (SELECT TOP 1 part_no FROM product_barcodes WHERE barcode = ?)
        """, (part_no,))
        row = fetchone_dict(cur)
    conn.close()
    if not row:
        return None
    res = _to_dict(row, warehouse_id)
    return _apply_prices([res], price_list_name=price_list_name)[0]


def get_products_by_part_nos(part_nos: list[str], warehouse_id: int = None) -> dict[str, dict]:
    """Bulk fetch existing products by part numbers dict for fast Excel batch imports."""
    if not part_nos:
        return {}
    conn = get_connection()
    cur  = conn.cursor()
    result = {}
    clean_pns = list(set([str(p).strip().upper() for p in part_nos if p and str(p).strip().upper() != 'NAN']))
    for i in range(0, len(clean_pns), 500):
        chunk = clean_pns[i:i+500]
        placeholders = ",".join(["?"] * len(chunk))
        cur.execute(f"SELECT {_get_base_select(warehouse_id)} FROM products p {_get_base_join(warehouse_id)} WHERE UPPER(p.part_no) IN ({placeholders})", chunk)
        rows = fetchall_dicts(cur)
        for r in rows:
            d = _to_dict(r, warehouse_id)
            if d and d.get("part_no"):
                result[d["part_no"].strip().upper()] = d
    conn.close()
    return result



def get_variants_of(template_part_no: str, warehouse_id: int = None, price_list_name: str = None) -> list[dict]:
    """
    All variant rows whose `variant_of` points at this template. Used by the
    variant-picker dialog to build its attribute matrix.
    """
    if not template_part_no:
        return []
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        f"SELECT {_get_base_select(warehouse_id)} FROM products p {_get_base_join(warehouse_id)} WHERE p.variant_of = ? ORDER BY p.name",
        (template_part_no.upper().strip(),),
    )
    rows = fetchall_dicts(cur)
    conn.close()
    products = [_to_dict(r, warehouse_id) for r in rows]
    return _apply_prices(products, price_list_name=price_list_name)



# =============================================================================
# WRITE
# =============================================================================

def create_product(part_no: str, name: str, price: float,
                   stock: float = 0.0, category: str = "",
                   uom: str = "Unit", conversion_factor: float = 1.0,
                   is_pharmacy_product: bool = False,
                   is_butchery_product: bool = False,
                   track_stock: bool = True,
                   is_product_bundle: bool = False,
                   cost_price: float = 0.0,
                   description: str = "",
                   tax_type: str = "",
                   tax_rate: float = 0.0,
                   reorder_level: float = 0.0,
                   batch_no: str = "",
                   expiry_date: str = "",
                   hs_code: str = "",
                   **orders) -> dict:
    """
    orders kwargs: order_1=True, order_2=False, … (all default False)
    """
    order_vals = [int(bool(orders.get(f"order_{i}", False))) for i in range(1, 7)]
    # Check for duplicate part_no before inserting
    if get_product_by_part_no(part_no):
        raise ValueError(f"A product with Part No '{part_no.upper().strip()}' already exists.")

    from models.advance_settings import AdvanceSettings
    if AdvanceSettings.load_from_file().capitalizeItemNames:
        name = " ".join([w[0].upper() + w[1:] if w else "" for w in name.split(" ")])

    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(f"""
        INSERT INTO products (part_no, name, description, price, stock, category, uom, conversion_factor,
                              is_pharmacy_product, is_butchery_product, track_stock, is_product_bundle, cost_price, tax_type, tax_rate, reorder_level, hs_code, {_ORDER_SEL})
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (part_no.upper().strip(), name.strip(), description.strip(), float(price),
          float(stock), category.strip(), uom.strip(), float(conversion_factor),
          int(bool(is_pharmacy_product)), int(bool(is_butchery_product)), int(bool(track_stock)), int(bool(is_product_bundle)), float(cost_price), tax_type, float(tax_rate), float(reorder_level), hs_code.strip(), *order_vals))
    new_id = int(cur.fetchone()[0])
    
    if float(stock) != 0:
        import time
        doc_no = f"OPEN-{int(time.time())}-{new_id}"
        
        warehouse_id = 1
        try:
            from models.company_defaults import get_defaults
            defs = get_defaults() or {}
            wh_name = defs.get("server_warehouse")
            if wh_name:
                cur.execute("SELECT id FROM warehouses WHERE name = ?", (wh_name,))
                r = cur.fetchone()
                if r:
                    warehouse_id = r[0]
            else:
                cur.execute("SELECT TOP 1 id FROM warehouses ORDER BY is_default DESC, id ASC")
                r = cur.fetchone()
                if r:
                    warehouse_id = r[0]
        except Exception:
            pass

        cur.execute("""
            INSERT INTO stock_entries (date, doc_no, synced, warehouse_id)
            OUTPUT INSERTED.id
            VALUES (SYSDATETIME(), ?, 0, ?)
        """, (doc_no, warehouse_id))
        se_id = int(cur.fetchone()[0])
        cur.execute("""
            INSERT INTO stock_entry_items (parent_id, product_id, qty, cost_price, selling_price)
            VALUES (?, ?, ?, ?, ?)
        """, (se_id, new_id, float(stock), float(cost_price), float(price)))

        if is_pharmacy_product and batch_no:
            try:
                cur.execute("""
                    INSERT INTO product_batches (product_id, batch_no, expiry_date, qty, synced)
                    VALUES (?, ?, ?, ?, 0)
                """, (new_id, batch_no, expiry_date if expiry_date else None, float(stock)))
            except Exception as e:
                print(f"Error inserting initial batch: {e}")

    conn.commit()
    conn.close()
    return get_product_by_id(new_id)


def update_product(product_id: int, part_no: str = None, name: str = None,
                   price: float = None, stock: float = None,
                   category: str = None, uom: str = None,
                   conversion_factor: float = None,
                   is_pharmacy_product: bool = None,
                   is_butchery_product: bool = None,
                   track_stock: bool = None,
                   is_product_bundle: bool = None,
                   cost_price: float = None,
                   description: str = None,
                   tax_type: str = None,
                   tax_rate: float = None,
                   reorder_level: float = None,
                   batch_no: str = "",
                   expiry_date: str = "",
                   hs_code: str = None,
                   **orders) -> dict | None:

    product = get_product_by_id(product_id)
    if not product:
        return None

    new_part_no  = part_no.upper().strip() if part_no  is not None else product["part_no"]
    
    # If part_no is changing, check for uniqueness
    if part_no is not None and new_part_no != product["part_no"]:
        if get_product_by_part_no(new_part_no):
            raise ValueError(f"A product with Part No '{new_part_no}' already exists.")

    new_name     = name.strip()            if name     is not None else product["name"]
    from models.advance_settings import AdvanceSettings
    if name is not None and AdvanceSettings.load_from_file().capitalizeItemNames:
        new_name = " ".join([w[0].upper() + w[1:] if w else "" for w in new_name.split(" ")])
        
    new_desc     = description.strip()     if description is not None else product.get("description", "")
    new_price    = float(price)            if price    is not None else product["price"]
    new_stock    = float(stock)              if stock    is not None else product["stock"]
    new_category = category.strip()        if category is not None else product["category"]
    new_uom      = uom.strip()             if uom      is not None else product["uom"]
    new_conv     = float(conversion_factor) if conversion_factor is not None else product["conversion_factor"]
    new_pharmacy = int(bool(is_pharmacy_product)) if is_pharmacy_product is not None \
                   else int(bool(product.get("is_pharmacy_product", 0)))
    new_butchery = int(bool(is_butchery_product)) if is_butchery_product is not None \
                   else int(bool(product.get("is_butchery_product", 0)))
    new_track    = int(bool(track_stock)) if track_stock is not None else int(bool(product.get("track_stock", 1)))
    new_bundle   = int(bool(is_product_bundle)) if is_product_bundle is not None else int(bool(product.get("is_product_bundle", 0)))
    new_cost     = float(cost_price)       if cost_price is not None else float(product.get("cost_price", 0.0))
    new_tax_type = tax_type if tax_type is not None else product.get("tax_type", "")
    new_tax_rate = float(tax_rate) if tax_rate is not None else float(product.get("tax_rate", 0.0))
    new_reorder  = float(reorder_level) if reorder_level is not None else float(product.get("reorder_level", 0.0))
    new_hs_code  = hs_code.strip() if hs_code is not None else product.get("hs_code", "")

    new_orders = [
        int(bool(orders[f"order_{i}"])) if f"order_{i}" in orders
        else int(product[f"order_{i}"])
        for i in range(1, 7)
    ]

    order_set = ", ".join(f"order_{i}=?" for i in range(1, 7))

    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(f"""
        UPDATE products
        SET part_no=?, name=?, description=?, price=?, stock=?, category=?, uom=?, conversion_factor=?,
            is_pharmacy_product=?, is_butchery_product=?, track_stock=?, is_product_bundle=?, cost_price=?, tax_type=?, tax_rate=?, reorder_level=?, hs_code=?,
            sync_status='pending',
            {order_set}
        WHERE id=?
    """, (new_part_no, new_name, new_desc, new_price, new_stock, new_category, new_uom, new_conv,
          new_pharmacy, new_butchery, new_track, new_bundle, new_cost, new_tax_type, new_tax_rate, new_reorder, new_hs_code, *new_orders, product_id))

    if new_pharmacy and batch_no:
        try:
            cur.execute("SELECT 1 FROM product_batches WHERE product_id=? AND batch_no=?", (product_id, batch_no))
            if cur.fetchone():
                cur.execute("UPDATE product_batches SET expiry_date=? WHERE product_id=? AND batch_no=?", (expiry_date if expiry_date else None, product_id, batch_no))
            else:
                cur.execute("INSERT INTO product_batches (product_id, batch_no, expiry_date, qty, synced) VALUES (?, ?, ?, 0, 0)", (product_id, batch_no, expiry_date if expiry_date else None))
        except Exception as e:
            print(f"Error updating batch: {e}")

    stock_diff = float(new_stock) - float(product["stock"])
    if stock_diff != 0:
        import time
        doc_no = f"ADJ-{int(time.time())}-{product_id}"
        
        warehouse_id = 1
        try:
            from models.company_defaults import get_defaults
            defs = get_defaults() or {}
            wh_name = defs.get("server_warehouse")
            if wh_name:
                cur.execute("SELECT id FROM warehouses WHERE name = ?", (wh_name,))
                r = cur.fetchone()
                if r:
                    warehouse_id = r[0]
            else:
                cur.execute("SELECT TOP 1 id FROM warehouses ORDER BY is_default DESC, id ASC")
                r = cur.fetchone()
                if r:
                    warehouse_id = r[0]
        except Exception:
            pass

        cur.execute("""
            INSERT INTO stock_entries (date, doc_no, synced, warehouse_id)
            OUTPUT INSERTED.id
            VALUES (SYSDATETIME(), ?, 0, ?)
        """, (doc_no, warehouse_id))
        se_id = int(cur.fetchone()[0])
        cur.execute("""
            INSERT INTO stock_entry_items (parent_id, product_id, qty, cost_price, selling_price)
            VALUES (?, ?, ?, ?, ?)
        """, (se_id, product_id, stock_diff, float(new_cost), float(new_price)))

    conn.commit()
    conn.close()
    return get_product_by_id(product_id)


def delete_product(product_id: int) -> bool:
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("UPDATE products SET active = 0 WHERE id = ?", (product_id,))
        affected = cur.rowcount
        conn.commit()
        return affected > 0
    except Exception as e:
        error_msg = str(e)
        if "REFERENCE constraint" in error_msg:
            if "stock_entry_items" in error_msg:
                raise ValueError("Cannot delete this product because it has associated stock entries (inventory history).")
            elif "sale" in error_msg.lower():
                raise ValueError("Cannot delete this product because it is linked to past sales.")
            else:
                raise ValueError("Cannot delete this product because it is linked to other historical records.")
        raise
    finally:
        conn.close()


def adjust_stock(product_id: int, quantity_delta: float, warehouse_id: int = None) -> dict | None:
    """
    Adjusts stock for a specific product. 
    If warehouse_id is provided, it updates (or creates) the entry in product_warehouse_stock.
    Also updates the global products.stock for backward compatibility / quick lookup.
    """
    conn = get_connection()
    cur  = conn.cursor()
    
    # 1. Update Global Stock
    cur.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (float(quantity_delta), product_id))
    
    # 2. Update Warehouse Stock if warehouse_id provided
    if warehouse_id:
        cur.execute("""
            IF EXISTS (SELECT 1 FROM product_warehouse_stock WHERE product_id = ? AND warehouse_id = ?)
                UPDATE product_warehouse_stock SET stock = stock + ? WHERE product_id = ? AND warehouse_id = ?
            ELSE
                INSERT INTO product_warehouse_stock (product_id, warehouse_id, stock) VALUES (?, ?, ?)
        """, (product_id, warehouse_id, float(quantity_delta), product_id, warehouse_id,
              product_id, warehouse_id, float(quantity_delta)))
        
    conn.commit()
    conn.close()
    return get_product_by_id(product_id, warehouse_id=warehouse_id)



def set_product_image(product_id: int, image_path: str) -> None:
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("UPDATE products SET image_path = ? WHERE id = ?", (image_path, product_id))
        conn.commit()
    except Exception:
        pass 
    conn.close()


def remove_product_image(product_id: int) -> None:
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("UPDATE products SET image_path = NULL WHERE id = ?", (product_id,))
        conn.commit()
    except Exception:
        pass
    conn.close()


# =============================================================================
# ITEM PRICES (Local Price List overrides)
# =============================================================================

def get_item_prices(part_no: str) -> list[dict]:
    """Retrieve all price entries for a specific product from the item_prices table."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, price_list, uom, qty, price, price_type
        FROM item_prices
        WHERE part_no = ?
        ORDER BY price_list, uom
    """, (part_no.strip().upper(),))
    rows = fetchall_dicts(cur)
    conn.close()
    return rows


def upsert_item_price(part_no: str, price_list: str, uom: str, price: float, price_type: str = "Selling", qty: float = 1.0) -> None:
    """Save or update a local price list entry for a product."""
    conn = get_connection()
    cur  = conn.cursor()
    # SQL Server MERGE for local persistence
    cur.execute("""
        MERGE item_prices AS target
        USING (SELECT ? AS part_no, ? AS price_list, ? AS uom) AS source
            ON target.part_no = source.part_no
           AND target.price_list = source.price_list
           AND target.uom = source.uom
        WHEN MATCHED THEN
            UPDATE SET price = ?, price_type = ?, qty = ?, updated_at = SYSDATETIME()
        WHEN NOT MATCHED THEN
            INSERT (part_no, price_list, uom, price, price_type, qty)
            VALUES (?, ?, ?, ?, ?, ?);
    """, (
        part_no.strip().upper(), price_list.strip(), uom.strip(),
        float(price), price_type, float(qty),
        part_no.strip().upper(), price_list.strip(), uom.strip(), float(price), price_type, float(qty)
    ))
    conn.commit()
    conn.close()


def delete_item_price(price_id: int) -> bool:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("DELETE FROM item_prices WHERE id = ?", (price_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# =============================================================================
# PRIVATE
# =============================================================================

def _calculate_bundle_stock(bundle_lines_json: str, warehouse_id: int = None) -> float:
    try:
        if not bundle_lines_json:
            return 0.0
        import json
        lines = json.loads(bundle_lines_json)
        if not lines:
            return 0.0
        
        from database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        min_qty = float("inf")
        for ln in lines:
            l_part = str(ln.get("item_code") or ln.get("product_code") or ln.get("code") or ln.get("part_no") or "").upper().strip()
            l_odoo = int(ln.get("product_id") or 0)
            l_qty = float(ln.get("quantity") or 1)
            if (not l_part and not l_odoo) or l_qty <= 0:
                continue
            
            if warehouse_id:
                try: wh_id_int = int(warehouse_id)
                except: wh_id_int = warehouse_id
                
                cur.execute("""
                    SELECT COALESCE(pws.stock, 0)
                    FROM products p
                    LEFT JOIN product_warehouse_stock pws 
                           ON p.id = pws.product_id AND pws.warehouse_id = ?
                    WHERE p.part_no = ? OR p.odoo_id = ?
                """, (wh_id_int, l_part, l_odoo))
            else:
                cur.execute("SELECT stock FROM products WHERE part_no = ? OR odoo_id = ?", (l_part, l_odoo))
                
            r = cur.fetchone()
            s = float(r[0]) if r else 0.0
            possible = s / l_qty
            if possible < min_qty:
                min_qty = possible
        conn.close()
        import math
        return float(math.floor(min_qty)) if min_qty != float("inf") else 0.0
    except Exception as e:
        print(f"[BundleStock] Error calculating bundle stock: {e}")
        return 0.0

def _to_dict(row: dict, warehouse_id: int = None) -> dict | None:
    if not row:
        return None
        
    stock = float(row["stock"])
    is_bundle = bool(row.get("is_product_bundle", 0))
    if is_bundle:
        stock = _calculate_bundle_stock(row.get("bundle_lines"), warehouse_id)
        
    return {
        "id":                row["id"],
        "part_no":           row["part_no"]    or "",
        "name":              row["name"]       or "",
        "description":       row.get("description") or "",
        "price":             float(row["price"]),
        "stock":             stock, # Switched to float for UOM precision
        "category":          row["category"]   or "",
        "image_path":        row.get("image_path") or "",
        "uom":               row.get("uom") or "Unit",
        "conversion_factor": float(row.get("conversion_factor") or 1.0),
        "is_pharmacy_product": bool(row.get("is_pharmacy_product", False)),
        "is_butchery_product": bool(row.get("is_butchery_product", False)),
        "track_stock":       bool(row.get("track_stock", True)),
        "cost_price":        float(row.get("cost_price") or 0.0),
        "reorder_level":     float(row.get("reorder_level") or 0.0),
        "tax_type":          row.get("tax_type") or "",
        "tax_rate":          float(row.get("tax_rate") or 0.0),
        "hs_code":           row.get("hs_code") or "",
        # Variant flags - present even on pre-migration rows via COALESCE.
        "is_template":   bool(row.get("is_template",  False)),
        "has_variants":  bool(row.get("has_variants", False)),
        "variant_of":    (row.get("variant_of") or "") or None,
        "attributes":    row.get("attributes") or "",
        "is_product_bundle": is_bundle,
        "bundle_lines":      row.get("bundle_lines") or "[]",
        **{f"order_{i}": bool(row.get(f"order_{i}", False)) for i in range(1, 7)},
    }


# =============================================================================
# PHARMACY - product batches
# =============================================================================

def get_batches_for_product(product_id: int) -> list[dict]:
    """
    Returns all batches for a product as a list of dicts:
        [{"batch_no": str, "expiry_date": str|None, "qty": float}, ...]
    Returns an empty list if the product has no batches (or if the
    product_batches table is missing - defensive for pre-migration DBs).
    """
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("""
            SELECT batch_no, expiry_date, qty
            FROM product_batches
            WHERE product_id = ?
            ORDER BY expiry_date, batch_no
        """, (product_id,))
        rows = fetchall_dicts(cur)
        conn.close()
    except Exception:
        return []

    out = []
    for r in rows:
        exp = r.get("expiry_date")
        exp_str = exp.isoformat() if hasattr(exp, "isoformat") else (str(exp) if exp else None)
        out.append({
            "batch_no":    r.get("batch_no") or "",
            "expiry_date": exp_str,
            "qty":         float(r.get("qty") or 0),
        })
    return out


def upsert_batches_for_product_by_part_no(part_no: str, batches: list) -> int:
    """Replace the local batch set for the product identified by part_no with
    the server-returned batches (wipe + insert fresh). Batches are pull-only
    from ERPNext; no partial merge is needed. Returns rows inserted."""
    if not part_no:
        return 0
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "SELECT id FROM products WHERE part_no = ?",
            (part_no.strip().upper(),),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return 0
        product_id = int(row[0])

        cur.execute("DELETE FROM product_batches WHERE product_id = ?", (product_id,))

        count = 0
        for b in (batches or []):
            bn = (b.get("batch_no") or "").strip()
            if not bn:
                continue
            cur.execute("""
                INSERT INTO product_batches
                    (product_id, batch_no, expiry_date, qty, synced)
                VALUES (?, ?, ?, ?, 1)
            """, (
                product_id, bn,
                b.get("expiry_date"),
                float(b.get("qty") or 0),
            ))
            count += 1

        conn.commit()
        conn.close()
        return count
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        print(f"[product] upsert_batches_for_product_by_part_no failed for {part_no}: {e}")
        return 0


def get_warehouse_id_by_name(wh_name: str) -> int | None:
    """Look up warehouse_id from warehouses table by warehouse name (case-insensitive)."""
    if not wh_name or not str(wh_name).strip():
        return None
    name_clean = str(wh_name).strip()
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM warehouses WHERE LTRIM(RTRIM(UPPER(name))) = ?", (name_clean.upper(),))
        r = cur.fetchone()
        conn.close()
        return int(r[0]) if r else None
    except Exception as e:
        print(f"[product] get_warehouse_id_by_name failed for '{wh_name}': {e}")
        return None
# =============================================================================
# models/product.py  —  SQL Server version (Updated with UOM & Conversion)
# =============================================================================

from database.db import get_connection, fetchall_dicts, fetchone_dict

_ORDER_COLS = [f"order_{i}" for i in range(1, 7)]
_ORDER_SEL  = ", ".join(_ORDER_COLS)   # order_1, order_2, … order_6

# Added uom and conversion_factor to the standard selection
# is_pharmacy_product is wrapped in COALESCE so pre-migration rows still work
# is_template / has_variants / variant_of / attributes come from task 3 (variants).
# All four are COALESCE'd so the SELECT never blows up on a DB that hasn't
# migrated yet (fresh installs pick them up via setup_database.py).
_BASE_SELECT = (
    "id, part_no, name, price, stock, category, image_path, uom, conversion_factor, "
    "COALESCE(is_pharmacy_product, 0) AS is_pharmacy_product, "
    "COALESCE(is_template, 0)         AS is_template, "
    "COALESCE(has_variants, 0)        AS has_variants, "
    "variant_of, "
    "attributes, "
    f"{_ORDER_SEL}"
)

# =============================================================================
# READ
# =============================================================================

# When include_variants=False (default), variant rows are hidden from the
# grid — only templates and standalone items appear. Cashiers reach variants
# via the variant-picker dialog launched on tapping a template.
_HIDE_VARIANTS = " AND (variant_of IS NULL OR variant_of = '')"


def get_all_products(include_variants: bool = False) -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    where = "" if include_variants else f"WHERE 1=1 {_HIDE_VARIANTS}"
    cur.execute(f"SELECT {_BASE_SELECT} FROM products {where} ORDER BY part_no")
    rows = fetchall_dicts(cur)
    conn.close()
    return [_to_dict(r) for r in rows]


def get_products_by_category(category: str, include_variants: bool = False) -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    tail = "" if include_variants else _HIDE_VARIANTS
    cur.execute(f"""
        SELECT {_BASE_SELECT}
        FROM products
        WHERE category = ? {tail}
        ORDER BY name
    """, (category,))
    rows = fetchall_dicts(cur)
    conn.close()
    return [_to_dict(r) for r in rows]


def get_categories() -> list[str]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT DISTINCT category FROM products
        WHERE category IS NOT NULL AND category != ''
        ORDER BY category
    """)
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def search_products(query: str) -> list[dict]:
    like = f"%{query}%"
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(f"""
        SELECT {_BASE_SELECT}
        FROM products
        WHERE part_no LIKE ? OR name LIKE ?
        ORDER BY part_no
    """, (like, like))
    rows = fetchall_dicts(cur)
    conn.close()
    return [_to_dict(r) for r in rows]


def get_product_by_id(product_id: int) -> dict | None:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(f"SELECT {_BASE_SELECT} FROM products WHERE id = ?", (product_id,))
    row = fetchone_dict(cur)
    conn.close()
    return _to_dict(row) if row else None


def get_product_by_part_no(part_no: str) -> dict | None:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(f"SELECT {_BASE_SELECT} FROM products WHERE part_no = ?", (part_no,))
    row = fetchone_dict(cur)
    conn.close()
    return _to_dict(row) if row else None


def get_variants_of(template_part_no: str) -> list[dict]:
    """
    All variant rows whose `variant_of` points at this template. Used by the
    variant-picker dialog to build its attribute matrix.
    """
    if not template_part_no:
        return []
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        f"SELECT {_BASE_SELECT} FROM products WHERE variant_of = ? ORDER BY name",
        (template_part_no.upper().strip(),),
    )
    rows = fetchall_dicts(cur)
    conn.close()
    return [_to_dict(r) for r in rows]


# =============================================================================
# WRITE
# =============================================================================

def create_product(part_no: str, name: str, price: float,
                   stock: int = 0, category: str = "",
                   uom: str = "Unit", conversion_factor: float = 1.0,
                   is_pharmacy_product: bool = False,
                   **orders) -> dict:
    """
    orders kwargs: order_1=True, order_2=False, … (all default False)
    """
    order_vals = [int(bool(orders.get(f"order_{i}", False))) for i in range(1, 7)]
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(f"""
        INSERT INTO products (part_no, name, price, stock, category, uom, conversion_factor,
                              is_pharmacy_product, {_ORDER_SEL})
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (part_no.upper().strip(), name.strip(), float(price),
          int(stock), category.strip(), uom.strip(), float(conversion_factor),
          int(bool(is_pharmacy_product)), *order_vals))
    new_id = int(cur.fetchone()[0])
    conn.commit()
    conn.close()
    return get_product_by_id(new_id)


def update_product(product_id: int, part_no: str = None, name: str = None,
                   price: float = None, stock: int = None,
                   category: str = None, uom: str = None,
                   conversion_factor: float = None,
                   is_pharmacy_product: bool = None,
                   **orders) -> dict | None:

    product = get_product_by_id(product_id)
    if not product:
        return None

    new_part_no  = part_no.upper().strip() if part_no  is not None else product["part_no"]
    new_name     = name.strip()            if name     is not None else product["name"]
    new_price    = float(price)            if price    is not None else product["price"]
    new_stock    = int(stock)              if stock    is not None else product["stock"]
    new_category = category.strip()        if category is not None else product["category"]
    new_uom      = uom.strip()             if uom      is not None else product["uom"]
    new_conv     = float(conversion_factor) if conversion_factor is not None else product["conversion_factor"]
    new_pharmacy = int(bool(is_pharmacy_product)) if is_pharmacy_product is not None \
                   else int(bool(product.get("is_pharmacy_product", 0)))

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
        SET part_no=?, name=?, price=?, stock=?, category=?, uom=?, conversion_factor=?,
            is_pharmacy_product=?,
            {order_set}
        WHERE id=?
    """, (new_part_no, new_name, new_price, new_stock, new_category, new_uom, new_conv,
          new_pharmacy, *new_orders, product_id))
    conn.commit()
    conn.close()
    return get_product_by_id(product_id)


def delete_product(product_id: int) -> bool:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def adjust_stock(product_id: int, quantity_delta: float) -> dict | None:
    """Note: quantity_delta changed to float to support fractional UOM adjustments"""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE products SET stock = stock + ? WHERE id = ?
    """, (float(quantity_delta), product_id))
    conn.commit()
    conn.close()
    return get_product_by_id(product_id)


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
# PRIVATE
# =============================================================================

def _to_dict(row: dict) -> dict | None:
    if not row:
        return None
    return {
        "id":                row["id"],
        "part_no":           row["part_no"]    or "",
        "name":              row["name"]       or "",
        "price":             float(row["price"]),
        "stock":             float(row["stock"]), # Switched to float for UOM precision
        "category":          row["category"]   or "",
        "image_path":        row.get("image_path") or "",
        "uom":               row.get("uom") or "Unit",
        "conversion_factor": float(row.get("conversion_factor") or 1.0),
        "is_pharmacy_product": bool(row.get("is_pharmacy_product", False)),
        # Variant flags — present even on pre-migration rows via COALESCE.
        "is_template":   bool(row.get("is_template",  False)),
        "has_variants":  bool(row.get("has_variants", False)),
        "variant_of":    (row.get("variant_of") or "") or None,
        "attributes":    row.get("attributes") or "",
        **{f"order_{i}": bool(row.get(f"order_{i}", False)) for i in range(1, 7)},
    }


# =============================================================================
# PHARMACY — product batches
# =============================================================================

def get_batches_for_product(product_id: int) -> list[dict]:
    """
    Returns all batches for a product as a list of dicts:
        [{"batch_no": str, "expiry_date": str|None, "qty": float}, ...]
    Returns an empty list if the product has no batches (or if the
    product_batches table is missing — defensive for pre-migration DBs).
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
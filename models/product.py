# =============================================================================
# models/product.py  —  SQL Server version (Updated with UOM & Conversion)
# =============================================================================

from database.db import get_connection, fetchall_dicts, fetchone_dict

_ORDER_COLS = [f"order_{i}" for i in range(1, 7)]
_ORDER_SEL  = ", ".join(_ORDER_COLS)   # order_1, order_2, … order_6

# Added uom and conversion_factor to the standard selection
# is_pharmacy_product is wrapped in COALESCE so pre-migration rows still work
_BASE_SELECT = (
    "id, part_no, name, price, stock, category, image_path, uom, conversion_factor, "
    "COALESCE(is_pharmacy_product, 0) AS is_pharmacy_product, "
    f"{_ORDER_SEL}"
)

# =============================================================================
# READ
# =============================================================================

def get_all_products() -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(f"SELECT {_BASE_SELECT} FROM products ORDER BY part_no")
    rows = fetchall_dicts(cur)
    conn.close()
    return [_to_dict(r) for r in rows]


def get_products_by_category(category: str) -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(f"""
        SELECT {_BASE_SELECT}
        FROM products
        WHERE category = ?
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


# =============================================================================
# WRITE
# =============================================================================

def create_product(part_no: str, name: str, price: float,
                   stock: int = 0, category: str = "",
                   uom: str = "Unit", conversion_factor: float = 1.0,
                   **orders) -> dict:
    """
    orders kwargs: order_1=True, order_2=False, … (all default False)
    """
    order_vals = [int(bool(orders.get(f"order_{i}", False))) for i in range(1, 7)]
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(f"""
        INSERT INTO products (part_no, name, price, stock, category, uom, conversion_factor,
                              {_ORDER_SEL})
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (part_no.upper().strip(), name.strip(), float(price),
          int(stock), category.strip(), uom.strip(), float(conversion_factor), *order_vals))
    new_id = int(cur.fetchone()[0])
    conn.commit()
    conn.close()
    return get_product_by_id(new_id)


def update_product(product_id: int, part_no: str = None, name: str = None,
                   price: float = None, stock: int = None,
                   category: str = None, uom: str = None, 
                   conversion_factor: float = None, **orders) -> dict | None:
    
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
            {order_set}
        WHERE id=?
    """, (new_part_no, new_name, new_price, new_stock, new_category, new_uom, new_conv,
          *new_orders, product_id))
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
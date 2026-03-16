# =============================================================================
# models/product.py  —  SQL Server version
# =============================================================================

from database.db import get_connection, fetchall_dicts, fetchone_dict


# =============================================================================
# READ
# =============================================================================

def get_all_products() -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, part_no, name, price, stock, category, image_path
        FROM products
        ORDER BY part_no
    """)
    rows = fetchall_dicts(cur)
    conn.close()
    return [_to_dict(r) for r in rows]


def get_products_by_category(category: str) -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, part_no, name, price, stock, category, image_path
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
    cur.execute("""
        SELECT id, part_no, name, price, stock, category, image_path
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
    cur.execute("""
        SELECT id, part_no, name, price, stock, category, image_path
        FROM products WHERE id = ?
    """, (product_id,))
    row = fetchone_dict(cur)
    conn.close()
    return _to_dict(row) if row else None


def get_product_by_part_no(part_no: str) -> dict | None:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, part_no, name, price, stock, category, image_path
        FROM products WHERE part_no = ?
    """, (part_no,))
    row = fetchone_dict(cur)
    conn.close()
    return _to_dict(row) if row else None


# =============================================================================
# WRITE
# =============================================================================

def create_product(part_no: str, name: str, price: float,
                   stock: int = 0, category: str = "") -> dict:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO products (part_no, name, price, stock, category)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?)
    """, (part_no.upper().strip(), name.strip(), float(price),
          int(stock), category.strip()))
    new_id = int(cur.fetchone()[0])
    conn.commit()
    conn.close()
    return get_product_by_id(new_id)


def update_product(product_id: int, part_no: str = None, name: str = None,
                   price: float = None, stock: int = None,
                   category: str = None) -> dict | None:
    product = get_product_by_id(product_id)
    if not product:
        return None

    new_part_no  = part_no.upper().strip() if part_no  is not None else product["part_no"]
    new_name     = name.strip()            if name     is not None else product["name"]
    new_price    = float(price)            if price    is not None else product["price"]
    new_stock    = int(stock)              if stock    is not None else product["stock"]
    new_category = category.strip()        if category is not None else product["category"]

    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE products
        SET part_no=?, name=?, price=?, stock=?, category=?
        WHERE id=?
    """, (new_part_no, new_name, new_price, new_stock, new_category, product_id))
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


def adjust_stock(product_id: int, quantity_delta: int) -> dict | None:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE products SET stock = stock + ? WHERE id = ?
    """, (quantity_delta, product_id))
    conn.commit()
    conn.close()
    return get_product_by_id(product_id)


def set_product_image(product_id: int, image_path: str) -> None:
    """Store an image path against a product (requires image_path column)."""
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            UPDATE products SET image_path = ? WHERE id = ?
        """, (image_path, product_id))
        conn.commit()
    except Exception:
        pass   # silently skip if column doesn't exist yet
    conn.close()


def remove_product_image(product_id: int) -> None:
    """Clear the image_path for a product, setting it to NULL."""
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            UPDATE products SET image_path = NULL WHERE id = ?
        """, (product_id,))
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
        "id":         row["id"],
        "part_no":    row["part_no"]    or "",
        "name":       row["name"]       or "",
        "price":      float(row["price"]),
        "stock":      int(row["stock"]),
        "category":   row["category"]   or "",
        "image_path": row.get("image_path") or "",   # empty string = no image
    }
# =============================================================================
# models/sale.py  —  SQL Server version
# =============================================================================

from database.db import get_connection, fetchall_dicts, fetchone_dict
from models.product import adjust_stock


# =============================================================================
# INVOICE NUMBER  —  ACC-SINV-YYYY-NNNNN
# =============================================================================

def _format_invoice_no(seq: int) -> str:
    from datetime import date
    return f"ACC-SINV-{date.today().year}-{seq:05d}"


def get_next_invoice_number() -> int:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(invoice_number), 0) FROM sales")
    row = cur.fetchone()
    conn.close()
    return int(row[0]) + 1


# =============================================================================
# READ
# =============================================================================

_SALE_SELECT = """
    SELECT s.id, s.invoice_number, s.created_at, s.cashier_id,
           s.total, s.tendered, s.method,
           COALESCE(u.username, '') AS username,
           s.invoice_no, s.invoice_date, s.kot,
           s.customer_name, s.customer_contact,
           s.currency, s.subtotal, s.total_vat,
           s.discount_amount, s.receipt_type, s.footer,
           s.cashier_name,
           s.synced,
           COALESCE(s.total_items, 0)   AS total_items,
           COALESCE(s.change_amount, 0) AS change_amount,
           COALESCE(s.company_name, '') AS company_name
    FROM sales s
    LEFT JOIN users u ON u.id = s.cashier_id
"""


def get_all_sales() -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(_SALE_SELECT + " ORDER BY s.id DESC")
    rows = fetchall_dicts(cur)
    conn.close()
    return [_sale_to_dict(r) for r in rows]


def get_sale_by_id(sale_id: int) -> dict | None:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(_SALE_SELECT + " WHERE s.id = ?", (sale_id,))
    row = fetchone_dict(cur)
    if not row:
        conn.close()
        return None
    sale = _sale_to_dict(row)
    sale["items"] = _fetch_items(sale_id, cur)
    conn.close()
    return sale


def get_sale_items(sale_id: int) -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    items = _fetch_items(sale_id, cur)
    conn.close()
    return items


def get_today_sales() -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        _SALE_SELECT +
        " WHERE CAST(s.created_at AS DATE) = CAST(GETDATE() AS DATE)"
        " ORDER BY s.id DESC"
    )
    rows = fetchall_dicts(cur)
    conn.close()
    return [_sale_to_dict(r) for r in rows]


def get_today_total() -> float:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(total), 0)
        FROM sales
        WHERE CAST(created_at AS DATE) = CAST(GETDATE() AS DATE)
    """)
    row = cur.fetchone()
    conn.close()
    return float(row[0])


def get_today_total_by_method() -> dict:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT method, COALESCE(SUM(total), 0)
        FROM sales
        WHERE CAST(created_at AS DATE) = CAST(GETDATE() AS DATE)
        GROUP BY method
    """)
    rows = cur.fetchall()
    conn.close()
    return {r[0]: float(r[1]) for r in rows}


# =============================================================================
# WRITE
# =============================================================================

def create_sale(
    items:             list[dict],
    total:             float,
    tendered:          float,
    method:            str   = "Cash",
    cashier_id:        int   = None,
    cashier_name:      str   = "",
    customer_name:     str   = "",
    customer_contact:  str   = "",
    company_name:      str   = "",
    kot:               str   = "",
    currency:          str   = "USD",
    subtotal:          float = None,
    total_vat:         float = 0.0,
    discount_amount:   float = 0.0,
    receipt_type:      str   = "Invoice",
    footer:            str   = "",
    change_amount:     float = None,
) -> dict:
    from datetime import date
    from models.product import get_product_by_id, adjust_stock # Ensure imports are here

    seq           = get_next_invoice_number()
    invoice_no    = _format_invoice_no(seq)
    invoice_date  = date.today().isoformat()
    effective_sub = subtotal if subtotal is not None else total

    total_items_val = sum(float(it.get("qty", 1)) for it in items)
    change_val      = change_amount if change_amount is not None else max(float(tendered) - float(total), 0.0)

    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        INSERT INTO sales (
            invoice_number, invoice_no, invoice_date,
            total, tendered, method, cashier_id,
            cashier_name, customer_name, customer_contact,
            company_name,
            kot, currency,
            subtotal, total_vat, discount_amount,
            receipt_type, footer, synced,
            total_items, change_amount
        )
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        seq, invoice_no, invoice_date,
        float(total), float(tendered), method, cashier_id,
        cashier_name, customer_name, customer_contact,
        company_name,
        kot, currency,
        float(effective_sub), float(total_vat), float(discount_amount),
        receipt_type, footer, 0,
        float(total_items_val), float(change_val),
    ))

    sale_id = int(cur.fetchone()[0])

    for item in items:
        # 1. Save the Sale Item entry
        cur.execute("""
            INSERT INTO sale_items (
                sale_id, part_no, product_name, qty, price,
                discount, tax, total,
                tax_type, tax_rate, tax_amount, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sale_id,
            item.get("part_no",      ""),
            item.get("product_name", ""),
            float(item.get("qty",      1)),
            float(item.get("price",    0)),
            float(item.get("discount", 0)),
            item.get("tax",            ""),
            float(item.get("total",    0)),
            item.get("tax_type",       ""),
            float(item.get("tax_rate",   0.0)),
            float(item.get("tax_amount", 0.0)),
            item.get("remarks",        ""),
        ))

        # 2. Requirement 6: Handle UOM Conversion Factor for Stock Deduction
        product_id = item.get("product_id")
        if product_id:
            # Fetch the actual product to get its specific conversion factor
            prod_data = get_product_by_id(product_id)
            # Default to 1.0 if not set
            factor = float(prod_data.get("conversion_factor", 1.0) or 1.0)
            
            # Actual units to remove = Quantity Sold * Conversion Factor
            # Example: 2 Boxes * 12 units/box = 24 units removed from stock
            total_units_to_remove = float(item.get("qty", 1)) * factor
            
            # Pass as negative to adjust_stock to decrease inventory
            adjust_stock(product_id, -total_units_to_remove)

    conn.commit()
    conn.close()
    return get_sale_by_id(sale_id)

def get_unsynced_sales() -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(_SALE_SELECT + " WHERE s.synced = 0 ORDER BY s.id")
    rows = fetchall_dicts(cur)
    conn.close()
    return [_sale_to_dict(r) for r in rows]


def mark_synced(sale_id: int) -> bool:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("UPDATE sales SET synced = 1 WHERE id = ?", (sale_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def mark_many_synced(sale_ids: list[int]) -> int:
    if not sale_ids:
        return 0
    conn = get_connection()
    cur  = conn.cursor()
    placeholders = ", ".join("?" * len(sale_ids))
    cur.execute(f"UPDATE sales SET synced = 1 WHERE id IN ({placeholders})", sale_ids)
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected


def delete_sale(sale_id: int) -> bool:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# =============================================================================
# MIGRATION
# =============================================================================

def migrate():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'sales'
        )
        CREATE TABLE sales (
            id               INT           IDENTITY(1,1) PRIMARY KEY,
            invoice_number   INT           NOT NULL DEFAULT 0,
            invoice_no       NVARCHAR(40)  NOT NULL DEFAULT '',
            invoice_date     NVARCHAR(20)  NOT NULL DEFAULT '',
            total            DECIMAL(12,2) NOT NULL DEFAULT 0,
            tendered         DECIMAL(12,2) NOT NULL DEFAULT 0,
            method           NVARCHAR(30)  NOT NULL DEFAULT 'Cash',
            cashier_id       INT           NULL,
            cashier_name     NVARCHAR(120) NOT NULL DEFAULT '',
            customer_name    NVARCHAR(120) NOT NULL DEFAULT '',
            customer_contact NVARCHAR(80)  NOT NULL DEFAULT '',
            company_name     NVARCHAR(120) NOT NULL DEFAULT '',
            kot              NVARCHAR(40)  NOT NULL DEFAULT '',
            currency         NVARCHAR(10)  NOT NULL DEFAULT 'USD',
            subtotal         DECIMAL(12,2) NOT NULL DEFAULT 0,
            total_vat        DECIMAL(12,2) NOT NULL DEFAULT 0,
            discount_amount  DECIMAL(12,2) NOT NULL DEFAULT 0,
            receipt_type     NVARCHAR(30)  NOT NULL DEFAULT 'Invoice',
            footer           NVARCHAR(MAX) NOT NULL DEFAULT '',
            created_at       DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
            total_items      DECIMAL(12,4) NOT NULL DEFAULT 0,
            change_amount    DECIMAL(12,2) NOT NULL DEFAULT 0,
            synced           INT           NOT NULL DEFAULT 0
        )
    """)

    # ── Safe ALTER for upgrades — adds any missing columns ────────────────────
    for col, definition in [
        ("total_items",   "DECIMAL(12,4) NOT NULL DEFAULT 0"),
        ("change_amount", "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ("synced",        "INT NOT NULL DEFAULT 0"),
        ("company_name",  "NVARCHAR(120) NOT NULL DEFAULT ''"),   # ← new
    ]:
        cur.execute(f"""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'sales' AND COLUMN_NAME = '{col}'
            )
            ALTER TABLE sales ADD {col} {definition}
        """)

    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'sale_items'
        )
        CREATE TABLE sale_items (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            sale_id      INT           NOT NULL
                             REFERENCES sales(id) ON DELETE CASCADE,
            part_no      NVARCHAR(50)  NOT NULL DEFAULT '',
            product_name NVARCHAR(120) NOT NULL,
            qty          DECIMAL(12,4) NOT NULL DEFAULT 1,
            price        DECIMAL(12,2) NOT NULL DEFAULT 0,
            discount     DECIMAL(12,2) NOT NULL DEFAULT 0,
            tax          NVARCHAR(20)  NOT NULL DEFAULT '',
            total        DECIMAL(12,2) NOT NULL DEFAULT 0,
            tax_type     NVARCHAR(20)  NOT NULL DEFAULT '',
            tax_rate     DECIMAL(8,4)  NOT NULL DEFAULT 0,
            tax_amount   DECIMAL(12,2) NOT NULL DEFAULT 0,
            remarks      NVARCHAR(MAX) NOT NULL DEFAULT ''
        )
    """)

    conn.commit()
    conn.close()
    print("[sale] ✅  Tables ready.")


# =============================================================================
# PRIVATE
# =============================================================================

def _fetch_items(sale_id: int, cur) -> list[dict]:
    cur.execute("""
        SELECT id, sale_id, part_no, product_name, qty, price,
               discount, tax, total,
               tax_type, tax_rate, tax_amount, remarks
        FROM sale_items
        WHERE sale_id = ?
        ORDER BY id
    """, (sale_id,))
    return [_item_to_dict(r) for r in fetchall_dicts(cur)]


def _sale_to_dict(row: dict) -> dict:
    from datetime import datetime
    raw_dt = row.get("created_at")
    if isinstance(raw_dt, str):
        try:
            dt = datetime.fromisoformat(raw_dt)
        except Exception:
            dt = None
    elif hasattr(raw_dt, "strftime"):
        dt = raw_dt
    else:
        dt = None

    return {
        "id":               row["id"],
        "number":           row["invoice_number"],
        "date":             f"{dt.month}/{dt.day}/{dt.year}" if dt else "",
        "time":             dt.strftime("%H:%M")             if dt else "",
        "cashier_id":       row["cashier_id"],
        "user":             row["username"] or str(row["cashier_id"] or ""),
        "total":            float(row["total"]),
        "tendered":         float(row["tendered"]),
        "method":           row["method"] or "Cash",
        "amount":           float(row["total"]),
        "invoice_no":       row["invoice_no"]       or "",
        "invoice_date":     row["invoice_date"]     or "",
        "kot":              row["kot"]              or "",
        "customer_name":    row["customer_name"]    or "",
        "customer_contact": row["customer_contact"] or "",
        "company_name":     row["company_name"]     or "",   # ← new
        "currency":         row["currency"]         or "USD",
        "subtotal":         float(row["subtotal"]        or 0),
        "total_vat":        float(row["total_vat"]       or 0),
        "discount_amount":  float(row["discount_amount"] or 0),
        "receipt_type":     row["receipt_type"]     or "Invoice",
        "footer":           row["footer"]           or "",
        "cashier_name":     row["cashier_name"]     or "",
        "synced":           bool(row.get("synced", False)),
        "total_items":      float(row.get("total_items",  0) or 0),
        "change_amount":    float(row.get("change_amount", 0) or 0),
    }


def _item_to_dict(row: dict) -> dict:
    return {
        "id":           row["id"],
        "sale_id":      row["sale_id"],
        "part_no":      row["part_no"]      or "",
        "product_name": row["product_name"] or "",
        "qty":          float(row["qty"]),
        "price":        float(row["price"]),
        "discount":     float(row["discount"]),
        "tax":          row["tax"]          or "",
        "total":        float(row["total"]),
        "tax_type":     row["tax_type"]     or "",
        "tax_rate":     float(row["tax_rate"]   or 0),
        "tax_amount":   float(row["tax_amount"] or 0),
        "remarks":      row["remarks"]      or "",
    }


def create_credit_note(original_sale_id: int, items_to_return: list[dict]) -> bool:
    """
    Requirement 2: Processes a return.
    1. Adjusts stock (adds items back).
    2. Marks items as returned in the DB.
    """
    from models.product import adjust_stock
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        for item in items_to_return:
            # 1. Add the quantity back to inventory
            if item.get("product_id"):
                adjust_stock(item["product_id"], float(item["qty"]))
            
            # 2. Record the credit note entry
            cur.execute("""
                INSERT INTO credit_notes (original_sale_id, part_no, qty, reason, created_at)
                VALUES (?, ?, ?, ?, GETDATE())
            """, (original_sale_id, item["part_no"], item["qty"], item.get("reason", "Customer Return")))
            
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
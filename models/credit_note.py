# =============================================================================
# models/credit_note.py
#
# Replaces the stub create_credit_note() in sale.py.
# Drop that function from sale.py — import from here instead.
#
# Table: credit_notes
#   id, cn_number, original_sale_id, original_invoice_no, frappe_ref,
#   frappe_cn_ref, total, currency, cashier_name, customer_name,
#   cn_status, created_at
#
# Table: credit_note_items
#   id, credit_note_id, part_no, product_name, qty, price, total, reason
#
# cn_status lifecycle:
#   pending_sync → original sale not yet in Frappe (no frappe_ref)
#   ready        → frappe_ref known, sync service will pick it up
#   synced       → submitted to Frappe, frappe_cn_ref stored
# =============================================================================
from __future__ import annotations

from database.db import get_connection
from datetime import date


# =============================================================================
# CN NUMBER  —  CN-YYYY-NNNNN
# =============================================================================

def _next_cn_number() -> str:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(id), 0) FROM credit_notes")
    row  = cur.fetchone()
    conn.close()
    seq  = int(row[0] or 0) + 1
    return f"CN-{date.today().year}-{seq:05d}"


# =============================================================================
# MIGRATE  —  run once via migrate_credit_notes.py
# =============================================================================

def migrate():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'credit_notes'
        )
        CREATE TABLE credit_notes (
            id                  INT           IDENTITY(1,1) PRIMARY KEY,
            cn_number           NVARCHAR(40)  NOT NULL DEFAULT '',
            original_sale_id    INT           NOT NULL,
            original_invoice_no NVARCHAR(40)  NOT NULL DEFAULT '',
            frappe_ref          NVARCHAR(80)  NULL,
            frappe_cn_ref       NVARCHAR(80)  NULL,
            total               DECIMAL(12,2) NOT NULL DEFAULT 0,
            currency            NVARCHAR(10)  NOT NULL DEFAULT 'USD',
            cashier_name        NVARCHAR(120) NOT NULL DEFAULT '',
            customer_name       NVARCHAR(120) NOT NULL DEFAULT '',
            cn_status           NVARCHAR(20)  NOT NULL DEFAULT 'pending_sync',
            created_at          DATETIME2     NOT NULL DEFAULT SYSDATETIME()
        )
    """)
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'credit_note_items'
        )
        CREATE TABLE credit_note_items (
            id             INT           IDENTITY(1,1) PRIMARY KEY,
            credit_note_id INT           NOT NULL
                               REFERENCES credit_notes(id) ON DELETE CASCADE,
            part_no        NVARCHAR(50)  NOT NULL DEFAULT '',
            product_name   NVARCHAR(120) NOT NULL DEFAULT '',
            qty            DECIMAL(12,4) NOT NULL DEFAULT 0,
            price          DECIMAL(12,2) NOT NULL DEFAULT 0,
            total          DECIMAL(12,2) NOT NULL DEFAULT 0,
            reason         NVARCHAR(255) NOT NULL DEFAULT 'Customer Return'
        )
    """)
    conn.commit()
    conn.close()


# =============================================================================
# CREATE
# =============================================================================

def create_credit_note(
    original_sale_id: int,
    items_to_return:  list[dict],
    currency:         str  = "USD",
    customer_name:    str  = "",
    cashier_name:     str  = "",
) -> dict:
    """
    Create a credit note locally and adjust stock.
    Returns the saved credit note dict including cn_number and cn_status.

    cn_status is set to:
      'ready'        if the original sale has a frappe_ref (can sync immediately)
      'pending_sync' if the original sale hasn't synced to Frappe yet
    """
    from models.product import adjust_stock

    # Look up the original sale for invoice_no and frappe_ref
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            "SELECT invoice_no, frappe_ref FROM sales WHERE id = ?",
            (original_sale_id,)
        )
        row = cur.fetchone()
        original_invoice_no = row[0] if row else ""
        frappe_ref          = row[1] if row else None

        cn_status = "ready" if frappe_ref else "pending_sync"
        cn_number = _next_cn_number()
        total     = sum(float(i.get("total", 0)) for i in items_to_return)

        # Insert header
        cur.execute("""
            INSERT INTO credit_notes
                (cn_number, original_sale_id, original_invoice_no,
                 frappe_ref, total, currency, cashier_name, customer_name, cn_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cn_number, original_sale_id, original_invoice_no,
            frappe_ref, total, currency, cashier_name, customer_name, cn_status
        ))
        cur.execute("SELECT SCOPE_IDENTITY()")
        row = cur.fetchone()
        if row and row[0] is not None:
            cn_id = int(row[0])
        else:
            cur.execute("SELECT id FROM credit_notes WHERE cn_number = ?", (cn_number,))
            cn_id = int(cur.fetchone()[0])

        # Insert items + adjust stock
        for item in items_to_return:
            qty   = float(item.get("qty",   0))
            price = float(item.get("price", 0))
            cur.execute("""
                INSERT INTO credit_note_items
                    (credit_note_id, part_no, product_name, qty, price, total, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                cn_id,
                item.get("part_no", ""),
                item.get("product_name", ""),
                qty,
                price,
                round(qty * price, 2),
                item.get("reason", "Customer Return"),
            ))
            # Return stock to inventory
            if item.get("product_id"):
                try:
                    adjust_stock(item["product_id"], qty)
                except Exception:
                    pass   # stock adjust failure shouldn't block the CN

        conn.commit()
        return {
            "id":                   cn_id,
            "cn_number":            cn_number,
            "original_sale_id":     original_sale_id,
            "original_invoice_no":  original_invoice_no,
            "frappe_ref":           frappe_ref or "",
            "total":                total,
            "currency":             currency,
            "cashier_name":         cashier_name,
            "customer_name":        customer_name,
            "cn_status":            cn_status,
            "items_to_return":      items_to_return,
        }

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# =============================================================================
# READ
# =============================================================================

def get_pending_credit_notes() -> list[dict]:
    """Return all CNs with cn_status = 'ready' that haven't synced yet."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT cn.id, cn.cn_number, cn.original_sale_id,
               cn.original_invoice_no, cn.frappe_ref,
               cn.total, cn.currency, cn.cashier_name, cn.customer_name,
               cn.cn_status
        FROM   credit_notes cn
        WHERE  cn.cn_status = 'ready'
        ORDER  BY cn.created_at
    """)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()

    # Attach items to each CN
    for cn in rows:
        cn["items_to_return"] = _get_items(cn["id"])
    return rows


def _get_items(cn_id: int) -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT part_no, product_name, qty, price, total, reason "
        "FROM credit_note_items WHERE credit_note_id = ?",
        (cn_id,)
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()
    return rows


# =============================================================================
# UPDATE
# =============================================================================

def mark_cn_synced(cn_id: int, frappe_cn_ref: str = "") -> None:
    """Called by the sync service after a successful Frappe submission."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE credit_notes SET cn_status = 'synced', frappe_cn_ref = ? WHERE id = ?",
        (frappe_cn_ref or None, cn_id)
    )
    conn.commit()
    conn.close()


def promote_pending_cns_for_sale(sale_id: int, frappe_ref: str) -> None:
    """
    Called by pos_upload_service after a sale is confirmed in Frappe.
    Flips pending_sync CNs for that sale to 'ready' so the sync daemon picks them up.
    """
    if not frappe_ref:
        return
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE credit_notes
        SET    cn_status  = 'ready',
               frappe_ref = ?
        WHERE  original_sale_id = ?
          AND  cn_status = 'pending_sync'
    """, (frappe_ref, sale_id))
    conn.commit()
    conn.close()
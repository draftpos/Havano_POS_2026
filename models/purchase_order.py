# =============================================================================
# models/purchase_order.py
# =============================================================================

from database.db import get_connection, fetchall_dicts, fetchone_dict
from models.product import adjust_stock

def create_purchase_order(supplier: str, warehouse: str, items: list, warehouse_id: int = None, cost_center_id: int = None) -> int | None:

    """
    items: list of dicts with {"product_id": int, "qty": float, "cost_price": float}
    """

    conn = get_connection()
    cur  = conn.cursor()
    try:
        total_amount = sum(item["qty"] * item["cost_price"] for item in items)
        
        # 1. Create the header
        cur.execute("""
            INSERT INTO purchase_orders (supplier, warehouse, warehouse_id, cost_center_id, total_amount, date, synced)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, SYSDATETIME(), 0)
        """, (supplier, warehouse, warehouse_id, cost_center_id, total_amount))
        po_id = int(cur.fetchone()[0])



        # 2. Add items and adjust stock
        for item in items:
            cur.execute("""
                INSERT INTO purchase_order_items (parent_id, product_id, qty, cost_price)
                VALUES (?, ?, ?, ?)
            """, (po_id, item["product_id"], item["qty"], item["cost_price"]))
            
            # Adjust stock locally
            adjust_stock(item["product_id"], item["qty"], warehouse_id=warehouse_id)


        conn.commit()
        return po_id
    except Exception as e:
        print(f"[PO] Create error: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

def get_all_purchase_orders() -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM purchase_orders ORDER BY date DESC")
    rows = fetchall_dicts(cur)
    conn.close()
    return rows

def get_po_items(po_id: int) -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT poi.*, p.name as product_name, p.part_no
        FROM purchase_order_items poi
        JOIN products p ON poi.product_id = p.id
        WHERE poi.parent_id = ?
    """, (po_id,))
    rows = fetchall_dicts(cur)
    conn.close()
    return rows

def migrate():
    conn = get_connection()
    cur  = conn.cursor()
    
    # Header Table
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='purchase_orders')
        CREATE TABLE purchase_orders (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            supplier     NVARCHAR(140) NULL,
            warehouse    NVARCHAR(140) NULL,
            warehouse_id INT           NULL,
            cost_center_id INT         NULL,
            total_amount DECIMAL(18,4) NOT NULL DEFAULT 0,

            date         DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
            synced       BIT           NOT NULL DEFAULT 0
        )
    """)
    
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='purchase_orders' AND COLUMN_NAME='cost_center_id')
        ALTER TABLE purchase_orders ADD cost_center_id INT NULL
    """)


    
    # Items Table
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='purchase_order_items')
        CREATE TABLE purchase_order_items (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            parent_id    INT           NOT NULL REFERENCES purchase_orders(id),
            product_id   INT           NOT NULL REFERENCES products(id),
            qty          DECIMAL(18,4) NOT NULL DEFAULT 0,
            cost_price   DECIMAL(18,4) NOT NULL DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()
    print("[PO] Migration complete.")

from __future__ import annotations
from database.db import get_connection

def is_restaurant_enabled() -> bool:
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT TOP 1 enabled FROM restaurant_settings")
        row = cur.fetchone()
        conn.close()
        return bool(row[0]) if row else False
    except Exception as e:
        print(f"[Model] Error checking restaurant enabled: {e}")
        return False

def save_restaurant_enabled(enabled: bool):
    try:
        conn = get_connection(); cur = conn.cursor()
        val = 1 if enabled else 0
        cur.execute("UPDATE restaurant_settings SET enabled = ?", (val,))
        if cur.rowcount == 0:
            cur.execute("INSERT INTO restaurant_settings (enabled) VALUES (?)", (val,))
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[Model] Error saving restaurant enabled: {e}")

def get_all_tables() -> list[dict]:
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT t.id, t.name, t.table_number, t.capacity, t.floor, t.active, t.status,
                   COALESCE((
                       SELECT SUM(roi.quantity * roi.rate) 
                       FROM restaurant_order_items roi 
                       JOIN restaurant_orders ro ON ro.id = roi.order_id 
                       WHERE ro.table_id = t.id AND ro.status IN ('Open', 'Ordered')
                   ), 0.0) as current_total
            FROM restaurant_tables t 
            WHERE t.active = 1
        """)
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[Model] Error getting all tables: {e}")
        return []

def create_table(name: str, number: str, capacity: int = 2, floor: str = "Main"):
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO restaurant_tables (name, table_number, capacity, floor, active)
            VALUES (?, ?, ?, ?, 1)
        """, (name, number, capacity, floor))
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[Model] Error creating table: {e}")
        raise e

def delete_table(table_id: int):
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("UPDATE restaurant_tables SET active = 0 WHERE id = ?", (table_id,))
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[Model] Error deleting table: {e}")

def ensure_floors_table():
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[restaurant_floors]') AND type in (N'U'))
            BEGIN
                CREATE TABLE [dbo].[restaurant_floors] (
                    [id]     INT IDENTITY(1,1) PRIMARY KEY,
                    [name]   NVARCHAR(100) NOT NULL,
                    [active] BIT DEFAULT 1
                )
                INSERT INTO [dbo].[restaurant_floors] (name, active) VALUES ('Main Floor', 1)
            END
        """)
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[Model] Error ensuring restaurant_floors table: {e}")

def get_all_floors() -> list[dict]:
    ensure_floors_table()
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT id, name FROM restaurant_floors WHERE active = 1 ORDER BY id")
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[Model] Error getting all floors: {e}")
        return []

def create_floor(name: str):
    ensure_floors_table()
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("INSERT INTO restaurant_floors (name, active) VALUES (?, 1)", (name,))
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[Model] Error creating floor: {e}")
        raise e

def delete_floor(floor_id: int):
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("UPDATE restaurant_floors SET active = 0 WHERE id = ?", (floor_id,))
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[Model] Error deleting floor: {e}")

def get_active_orders() -> list[dict]:
    """Returns open restaurant orders with their table info."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT o.id, o.table_id, t.name as table_name, t.table_number, t.floor, o.customer_name, o.status, o.created_at, o.waiter_id
            FROM restaurant_orders o
            JOIN restaurant_tables t ON o.table_id = t.id
            WHERE o.status IN ('Open', 'Ordered')
        """)
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[Model] Error getting active orders: {e}")
        return []

def get_order_by_table(table_id: int) -> dict | None:
    """Returns the active order for a given table (Open or legacy Ordered)."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT id, table_id, customer_name, status, created_at, waiter_id
            FROM restaurant_orders
            WHERE table_id = ? AND status IN ('Open', 'Ordered')
            ORDER BY created_at DESC
        """, (table_id,))
        cols = [desc[0] for desc in cur.description]
        row = cur.fetchone()
        conn.close()
        return dict(zip(cols, row)) if row else None
    except Exception as e:
        print(f"[Model] Error getting order by table: {e}")
        return None

def get_order_items(order_id: int) -> list[dict]:
    """Returns all items in a restaurant order."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT product_id, item_code, item_name, quantity as qty, rate as price
            FROM restaurant_order_items
            WHERE order_id = ?
        """, (order_id,))
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[Model] Error getting order items: {e}")
        return []

def get_recent_orders(limit: int = 50) -> list[dict]:
    """Returns recent restaurant orders (Open and Paid) with table info."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute(f"""
            SELECT TOP {limit} o.id, o.table_id, t.name as table_name, t.table_number, t.floor, o.customer_name, o.status, o.created_at, o.waiter_id
            FROM restaurant_orders o
            JOIN restaurant_tables t ON o.table_id = t.id
            WHERE o.status <> 'Cancelled'
            ORDER BY o.created_at DESC
        """)
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[Model] Error getting recent orders: {e}")
        return []

def cancel_order(order_id: int):
    """Mark an order as Cancelled."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("UPDATE restaurant_orders SET status = 'Cancelled', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (order_id,))
        conn.commit(); conn.close()
        return True
    except Exception as e:
        print(f"[Model] Error cancelling order: {e}")
        return False

def get_orders_for_table(table_id: int) -> list[dict]:
    """Returns all active orders for a given table."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT id, table_id, customer_name, status, created_at, waiter_id
            FROM restaurant_orders
            WHERE table_id = ? AND status IN ('Open', 'Ordered')
            ORDER BY created_at ASC
        """, (table_id,))
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[Model] Error getting orders for table: {e}")
        return []

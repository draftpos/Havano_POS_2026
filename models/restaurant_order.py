"""
models/restaurant_order.py
===========================
All restaurant DB operations including Phase-1 features:
 - auto_logout_on_finalise
 - waiter_isolation (hide other waiters' tables)
 - allow_split_bill
 - KOT cancel reason
 - KOT modify reason
 - item notes
 - bill notes
 - table open-time tracking
 - cancel/modify log

Self-healing migrate() runs at startup:
  1. Creates every table that doesn't exist yet (full schema).
  2. Adds any missing columns to tables that already exist.
  3. Seeds required default rows (e.g. a "Main Floor").
Call migrate() once from your app entry-point before anything else.
"""
from __future__ import annotations
from database.db import get_connection


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _table_exists(cur, table_name: str) -> bool:
    """Return True if *table_name* already exists in the database."""
    cur.execute(
        "SELECT COUNT(*) FROM sys.objects "
        "WHERE object_id = OBJECT_ID(?) AND type = N'U'",
        (f"[dbo].[{table_name}]",),
    )
    return cur.fetchone()[0] > 0


def _column_exists(cur, table_name: str, col_name: str) -> bool:
    """Return True if *col_name* exists in *table_name*."""
    cur.execute(
        "SELECT COUNT(*) FROM sys.columns "
        "WHERE object_id = OBJECT_ID(?) AND name = ?",
        (f"[dbo].[{table_name}]", col_name),
    )
    return cur.fetchone()[0] > 0


def _ensure_columns(cur, conn, table_name: str, columns: list[tuple[str, str]]):
    """
    Add each (col_name, definition) to *table_name* if it doesn't exist.
    Each ALTER is committed independently so a single failure doesn't block the rest.
    """
    for col, definition in columns:
        if not _column_exists(cur, table_name, col):
            try:
                cur.execute(f"ALTER TABLE [{table_name}] ADD [{col}] {definition}")
                conn.commit()
                print(f"[Migrate] Added column {table_name}.{col}")
            except Exception as e:
                conn.rollback()
                print(f"[Migrate] Could not add {table_name}.{col}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SELF-HEALING MIGRATION — call once at startup
# ─────────────────────────────────────────────────────────────────────────────

def migrate():
    """
    Idempotent, self-healing schema migration.
    • Creates every core table if it is missing.
    • Adds any missing columns to tables that already exist.
    • Seeds required default rows.
    Safe to call on every startup — nothing is dropped or truncated.
    """
    conn = get_connection()
    cur  = conn.cursor()

    # ── 1. restaurant_settings ───────────────────────────────────────────────
    if not _table_exists(cur, "restaurant_settings"):
        cur.execute("""
            CREATE TABLE [dbo].[restaurant_settings] (
                [id]                      INT IDENTITY(1,1) PRIMARY KEY,
                [enabled]                 BIT DEFAULT 0,
                [auto_logout_on_finalise] BIT DEFAULT 0,
                [waiter_isolation]        BIT DEFAULT 0,
                [allow_split_bill]        BIT DEFAULT 0,
                [require_cancel_reason]   BIT DEFAULT 0,
                [require_modify_reason]   BIT DEFAULT 0,
                [lock_pay_kot]            BIT DEFAULT 0,
                [allow_partial_payment]   BIT DEFAULT 0
            )
        """)
        conn.commit()
        # Seed one default row so SELECT TOP 1 always returns something
        cur.execute("""
            INSERT INTO [dbo].[restaurant_settings]
                (enabled, auto_logout_on_finalise, waiter_isolation,
                 allow_split_bill, require_cancel_reason, require_modify_reason,
                 lock_pay_kot, allow_partial_payment)
            VALUES (0, 0, 0, 0, 0, 0, 0, 0)
        """)
        conn.commit()
        print("[Migrate] Created table: restaurant_settings")
    else:
        _ensure_columns(cur, conn, "restaurant_settings", [
            ("enabled",                 "BIT DEFAULT 0"),
            ("auto_logout_on_finalise", "BIT DEFAULT 0"),
            ("waiter_isolation",        "BIT DEFAULT 0"),
            ("allow_split_bill",        "BIT DEFAULT 0"),
            ("require_cancel_reason",   "BIT DEFAULT 0"),
            ("require_modify_reason",   "BIT DEFAULT 0"),
            ("lock_pay_kot",            "BIT DEFAULT 0"),
            ("allow_partial_payment",   "BIT DEFAULT 0"),
        ])
        # Seed default row if table is empty
        cur.execute("SELECT COUNT(*) FROM [dbo].[restaurant_settings]")
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO [dbo].[restaurant_settings]
                    (enabled, auto_logout_on_finalise, waiter_isolation,
                     allow_split_bill, require_cancel_reason, require_modify_reason,
                     lock_pay_kot, allow_partial_payment)
                VALUES (0, 0, 0, 0, 0, 0, 0, 0)
            """)
            conn.commit()

    # ── 2. restaurant_floors ─────────────────────────────────────────────────
    if not _table_exists(cur, "restaurant_floors"):
        cur.execute("""
            CREATE TABLE [dbo].[restaurant_floors] (
                [id]     INT IDENTITY(1,1) PRIMARY KEY,
                [name]   NVARCHAR(100) NOT NULL,
                [active] BIT DEFAULT 1
            )
        """)
        conn.commit()
        cur.execute(
            "INSERT INTO [dbo].[restaurant_floors] (name, active) VALUES ('Main Floor', 1)"
        )
        conn.commit()
        print("[Migrate] Created table: restaurant_floors")
    else:
        _ensure_columns(cur, conn, "restaurant_floors", [
            ("name",   "NVARCHAR(100) NOT NULL"),
            ("active", "BIT DEFAULT 1"),
        ])
        # Seed a default floor if the table is empty
        cur.execute("SELECT COUNT(*) FROM [dbo].[restaurant_floors]")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO [dbo].[restaurant_floors] (name, active) VALUES ('Main Floor', 1)"
            )
            conn.commit()

    # ── 3. restaurant_tables ─────────────────────────────────────────────────
    if not _table_exists(cur, "restaurant_tables"):
        cur.execute("""
            CREATE TABLE [dbo].[restaurant_tables] (
                [id]           INT IDENTITY(1,1) PRIMARY KEY,
                [name]         NVARCHAR(100) NOT NULL,
                [table_number] NVARCHAR(20)  NULL,
                [capacity]     INT           DEFAULT 2,
                [floor]        NVARCHAR(100) DEFAULT 'Main',
                [active]       BIT           DEFAULT 1,
                [status]       NVARCHAR(20)  DEFAULT 'Available'
            )
        """)
        conn.commit()
        print("[Migrate] Created table: restaurant_tables")
    else:
        _ensure_columns(cur, conn, "restaurant_tables", [
            ("name",         "NVARCHAR(100) NOT NULL"),
            ("table_number", "NVARCHAR(20)  NULL"),
            ("capacity",     "INT           DEFAULT 2"),
            ("floor",        "NVARCHAR(100) DEFAULT 'Main'"),
            ("active",       "BIT           DEFAULT 1"),
            ("status",       "NVARCHAR(20)  DEFAULT 'Available'"),
        ])

    # ── 4. restaurant_orders ─────────────────────────────────────────────────
    if not _table_exists(cur, "restaurant_orders"):
        cur.execute("""
            CREATE TABLE [dbo].[restaurant_orders] (
                [id]            INT IDENTITY(1,1) PRIMARY KEY,
                [table_id]      INT           NOT NULL,
                [customer_name] NVARCHAR(200) NULL,
                [status]        NVARCHAR(20)  DEFAULT 'Open',
                [waiter_id]     INT           NULL,
                [bill_notes]    NVARCHAR(500) NULL,
                [opened_at]     DATETIME      NULL,
                [created_at]    DATETIME      DEFAULT CURRENT_TIMESTAMP,
                [updated_at]    DATETIME      NULL,
                [prep_status]   NVARCHAR(20)  DEFAULT 'Preparing'
            )
        """)
        conn.commit()
        print("[Migrate] Created table: restaurant_orders")
    else:
        _ensure_columns(cur, conn, "restaurant_orders", [
            ("table_id",      "INT           NOT NULL"),
            ("customer_name", "NVARCHAR(200) NULL"),
            ("status",        "NVARCHAR(20)  DEFAULT 'Open'"),
            ("waiter_id",     "INT           NULL"),
            ("bill_notes",    "NVARCHAR(500) NULL"),
            ("opened_at",     "DATETIME      NULL"),
            ("created_at",    "DATETIME      DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at",    "DATETIME      NULL"),
            ("prep_status",   "NVARCHAR(20)  DEFAULT 'Preparing'"),
        ])

    # ── 5. restaurant_order_items ────────────────────────────────────────────
    if not _table_exists(cur, "restaurant_order_items"):
        cur.execute("""
            CREATE TABLE [dbo].[restaurant_order_items] (
                [id]          INT IDENTITY(1,1) PRIMARY KEY,
                [order_id]    INT             NOT NULL,
                [product_id]  INT             NULL,
                [item_code]   NVARCHAR(50)    NULL,
                [item_name]   NVARCHAR(200)   NOT NULL,
                [quantity]    DECIMAL(10,2)   DEFAULT 1,
                [rate]        DECIMAL(10,2)   DEFAULT 0,
                [item_notes]  NVARCHAR(300)   NULL,
                [order_1]     BIT             DEFAULT 0,
                [order_2]     BIT             DEFAULT 0,
                [order_3]     BIT             DEFAULT 0,
                [order_4]     BIT             DEFAULT 0,
                [order_5]     BIT             DEFAULT 0,
                [order_6]     BIT             DEFAULT 0,
                [item_status] NVARCHAR(20)    DEFAULT 'Preparing'
            )
        """)
        conn.commit()
        print("[Migrate] Created table: restaurant_order_items")
    else:
        _ensure_columns(cur, conn, "restaurant_order_items", [
            ("order_id",   "INT           NOT NULL"),
            ("product_id", "INT           NULL"),
            ("item_code",  "NVARCHAR(50)  NULL"),
            ("item_name",  "NVARCHAR(200) NOT NULL"),
            ("quantity",   "DECIMAL(10,2) DEFAULT 1"),
            ("rate",       "DECIMAL(10,2) DEFAULT 0"),
            ("item_notes", "NVARCHAR(300) NULL"),
            ("order_1",    "BIT DEFAULT 0"),
            ("order_2",    "BIT DEFAULT 0"),
            ("order_3",    "BIT DEFAULT 0"),
            ("order_4",    "BIT DEFAULT 0"),
            ("order_5",    "BIT DEFAULT 0"),
            ("order_6",    "BIT DEFAULT 0"),
            ("item_status", "NVARCHAR(20) DEFAULT 'Preparing'"),
        ])

    # ── 6. restaurant_kot_log ────────────────────────────────────────────────
    if not _table_exists(cur, "restaurant_kot_log"):
        cur.execute("""
            CREATE TABLE [dbo].[restaurant_kot_log] (
                [id]        INT IDENTITY(1,1) PRIMARY KEY,
                [order_id]  INT           NOT NULL,
                [action]    NVARCHAR(20)  NOT NULL,
                [reason]    NVARCHAR(500) NULL,
                [waiter_id] INT           NULL,
                [logged_at] DATETIME      DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("[Migrate] Created table: restaurant_kot_log")
    else:
        _ensure_columns(cur, conn, "restaurant_kot_log", [
            ("order_id",  "INT           NOT NULL"),
            ("action",    "NVARCHAR(20)  NOT NULL"),
            ("reason",    "NVARCHAR(500) NULL"),
            ("waiter_id", "INT           NULL"),
            ("logged_at", "DATETIME      DEFAULT CURRENT_TIMESTAMP"),
        ])

    # ── 7. restaurant_bill_splits ────────────────────────────────────────────
    if not _table_exists(cur, "restaurant_bill_splits"):
        cur.execute("""
            CREATE TABLE [dbo].[restaurant_bill_splits] (
                [id]          INT IDENTITY(1,1) PRIMARY KEY,
                [table_id]    INT            NOT NULL,
                [label]       NVARCHAR(100)  NULL,
                [mop_label]   NVARCHAR(100)  NOT NULL,
                [currency]    NVARCHAR(10)   NOT NULL DEFAULT 'USD',
                [amount_raw]  DECIMAL(10,2)  NOT NULL,
                [amount_usd]  DECIMAL(10,2)  NOT NULL,
                [created_at]  DATETIME       DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("[Migrate] Created table: restaurant_bill_splits")
    else:
        _ensure_columns(cur, conn, "restaurant_bill_splits", [
            ("table_id",   "INT           NOT NULL"),
            ("label",      "NVARCHAR(100) NULL"),
            ("mop_label",  "NVARCHAR(100) NOT NULL"),
            ("currency",   "NVARCHAR(10)  NOT NULL DEFAULT 'USD'"),
            ("amount_raw", "DECIMAL(10,2) NOT NULL"),
            ("amount_usd", "DECIMAL(10,2) NOT NULL"),
            ("created_at", "DATETIME      DEFAULT CURRENT_TIMESTAMP"),
        ])

    conn.close()
    print("[Migrate] Schema check complete — all tables and columns are up to date.")


# ─────────────────────────────────────────────────────────────────────────────
# RESTAURANT SETTINGS
# ─────────────────────────────────────────────────────────────────────────────

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


def get_restaurant_settings() -> dict:
    """Return full restaurant_settings row as a dict (with safe defaults)."""
    defaults = {
        "enabled":                 False,
        "auto_logout_on_finalise": False,
        "waiter_isolation":        False,
        "allow_split_bill":        False,
        "require_cancel_reason":   False,
        "require_modify_reason":   False,
        "lock_pay_kot":            False,
        "allow_partial_payment":   False,
    }
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT TOP 1 * FROM restaurant_settings")
        row = cur.fetchone()
        conn.close()
        if row:
            cols = [desc[0] for desc in cur.description]
            data = dict(zip(cols, row))
            for k in defaults:
                defaults[k] = bool(data.get(k, defaults[k]))
        return defaults
    except Exception as e:
        print(f"[Model] Error getting restaurant settings: {e}")
        return defaults


def save_restaurant_settings(settings: dict):
    """Upsert all restaurant setting flags."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM restaurant_settings")
        count = cur.fetchone()[0]

        fields = [
            "auto_logout_on_finalise",
            "waiter_isolation",
            "allow_split_bill",
            "require_cancel_reason",
            "require_modify_reason",
            "lock_pay_kot",
            "allow_partial_payment",
            "enabled",
        ]

        if count == 0:
            placeholders = ", ".join(["?"] * len(fields))
            cols = ", ".join(fields)
            values = [1 if settings.get(f) else 0 for f in fields]
            cur.execute(f"INSERT INTO restaurant_settings ({cols}) VALUES ({placeholders})", values)
        else:
            set_clause = ", ".join(f"{f} = ?" for f in fields)
            values = [1 if settings.get(f) else 0 for f in fields]
            cur.execute(f"UPDATE restaurant_settings SET {set_clause}", values)

        conn.commit(); conn.close()
    except Exception as e:
        print(f"[Model] Error saving restaurant settings: {e}")
        raise e


# ─────────────────────────────────────────────────────────────────────────────
# FLOORS
# ─────────────────────────────────────────────────────────────────────────────

def ensure_floors_table():
    """Legacy guard — migrate() now handles this; kept for backwards compat."""
    migrate()


def get_all_floors() -> list[dict]:
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


# ─────────────────────────────────────────────────────────────────────────────
# TABLES
# ─────────────────────────────────────────────────────────────────────────────

def get_all_tables(waiter_id: int | None = None, waiter_isolation: bool = False) -> list[dict]:
    """
    Returns all active tables.
    If waiter_isolation=True, occupied tables belonging to another waiter are hidden.
    """
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT t.id, t.name, t.table_number, t.capacity, t.floor, t.active,
                   CASE 
                       WHEN (SELECT COUNT(*) FROM restaurant_orders ro WHERE ro.table_id = t.id AND ro.status IN ('Open', 'Ordered')) > 0 
                       THEN 'Occupied' 
                       ELSE 'Available' 
                   END as status,
                   COALESCE((
                       SELECT SUM(roi.quantity * roi.rate)
                       FROM restaurant_order_items roi
                       JOIN restaurant_orders ro ON ro.id = roi.order_id
                       WHERE ro.table_id = t.id AND ro.status IN ('Open', 'Ordered')
                   ), 0.0) as current_total,
                   (
                       SELECT TOP 1 ro.waiter_id
                       FROM restaurant_orders ro
                       WHERE ro.table_id = t.id AND ro.status IN ('Open', 'Ordered')
                       ORDER BY ro.created_at DESC
                   ) as active_waiter_id,
                   (
                       SELECT TOP 1 ro.opened_at
                       FROM restaurant_orders ro
                       WHERE ro.table_id = t.id AND ro.status IN ('Open', 'Ordered')
                       ORDER BY ro.created_at DESC
                   ) as opened_at,
                   (
                       SELECT TOP 1 ro.created_at
                       FROM restaurant_orders ro
                       WHERE ro.table_id = t.id AND ro.status IN ('Open', 'Ordered')
                       ORDER BY ro.created_at DESC
                   ) as last_order_at
            FROM restaurant_tables t
            WHERE t.active = 1
        """)
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()

        if waiter_isolation and waiter_id is not None:
            result = []
            for t in rows:
                aw = t.get("active_waiter_id")
                if t.get("status") != "Occupied" or aw is None or aw == waiter_id:
                    result.append(t)
            return result

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


# ─────────────────────────────────────────────────────────────────────────────
# ORDERS
# ─────────────────────────────────────────────────────────────────────────────

def get_active_orders() -> list[dict]:
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT o.id, o.table_id, t.name as table_name, t.table_number, t.floor,
                   o.customer_name, o.status, o.created_at, o.waiter_id,
                   o.bill_notes, o.opened_at
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
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT id, table_id, customer_name, status, created_at, waiter_id, bill_notes, opened_at
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
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT product_id, item_code, item_name, quantity as qty, rate as price,
                   COALESCE(item_notes, '') as item_notes,
                   order_1, order_2, order_3, order_4, order_5, order_6,
                   item_status
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


def update_bill_notes(order_id: int, notes: str):
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("UPDATE restaurant_orders SET bill_notes = ? WHERE id = ?", (notes, order_id))
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[Model] Error updating bill notes: {e}")


def get_recent_orders(limit: int = 200) -> list[dict]:
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute(f"""
            SELECT TOP {limit} o.id, o.table_id, t.name as table_name, t.table_number,
                   t.floor, o.customer_name, o.status, o.created_at, o.waiter_id,
                   o.bill_notes, o.opened_at
            FROM restaurant_orders o
            JOIN restaurant_tables t ON o.table_id = t.id
            ORDER BY o.created_at DESC
        """)
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[Model] Error getting recent orders: {e}")
        return []


def cancel_order(order_id: int, reason: str = "", waiter_id: int | None = None) -> bool:
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute(
            "UPDATE restaurant_orders SET status = 'Cancelled', prep_status = 'Cancelled', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (order_id,)
        )
        cur.execute(
            "INSERT INTO restaurant_kot_log (order_id, action, reason, waiter_id) VALUES (?, 'Cancel', ?, ?)",
            (order_id, reason or None, waiter_id)
        )
        conn.commit(); conn.close()
        
        # Notify KDS
        try:
            from services.kds_service import kds_service
            kds_service.broadcast_sync({"type": "refresh", "order_id": order_id})
        except Exception:
            pass
            
        return True
    except Exception as e:
        print(f"[Model] Error cancelling order: {e}")
        return False


def log_kot_modify(order_id: int, reason: str = "", waiter_id: int | None = None):
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO restaurant_kot_log (order_id, action, reason, waiter_id) VALUES (?, 'Modify', ?, ?)",
            (order_id, reason or None, waiter_id)
        )
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[Model] Error logging KOT modify: {e}")


def get_orders_for_table(table_id: int) -> list[dict]:
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


# ─────────────────────────────────────────────────────────────────────────────
# KOT LOG — cancelled and modified history
# ─────────────────────────────────────────────────────────────────────────────

def get_kot_log(action: str | None = None, limit: int = 200) -> list[dict]:
    """Return recent KOT cancel/modify log. action='Cancel'|'Modify'|None for both."""
    try:
        conn = get_connection(); cur = conn.cursor()
        where = f"WHERE l.action = '{action}'" if action else ""
        cur.execute(f"""
            SELECT TOP {limit}
                   l.id, l.order_id, l.action, l.reason, l.logged_at,
                   u.username as waiter_name,
                   t.name as table_name, t.table_number
            FROM restaurant_kot_log l
            LEFT JOIN users u ON u.id = l.waiter_id
            LEFT JOIN restaurant_orders ro ON ro.id = l.order_id
            LEFT JOIN restaurant_tables t ON t.id = ro.table_id
            {where}
            ORDER BY l.logged_at DESC
        """)
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[Model] Error getting KOT log: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# WAITER NAME HELPER
# ─────────────────────────────────────────────────────────────────────────────

def get_waiter_name(waiter_id: int | None) -> str:
    if not waiter_id:
        return ""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT TOP 1 username FROM users WHERE id = ?", (waiter_id,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else ""
    except Exception:
        return ""

# ─────────────────────────────────────────────────────────────────────────────
# KDS HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def update_order_prep_status(order_id: int, status: str):
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("UPDATE restaurant_orders SET prep_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, order_id))
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[Model] Error updating order prep status: {e}")

def update_item_prep_status(order_id: int, item_name: str, status: str):
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            UPDATE restaurant_order_items 
            SET item_status = ? 
            WHERE order_id = ? AND item_name = ?
        """, (status, order_id, item_name))
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[Model] Error updating item prep status: {e}")

def get_kds_orders() -> list[dict]:
    """Fetch orders for KDS including items."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT o.id, o.table_id, t.name as table_name, t.table_number,
                   o.customer_name, o.prep_status, o.created_at, o.waiter_id, o.bill_notes
            FROM restaurant_orders o
            JOIN restaurant_tables t ON o.table_id = t.id
            WHERE o.prep_status IN ('Preparing', 'Ready', 'Cancelled')
            ORDER BY o.created_at ASC
        """ )
        cols = [desc[0] for desc in cur.description]
        orders = [dict(zip(cols, row)) for row in cur.fetchall()]
        
        for o in orders:
            cur.execute("""
                SELECT item_name, quantity as qty, item_status, item_notes
                FROM restaurant_order_items
                WHERE order_id = ?
            """, (o["id"],))
            i_cols = [desc[0] for desc in cur.description]
            o["items"] = [dict(zip(i_cols, row)) for row in cur.fetchall()]
            
        conn.close()
        return orders
    except Exception as e:
        print(f"[Model] Error getting KDS orders: {e}")
        return []

# ─────────────────────────────────────────────────────────────────────────────
# BILL SPLITS — partial payment collection per table
# ─────────────────────────────────────────────────────────────────────────────

def get_bill_splits(table_id: int) -> list[dict]:
    """Return all pending split entries for a table."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT id, table_id, label, mop_label, currency, amount_raw, amount_usd, created_at
            FROM restaurant_bill_splits
            WHERE table_id = ?
            ORDER BY created_at ASC
        """, (table_id,))
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[Model] Error getting bill splits: {e}")
        return []


def add_bill_split(table_id: int, mop_label: str, currency: str,
                   amount_raw: float, amount_usd: float, label: str = "") -> bool:
    """Record one person's share for a table."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO restaurant_bill_splits
                (table_id, label, mop_label, currency, amount_raw, amount_usd)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (table_id, label or None, mop_label, currency, amount_raw, amount_usd))
        conn.commit(); conn.close()
        return True
    except Exception as e:
        print(f"[Model] Error adding bill split: {e}")
        return False


def delete_bill_split(split_id: int) -> bool:
    """Remove a single split entry (e.g. cashier made a mistake)."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("DELETE FROM restaurant_bill_splits WHERE id = ?", (split_id,))
        conn.commit(); conn.close()
        return True
    except Exception as e:
        print(f"[Model] Error deleting bill split: {e}")
        return False


def clear_bill_splits(table_id: int):
    """Wipe all split entries for a table after payment is finalised."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("DELETE FROM restaurant_bill_splits WHERE table_id = ?", (table_id,))
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[Model] Error clearing bill splits: {e}")
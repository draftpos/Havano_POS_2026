# =============================================================================
# models/sales_order.py  —  Local DB model for Laybye / Sales Orders
#
# Target: Microsoft SQL Server (pyodbc)
#
# Table: sales_order
#   id               INT PK IDENTITY(1,1)
#   order_no         NVARCHAR(100)
#   customer_id      INT FK → customer.id  (nullable)
#   customer_name    NVARCHAR(255)
#   company          NVARCHAR(255)
#   order_date       NVARCHAR(50)  (ISO date)
#   delivery_date    NVARCHAR(50)  DEFAULT ''
#   order_type       NVARCHAR(50)  DEFAULT 'Sales'
#   total            FLOAT
#   deposit_amount   FLOAT         DEFAULT 0
#   deposit_method   NVARCHAR(100)
#   balance_due      FLOAT
#   status           NVARCHAR(50)  DEFAULT 'Draft'
#   synced           INT           DEFAULT 0
#   frappe_ref       NVARCHAR(255) DEFAULT ''
#   created_at       NVARCHAR(50)
#
# Table: sales_order_item
#   id               INT PK IDENTITY(1,1)
#   sales_order_id   INT FK → sales_order.id
#   item_code        NVARCHAR(100)
#   item_name        NVARCHAR(255)
#   qty              FLOAT
#   rate             FLOAT
#   amount           FLOAT
#   warehouse        NVARCHAR(255)
# =============================================================================

from __future__ import annotations
import logging
from datetime import datetime, date

log = logging.getLogger("sales_order")


# =============================================================================
# DB connection helper
# =============================================================================

def _get_conn():
    """Return a live DB connection from the project's db module."""
    from database.db import get_connection
    return get_connection()


def _dict_row(cursor, row) -> dict:
    """Convert a pyodbc Row to a plain dict."""
    return {col[0]: val for col, val in zip(cursor.description, row)}


# =============================================================================
# Schema helpers (T-SQL safe)
# =============================================================================

def _table_exists(cur, table: str) -> bool:
    cur.execute(
        "SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(?) AND type = 'U'",
        (table,)
    )
    return cur.fetchone() is not None


def _column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        "SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(?) AND name = ?",
        (table, column)
    )
    return cur.fetchone() is not None


def _add_column_if_missing(cur, conn, table: str, col: str, defn: str):
    if not _column_exists(cur, table, col):
        try:
            cur.execute(f"ALTER TABLE {table} ADD {col} {defn}")
            conn.commit()
            log.info("Migration: added column %s.%s", table, col)
        except Exception as exc:
            log.warning("Could not add %s.%s: %s", table, col, exc)


# =============================================================================
# Schema migration — call once at startup
# =============================================================================

def ensure_tables():
    """Create sales_order and sales_order_item tables if they don't exist."""
    conn = _get_conn()
    cur  = conn.cursor()

    # ── sales_order ──────────────────────────────────────────────────────────
    if not _table_exists(cur, "sales_order"):
        cur.execute("""
            CREATE TABLE sales_order (
                id              INT             PRIMARY KEY IDENTITY(1,1),
                order_no        NVARCHAR(100)   NULL,
                customer_id     INT             NULL,
                customer_name   NVARCHAR(255)   NULL,
                company         NVARCHAR(255)   NULL,
                order_date      NVARCHAR(50)    NULL,
                delivery_date   NVARCHAR(50)    NOT NULL DEFAULT '',
                order_type      NVARCHAR(50)    NOT NULL DEFAULT 'Sales',
                total           FLOAT           NOT NULL DEFAULT 0,
                deposit_amount  FLOAT           NOT NULL DEFAULT 0,
                deposit_method  NVARCHAR(100)   NOT NULL DEFAULT '',
                balance_due     FLOAT           NOT NULL DEFAULT 0,
                status          NVARCHAR(50)    NOT NULL DEFAULT 'Draft',
                synced          INT             NOT NULL DEFAULT 0,
                frappe_ref      NVARCHAR(255)   NOT NULL DEFAULT '',
                created_at      NVARCHAR(50)    NULL
            )
        """)
        conn.commit()
        log.info("Created table: sales_order")

    # Migration: add any columns introduced after initial deployment
    _add_column_if_missing(cur, conn, "sales_order", "delivery_date", "NVARCHAR(50)  NOT NULL DEFAULT ''")
    _add_column_if_missing(cur, conn, "sales_order", "order_type",    "NVARCHAR(50)  NOT NULL DEFAULT 'Sales'")
    _add_column_if_missing(cur, conn, "sales_order", "frappe_ref",    "NVARCHAR(255) NOT NULL DEFAULT ''")
    _add_column_if_missing(cur, conn, "sales_order", "synced",        "INT           NOT NULL DEFAULT 0")

    # ── sales_order_item ─────────────────────────────────────────────────────
    if not _table_exists(cur, "sales_order_item"):
        cur.execute("""
            CREATE TABLE sales_order_item (
                id              INT             PRIMARY KEY IDENTITY(1,1),
                sales_order_id  INT             NOT NULL
                                    REFERENCES sales_order(id),
                item_code       NVARCHAR(100)   NULL,
                item_name       NVARCHAR(255)   NULL,
                qty             FLOAT           NOT NULL DEFAULT 1,
                rate            FLOAT           NOT NULL DEFAULT 0,
                amount          FLOAT           NOT NULL DEFAULT 0,
                warehouse       NVARCHAR(255)   NOT NULL DEFAULT ''
            )
        """)
        conn.commit()
        log.info("Created table: sales_order_item")

    log.debug("sales_order tables ensured.")


# =============================================================================
# Order number generator
# =============================================================================

def _next_order_no(cur) -> str:
    cur.execute("SELECT COUNT(*) FROM sales_order")
    count = cur.fetchone()[0]
    return f"SO-{count + 1:04d}"


# =============================================================================
# CRUD
# =============================================================================

def create_sales_order(
    cart_items:      list[dict],
    total:           float,
    deposit_amount:  float = 0.0,
    deposit_method:  str   = "",
    customer:        dict  | None = None,
    company:         str   = "",
    order_date:      str   = "",
    delivery_date:   str   = "",
    order_type:      str   = "Sales",
) -> int:
    """
    Persist a new laybye (sales order) and its line items.
    Returns the new sales_order.id.
    """
    ensure_tables()

    if not order_date:
        order_date = date.today().isoformat()

    balance_due   = round(max(total - deposit_amount, 0.0), 4)
    customer_id   = (customer or {}).get("id") or (customer or {}).get("customer_id")
    customer_name = (customer or {}).get("customer_name") or "Walk-in Customer"
    created_at    = datetime.now().isoformat(timespec="seconds")

    conn = _get_conn()
    cur  = conn.cursor()

    order_no = _next_order_no(cur)

    # SQL Server uses OUTPUT INSERTED.id instead of lastrowid
    cur.execute("""
        INSERT INTO sales_order
            (order_no, customer_id, customer_name, company, order_date,
             delivery_date, order_type,
             total, deposit_amount, deposit_method, balance_due,
             status, synced, frappe_ref, created_at)
        OUTPUT INSERTED.id
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        order_no,
        customer_id,
        customer_name,
        company,
        order_date,
        delivery_date or "",
        order_type or "Sales",
        round(total, 4),
        round(deposit_amount, 4),
        deposit_method or "",
        balance_due,
        "Draft",
        0,
        "",
        created_at,
    ))

    order_id = cur.fetchone()[0]

    for item in cart_items:
        item_code = item.get("item_code") or item.get("code") or ""
        item_name = item.get("item_name") or item.get("name") or item_code
        qty       = float(item.get("qty") or item.get("quantity") or 1)
        rate      = float(item.get("rate") or item.get("price") or 0.0)
        amount    = float(item.get("amount") or item.get("total") or round(qty * rate, 4))
        warehouse = item.get("warehouse") or ""

        cur.execute("""
            INSERT INTO sales_order_item
                (sales_order_id, item_code, item_name, qty, rate, amount, warehouse)
            VALUES (?,?,?,?,?,?,?)
        """, (order_id, item_code, item_name, qty, rate, amount, warehouse))

    conn.commit()
    log.info("Laybye created: %s  id=%d  total=%.2f  deposit=%.2f  balance=%.2f",
             order_no, order_id, total, deposit_amount, balance_due)
    return order_id


def get_sales_order(order_id: int) -> dict | None:
    """Fetch a single sales order by id, including its line items."""
    ensure_tables()
    conn = _get_conn()
    cur  = conn.cursor()

    cur.execute("SELECT * FROM sales_order WHERE id = ?", (order_id,))
    row = cur.fetchone()
    if not row:
        return None

    order = _dict_row(cur, row)

    cur.execute("SELECT * FROM sales_order_item WHERE sales_order_id = ?", (order_id,))
    order["items"] = [_dict_row(cur, r) for r in cur.fetchall()]
    return order


def get_all_sales_orders(status: str | None = None) -> list[dict]:
    """Return all sales orders, optionally filtered by status."""
    ensure_tables()
    conn = _get_conn()
    cur  = conn.cursor()

    if status:
        cur.execute(
            "SELECT * FROM sales_order WHERE status = ? ORDER BY id DESC", (status,))
    else:
        cur.execute("SELECT * FROM sales_order ORDER BY id DESC")

    rows = cur.fetchall()
    return [_dict_row(cur, r) for r in rows]


def get_unsynced_orders() -> list[dict]:
    """Return orders that have not yet been pushed to ERPNext."""
    ensure_tables()
    conn = _get_conn()
    cur  = conn.cursor()

    cur.execute("SELECT * FROM sales_order WHERE synced = 0 ORDER BY id ASC")
    rows = cur.fetchall()
    return [_dict_row(cur, r) for r in rows]


def get_order_items(order_id: int) -> list[dict]:
    """Return all line items for a given sales order."""
    ensure_tables()
    conn = _get_conn()
    cur  = conn.cursor()

    cur.execute(
        "SELECT * FROM sales_order_item WHERE sales_order_id = ?", (order_id,))
    rows = cur.fetchall()
    return [_dict_row(cur, r) for r in rows]


def mark_order_synced(order_id: int, frappe_ref: str = ""):
    """Mark an order as successfully pushed to Frappe."""
    ensure_tables()
    conn = _get_conn()
    conn.execute(
        "UPDATE sales_order SET synced = 1, frappe_ref = ? WHERE id = ?",
        (frappe_ref, order_id))
    conn.commit()


def update_order_status(order_id: int, status: str):
    """status: 'Draft' | 'Confirmed' | 'Completed' | 'Cancelled'"""
    ensure_tables()
    conn = _get_conn()
    conn.execute(
        "UPDATE sales_order SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()


def add_deposit_payment(order_id: int, amount: float, method: str):
    """
    Record an additional deposit payment against an existing Sales Order.
    Reduces balance_due and updates deposit_amount.
    Automatically sets status to 'Completed' when balance reaches zero.
    """
    ensure_tables()
    conn = _get_conn()
    cur  = conn.cursor()

    cur.execute(
        "SELECT total, deposit_amount FROM sales_order WHERE id = ?", (order_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Sales order {order_id} not found.")

    total, existing_deposit = row[0], row[1]
    new_deposit = round(existing_deposit + amount, 4)
    new_balance = round(max(total - new_deposit, 0.0), 4)
    new_status  = "Completed" if new_balance <= 0.005 else "Confirmed"

    conn.execute(
        """
        UPDATE sales_order
        SET    deposit_amount = ?,
               deposit_method = ?,
               balance_due    = ?,
               status         = ?,
               synced         = 0
        WHERE  id = ?
        """,
        (new_deposit, method, new_balance, new_status, order_id))
    conn.commit()

    log.info("Deposit added to order %d: +%.2f via %s  balance=%.2f",
             order_id, amount, method, new_balance)
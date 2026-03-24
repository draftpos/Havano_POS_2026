#!/usr/bin/env python3
"""
migrate_sales_order.py
======================
Run this script ONCE to bring an existing database up to date with
the latest sales_order schema.

Usage:
    python migrate_sales_order.py

The script is safe to run multiple times — it skips columns / tables that
already exist.

Target: Microsoft SQL Server (T-SQL via pyodbc)
"""

import sys
import os


# ---------------------------------------------------------------------------
# Resolve DB connection the same way the app does
# ---------------------------------------------------------------------------
def _get_conn():
    for mod in ("database.db", "models.db", "db"):
        try:
            import importlib
            m  = importlib.import_module(mod)
            fn = getattr(m, "get_connection", None)
            if fn:
                conn = fn()
                print(f"  Using connection from: {mod}.get_connection()")
                return conn
        except Exception:
            pass

    raise RuntimeError(
        "Could not find a database connection.\n"
        "Make sure you run this script from the project root directory\n"
        "or that models/db.py / database/db.py is importable."
    )


# ---------------------------------------------------------------------------
# T-SQL helpers
# ---------------------------------------------------------------------------

def _table_exists_sql(table: str) -> str:
    """Return a T-SQL IF block that creates the table only when it is missing."""
    tables = {

        "sales_order": """
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'{table}') AND type = N'U'
)
BEGIN
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
END
""".replace("{table}", table),

        "sales_order_item": """
IF NOT EXISTS (
    SELECT 1 FROM sys.objects
    WHERE object_id = OBJECT_ID(N'{table}') AND type = N'U'
)
BEGIN
    CREATE TABLE sales_order_item (
        id              INT     PRIMARY KEY IDENTITY(1,1),
        sales_order_id  INT     NOT NULL REFERENCES sales_order(id),
        item_code       NVARCHAR(100)   NULL,
        item_name       NVARCHAR(255)   NULL,
        qty             FLOAT   NOT NULL DEFAULT 1,
        rate            FLOAT   NOT NULL DEFAULT 0,
        amount          FLOAT   NOT NULL DEFAULT 0,
        warehouse       NVARCHAR(255)   NOT NULL DEFAULT ''
    )
END
""".replace("{table}", table),
    }
    return tables[table]


def _column_exists(cur, table: str, column: str) -> bool:
    """Return True if the column already exists in the table."""
    cur.execute(
        """
        SELECT 1
        FROM   sys.columns
        WHERE  object_id = OBJECT_ID(?)
          AND  name      = ?
        """,
        (table, column),
    )
    return cur.fetchone() is not None


def _sql_type(defn: str) -> str:
    """
    Convert a simplified SQLite-style column definition to a T-SQL one.
    e.g.  'TEXT DEFAULT '''  ->  "NVARCHAR(255) NOT NULL DEFAULT ''"
          'REAL DEFAULT 0'   ->  'FLOAT NOT NULL DEFAULT 0'
          'INTEGER NOT NULL DEFAULT 0' -> 'INT NOT NULL DEFAULT 0'
    """
    defn = defn.strip()
    # Replace type keywords
    defn = defn.replace("INTEGER", "INT")
    defn = defn.replace("REAL",    "FLOAT")
    # TEXT → NVARCHAR(255), but keep the rest of the definition
    if defn.upper().startswith("TEXT"):
        defn = "NVARCHAR(255)" + defn[4:]
    return defn


# ---------------------------------------------------------------------------
# Migration steps
# ---------------------------------------------------------------------------

MIGRATIONS = [
    # (description, table_key)
    ("Create sales_order table (if not exists)",      "sales_order"),
    ("Create sales_order_item table (if not exists)", "sales_order_item"),
]

# Columns to add if they're missing
# (table, column_name, sqlite-style column definition)
ALTER_COLUMNS = [
    # ── sales_order ──────────────────────────────────────────────────────────
    ("sales_order", "delivery_date", "TEXT DEFAULT ''"),
    ("sales_order", "order_type",    "TEXT DEFAULT 'Sales'"),
    ("sales_order", "frappe_ref",    "TEXT DEFAULT ''"),
    ("sales_order", "synced",        "INTEGER NOT NULL DEFAULT 0"),
    # ── sale ─────────────────────────────────────────────────────────────────
    ("sale",        "discount_percent", "REAL DEFAULT 0"),
    ("sale",        "discount_amount",  "REAL DEFAULT 0"),
    # ── sale_items ───────────────────────────────────────────────────────────
    ("sale_items",  "discount",         "REAL DEFAULT 0"),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run():
    print("=" * 60)
    print("  Havano POS — Database Migration  (SQL Server / T-SQL)")
    print("=" * 60)

    try:
        conn = _get_conn()
    except RuntimeError as e:
        print(f"\n❌  {e}")
        sys.exit(1)

    # Some pyodbc connections need autocommit off and explicit commits;
    # others need autocommit on for DDL.  We set autocommit=True so that
    # each DDL statement is its own transaction (SQL Server requires this
    # for CREATE TABLE inside an IF block when using pyodbc).
    try:
        conn.autocommit = True
    except AttributeError:
        pass  # Not a pyodbc connection — ignore

    cur     = conn.cursor()
    ok      = 0
    skipped = 0
    errors  = 0

    # ── 1. CREATE TABLE (IF NOT EXISTS equivalent) ───────────────────────────
    for desc, table_key in MIGRATIONS:
        sql = _table_exists_sql(table_key)
        try:
            cur.execute(sql.strip())
            print(f"  ✔  {desc}")
            ok += 1
        except Exception as exc:
            print(f"  ⚠  {desc} — {exc}")
            errors += 1

    # ── 2. ALTER TABLE … ADD … (column-exists check via sys.columns) ─────────
    for table, col, raw_defn in ALTER_COLUMNS:
        try:
            exists = _column_exists(cur, table, col)
        except Exception as exc:
            print(f"  ⚠  Could not check {table}.{col}: {exc}")
            errors += 1
            continue

        if exists:
            print(f"  –  {table}.{col} already exists, skipping.")
            skipped += 1
            continue

        tsql_defn = _sql_type(raw_defn)
        sql = f"ALTER TABLE {table} ADD {col} {tsql_defn}"

        try:
            cur.execute(sql)
            print(f"  ✔  Added {table}.{col}  ({tsql_defn})")
            ok += 1
        except Exception as exc:
            msg = str(exc)
            if "duplicate column" in msg.lower() or "already exists" in msg.lower():
                print(f"  –  {table}.{col} already exists (caught on ALTER).")
                skipped += 1
            else:
                print(f"  ❌  Failed to add {table}.{col}: {msg}")
                errors += 1

    print()
    print(f"  Done.  ✔ {ok} applied  –  {skipped} skipped  ❌ {errors} errors")

    if errors:
        print("\n  Some steps failed. Check messages above.")
        print("  If errors relate to tables that don't exist yet (e.g. 'sale'),")
        print("  they will be created automatically on first app run.")
    else:
        print("\n  Migration complete — database is up to date.")

    try:
        conn.close()
    except Exception:
        pass


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    run()
# fix_sales_table.py
# Run once from your project root:  python fix_sales_table.py

import sqlite3, os, sys

DB_PATH = os.path.join(os.path.dirname(__file__), "pos.db")

def fix():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Check the path and update DB_PATH at the top of this script.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    # ── Create sales table if missing ────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number INTEGER NOT NULL DEFAULT 0,
            total          REAL    NOT NULL DEFAULT 0,
            tendered       REAL    NOT NULL DEFAULT 0,
            method         TEXT    NOT NULL DEFAULT 'Cash',
            cashier_id     INTEGER,
            created_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    print("✔  sales table created / verified.")

    # ── Create sale_items table if missing ───────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id      INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
            part_no      TEXT    NOT NULL DEFAULT '',
            product_name TEXT    NOT NULL DEFAULT '',
            qty          REAL    NOT NULL DEFAULT 1,
            price        REAL    NOT NULL DEFAULT 0,
            discount     REAL    NOT NULL DEFAULT 0,
            tax          TEXT    NOT NULL DEFAULT '',
            total        REAL    NOT NULL DEFAULT 0
        )
    """)
    print("✔  sale_items table created / verified.")

    # ── Add any missing columns to existing sales table ──────────────────────
    columns_to_add = [
        ("invoice_number", "INTEGER NOT NULL DEFAULT 0"),
        ("tendered",       "REAL    NOT NULL DEFAULT 0"),
        ("method",         "TEXT    NOT NULL DEFAULT 'Cash'"),
        ("cashier_id",     "INTEGER"),
        ("created_at",     "TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))"),
    ]

    existing = {row[1] for row in conn.execute("PRAGMA table_info(sales)")}
    for col, definition in columns_to_add:
        if col not in existing:
            conn.execute(f"ALTER TABLE sales ADD COLUMN {col} {definition}")
            print(f"  + Added column sales.{col}")

    conn.commit()
    conn.close()
    print("\n✅  Done! Run: python main.py")

if __name__ == "__main__":
    fix()
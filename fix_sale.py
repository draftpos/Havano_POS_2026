# fix_sale_items.py
# Run once from your project root:  python fix_sale_items.py

import sqlite3, os, sys

DB_PATH = os.path.join(os.path.dirname(__file__), "pos.db")

def fix():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    # All columns sale_items should have
    columns_to_add = [
        ("part_no",      "TEXT NOT NULL DEFAULT ''"),
        ("product_name", "TEXT NOT NULL DEFAULT ''"),
        ("qty",          "REAL NOT NULL DEFAULT 1"),
        ("price",        "REAL NOT NULL DEFAULT 0"),
        ("discount",     "REAL NOT NULL DEFAULT 0"),
        ("tax",          "TEXT NOT NULL DEFAULT ''"),
        ("total",        "REAL NOT NULL DEFAULT 0"),
    ]

    existing = {row[1] for row in conn.execute("PRAGMA table_info(sale_items)")}
    print(f"Existing columns: {existing}")

    for col, definition in columns_to_add:
        if col not in existing:
            conn.execute(f"ALTER TABLE sale_items ADD COLUMN {col} {definition}")
            print(f"  + Added column sale_items.{col}")
        else:
            print(f"  ✔ {col} already exists")

    conn.commit()
    conn.close()
    print("\n✅  Done! Run: python main.py")

if __name__ == "__main__":
    fix()
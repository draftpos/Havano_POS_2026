"""
reset_database.py — drops all POS tables so the app rebuilds from scratch.

Usage:
    python reset_database.py
"""

import sys
import json
import pyodbc
from pathlib import Path

# ── same driver detection as db.py ────────────────────────────────────────────
def _best_driver() -> str:
    preferred = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "SQL Server",
    ]
    for d in preferred:
        if d in pyodbc.drivers():
            return d
    raise RuntimeError("No SQL Server ODBC driver found.")

def _get_connection():
    path = Path("app_data/sql_settings.json")
    if not path.exists():
        print("ERROR: app_data/sql_settings.json not found.")
        print("Make sure you run this script from your project root folder.")
        sys.exit(1)

    cfg  = json.loads(path.read_text(encoding="utf-8"))
    drv  = _best_driver()

    if cfg.get("auth_mode") == "windows":
        conn_str = (
            f"DRIVER={{{drv}}};"
            f"SERVER={cfg['server']};"
            f"DATABASE={cfg['database']};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )
    else:
        conn_str = (
            f"DRIVER={{{drv}}};"
            f"SERVER={cfg['server']};"
            f"DATABASE={cfg['database']};"
            f"UID={cfg['username']};"
            f"PWD={cfg['password']};"
            "TrustServerCertificate=yes;"
        )

    return pyodbc.connect(conn_str)


# ── tables to drop (dependants first so FK constraints don't block) ───────────
TABLES = [
    "sale_items",
    "sales",
    "credit_note_items",
    "credit_notes",
    "customers",
    "customer_groups",
    "products",
    "price_list_items",
    "price_lists",
    "warehouses",
    "cost_centers",
    "companies",
    "users",
    "company_defaults",
]


def reset():
    conn = _get_connection()
    cur  = conn.cursor()

    print("\n" + "="*52)
    print("   POS DATABASE RESET")
    print("="*52)

    # turn off all FK checks so we can drop in any order
    try:
        cur.execute("EXEC sp_MSforeachtable 'ALTER TABLE ? NOCHECK CONSTRAINT ALL'")
        conn.commit()
    except Exception:
        pass

    dropped = 0
    for table in TABLES:
        try:
            cur.execute(f"""
                IF OBJECT_ID('{table}', 'U') IS NOT NULL
                    DROP TABLE [{table}]
            """)
            conn.commit()
            print(f"  Dropped : {table}")
            dropped += 1
        except Exception as e:
            print(f"  Skipped : {table}  ({e})")

    conn.close()
    print("="*52)
    print(f"  Done - {dropped} table(s) dropped.")
    print("  Launch the app normally to rebuild all tables.\n")


if __name__ == "__main__":
    print("\n  WARNING: This will permanently delete ALL data.")
    confirm = input("  Type  YES  to continue: ").strip()
    if confirm == "YES":
        reset()
    else:
        print("  Aborted - nothing was changed.\n")
# import re

# with open('database/db.py', encoding='utf-8') as f:
#     content = f.read()

# # Remove git conflict markers - keep HEAD version, discard incoming
# fixed = re.sub(r'<<<<<<< HEAD\n', '', content)
# fixed = re.sub(r'\n=======\n.*?\n>>>>>>> [^\n]+', '', fixed, flags=re.DOTALL)

# with open('database/db.py', 'w', encoding='utf-8') as f:
#     f.write(fixed)

# print("Fixed. db.py is clean.")

"""
migrate_users.py
================
Run once to create / upgrade the users table in SQL Server.

Usage:
    python migrate_users.py

What it does:
  1. Creates the users table if it doesn't exist (with ALL columns)
  2. Adds any missing columns to an existing table:
       allow_discount, allow_receipt, allow_credit_note, allow_reprint
  3. Reports what was done
"""

import sys
import os

# Allow running from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import get_connection


def run():
    conn = get_connection()
    cur  = conn.cursor()

    # ── 1. Create table if missing ────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='users'
        )
        CREATE TABLE users (
            id                 INT           IDENTITY(1,1) PRIMARY KEY,
            username           NVARCHAR(80)  NOT NULL UNIQUE,
            password           NVARCHAR(255) NOT NULL,
            role               NVARCHAR(20)  NOT NULL DEFAULT 'cashier',
            display_name       NVARCHAR(120) NULL,
            email              NVARCHAR(120) NULL,
            full_name          NVARCHAR(120) NULL,
            first_name         NVARCHAR(80)  NULL,
            last_name          NVARCHAR(80)  NULL,
            pin                NVARCHAR(20)  NULL,
            cost_center        NVARCHAR(140) NULL,
            warehouse          NVARCHAR(140) NULL,
            frappe_user        NVARCHAR(120) NULL,
            synced_from_frappe BIT           NOT NULL DEFAULT 0,
            active             BIT           NOT NULL DEFAULT 1,
            allow_discount     BIT           NOT NULL DEFAULT 1,
            allow_receipt      BIT           NOT NULL DEFAULT 1,
            allow_credit_note  BIT           NOT NULL DEFAULT 1,
            allow_reprint      BIT           NOT NULL DEFAULT 1
        )
    """)
    conn.commit()
    print("✅  users table: exists (or just created)")

    # ── 2. Add any missing columns (safe on existing tables) ──────────────────
    upgrades = [
        ("allow_discount",    "BIT NOT NULL DEFAULT 1"),
        ("allow_receipt",     "BIT NOT NULL DEFAULT 1"),
        ("allow_credit_note", "BIT NOT NULL DEFAULT 1"),
        ("allow_reprint",     "BIT NOT NULL DEFAULT 1"),
        ("pin",               "NVARCHAR(20) NULL"),
        ("full_name",         "NVARCHAR(120) NULL"),
        ("email",             "NVARCHAR(120) NULL"),
        ("cost_center",       "NVARCHAR(140) NULL"),
        ("warehouse",         "NVARCHAR(140) NULL"),
        ("display_name",      "NVARCHAR(120) NULL"),
        ("first_name",        "NVARCHAR(80) NULL"),
        ("last_name",         "NVARCHAR(80) NULL"),
        ("frappe_user",       "NVARCHAR(120) NULL"),
        ("synced_from_frappe","BIT NOT NULL DEFAULT 0"),
        ("active",            "BIT NOT NULL DEFAULT 1"),
    ]

    for col, definition in upgrades:
        try:
            cur.execute(f"""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME='users' AND COLUMN_NAME='{col}'
                )
                ALTER TABLE users ADD {col} {definition}
            """)
            conn.commit()
            print(f"   + {col}")
        except Exception as e:
            print(f"   ! {col}: {e}")

    # ── 3. Verify ─────────────────────────────────────────────────────────────
    cur.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
        FROM   INFORMATION_SCHEMA.COLUMNS
        WHERE  TABLE_NAME = 'users'
        ORDER  BY ORDINAL_POSITION
    """)
    rows = cur.fetchall()
    print("\n── Current users table columns ──────────────────────────")
    for col_name, dtype, nullable in rows:
        print(f"   {col_name:<25} {dtype:<15} {'NULL' if nullable=='YES' else 'NOT NULL'}")

    conn.close()
    print("\n✅  Migration complete.")


if __name__ == "__main__":
    run()
    
    
    
import pyodbc
from database.db import get_connection

def run_migrations():
    print("🚀 Starting Database Migration...")
    conn = get_connection()
    cur = conn.cursor()

    # SQL Server uses IDENTITY(1,1) instead of AUTOINCREMENT
    # We check existence using information_schema
    tables = {
        "customer_groups": """
            CREATE TABLE customer_groups (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255) UNIQUE NOT NULL
            )""",
        "warehouses": """
            CREATE TABLE warehouses (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255) UNIQUE NOT NULL
            )""",
        "cost_centers": """
            CREATE TABLE cost_centers (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255) UNIQUE NOT NULL
            )""",
        "price_lists": """
            CREATE TABLE price_lists (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255) UNIQUE NOT NULL
            )""",
        "customers": """
            CREATE TABLE customers (
                id INT IDENTITY(1,1) PRIMARY KEY,
                customer_name NVARCHAR(255) UNIQUE NOT NULL,
                customer_type NVARCHAR(50) DEFAULT 'Individual',
                customer_group_id INT,
                custom_trade_name NVARCHAR(255),
                custom_telephone_number NVARCHAR(50),
                custom_email_address NVARCHAR(255),
                custom_city NVARCHAR(100),
                custom_house_no NVARCHAR(50),
                custom_warehouse_id INT,
                custom_cost_center_id INT,
                default_price_list_id INT,
                balance DECIMAL(18, 4) DEFAULT 0.0,
                outstanding_amount DECIMAL(18, 4) DEFAULT 0.0,
                loyalty_points INT DEFAULT 0,
                CONSTRAINT FK_C_Group FOREIGN KEY (customer_group_id) REFERENCES customer_groups(id),
                CONSTRAINT FK_C_WH FOREIGN KEY (custom_warehouse_id) REFERENCES warehouses(id),
                CONSTRAINT FK_C_CC FOREIGN KEY (custom_cost_center_id) REFERENCES cost_centers(id),
                CONSTRAINT FK_C_PL FOREIGN KEY (default_price_list_id) REFERENCES price_lists(id)
            )"""
    }

    for table_name, create_sql in tables.items():
        try:
            # Check if table exists
            cur.execute(f"SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}'")
            if not cur.fetchone():
                print(f"📦 Creating table: {table_name}...")
                cur.execute(create_sql)
                conn.commit()
            else:
                print(f"✅ Table already exists: {table_name}")
        except Exception as e:
            print(f"❌ Error creating {table_name}: {e}")

    # Seed initial data for lookups so the sync service can find the IDs
    seed_data = {
        "warehouses": ["Stores - AT"],
        "cost_centers": ["Main - AT"],
        "price_lists": ["Standard Selling", "Standard Selling ZWG"]
    }

    for table, names in seed_data.items():
        for name in names:
            try:
                cur.execute(f"SELECT 1 FROM {table} WHERE name = ?", (name,))
                if not cur.fetchone():
                    print(f"🌱 Seeding {table}: {name}")
                    cur.execute(f"INSERT INTO {table} (name) VALUES (?)", (name,))
                    conn.commit()
            except Exception as e:
                print(f"⚠️ Could not seed {name} in {table}: {e}")

    cur.close()
    conn.close()
    print("\n✨ Migration and Seeding Complete.")

if __name__ == "__main__":
    run_migrations()
# # =============================================================================
# # seed.py  —  Run migrations then seed 20 products
# # Usage:  python seed.py
# # Place this file in your project root (same folder as models/)
# # =============================================================================

# import sys
# import os

# sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# # =============================================================================
# # STEP 1 — MIGRATE  (create tables if they don't exist)
# # =============================================================================

# def run_migrations():
#     print("\n" + "=" * 55)
#     print("  STEP 1 — Running migrations...")
#     print("=" * 55)

#     from database.db import get_connection

#     conn = get_connection()
#     cur  = conn.cursor()

#     # ── products ──────────────────────────────────────────────────────────────
#     cur.execute("""
#         IF NOT EXISTS (
#             SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'products'
#         )
#         CREATE TABLE products (
#             id          INT           IDENTITY(1,1) PRIMARY KEY,
#             part_no     NVARCHAR(50)  NOT NULL UNIQUE,
#             name        NVARCHAR(120) NOT NULL,
#             price       DECIMAL(12,2) NOT NULL DEFAULT 0,
#             stock       INT           NOT NULL DEFAULT 0,
#             category    NVARCHAR(80)  NOT NULL DEFAULT '',
#             image_path  NVARCHAR(500) NOT NULL DEFAULT ''
#         )
#     """)
#     print("  OK    products table")

#     # ── sales ─────────────────────────────────────────────────────────────────
#     cur.execute("""
#         IF NOT EXISTS (
#             SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'sales'
#         )
#         CREATE TABLE sales (
#             id               INT           IDENTITY(1,1) PRIMARY KEY,
#             invoice_number   INT           NOT NULL DEFAULT 0,
#             invoice_no       NVARCHAR(40)  NOT NULL DEFAULT '',
#             invoice_date     NVARCHAR(20)  NOT NULL DEFAULT '',
#             total            DECIMAL(12,2) NOT NULL DEFAULT 0,
#             tendered         DECIMAL(12,2) NOT NULL DEFAULT 0,
#             method           NVARCHAR(30)  NOT NULL DEFAULT 'Cash',
#             cashier_id       INT           NULL,
#             cashier_name     NVARCHAR(120) NOT NULL DEFAULT '',
#             customer_name    NVARCHAR(120) NOT NULL DEFAULT '',
#             customer_contact NVARCHAR(80)  NOT NULL DEFAULT '',
#             kot              NVARCHAR(40)  NOT NULL DEFAULT '',
#             currency         NVARCHAR(10)  NOT NULL DEFAULT 'USD',
#             subtotal         DECIMAL(12,2) NOT NULL DEFAULT 0,
#             total_vat        DECIMAL(12,2) NOT NULL DEFAULT 0,
#             discount_amount  DECIMAL(12,2) NOT NULL DEFAULT 0,
#             receipt_type     NVARCHAR(30)  NOT NULL DEFAULT 'Invoice',
#             footer           NVARCHAR(MAX) NOT NULL DEFAULT '',
#             created_at       DATETIME2     NOT NULL DEFAULT SYSDATETIME()
#         )
#     """)
#     print("  OK    sales table")

#     # ── sale_items ────────────────────────────────────────────────────────────
#     cur.execute("""
#         IF NOT EXISTS (
#             SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'sale_items'
#         )
#         CREATE TABLE sale_items (
#             id           INT           IDENTITY(1,1) PRIMARY KEY,
#             sale_id      INT           NOT NULL
#                              REFERENCES sales(id) ON DELETE CASCADE,
#             part_no      NVARCHAR(50)  NOT NULL DEFAULT '',
#             product_name NVARCHAR(120) NOT NULL,
#             qty          DECIMAL(12,4) NOT NULL DEFAULT 1,
#             price        DECIMAL(12,2) NOT NULL DEFAULT 0,
#             discount     DECIMAL(12,2) NOT NULL DEFAULT 0,
#             tax          NVARCHAR(20)  NOT NULL DEFAULT '',
#             total        DECIMAL(12,2) NOT NULL DEFAULT 0,
#             tax_type     NVARCHAR(20)  NOT NULL DEFAULT '',
#             tax_rate     DECIMAL(8,4)  NOT NULL DEFAULT 0,
#             tax_amount   DECIMAL(12,2) NOT NULL DEFAULT 0,
#             remarks      NVARCHAR(MAX) NOT NULL DEFAULT ''
#         )
#     """)
#     print("  OK    sale_items table")

#     # ── users ─────────────────────────────────────────────────────────────────
#     cur.execute("""
#         IF NOT EXISTS (
#             SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'users'
#         )
#         CREATE TABLE users (
#             id           INT           IDENTITY(1,1) PRIMARY KEY,
#             username     NVARCHAR(80)  NOT NULL UNIQUE,
#             password     NVARCHAR(255) NOT NULL,
#             role         NVARCHAR(20)  NOT NULL DEFAULT 'cashier',
#             created_at   DATETIME2     NOT NULL DEFAULT SYSDATETIME()
#         )
#     """)
#     print("  OK    users table")

#     # ── shifts ────────────────────────────────────────────────────────────────
#     cur.execute("""
#         IF NOT EXISTS (
#             SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'shifts'
#         )
#         CREATE TABLE shifts (
#             id           INT           IDENTITY(1,1) PRIMARY KEY,
#             shift_number INT           NOT NULL DEFAULT 1,
#             station      INT           NOT NULL DEFAULT 1,
#             cashier_id   INT           NULL,
#             date         NVARCHAR(20)  NOT NULL,
#             start_time   NVARCHAR(20)  NOT NULL,
#             end_time     NVARCHAR(20)  NULL,
#             door_counter INT           NOT NULL DEFAULT 0,
#             customers    INT           NOT NULL DEFAULT 0,
#             notes        NVARCHAR(MAX) NOT NULL DEFAULT '',
#             created_at   DATETIME2     NOT NULL DEFAULT SYSDATETIME()
#         )
#     """)
#     print("  OK    shifts table")

#     # ── shift_rows ────────────────────────────────────────────────────────────
#     cur.execute("""
#         IF NOT EXISTS (
#             SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'shift_rows'
#         )
#         CREATE TABLE shift_rows (
#             id           INT           IDENTITY(1,1) PRIMARY KEY,
#             shift_id     INT           NOT NULL
#                              REFERENCES shifts(id) ON DELETE CASCADE,
#             method       NVARCHAR(50)  NOT NULL,
#             start_float  DECIMAL(12,2) NOT NULL DEFAULT 0,
#             income       DECIMAL(12,2) NOT NULL DEFAULT 0,
#             counted      DECIMAL(12,2) NOT NULL DEFAULT 0
#         )
#     """)
#     print("  OK    shift_rows table")

#     conn.commit()
#     conn.close()
#     print("  ✅  All tables ready.")


# # =============================================================================
# # STEP 2 — SEED PRODUCTS
# # =============================================================================

# PRODUCTS = [
#     # (part_no,   name,                        price,   stock, category)
#     ("DK001",  "Coca-Cola 500ml",               1.20,   50,  "Drinks"),
#     ("DK002",  "Fanta Orange 500ml",            1.20,   50,  "Drinks"),
#     ("DK003",  "Mineral Water 750ml",           0.80,   80,  "Drinks"),
#     ("DK004",  "Orange Juice 1L",               2.50,   30,  "Drinks"),
#     ("GR001",  "Cooking Oil 2L",                3.50,   40,  "Grocery"),
#     ("GR002",  "Sugar 2kg",                     2.00,   60,  "Grocery"),
#     ("GR003",  "Bread Loaf",                    1.50,   25,  "Grocery"),
#     ("GR004",  "Rice 5kg",                      6.00,   35,  "Grocery"),
#     ("GR005",  "Maize Meal 10kg",               8.00,   20,  "Grocery"),
#     ("SN001",  "Lay's Chips 100g",              1.00,   45,  "Snacks"),
#     ("SN002",  "Biscuits Assorted 200g",        1.50,   40,  "Snacks"),
#     ("SN003",  "Chocolate Bar 50g",             0.90,   60,  "Snacks"),
#     ("HH001",  "Washing Powder 1kg",            3.00,   30,  "Household"),
#     ("HH002",  "Dish Soap 500ml",               1.80,   35,  "Household"),
#     ("HH003",  "Toilet Paper 6-pack",           4.50,   25,  "Household"),
#     ("TB001",  "Toothpaste 100ml",              2.20,   30,  "Toiletries"),
#     ("TB002",  "Soap Bar 150g",                 0.70,   50,  "Toiletries"),
#     ("TB003",  "Shampoo 400ml",                 3.80,   20,  "Toiletries"),
#     ("EL001",  "AA Batteries 4-pack",           2.50,   40,  "Electronics"),
#     ("S",      "Service Charge",               50.00,    0,  "Services"),
# ]


# def seed_products():
#     print("\n" + "=" * 55)
#     print("  STEP 2 — Seeding 20 products...")
#     print("=" * 55)

#     from models.product import create_product, get_all_products

#     existing = {p["part_no"] for p in get_all_products()}
#     inserted = 0
#     skipped  = 0

#     for part_no, name, price, stock, category in PRODUCTS:
#         if part_no in existing:
#             print(f"  SKIP  {part_no:<8}  {name}  (already exists)")
#             skipped += 1
#         else:
#             try:
#                 p = create_product(part_no, name, price, stock, category)
#                 print(f"  OK    {p['part_no']:<8}  {p['name']:<30}  ${p['price']:.2f}  stock={p['stock']}")
#                 inserted += 1
#             except Exception as e:
#                 print(f"  ERR   {part_no:<8}  {name}  → {e}")

#     print("=" * 55)
#     print(f"  ✅  Products done.  Inserted: {inserted}   Skipped: {skipped}")


# # =============================================================================
# # STEP 3 — SEED DEFAULT ADMIN USER
# # =============================================================================

# def seed_admin():
#     print("\n" + "=" * 55)
#     print("  STEP 3 — Seeding default admin user...")
#     print("=" * 55)

#     from database.db import get_connection

#     conn = get_connection()
#     cur  = conn.cursor()

#     cur.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
#     exists = cur.fetchone()[0]

#     if exists:
#         print("  SKIP  admin user already exists")
#     else:
#         try:
#             try:
#                 from models.user import create_user
#                 create_user("admin", "admin123", "admin")
#                 print("  OK    admin user created  (username: admin  password: admin123)")
#             except Exception:
#                 cur.execute("""
#                     INSERT INTO users (username, password, role)
#                     VALUES (?, ?, ?)
#                 """, ("admin", "admin123", "admin"))
#                 conn.commit()
#                 print("  OK    admin user created  (username: admin  password: admin123)")
#         except Exception as e:
#             print(f"  ERR   Could not create admin user → {e}")

#     conn.close()
#     print("  ✅  Users done.")


# # =============================================================================
# # MAIN
# # =============================================================================

# if __name__ == "__main__":
#     print("\n  Havano POS — Database Setup")

#     try:
#         run_migrations()
#     except Exception as e:
#         print(f"\n  ❌  Migration failed: {e}")
#         sys.exit(1)

#     try:
#         seed_products()
#     except Exception as e:
#         print(f"\n  ❌  Product seed failed: {e}")

#     try:
#         seed_admin()
#     except Exception as e:
#         print(f"\n  ❌  Admin seed failed: {e}")

#     print("\n" + "=" * 55)
#     print("  🎉  Setup complete — you can now run:  py main.py")
#     print("=" * 55 + "\n")

# =============================================================================
# migrate.py  —  Run once to bring the database schema up to date.
#
# Safe to run on an existing database — every ALTER is guarded by
# IF NOT EXISTS so it will not fail if the column already exists.
#
# Usage:
#   python migrate.py
# =============================================================================

import sys
import traceback


def run_migration():
    try:
        from database.db import get_connection
    except ImportError as e:
        print(f"[migrate] ✗  Could not import database module: {e}")
        print("           Make sure you run this script from the project root.")
        sys.exit(1)

    conn = get_connection()
    cur  = conn.cursor()
    ok   = True

    # =========================================================================
    # SALES TABLE
    # =========================================================================
    print("[migrate] Checking  sales  table …")

    # ── Create table if it doesn't exist yet ─────────────────────────────────
    try:
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = 'sales'
            )
            CREATE TABLE sales (
                id               INT           IDENTITY(1,1) PRIMARY KEY,
                invoice_number   INT           NOT NULL DEFAULT 0,
                invoice_no       NVARCHAR(40)  NOT NULL DEFAULT '',
                invoice_date     NVARCHAR(20)  NOT NULL DEFAULT '',
                total            DECIMAL(12,2) NOT NULL DEFAULT 0,
                tendered         DECIMAL(12,2) NOT NULL DEFAULT 0,
                method           NVARCHAR(30)  NOT NULL DEFAULT 'Cash',
                cashier_id       INT           NULL,
                cashier_name     NVARCHAR(120) NOT NULL DEFAULT '',
                customer_name    NVARCHAR(120) NOT NULL DEFAULT '',
                customer_contact NVARCHAR(80)  NOT NULL DEFAULT '',
                kot              NVARCHAR(40)  NOT NULL DEFAULT '',
                currency         NVARCHAR(10)  NOT NULL DEFAULT 'USD',
                subtotal         DECIMAL(12,2) NOT NULL DEFAULT 0,
                total_vat        DECIMAL(12,2) NOT NULL DEFAULT 0,
                discount_amount  DECIMAL(12,2) NOT NULL DEFAULT 0,
                receipt_type     NVARCHAR(30)  NOT NULL DEFAULT 'Invoice',
                footer           NVARCHAR(MAX) NOT NULL DEFAULT '',
                created_at       DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
                total_items      DECIMAL(12,4) NOT NULL DEFAULT 0,
                change_amount    DECIMAL(12,2) NOT NULL DEFAULT 0,
                synced           INT           NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
        print("[migrate]   ✓  sales  table exists / created.")
    except Exception as e:
        print(f"[migrate]   ✗  Could not create sales table: {e}")
        ok = False

    # ── Add new columns to the existing sales table ───────────────────────────
    sales_columns = [
        ("total_items",      "DECIMAL(12,4) NOT NULL DEFAULT 0"),
        ("change_amount",    "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ("synced",           "INT           NOT NULL DEFAULT 0"),
        # columns that older builds may be missing
        ("invoice_no",       "NVARCHAR(40)  NOT NULL DEFAULT ''"),
        ("invoice_date",     "NVARCHAR(20)  NOT NULL DEFAULT ''"),
        ("cashier_name",     "NVARCHAR(120) NOT NULL DEFAULT ''"),
        ("customer_name",    "NVARCHAR(120) NOT NULL DEFAULT ''"),
        ("customer_contact", "NVARCHAR(80)  NOT NULL DEFAULT ''"),
        ("kot",              "NVARCHAR(40)  NOT NULL DEFAULT ''"),
        ("currency",         "NVARCHAR(10)  NOT NULL DEFAULT 'USD'"),
        ("subtotal",         "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ("total_vat",        "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ("discount_amount",  "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ("receipt_type",     "NVARCHAR(30)  NOT NULL DEFAULT 'Invoice'"),
        ("footer",           "NVARCHAR(MAX) NOT NULL DEFAULT ''"),
    ]

    for col, defn in sales_columns:
        try:
            cur.execute(f"""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'sales' AND COLUMN_NAME = '{col}'
                )
                ALTER TABLE sales ADD {col} {defn}
            """)
            conn.commit()
            print(f"[migrate]   ✓  sales.{col}")
        except Exception as e:
            print(f"[migrate]   ✗  sales.{col}: {e}")
            ok = False

    # ── Back-fill total_items for older rows that have 0 ─────────────────────
    try:
        cur.execute("""
            UPDATE s
            SET    s.total_items = sub.qty_sum
            FROM   sales s
            JOIN (
                SELECT sale_id, SUM(qty) AS qty_sum
                FROM   sale_items
                GROUP BY sale_id
            ) sub ON sub.sale_id = s.id
            WHERE  s.total_items = 0
        """)
        affected = cur.rowcount
        conn.commit()
        if affected:
            print(f"[migrate]   ✓  Back-filled total_items for {affected} row(s).")
    except Exception as e:
        # sale_items may not exist yet — silently skip
        print(f"[migrate]   ⚠  Could not back-fill total_items (OK if sale_items is new): {e}")

    # ── Back-fill change_amount for older rows ────────────────────────────────
    try:
        cur.execute("""
            UPDATE sales
            SET    change_amount = CASE
                       WHEN tendered > total THEN tendered - total
                       ELSE 0
                   END
            WHERE  change_amount = 0
              AND  tendered      > 0
        """)
        affected = cur.rowcount
        conn.commit()
        if affected:
            print(f"[migrate]   ✓  Back-filled change_amount for {affected} row(s).")
    except Exception as e:
        print(f"[migrate]   ✗  Back-fill change_amount: {e}")
        ok = False

    # =========================================================================
    # SALE_ITEMS TABLE
    # =========================================================================
    print("[migrate] Checking  sale_items  table …")

    try:
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = 'sale_items'
            )
            CREATE TABLE sale_items (
                id           INT           IDENTITY(1,1) PRIMARY KEY,
                sale_id      INT           NOT NULL
                                 REFERENCES sales(id) ON DELETE CASCADE,
                part_no      NVARCHAR(50)  NOT NULL DEFAULT '',
                product_name NVARCHAR(120) NOT NULL,
                qty          DECIMAL(12,4) NOT NULL DEFAULT 1,
                price        DECIMAL(12,2) NOT NULL DEFAULT 0,
                discount     DECIMAL(12,2) NOT NULL DEFAULT 0,
                tax          NVARCHAR(20)  NOT NULL DEFAULT '',
                total        DECIMAL(12,2) NOT NULL DEFAULT 0,
                tax_type     NVARCHAR(20)  NOT NULL DEFAULT '',
                tax_rate     DECIMAL(8,4)  NOT NULL DEFAULT 0,
                tax_amount   DECIMAL(12,2) NOT NULL DEFAULT 0,
                remarks      NVARCHAR(MAX) NOT NULL DEFAULT ''
            )
        """)
        conn.commit()
        print("[migrate]   ✓  sale_items  table exists / created.")
    except Exception as e:
        print(f"[migrate]   ✗  Could not create sale_items table: {e}")
        ok = False

    sale_item_columns = [
        ("part_no",      "NVARCHAR(50)  NOT NULL DEFAULT ''"),
        ("discount",     "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ("tax_type",     "NVARCHAR(20)  NOT NULL DEFAULT ''"),
        ("tax_rate",     "DECIMAL(8,4)  NOT NULL DEFAULT 0"),
        ("tax_amount",   "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ("remarks",      "NVARCHAR(MAX) NOT NULL DEFAULT ''"),
    ]

    for col, defn in sale_item_columns:
        try:
            cur.execute(f"""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'sale_items' AND COLUMN_NAME = '{col}'
                )
                ALTER TABLE sale_items ADD {col} {defn}
            """)
            conn.commit()
            print(f"[migrate]   ✓  sale_items.{col}")
        except Exception as e:
            print(f"[migrate]   ✗  sale_items.{col}: {e}")
            ok = False

    # =========================================================================
    # USERS TABLE  (basic guard)
    # =========================================================================
    print("[migrate] Checking  users  table …")
    try:
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = 'users'
            )
            CREATE TABLE users (
                id           INT           IDENTITY(1,1) PRIMARY KEY,
                username     NVARCHAR(80)  NOT NULL UNIQUE,
                password     NVARCHAR(255) NOT NULL DEFAULT '',
                role         NVARCHAR(30)  NOT NULL DEFAULT 'cashier',
                created_at   DATETIME2     NOT NULL DEFAULT SYSDATETIME()
            )
        """)
        conn.commit()
        print("[migrate]   ✓  users  table exists / created.")
    except Exception as e:
        print(f"[migrate]   ✗  users table: {e}")
        ok = False

    # =========================================================================
    # PRODUCTS TABLE  (basic guard + image_path column)
    # =========================================================================
    print("[migrate] Checking  products  table …")
    try:
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = 'products'
            )
            CREATE TABLE products (
                id           INT           IDENTITY(1,1) PRIMARY KEY,
                part_no      NVARCHAR(50)  NOT NULL UNIQUE DEFAULT '',
                name         NVARCHAR(120) NOT NULL DEFAULT '',
                price        DECIMAL(12,2) NOT NULL DEFAULT 0,
                stock        INT           NOT NULL DEFAULT 0,
                category     NVARCHAR(80)  NOT NULL DEFAULT '',
                image_path   NVARCHAR(MAX) NULL
            )
        """)
        conn.commit()
        print("[migrate]   ✓  products  table exists / created.")
    except Exception as e:
        print(f"[migrate]   ✗  products table: {e}")
        ok = False

    try:
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'image_path'
            )
            ALTER TABLE products ADD image_path NVARCHAR(MAX) NULL
        """)
        conn.commit()
        print("[migrate]   ✓  products.image_path")
    except Exception as e:
        print(f"[migrate]   ✗  products.image_path: {e}")
        ok = False

    # =========================================================================
    # DONE
    # =========================================================================
    conn.close()
    if ok:
        print("\n[migrate] ✅  All migrations completed successfully.")
    else:
        print("\n[migrate] ⚠   Migration finished with some errors (see above).")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
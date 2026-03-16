# =============================================================================
# migrate.py  —  run this ONCE to create / update all tables in SQL Server
# Usage:  python migrate.py
# Safe to re-run — all CREATE TABLE blocks use IF NOT EXISTS
# New columns are added with ALTER TABLE … IF NOT EXISTS checks
# =============================================================================

from database.db import get_connection


def migrate():
    conn = get_connection()
    cur  = conn.cursor()
    print("[migrate] Connecting to SQL Server...")

    # ── users ─────────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='users')
        CREATE TABLE users (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            username     NVARCHAR(80)  NOT NULL UNIQUE,
            password     NVARCHAR(255) NOT NULL,
            role         NVARCHAR(20)  NOT NULL DEFAULT 'cashier',
            display_name NVARCHAR(120) NULL,
            active       BIT           NOT NULL DEFAULT 1
        )
    """); print("[migrate] ✅  users")

    # ── products ──────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='products')
        CREATE TABLE products (
            id         INT           IDENTITY(1,1) PRIMARY KEY,
            part_no    NVARCHAR(50)  NOT NULL DEFAULT '',
            name       NVARCHAR(120) NOT NULL,
            price      DECIMAL(12,2) NOT NULL DEFAULT 0,
            stock      INT           NOT NULL DEFAULT 0,
            category   NVARCHAR(80)  NOT NULL DEFAULT 'General',
            active     BIT           NOT NULL DEFAULT 1,
            image_path NVARCHAR(500) NULL
        )
    """); print("[migrate] ✅  products")

    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                       WHERE TABLE_NAME='products' AND COLUMN_NAME='image_path')
        ALTER TABLE products ADD image_path NVARCHAR(500) NULL
    """); print("[migrate] ✅  products.image_path ensured")

    # ── sales ─────────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='sales')
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
            synced           BIT           NOT NULL DEFAULT 0,
            created_at       DATETIME2     NOT NULL DEFAULT SYSDATETIME()
        )
    """); print("[migrate] ✅  sales")

    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                       WHERE TABLE_NAME='sales' AND COLUMN_NAME='synced')
        ALTER TABLE sales ADD synced BIT NOT NULL DEFAULT 0
    """); print("[migrate] ✅  sales.synced ensured")

    # ── sale_items ────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='sale_items')
        CREATE TABLE sale_items (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            sale_id      INT           NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
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
    """); print("[migrate] ✅  sale_items")

    # ── shifts ────────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='shifts')
        CREATE TABLE shifts (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            shift_number INT           NOT NULL DEFAULT 1,
            station      INT           NOT NULL DEFAULT 1,
            cashier_id   INT           NULL,
            date         NVARCHAR(20)  NOT NULL,
            start_time   NVARCHAR(20)  NOT NULL,
            end_time     NVARCHAR(20)  NULL,
            door_counter INT           NOT NULL DEFAULT 0,
            customers    INT           NOT NULL DEFAULT 0,
            notes        NVARCHAR(MAX) NOT NULL DEFAULT '',
            created_at   DATETIME2     NOT NULL DEFAULT SYSDATETIME()
        )
    """); print("[migrate] ✅  shifts")

    # ── shift_rows ────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='shift_rows')
        CREATE TABLE shift_rows (
            id          INT           IDENTITY(1,1) PRIMARY KEY,
            shift_id    INT           NOT NULL REFERENCES shifts(id) ON DELETE CASCADE,
            method      NVARCHAR(50)  NOT NULL,
            start_float DECIMAL(12,2) NOT NULL DEFAULT 0,
            income      DECIMAL(12,2) NOT NULL DEFAULT 0,
            counted     DECIMAL(12,2) NOT NULL DEFAULT 0
        )
    """); print("[migrate] ✅  shift_rows")

    # ── companies ─────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='companies')
        CREATE TABLE companies (
            id               INT           IDENTITY(1,1) PRIMARY KEY,
            name             NVARCHAR(120) NOT NULL UNIQUE,
            abbreviation     NVARCHAR(40)  NOT NULL,
            default_currency NVARCHAR(10)  NOT NULL DEFAULT 'USD',
            country          NVARCHAR(80)  NOT NULL
        )
    """); print("[migrate] ✅  companies")

    # ── customer_groups ───────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='customer_groups')
        CREATE TABLE customer_groups (
            id              INT           IDENTITY(1,1) PRIMARY KEY,
            name            NVARCHAR(120) NOT NULL UNIQUE,
            parent_group_id INT           NULL REFERENCES customer_groups(id)
        )
    """); print("[migrate] ✅  customer_groups")

    # ── warehouses ────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='warehouses')
        CREATE TABLE warehouses (
            id         INT           IDENTITY(1,1) PRIMARY KEY,
            name       NVARCHAR(120) NOT NULL,
            company_id INT           NOT NULL REFERENCES companies(id)
        )
    """); print("[migrate] ✅  warehouses")

    # ── cost_centers ──────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='cost_centers')
        CREATE TABLE cost_centers (
            id         INT           IDENTITY(1,1) PRIMARY KEY,
            name       NVARCHAR(120) NOT NULL,
            company_id INT           NOT NULL REFERENCES companies(id)
        )
    """); print("[migrate] ✅  cost_centers")

    # ── price_lists ───────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='price_lists')
        CREATE TABLE price_lists (
            id      INT           IDENTITY(1,1) PRIMARY KEY,
            name    NVARCHAR(120) NOT NULL UNIQUE,
            selling BIT           NOT NULL DEFAULT 1
        )
    """); print("[migrate] ✅  price_lists")

    # ── customers ─────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='customers')
        CREATE TABLE customers (
            id                       INT           IDENTITY(1,1) PRIMARY KEY,
            customer_name            NVARCHAR(120) NOT NULL,
            customer_group_id        INT           NOT NULL REFERENCES customer_groups(id),
            customer_type            NVARCHAR(20)  NULL,
            custom_trade_name        NVARCHAR(120) NOT NULL DEFAULT '',
            custom_telephone_number  NVARCHAR(40)  NOT NULL DEFAULT '',
            custom_email_address     NVARCHAR(120) NOT NULL DEFAULT '',
            custom_city              NVARCHAR(80)  NOT NULL DEFAULT '',
            custom_house_no          NVARCHAR(40)  NOT NULL DEFAULT '',
            custom_warehouse_id      INT           NOT NULL REFERENCES warehouses(id),
            custom_cost_center_id    INT           NOT NULL REFERENCES cost_centers(id),
            default_price_list_id    INT           NOT NULL REFERENCES price_lists(id)
        )
    """); print("[migrate] ✅  customers")

    # ── Seed default admin if users table is empty ────────────────────────────
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        import hashlib
        hashed = hashlib.sha256("admin123".encode()).hexdigest()
        cur.execute(
            "INSERT INTO users (username, password, role, display_name) VALUES (?, ?, ?, ?)",
            ("admin", hashed, "admin", "Administrator")
        )
        print("[migrate] ✅  Default admin created  (admin / admin123)")

    conn.commit()
    conn.close()
    print()
    print("[migrate] 🎉  All tables ready. Run:  py main.py")


if __name__ == "__main__":
    migrate()
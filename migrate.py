# =============================================================================
# migrate.py  —  run this ONCE to create / update all tables in SQL Server
# Usage:  python migrate.py
# Safe to re-run — all CREATE TABLE blocks use IF NOT EXISTS
# New columns are added with ALTER TABLE … IF NOT EXISTS checks
# =============================================================================

from database.db import get_connection


def migrate():
    conn = get_connection()
    cur = conn.cursor()
    print("[migrate] Connecting to SQL Server...")
    
    def _add_column_if_missing(table: str, col: str, defn: str):
        """Helper to add column if it doesn't exist."""
        try:
            cur.execute(f"IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{table}' AND COLUMN_NAME='{col}') "
                        f"ALTER TABLE {table} ADD {col} {defn}")
            conn.commit()
        except Exception as e:
            print(f"[migrate]   ! Could not add {table}.{col}: {e}")

    # ── users ─────────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='users')
        CREATE TABLE users (
            id                   INT           IDENTITY(1,1) PRIMARY KEY,
            username             NVARCHAR(80)  NOT NULL UNIQUE,
            password             NVARCHAR(255) NOT NULL,
            display_name         NVARCHAR(120) NULL,
            active               BIT           NOT NULL DEFAULT 1,
            role                 NVARCHAR(20)  NULL DEFAULT 'cashier',
            email                NVARCHAR(120) NULL,
            full_name            NVARCHAR(120) NULL,
            first_name           NVARCHAR(80)  NULL,
            last_name            NVARCHAR(80)  NULL,
            pin                  NVARCHAR(20)  NULL,
            cost_center          NVARCHAR(140) NULL,
            warehouse            NVARCHAR(140) NULL,
            frappe_user          NVARCHAR(120) NULL,
            synced_from_frappe   BIT           NOT NULL DEFAULT 0,
            allow_discount       BIT           NOT NULL DEFAULT 1,
            allow_receipt        BIT           NOT NULL DEFAULT 1,
            allow_credit_note    BIT           NOT NULL DEFAULT 1,
            allow_reprint        BIT           NOT NULL DEFAULT 1,
            allow_laybye         BIT           NOT NULL DEFAULT 1,
            allow_quote          BIT           NOT NULL DEFAULT 1,
            allow_cancel_kot     BIT           NOT NULL DEFAULT 0,
            allow_pay_kot        BIT           NOT NULL DEFAULT 1,
            company              NVARCHAR(140) NULL DEFAULT '',
            max_discount_percent INT           NULL DEFAULT 0,
            api_key              NVARCHAR(255) NULL DEFAULT '',
            api_secret           NVARCHAR(255) NULL DEFAULT '',
            cloud_user_id        INT           NULL
        )
    """)
    print("[migrate] OK users")
    _add_column_if_missing("users", "allow_laybye", "BIT NOT NULL DEFAULT 1")
    _add_column_if_missing("users", "allow_quote", "BIT NOT NULL DEFAULT 1")
    _add_column_if_missing("users", "allow_cancel_kot", "BIT NOT NULL DEFAULT 0")
    _add_column_if_missing("users", "allow_pay_kot", "BIT NOT NULL DEFAULT 1")
    _add_column_if_missing("users", "api_key", "NVARCHAR(255) NULL DEFAULT ''")
    _add_column_if_missing("users", "api_secret", "NVARCHAR(255) NULL DEFAULT ''")
    _add_column_if_missing("users", "cloud_user_id", "INT NULL")

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
    """)
    print("[migrate] OK  companies")
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM companies)
            INSERT INTO companies (name, abbreviation, default_currency, country)
            VALUES ('Default Company', 'DEF', 'USD', 'Zimbabwe')
    """)
    conn.commit()

    # ── company_defaults ──────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='company_defaults')
        CREATE TABLE company_defaults (
            id                      INT           IDENTITY(1,1) PRIMARY KEY,
            company_name            NVARCHAR(200) NOT NULL DEFAULT '',
            address_1               NVARCHAR(200) NOT NULL DEFAULT '',
            address_2               NVARCHAR(200) NOT NULL DEFAULT '',
            email                   NVARCHAR(200) NOT NULL DEFAULT '',
            phone                   NVARCHAR(100) NOT NULL DEFAULT '',
            vat_number              NVARCHAR(100) NOT NULL DEFAULT '',
            tin_number              NVARCHAR(100) NOT NULL DEFAULT '',
            footer_text             NVARCHAR(500) NOT NULL DEFAULT '',
            zimra_serial_no         NVARCHAR(100) NOT NULL DEFAULT '',
            zimra_device_id         NVARCHAR(100) NOT NULL DEFAULT '',
            zimra_api_key           NVARCHAR(500) NOT NULL DEFAULT '',
            zimra_api_url           NVARCHAR(300) NOT NULL DEFAULT '',
            server_company          NVARCHAR(200) NOT NULL DEFAULT '',
            server_warehouse        NVARCHAR(200) NOT NULL DEFAULT '',
            server_cost_center      NVARCHAR(200) NOT NULL DEFAULT '',
            server_username         NVARCHAR(200) NOT NULL DEFAULT '',
            server_email            NVARCHAR(200) NOT NULL DEFAULT '',
            server_role             NVARCHAR(100) NOT NULL DEFAULT '',
            server_full_name        NVARCHAR(200) NOT NULL DEFAULT '',
            updated_at              DATETIME      NOT NULL DEFAULT GETDATE(),
            server_first_name       NVARCHAR(100) NOT NULL DEFAULT '',
            server_last_name        NVARCHAR(100) NOT NULL DEFAULT '',
            server_mobile           NVARCHAR(100) NOT NULL DEFAULT '',
            server_profile          NVARCHAR(100) NOT NULL DEFAULT '',
            server_vat_enabled      NVARCHAR(10)  NOT NULL DEFAULT '',
            api_key                 NVARCHAR(200) NOT NULL DEFAULT '',
            api_secret              NVARCHAR(200) NOT NULL DEFAULT '',
            invoice_prefix          NVARCHAR(6)   NOT NULL DEFAULT '',
            invoice_start_number    INT           NOT NULL DEFAULT 0,
            server_company_currency NVARCHAR(10)  NOT NULL DEFAULT 'USD',
            server_api_host         NVARCHAR(255) NOT NULL DEFAULT '',
            server_pos_account      NVARCHAR(255) NOT NULL DEFAULT '',
            server_taxes_and_charges NVARCHAR(255) NOT NULL DEFAULT '',
            server_walk_in_customer NVARCHAR(255) NOT NULL DEFAULT 'default',
            pharmacy_mode           NVARCHAR(10)  NOT NULL DEFAULT '0',
            server_database         NVARCHAR(100) NOT NULL DEFAULT ''
        )
    """)
    print("[migrate] OK  company_defaults")
    _add_column_if_missing("company_defaults", "odoo_token", "NVARCHAR(MAX) NOT NULL DEFAULT ''")
    _add_column_if_missing("company_defaults", "system_mode", "NVARCHAR(20) NOT NULL DEFAULT 'frappe'")
    _add_column_if_missing("company_defaults", "pharmacy_mode", "NVARCHAR(10) NOT NULL DEFAULT '0'")
    _add_column_if_missing("company_defaults", "allow_cashier_pharmacy_sales", "NVARCHAR(10) NOT NULL DEFAULT '0'")
    _add_column_if_missing("company_defaults", "butchery_mode", "NVARCHAR(10) NOT NULL DEFAULT '0'")
    _add_column_if_missing("company_defaults", "server_database", "NVARCHAR(100) NOT NULL DEFAULT ''")
    _add_column_if_missing("company_defaults", "server_terminal_id", "NVARCHAR(100) NOT NULL DEFAULT ''")
    _add_column_if_missing("company_defaults", "server_shop_id", "NVARCHAR(100) NOT NULL DEFAULT ''")

    try:
        cur.execute("UPDATE company_defaults SET server_company_currency = 'USD' WHERE server_company_currency IS NULL OR server_company_currency = '' OR server_company_currency = 'ZAR'")
        conn.commit()
    except Exception:
        pass

    # ── cost_centers ──────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='cost_centers')
        CREATE TABLE cost_centers (
            id         INT           IDENTITY(1,1) PRIMARY KEY,
            name       NVARCHAR(120) NOT NULL,
            company_id INT           NOT NULL REFERENCES companies(id)
        )
    """)
    print("[migrate] OK  cost_centers")

    # ── warehouses ────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='warehouses')
        CREATE TABLE warehouses (
            id         INT           IDENTITY(1,1) PRIMARY KEY,
            name       NVARCHAR(120) NOT NULL,
            company_id INT           NOT NULL REFERENCES companies(id)
        )
    """)
    print("[migrate] OK  warehouses")

    # ── customer_groups ───────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='customer_groups')
        CREATE TABLE customer_groups (
            id              INT           IDENTITY(1,1) PRIMARY KEY,
            name            NVARCHAR(120) NOT NULL UNIQUE,
            parent_group_id INT           NULL REFERENCES customer_groups(id)
        )
    """)
    print("[migrate] OK  customer_groups")

    # ── price_lists ───────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='price_lists')
        CREATE TABLE price_lists (
            id      INT           IDENTITY(1,1) PRIMARY KEY,
            name    NVARCHAR(120) NOT NULL UNIQUE,
            selling BIT           NULL DEFAULT 1
        )
    """)
    print("[migrate] OK  price_lists")
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM price_lists)
            INSERT INTO price_lists (name, selling) VALUES ('Standard Selling', 1)
    """)
    conn.commit()

    # ── customers ─────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='customers')
        CREATE TABLE customers (
            id                       INT           IDENTITY(1,1) PRIMARY KEY,
            customer_name            NVARCHAR(120) NOT NULL,
            customer_group_id        INT           NULL REFERENCES customer_groups(id),
            customer_type            NVARCHAR(20)  NULL,
            custom_trade_name        NVARCHAR(120) NULL,
            custom_telephone_number  NVARCHAR(120) NULL,
            custom_email_address     NVARCHAR(120) NULL,
            custom_city              NVARCHAR(120) NULL,
            custom_house_no          NVARCHAR(120) NULL,
            custom_warehouse_id      INT           NULL REFERENCES warehouses(id),
            custom_cost_center_id    INT           NULL REFERENCES cost_centers(id),
            default_price_list_id    INT           NULL REFERENCES price_lists(id),
            custom_customer_tin      NVARCHAR(100) NULL,
            custom_customer_vat      NVARCHAR(100) NULL,
            balance                  DECIMAL(18,2) NULL DEFAULT 0,
            outstanding_amount       DECIMAL(18,2) NULL DEFAULT 0,
            loyalty_points           INT           NULL DEFAULT 0,
            frappe_synced            BIT           NOT NULL DEFAULT 0,
            laybye_balance           DECIMAL(18,2) NULL DEFAULT 0
        )
    """)
    print("[migrate] OK  customers")
    conn.commit()
    _add_column_if_missing("customers", "frappe_synced", "BIT NOT NULL DEFAULT 0")
    _add_column_if_missing("customers", "laybye_balance", "DECIMAL(18,2) NULL DEFAULT 0")
    _add_column_if_missing("customers", "custom_customer_tin", "NVARCHAR(100) NULL")
    _add_column_if_missing("customers", "custom_customer_vat", "NVARCHAR(100) NULL")

    # ── products ──────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='products')
        CREATE TABLE products (
            id                 INT           IDENTITY(1,1) PRIMARY KEY,
            part_no            NVARCHAR(50)  NOT NULL DEFAULT '',
            name               NVARCHAR(120) NOT NULL,
            price              DECIMAL(12,2) NOT NULL DEFAULT 0,
            stock DECIMAL(24,6) NOT NULL DEFAULT 0,
            category           NVARCHAR(80)  NOT NULL DEFAULT 'General',
            active             BIT           NULL DEFAULT 1,
            image_path         NVARCHAR(500) NULL,
            order_1            BIT           NOT NULL DEFAULT 0,
            order_2            BIT           NOT NULL DEFAULT 0,
            order_3            BIT           NOT NULL DEFAULT 0,
            order_4            BIT           NOT NULL DEFAULT 0,
            order_5            BIT           NOT NULL DEFAULT 0,
            order_6            BIT           NOT NULL DEFAULT 0,
            uom                NVARCHAR(20)  NULL,
            conversion_factor  DECIMAL(12,4) NULL,
            cost_price         DECIMAL(12,2) NOT NULL DEFAULT 0,
            track_stock        BIT           NOT NULL DEFAULT 1,
            reorder_level      DECIMAL(12,4) NULL DEFAULT 0
        )
    """)
    print("[migrate] OK  products")
    _add_column_if_missing("products", "cost_price", "DECIMAL(12,2) NOT NULL DEFAULT 0")
    _add_column_if_missing("products", "track_stock", "BIT NOT NULL DEFAULT 1")
    _add_column_if_missing("products", "is_product_bundle", "BIT NOT NULL DEFAULT 0")
    _add_column_if_missing("products", "description", "NVARCHAR(MAX) NULL")
    _add_column_if_missing("products", "reorder_level", "DECIMAL(12,4) NULL DEFAULT 0")

    try:
        cur.execute("ALTER TABLE products ALTER COLUMN stock DECIMAL(24,6) NOT NULL")
        conn.commit()
    except Exception as e:
        print(f"[migrate]   ! Could not alter products.stock to DECIMAL: {e}")

    # ── product_uom_prices ────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='product_uom_prices')
        CREATE TABLE product_uom_prices (
            id      INT           IDENTITY(1,1) PRIMARY KEY,
            part_no NVARCHAR(50)  NOT NULL,
            uom     NVARCHAR(40)  NOT NULL,
            price   DECIMAL(12,2) NOT NULL DEFAULT 0,
            CONSTRAINT UQ_product_uom UNIQUE (part_no, uom)
        )
    """)
    print("[migrate] OK  product_uom_prices")

    # ── product_barcodes ──────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='product_barcodes')
        CREATE TABLE product_barcodes (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            part_no      NVARCHAR(50)  NOT NULL,
            barcode      NVARCHAR(100) NOT NULL,
            uom          NVARCHAR(40),
            barcode_type NVARCHAR(50),
            CONSTRAINT UQ_product_barcode UNIQUE (part_no, barcode)
        )
    """)
    print("[migrate] OK  product_barcodes")

    # ── item_groups ───────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='item_groups')
        CREATE TABLE item_groups (
            id                  INT           IDENTITY(1,1) PRIMARY KEY,
            name                NVARCHAR(100) NOT NULL UNIQUE,
            item_group_name     NVARCHAR(100) NOT NULL DEFAULT '',
            parent_item_group   NVARCHAR(100) NOT NULL DEFAULT '',
            synced_from_api     BIT           NOT NULL DEFAULT 0,
            created_at          DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
            updated_at          DATETIME2     NOT NULL DEFAULT SYSDATETIME()
        )
    """)
    print("[migrate] OK  item_groups")

    # ── sales ─────────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='sales')
        CREATE TABLE sales (
            id               INT           IDENTITY(1,1) PRIMARY KEY,
            invoice_number   INT           NOT NULL DEFAULT 0,
            invoice_no       NVARCHAR(40)  NOT NULL DEFAULT '',
            invoice_date     DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
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
            total_items      DECIMAL(12,4) NOT NULL DEFAULT 0,
            change_amount    DECIMAL(12,2) NOT NULL DEFAULT 0,
            company_name     NVARCHAR(120) NOT NULL DEFAULT '',
            frappe_ref       NVARCHAR(80)  NULL,
            created_at       DATETIME2     NULL DEFAULT SYSDATETIME(),
            payment_entry_ref NVARCHAR(80) NULL,
            payment_synced   BIT           NOT NULL DEFAULT 0,
            is_on_account    BIT           NOT NULL DEFAULT 0,
            shift_id         INT           NULL,
            waiter_name      NVARCHAR(120) NULL
        )
    """)
    print("[migrate] OK  sales")
    _add_column_if_missing("sales", "odoo_invoice_id", "INT NULL")
    # ── per-warehouse stock ───────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='product_warehouse_stock')
        CREATE TABLE product_warehouse_stock (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            product_id   INT           NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            warehouse_id INT           NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
            stock DECIMAL(24,6) NOT NULL DEFAULT 0,
            CONSTRAINT UQ_prod_wh UNIQUE (product_id, warehouse_id)
        )
    """)
    print("[migrate] OK  product_warehouse_stock")

    # Initial seeding: if per-warehouse stock is empty, migrate from products
    cur.execute("SELECT COUNT(*) FROM product_warehouse_stock")
    if cur.fetchone()[0] == 0:
        cur.execute("SELECT id FROM warehouses WHERE name = 'Main'")
        wh = cur.fetchone()
        if not wh:
            cur.execute("SELECT TOP 1 id FROM warehouses")
            wh = cur.fetchone()
        
        if wh:
            wh_id = wh[0]
            print(f"[migrate] Migrating stock to warehouse ID {wh_id}...")
            cur.execute("""
                INSERT INTO product_warehouse_stock (product_id, warehouse_id, stock)
                SELECT id, ?, stock FROM products WHERE stock <> 0
            """, (wh_id,))
            conn.commit()

    # ── sales additions ───────────────────────────────────────────────────────
    _add_column_if_missing("sales", "is_on_account", "BIT NOT NULL DEFAULT 0")
    _add_column_if_missing("sales", "shift_id", "INT NULL")
    _add_column_if_missing("sales", "waiter_name", "NVARCHAR(120) NULL")
    _add_column_if_missing("sales", "warehouse_id", "INT NULL REFERENCES warehouses(id)")
    _add_column_if_missing("sales", "cost_center_id", "INT NULL REFERENCES cost_centers(id)")
    _add_column_if_missing("sales", "sync_error", "NVARCHAR(MAX) NULL")
    _add_column_if_missing("sales", "cashier_cloud_user_id", "INT NULL")

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
            remarks      NVARCHAR(MAX) NOT NULL DEFAULT '',
            order_1      BIT           NOT NULL DEFAULT 0,
            order_2      BIT           NOT NULL DEFAULT 0,
            order_3      BIT           NOT NULL DEFAULT 0,
            order_4      BIT           NOT NULL DEFAULT 0,
            order_5      BIT           NOT NULL DEFAULT 0,
            order_6      BIT           NOT NULL DEFAULT 0,
            cost_price   DECIMAL(12,2) NOT NULL DEFAULT 0
        )
    """)
    print("[migrate] OK  sale_items")

    # ── shifts ────────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='shifts')
        CREATE TABLE shifts (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            shift_number INT           NOT NULL DEFAULT 1,
            station      INT           NOT NULL DEFAULT 1,
            cashier_id   INT           NULL,
            date         DATE          NOT NULL,
            start_time   DATETIME2     NOT NULL,
            end_time     DATETIME2     NULL,
            door_counter INT           NOT NULL DEFAULT 0,
            customers    INT           NOT NULL DEFAULT 0,
            notes        NVARCHAR(MAX) NULL,
            created_at   DATETIME2     NULL DEFAULT SYSDATETIME()
        )
    """)
    print("[migrate] OK  shifts")

    # ── shift_rows ────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='shift_rows')
        CREATE TABLE shift_rows (
            id          INT           IDENTITY(1,1) PRIMARY KEY,
            shift_id    INT           NOT NULL REFERENCES shifts(id) ON DELETE CASCADE,
            method      NVARCHAR(50)  NOT NULL,
            currency    NVARCHAR(10)  NOT NULL DEFAULT 'USD',
            start_float DECIMAL(12,2) NOT NULL DEFAULT 0,
            income      DECIMAL(12,2) NOT NULL DEFAULT 0,
            counted     DECIMAL(12,2) NOT NULL DEFAULT 0
        )
    """)
    print("[migrate] OK  shift_rows")
    _add_column_if_missing("shift_rows", "currency", "NVARCHAR(10) NOT NULL DEFAULT 'USD'")

    # ── shift_reports ─────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='shift_reports')
        CREATE TABLE shift_reports (
            id             INT           IDENTITY(1,1) PRIMARY KEY,
            cashier_id     INT           NULL,
            cashier_name   NVARCHAR(100) NULL,
            shift_number   INT           NULL,
            total_expected DECIMAL(18,2) NULL,
            total_actual   DECIMAL(18,2) NULL,
            total_variance DECIMAL(18,2) NULL,
            report_date    DATE          NULL,
            created_at     DATETIME2     NULL DEFAULT SYSDATETIME()
        )
    """)
    print("[migrate] OK  shift_reports")

    # ── shift_report_details ──────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='shift_report_details')
        CREATE TABLE shift_report_details (
            id               INT           IDENTITY(1,1) PRIMARY KEY,
            report_id        INT           NULL,
            payment_method   NVARCHAR(50)  NULL,
            amount_expected  DECIMAL(18,2) NULL,
            amount_available DECIMAL(18,2) NULL,
            variance         DECIMAL(18,2) NULL,
            created_at       DATETIME2     NULL DEFAULT SYSDATETIME()
        )
    """)
    print("[migrate] OK  shift_report_details")

    # ── cashier_reconciliations ───────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='cashier_reconciliations')
        CREATE TABLE cashier_reconciliations (
            id                   INT           IDENTITY(1,1) PRIMARY KEY,
            shift_id             INT           NOT NULL REFERENCES shifts(id) ON DELETE CASCADE,
            cashier_id           INT           NOT NULL,
            cashier_name         NVARCHAR(100) NOT NULL,
            counted_json         NVARCHAR(MAX) NOT NULL,
            is_finalized         BIT           NOT NULL DEFAULT 0,
            finalized_at         DATETIME2     NULL,
            is_modified          BIT           NOT NULL DEFAULT 0,
            created_at           DATETIME2     NOT NULL DEFAULT SYSDATETIME()
        )
    """)
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'cashier_reconciliations' AND COLUMN_NAME = 'is_modified')
        ALTER TABLE cashier_reconciliations ADD is_modified BIT NOT NULL DEFAULT 0;
    """)
    print("[migrate] OK  cashier_reconciliations")

    # ── credit_notes ──────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='credit_notes')
        CREATE TABLE credit_notes (
            id                 INT           IDENTITY(1,1) PRIMARY KEY,
            cn_number          NVARCHAR(40)  NOT NULL DEFAULT '',
            original_sale_id   INT           NOT NULL,
            original_invoice_no NVARCHAR(40) NOT NULL DEFAULT '',
            frappe_ref         NVARCHAR(80)  NULL,
            frappe_cn_ref      NVARCHAR(80)  NULL,
            total              DECIMAL(12,2) NOT NULL DEFAULT 0,
            currency           NVARCHAR(10)  NOT NULL DEFAULT 'USD',
            cashier_name       NVARCHAR(120) NOT NULL DEFAULT '',
            customer_name      NVARCHAR(120) NOT NULL DEFAULT '',
            cn_status          NVARCHAR(20)  NOT NULL DEFAULT 'pending_sync',
            created_at         DATETIME2     NOT NULL DEFAULT SYSDATETIME()
        )
    """)
    print("[migrate] OK  credit_notes")
    _add_column_if_missing("credit_notes", "sync_error", "NVARCHAR(MAX) NULL")

    # ── credit_note_items ─────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='credit_note_items')
        CREATE TABLE credit_note_items (
            id             INT           IDENTITY(1,1) PRIMARY KEY,
            credit_note_id INT           NOT NULL REFERENCES credit_notes(id) ON DELETE CASCADE,
            part_no        NVARCHAR(50)  NOT NULL DEFAULT '',
            product_name   NVARCHAR(120) NOT NULL DEFAULT '',
            qty            DECIMAL(12,4) NOT NULL DEFAULT 0,
            price          DECIMAL(12,2) NOT NULL DEFAULT 0,
            total          DECIMAL(12,2) NOT NULL DEFAULT 0,
            reason         NVARCHAR(255) NOT NULL DEFAULT 'Customer Return'
        )
    """)
    print("[migrate] OK  credit_note_items")

    # ── gl_accounts ───────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='gl_accounts')
        CREATE TABLE gl_accounts (
            id               INT           IDENTITY(1,1) PRIMARY KEY,
            name             NVARCHAR(140) NOT NULL UNIQUE,
            account_name     NVARCHAR(140) NOT NULL DEFAULT '',
            account_number   NVARCHAR(80)  NULL,
            company          NVARCHAR(120) NOT NULL DEFAULT '',
            parent_account   NVARCHAR(140) NOT NULL DEFAULT '',
            account_type     NVARCHAR(80)  NOT NULL DEFAULT '',
            account_currency NVARCHAR(10)  NOT NULL DEFAULT 'USD',
            updated_at       DATETIME2     NOT NULL DEFAULT SYSDATETIME()
        )
    """)
    print("[migrate] OK  gl_accounts")

    # ── payment_entries ───────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='payment_entries')
        CREATE TABLE payment_entries (
            id                      INT           IDENTITY(1,1) PRIMARY KEY,
            sale_id                 INT           NULL,
            sale_invoice_no         NVARCHAR(80)  NULL,
            frappe_invoice_ref      NVARCHAR(80)  NULL,
            party                   NVARCHAR(120) NULL,
            party_name              NVARCHAR(120) NULL,
            paid_amount             DECIMAL(12,2) NOT NULL DEFAULT 0,
            received_amount         DECIMAL(12,2) NOT NULL DEFAULT 0,
            source_exchange_rate    DECIMAL(12,6) NOT NULL DEFAULT 1,
            paid_to_account_currency NVARCHAR(10) NULL,
            currency                NVARCHAR(10)  NULL,
            paid_to                 NVARCHAR(255) NULL,
            mode_of_payment         NVARCHAR(80)  NULL,
            reference_no            NVARCHAR(80)  NULL,
            reference_date          DATE          NULL,
            remarks                 NVARCHAR(255) NULL,
            payment_type            NVARCHAR(20)  NOT NULL DEFAULT 'Receive',
            synced                  BIT           NOT NULL DEFAULT 0,
            frappe_payment_ref      NVARCHAR(80)  NULL,
            created_at              DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
            frappe_so_ref           NVARCHAR(255) NULL,
            sync_attempts           INT           NOT NULL DEFAULT 0,
            sync_error              NVARCHAR(MAX) NULL,
            last_error              NVARCHAR(MAX) NULL,
            shift_id                INT           NULL
        )
    """)
    print("[migrate] OK  payment_entries")
    _add_column_if_missing("payment_entries", "sync_attempts", "INT NOT NULL DEFAULT 0")
    _add_column_if_missing("payment_entries", "last_error", "NVARCHAR(MAX) NULL")
    _add_column_if_missing("payment_entries", "sync_error", "NVARCHAR(MAX) NULL")
    _add_column_if_missing("payment_entries", "frappe_so_ref", "NVARCHAR(255) NULL")
    _add_column_if_missing("payment_entries", "shift_id", "INT NULL")

    # ── sales_order ───────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='sales_order')
        CREATE TABLE sales_order (
            id              INT           IDENTITY(1,1) PRIMARY KEY,
            order_no        NVARCHAR(100) NULL,
            customer_id     INT           NULL,
            customer_name   NVARCHAR(255) NULL,
            company         NVARCHAR(255) NULL,
            order_date      NVARCHAR(50)  NULL,
            delivery_date   NVARCHAR(50)  NOT NULL DEFAULT '',
            order_type      NVARCHAR(50)  NOT NULL DEFAULT 'Sales',
            total           FLOAT         NOT NULL DEFAULT 0,
            deposit_amount  FLOAT         NOT NULL DEFAULT 0,
            deposit_method  NVARCHAR(100) NOT NULL DEFAULT '',
            balance_due     FLOAT         NOT NULL DEFAULT 0,
            status          NVARCHAR(50)  NOT NULL DEFAULT 'Draft',
            synced          INT           NOT NULL DEFAULT 0,
            frappe_ref      NVARCHAR(255) NOT NULL DEFAULT '',
            created_at      NVARCHAR(50)  NULL,
            waiter_name     NVARCHAR(120) NULL
        )
    """)
    print("[migrate] OK  sales_order")
    _add_column_if_missing("sales_order", "waiter_name", "NVARCHAR(120) NULL")
    _add_column_if_missing("sales_order", "sync_error", "NVARCHAR(MAX) NULL")

    # ── sales_order_item ──────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='sales_order_item')
        CREATE TABLE sales_order_item (
            id              INT           IDENTITY(1,1) PRIMARY KEY,
            sales_order_id  INT           NOT NULL REFERENCES sales_order(id),
            item_code       NVARCHAR(100) NULL,
            item_name       NVARCHAR(255) NULL,
            qty             FLOAT         NOT NULL DEFAULT 1,
            rate            FLOAT         NOT NULL DEFAULT 0,
            amount          FLOAT         NOT NULL DEFAULT 0,
            warehouse       NVARCHAR(255) NOT NULL DEFAULT ''
        )
    """)
    print("[migrate] OK  sales_order_item")

    # ── laybye_payment_entries ────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='laybye_payment_entries')
        CREATE TABLE laybye_payment_entries (
            id                  INT           IDENTITY(1,1) PRIMARY KEY,
            sales_order_id      INT           NOT NULL,
            order_no            NVARCHAR(100) NOT NULL DEFAULT '',
            customer_id         NVARCHAR(255) NOT NULL DEFAULT '',
            customer_name       NVARCHAR(255) NOT NULL DEFAULT '',
            deposit_amount      FLOAT         NOT NULL DEFAULT 0,
            deposit_method      NVARCHAR(100) NOT NULL DEFAULT '',
            account_paid_to     NVARCHAR(255) NOT NULL DEFAULT '',
            account_currency    NVARCHAR(20)  NOT NULL DEFAULT 'USD',
            frappe_so_ref       NVARCHAR(255) NOT NULL DEFAULT '',
            frappe_pe_ref       NVARCHAR(255) NOT NULL DEFAULT '',
            status              NVARCHAR(50)  NOT NULL DEFAULT 'pending',
            sync_attempts       INT           NOT NULL DEFAULT 0,
            created_at          NVARCHAR(50)  NOT NULL DEFAULT '',
            last_attempt_at     NVARCHAR(50)  NOT NULL DEFAULT '',
            error_message       NVARCHAR(MAX) NOT NULL DEFAULT ''
        )
    """)
    print("[migrate] OK  laybye_payment_entries")
    _add_column_if_missing("laybye_payment_entries", "sync_error", "NVARCHAR(MAX) NULL")


    # ── customer_payments ─────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='customer_payments')
        CREATE TABLE customer_payments (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            customer_id  INT           NOT NULL,
            amount       DECIMAL(12,2) NOT NULL DEFAULT 0,
            method       NVARCHAR(30)  NOT NULL DEFAULT '',
            reference    NVARCHAR(100) NULL,
            cashier_id   INT           NULL,
            created_at   DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
            currency     NVARCHAR(10)  NULL DEFAULT 'USD',
            account_name NVARCHAR(100) NULL,
            payment_date DATE          NULL
        )
    """)
    print("[migrate] OK  customer_payments")
    _add_column_if_missing("customer_payments", "synced", "INT NOT NULL DEFAULT 0")
    _add_column_if_missing("customer_payments", "sync_attempts", "INT NOT NULL DEFAULT 0")
    _add_column_if_missing("customer_payments", "last_sync_attempt", "DATETIME2 NULL")
    _add_column_if_missing("customer_payments", "sync_error", "NVARCHAR(MAX) NULL")
    _add_column_if_missing("customer_payments", "payment_type", "NVARCHAR(20) NOT NULL DEFAULT 'outstanding'")
    _add_column_if_missing("customer_payments", "splits_json", "NVARCHAR(MAX) NULL")
    _add_column_if_missing("customer_payments", "frappe_ref", "NVARCHAR(255) NOT NULL DEFAULT ''")
    _add_column_if_missing("customer_payments", "syncing", "INT NOT NULL DEFAULT 0")
    _add_column_if_missing("customer_payments", "amount_usd", "DECIMAL(18,2) NOT NULL DEFAULT 0")
    _add_column_if_missing("customer_payments", "exchange_rate", "DECIMAL(18,6) NOT NULL DEFAULT 1.0")

    # ── exchange_rates ────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='exchange_rates')
        CREATE TABLE exchange_rates (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            from_currency NVARCHAR(10) NOT NULL,
            to_currency   NVARCHAR(10) NOT NULL,
            rate         DECIMAL(18,6) NOT NULL DEFAULT 1,
            rate_date    NVARCHAR(20) NOT NULL,
            updated_at   DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
            CONSTRAINT UQ_exchange_rates UNIQUE (from_currency, to_currency, rate_date)
        )
    """)
    print("[migrate] OK  exchange_rates")

    # ── pos_settings ──────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='pos_settings')
        CREATE TABLE pos_settings (
            setting_key   NVARCHAR(80)  NOT NULL PRIMARY KEY,
            setting_value NVARCHAR(255) NOT NULL DEFAULT '0'
        )
    """)
    print("[migrate] OK  pos_settings")

    # ── payment_methods ───────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='payment_methods')
        CREATE TABLE payment_methods (
            id           INT           PRIMARY KEY,
            name         NVARCHAR(120) NOT NULL,
            code         NVARCHAR(50)  NOT NULL,
            payment_type NVARCHAR(50)  NOT NULL
        )
    """)
    print("[migrate] OK  payment_methods")
    # Seed new settings if missing
    for key, val in [
        ("enable_quotation_printing", "1"),
        ("auto_print_quotations", "0"),
        ("allow_others_to_view_orders", "1"),
        ("allow_others_to_close_orders", "1"),
    ]:
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM pos_settings WHERE setting_key = ?)
            INSERT INTO pos_settings (setting_key, setting_value) VALUES (?, ?)
        """, (key, key, val))

    # ── doctors ───────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='doctors')
        CREATE TABLE doctors (
            id            INT           IDENTITY(1,1) PRIMARY KEY,
            frappe_name   NVARCHAR(140) NULL UNIQUE,
            full_name     NVARCHAR(200) NOT NULL,
            practice_no   NVARCHAR(100) NULL,
            qualification NVARCHAR(200) NULL,
            school        NVARCHAR(200) NULL,
            phone         NVARCHAR(50)  NULL,
            synced        BIT           NOT NULL DEFAULT 0,
            sync_date     DATETIME      NULL
        )
    """)
    print("[migrate] OK  doctors")
    _add_column_if_missing("doctors", "doctor_certificate_filename", "NVARCHAR(500) NULL")
    _add_column_if_missing("doctors", "doctor_certificate", "NVARCHAR(MAX) NULL")

    # ── dosages ───────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='dosages')
        CREATE TABLE dosages (
            id          INT           IDENTITY(1,1) PRIMARY KEY,
            frappe_name NVARCHAR(140) NULL UNIQUE,
            code        NVARCHAR(50)  NOT NULL UNIQUE,
            description NVARCHAR(500) NULL,
            synced      BIT           NOT NULL DEFAULT 0,
            sync_date   DATETIME      NULL
        )
    """)
    print("[migrate] OK  dosages")

    # ── product_batches ───────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='product_batches')
        CREATE TABLE product_batches (
            id               INT           IDENTITY(1,1) PRIMARY KEY,
            product_id       INT           NOT NULL,
            batch_no         NVARCHAR(100) NOT NULL,
            manufacture_date DATE          NULL,
            expiry_date      DATE          NULL,
            qty              DECIMAL(18,4) NOT NULL DEFAULT 0,
            created_by       NVARCHAR(100) NULL,
            synced           BIT           NOT NULL DEFAULT 0
        )
    """)
    print("[migrate] OK  product_batches")
    _add_column_if_missing("product_batches", "manufacture_date", "DATE NULL")
    _add_column_if_missing("product_batches", "created_by", "NVARCHAR(100) NULL")

    # pharmacy ALTER TABLE additions ────────────────────────────────────────
    # products — pharmacy + cost_price columns
    _add_column_if_missing("products", "is_pharmacy_product", "BIT NOT NULL DEFAULT 0")
    _add_column_if_missing("products", "is_butchery_product", "BIT NOT NULL DEFAULT 0")
    _add_column_if_missing("products", "cost_price", "DECIMAL(12,2) NOT NULL DEFAULT 0")
    print("[migrate] OK  products.is_pharmacy_product")
    print("[migrate] OK  products.cost_price")

    # customers.doctor_id / doctor_frappe_name
    _add_column_if_missing("customers", "doctor_id",          "INT NULL")
    _add_column_if_missing("customers", "doctor_frappe_name", "NVARCHAR(140) NULL")
    print("[migrate] OK  customers.doctor_id / doctor_frappe_name")

    # quotation_items pharmacy columns + cost_price
    # Ensure the quotations + quotation_items tables exist before altering.
    # Importing models.quotation runs its create_quotations_table() side-effect.
    try:
        from models.quotation import create_quotations_table
        create_quotations_table()
    except Exception as _e:
        print(f"[migrate]   ! quotation_items table setup warning: {_e}")
    _add_column_if_missing("quotation_items", "is_pharmacy", "BIT NOT NULL DEFAULT 0")
    _add_column_if_missing("quotation_items", "dosage",      "NVARCHAR(500) NULL")
    _add_column_if_missing("quotation_items", "batch_no",    "NVARCHAR(100) NULL")
    _add_column_if_missing("quotation_items", "expiry_date", "DATE NULL")
    _add_column_if_missing("quotation_items", "cost_price",  "DECIMAL(12,2) NOT NULL DEFAULT 0")
    print("[migrate] OK  quotation_items pharmacy columns")
    print("[migrate] OK  quotation_items.cost_price")

    # sale_items pharmacy columns
    _add_column_if_missing("sale_items", "is_pharmacy", "BIT NOT NULL DEFAULT 0")
    _add_column_if_missing("sale_items", "dosage",      "NVARCHAR(500) NULL")
    _add_column_if_missing("sale_items", "batch_no",    "NVARCHAR(100) NULL")
    _add_column_if_missing("sale_items", "expiry_date", "DATE NULL")
    _add_column_if_missing("sale_items", "cost_price",  "DECIMAL(12,2) NOT NULL DEFAULT 0")
    print("[migrate] OK  sale_items pharmacy columns")
    print("[migrate] OK  sale_items.cost_price")

    # ── Pharmacy label data gaps (Phase 9) ────────────────────────────────────
    _add_column_if_missing("quotations", "cashier_name", "NVARCHAR(120) NULL")
    print("[migrate] OK  quotations.cashier_name")

    _add_column_if_missing("sale_items", "uom", "NVARCHAR(20) NULL")
    print("[migrate] OK  sale_items.uom")

    # ── De-duplicate products + add UNIQUE (part_no) ──────────────────────────
    try:
        cur.execute("UPDATE products SET part_no = UPPER(part_no) WHERE part_no <> UPPER(part_no)")
        cur.execute("""
            DELETE FROM products
            WHERE id NOT IN (
                SELECT MAX(id) FROM products GROUP BY part_no
            )
        """)
        removed = cur.rowcount if cur.rowcount is not None else 0
        conn.commit()
        if removed and removed > 0:
            print(f"[migrate] 🧹  Removed {removed} duplicate product row(s)")

        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM sys.indexes
                WHERE name = 'UQ_products_part_no' AND object_id = OBJECT_ID('products')
            )
            ALTER TABLE products ADD CONSTRAINT UQ_products_part_no UNIQUE (part_no)
        """)
        conn.commit()
        print("[migrate] OK  products.part_no UNIQUE constraint")
    except Exception as _e:
        print(f"[migrate]   ! product dedupe / UNIQUE failed: {_e}")

    # ── Seed default admin if users table is empty (All Modes) ───────
    try:
        cur.execute("SELECT id FROM users WHERE username = 'admin'")
        if not cur.fetchone():
            import hashlib
            hashed = hashlib.sha256("admin123".encode()).hexdigest()
            cur.execute(
                "INSERT INTO users (username, password, role, display_name, full_name, pin, active) VALUES (?, ?, ?, ?, ?, '7878', 1)",
                ("admin", hashed, "admin", "Administrator", "Administrator")
            )
            print("[migrate] OK  Default admin created (admin / admin123 / PIN: 7878)")
        else:
            cur.execute("UPDATE users SET pin = '7878' WHERE username = 'admin' AND (pin IS NULL OR pin = '')")
    except Exception as e:
        print(f"[migrate] admin seeding skipped: {e}")
    # ── purchase_orders ───────────────────────────────────────────────────────
    try:
        from models.purchase_order import migrate as _po_migrate
        _po_migrate()
    except Exception as e:
        print(f"[migrate]   ! purchase_order migration failed: {e}")

    # ── stock_entries ─────────────────────────────────────────────────────────
    try:
        from models.stock_entry import migrate as _se_migrate
        _se_migrate()
    except Exception as e:
        print(f"[migrate]   ! stock_entry migration failed: {e}")

    # ── suppliers ─────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[suppliers]') AND type in (N'U'))
        BEGIN
            CREATE TABLE [dbo].[suppliers](
                [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
                [name] [nvarchar](200) NOT NULL,
                [email] [nvarchar](200) NULL,
                [phone] [nvarchar](50) NULL,
                [address] [nvarchar](max) NULL,
                [balance] [decimal](18,4) DEFAULT 0.0,
                [created_at] [datetime] DEFAULT GETDATE()
            )
        END
        ELSE
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='suppliers' AND COLUMN_NAME='balance')
            ALTER TABLE suppliers ADD balance DECIMAL(18,4) DEFAULT 0.0;
        END
    """)
    print("[migrate] OK  suppliers")

    # ── expense_categories ────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[expense_categories]') AND type in (N'U'))
        BEGIN
            CREATE TABLE [dbo].[expense_categories](
                [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
                [name] [nvarchar](100) NOT NULL UNIQUE
            )
        END
    """)
    print("[migrate] OK  expense_categories")

    # ── expenses ──────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[expenses]') AND type in (N'U'))
        BEGIN
            CREATE TABLE [dbo].[expenses](
                [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
                [name] [nvarchar](200) NOT NULL,
                [expense_category_id] [int] NOT NULL REFERENCES expense_categories(id),
                [amount] [decimal](18,4) NOT NULL DEFAULT 0.0,
                [supplier_id] [int] NULL REFERENCES suppliers(id),
                [paid] [bit] NOT NULL DEFAULT 1,
                [expense_number] [nvarchar](50) NULL,
                [balance] [decimal](18,4) NULL,
                [created_at] [datetime] DEFAULT GETDATE()
            )
        END
        ELSE
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='expense_number')
            ALTER TABLE expenses ADD expense_number NVARCHAR(50) NULL;
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='balance')
            BEGIN
                ALTER TABLE expenses ADD balance DECIMAL(18,4) NULL;
                EXEC('UPDATE expenses SET balance = amount WHERE balance IS NULL');
            END
        END
    """)
    print("[migrate] OK  expenses")

    # ── supplier_payments ─────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='supplier_payments')
        CREATE TABLE supplier_payments (
            id               INT           IDENTITY(1,1) PRIMARY KEY,
            supplier_id      INT           NULL,
            supplier_name    NVARCHAR(200) NOT NULL DEFAULT '',
            amount           DECIMAL(12,2) NOT NULL DEFAULT 0,
            method           NVARCHAR(50)  NOT NULL DEFAULT '',
            reference        NVARCHAR(200) NULL,
            created_at       DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
            synced           BIT           NOT NULL DEFAULT 0
        )
    """)
    print("[migrate] OK  supplier_payments")

    # ── uoms ──────────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='uoms')
        CREATE TABLE uoms (
            id               INT           IDENTITY(1,1) PRIMARY KEY,
            name             NVARCHAR(100) NOT NULL UNIQUE,
            abbreviation     NVARCHAR(50)  NULL,
            synced           BIT           NOT NULL DEFAULT 0,
            sync_date        DATETIME      NULL
        )
    """)
    print("[migrate] OK  uoms")

    # Fix UNIQUE constraints on frappe_name for dosages & doctors to allow multiple NULLs in SQL Server
    for tname in ('dosages', 'doctors'):
        try:
            cur.execute("""
                SELECT kc.name
                FROM sys.key_constraints kc
                JOIN sys.index_columns ic ON kc.parent_object_id = ic.object_id AND kc.unique_index_id = ic.index_id
                JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                WHERE kc.parent_object_id = OBJECT_ID(?) AND c.name = 'frappe_name'
            """, (f"dbo.{tname}",))
            for row in cur.fetchall():
                cname = row[0]
                cur.execute(f"ALTER TABLE {tname} DROP CONSTRAINT {cname}")

            cur.execute(f"""
                IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_{tname}_frappe_name' AND object_id = OBJECT_ID('{tname}'))
                BEGIN
                    CREATE UNIQUE NONCLUSTERED INDEX UX_{tname}_frappe_name 
                    ON {tname}(frappe_name) 
                    WHERE frappe_name IS NOT NULL
                END
            """)
            conn.commit()
        except Exception as _ex:
            print(f"[migrate] Warning updating {tname} frappe_name index: {_ex}")

    conn.close()
    print()
    print("[migrate] OK  All tables ready. Run:  py main.py")


if __name__ == "__main__":
    migrate()
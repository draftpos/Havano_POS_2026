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
            company              NVARCHAR(140) NULL DEFAULT '',
            max_discount_percent INT           NULL DEFAULT 0
        )
    """)
    print("[migrate] OK users")
    _add_column_if_missing("users", "allow_laybye", "BIT NOT NULL DEFAULT 1")
    _add_column_if_missing("users", "allow_quote", "BIT NOT NULL DEFAULT 1")
    _add_column_if_missing("users", "allow_cancel_kot", "BIT NOT NULL DEFAULT 0")

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
            server_walk_in_customer NVARCHAR(255) NOT NULL DEFAULT 'default'
        )
    """)
    print("[migrate] OK  company_defaults")

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
            INSERT INTO price_lists (name, selling) VALUES ('Standard', 1)
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
            balance                  DECIMAL(18,2) NULL DEFAULT 0,
            outstanding_amount       DECIMAL(18,2) NULL DEFAULT 0,
            loyalty_points           INT           NULL DEFAULT 0,
            frappe_synced            BIT           NOT NULL DEFAULT 0,
            laybye_balance           DECIMAL(18,2) NULL DEFAULT 0
        )
    """)
    print("[migrate] OK  customers")
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM customers WHERE id=1)
            SET IDENTITY_INSERT customers ON;
            INSERT INTO customers (id, customer_name, customer_type, frappe_synced, balance, outstanding_amount, loyalty_points)
            VALUES (1, 'Walk-in', 'Individual', 0, 0, 0, 0);
            SET IDENTITY_INSERT customers OFF;
    """)
    conn.commit()
    _add_column_if_missing("customers", "frappe_synced", "BIT NOT NULL DEFAULT 0")
    _add_column_if_missing("customers", "laybye_balance", "DECIMAL(18,2) NULL DEFAULT 0")

    # ── products ──────────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='products')
        CREATE TABLE products (
            id                 INT           IDENTITY(1,1) PRIMARY KEY,
            part_no            NVARCHAR(50)  NOT NULL DEFAULT '',
            name               NVARCHAR(120) NOT NULL,
            price              DECIMAL(12,2) NOT NULL DEFAULT 0,
            stock              INT           NOT NULL DEFAULT 0,
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
            conversion_factor  DECIMAL(12,4) NULL
        )
    """)
    print("[migrate] OK  products")

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
            shift_id         INT           NULL
        )
    """)
    print("[migrate] OK  sales")
    _add_column_if_missing("sales", "is_on_account", "BIT NOT NULL DEFAULT 0")
    _add_column_if_missing("sales", "shift_id", "INT NULL")

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
            order_6      BIT           NOT NULL DEFAULT 0
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
            created_at      NVARCHAR(50)  NULL
        )
    """)
    print("[migrate] OK  sales_order")

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
            id          INT           IDENTITY(1,1) PRIMARY KEY,
            product_id  INT           NOT NULL,
            batch_no    NVARCHAR(100) NOT NULL,
            expiry_date DATE          NULL,
            qty         DECIMAL(18,4) NOT NULL DEFAULT 0,
            synced      BIT           NOT NULL DEFAULT 0
        )
    """)
    print("[migrate] OK  product_batches")

    # ── pharmacy ALTER TABLE additions ────────────────────────────────────────
    # products.is_pharmacy_product
    _add_column_if_missing("products", "is_pharmacy_product", "BIT NOT NULL DEFAULT 0")
    print("[migrate] OK  products.is_pharmacy_product")

    # customers.doctor_id / doctor_frappe_name
    _add_column_if_missing("customers", "doctor_id",          "INT NULL")
    _add_column_if_missing("customers", "doctor_frappe_name", "NVARCHAR(140) NULL")
    print("[migrate] OK  customers.doctor_id / doctor_frappe_name")

    # quotation_items pharmacy columns
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
    print("[migrate] OK  quotation_items pharmacy columns")

    # sale_items pharmacy columns
    _add_column_if_missing("sale_items", "is_pharmacy", "BIT NOT NULL DEFAULT 0")
    _add_column_if_missing("sale_items", "dosage",      "NVARCHAR(500) NULL")
    _add_column_if_missing("sale_items", "batch_no",    "NVARCHAR(100) NULL")
    _add_column_if_missing("sale_items", "expiry_date", "DATE NULL")
    print("[migrate] OK  sale_items pharmacy columns")

    # ── Pharmacy label data gaps (Phase 9) ────────────────────────────────────
    # quotations.cashier_name — the creator of the quote, used on label preview
    # as the pharmacist name. Legacy rows stay NULL and fall back to the
    # current logged-in user.
    _add_column_if_missing("quotations", "cashier_name", "NVARCHAR(120) NULL")
    print("[migrate] OK  quotations.cashier_name")

    # sale_items.uom — so sale labels can render "30 tablets" instead of just
    # "30". Populated from the cart at save time; legacy rows stay NULL and
    # render as empty string on the label.
    _add_column_if_missing("sale_items", "uom", "NVARCHAR(20) NULL")
    print("[migrate] OK  sale_items.uom")

    # ── De-duplicate products + add UNIQUE (part_no) ──────────────────────────
    # Two sync paths (login sync_service.sync_products AND background
    # SyncWorker → sync_products_smart) run concurrently after login, and
    # products.part_no had no UNIQUE constraint, so a race between them
    # inserted the same item twice. Clean up any existing duplicates, then
    # add the constraint so future races fail fast instead of silently
    # doubling the catalog.
    try:
        # Normalise casing first so UPPER collapses "Amoxlyn" + "AMOXLYN"
        cur.execute("UPDATE products SET part_no = UPPER(part_no) WHERE part_no <> UPPER(part_no)")
        # Keep the highest-id row per part_no, drop the rest.
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

        # Add the UNIQUE constraint if it isn't there yet.
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

    # ── Seed default admin if users table is empty ────────────────────────────
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        import hashlib
        hashed = hashlib.sha256("admin123".encode()).hexdigest()
        cur.execute(
            "INSERT INTO users (username, password, role, display_name, full_name) VALUES (?, ?, ?, ?, ?)",
            ("admin", hashed, "admin", "Administrator", "Administrator")
        )
        print("[migrate] OK  Default admin created  (admin / admin123)")

    conn.commit()
    conn.close()
    print()
    print("[migrate] 🎉  All tables ready. Run:  py main.py")


if __name__ == "__main__":
    migrate()
    

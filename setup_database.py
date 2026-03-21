# =============================================================================
# setup_database.py  —  Havano POS
#
# Derived from ALL model files. Safe to run on a fresh DB or an existing one.
# Every CREATE TABLE and ALTER TABLE is guarded with IF NOT EXISTS checks.
#
# Run after first install (or after a wipe):
#   python setup_database.py
#
# Seeds one default admin user if the users table is empty:
#   Username : admin
#   Password : admin123
# =============================================================================

import sys
import os
import hashlib


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def run():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    try:
        from database.db import get_connection
    except Exception as e:
        print(f"[ERROR] Cannot import database.db: {e}")
        print("Make sure you run this from the project root folder.")
        sys.exit(1)

    conn = get_connection()
    cur  = conn.cursor()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def table_exists(name: str) -> bool:
        cur.execute(
            "SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = ?", (name,))
        return cur.fetchone() is not None

    def col_exists(table: str, col: str) -> bool:
        cur.execute(
            "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_NAME = ? AND COLUMN_NAME = ?", (table, col))
        return cur.fetchone() is not None

    def add_col(table: str, col: str, definition: str):
        if not col_exists(table, col):
            cur.execute(f"ALTER TABLE [{table}] ADD [{col}] {definition}")
            print(f"    + {table}.{col}")

    def ok(name):   print(f"  [+] Created : {name}")
    def skip(name): print(f"  [ ] Exists  : {name}")

    print("\n======================================")
    print("  Havano POS - Database Setup")
    print("======================================\n")

    # ==================================================================
    # 1. companies
    # ==================================================================
    if not table_exists("companies"):
        cur.execute("""
            CREATE TABLE companies (
                id               INT           IDENTITY(1,1) PRIMARY KEY,
                name             NVARCHAR(120) NOT NULL UNIQUE,
                abbreviation     NVARCHAR(40)  NOT NULL DEFAULT '',
                default_currency NVARCHAR(10)  NOT NULL DEFAULT 'USD',
                country          NVARCHAR(80)  NOT NULL DEFAULT ''
            )
        """); ok("companies")
    else:
        skip("companies")

    # ==================================================================
    # 2. company_defaults
    # ==================================================================
    if not table_exists("company_defaults"):
        cur.execute("""
            CREATE TABLE company_defaults (
                id                       INT           IDENTITY(1,1) PRIMARY KEY,
                company_name             NVARCHAR(255) NOT NULL DEFAULT '',
                address_1                NVARCHAR(255) NOT NULL DEFAULT '',
                address_2                NVARCHAR(255) NOT NULL DEFAULT '',
                email                    NVARCHAR(100) NOT NULL DEFAULT '',
                phone                    NVARCHAR(50)  NOT NULL DEFAULT '',
                vat_number               NVARCHAR(50)  NOT NULL DEFAULT '',
                tin_number               NVARCHAR(50)  NOT NULL DEFAULT '',
                footer_text              NVARCHAR(MAX) NOT NULL DEFAULT '',
                zimra_serial_no          NVARCHAR(80)  NOT NULL DEFAULT '',
                zimra_device_id          NVARCHAR(80)  NOT NULL DEFAULT '',
                zimra_api_key            NVARCHAR(255) NOT NULL DEFAULT '',
                zimra_api_url            NVARCHAR(255) NOT NULL DEFAULT '',
                invoice_prefix           NVARCHAR(20)  NOT NULL DEFAULT '',
                invoice_start_number     NVARCHAR(20)  NOT NULL DEFAULT '0',
                server_company           NVARCHAR(255) NOT NULL DEFAULT '',
                server_warehouse         NVARCHAR(255) NOT NULL DEFAULT '',
                server_cost_center       NVARCHAR(255) NOT NULL DEFAULT '',
                server_username          NVARCHAR(255) NOT NULL DEFAULT '',
                server_email             NVARCHAR(255) NOT NULL DEFAULT '',
                server_role              NVARCHAR(80)  NOT NULL DEFAULT '',
                server_full_name         NVARCHAR(255) NOT NULL DEFAULT '',
                server_first_name        NVARCHAR(255) NOT NULL DEFAULT '',
                server_last_name         NVARCHAR(255) NOT NULL DEFAULT '',
                server_mobile            NVARCHAR(80)  NOT NULL DEFAULT '',
                server_profile           NVARCHAR(255) NOT NULL DEFAULT '',
                server_vat_enabled       NVARCHAR(20)  NOT NULL DEFAULT '',
                server_company_currency  NVARCHAR(10)  NOT NULL DEFAULT 'USD',
                server_api_host          NVARCHAR(255) NOT NULL DEFAULT '',
                server_pos_account       NVARCHAR(255) NOT NULL DEFAULT '',
                server_taxes_and_charges NVARCHAR(255) NOT NULL DEFAULT '',
                server_walk_in_customer  NVARCHAR(255) NOT NULL DEFAULT 'default',
                api_key                  NVARCHAR(255) NOT NULL DEFAULT '',
                api_secret               NVARCHAR(255) NOT NULL DEFAULT '',
                updated_at               DATETIME      NOT NULL DEFAULT GETDATE()
            )
        """)
        cur.execute("INSERT INTO company_defaults DEFAULT VALUES")
        ok("company_defaults")
    else:
        skip("company_defaults")
        for col, defn in [
            ("zimra_serial_no",          "NVARCHAR(80)  NOT NULL DEFAULT ''"),
            ("zimra_device_id",          "NVARCHAR(80)  NOT NULL DEFAULT ''"),
            ("zimra_api_key",            "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("zimra_api_url",            "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("invoice_prefix",           "NVARCHAR(20)  NOT NULL DEFAULT ''"),
            ("invoice_start_number",     "NVARCHAR(20)  NOT NULL DEFAULT '0'"),
            ("server_company",           "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("server_warehouse",         "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("server_cost_center",       "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("server_username",          "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("server_email",             "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("server_role",              "NVARCHAR(80)  NOT NULL DEFAULT ''"),
            ("server_full_name",         "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("server_first_name",        "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("server_last_name",         "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("server_mobile",            "NVARCHAR(80)  NOT NULL DEFAULT ''"),
            ("server_profile",           "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("server_vat_enabled",       "NVARCHAR(20)  NOT NULL DEFAULT ''"),
            ("server_company_currency",  "NVARCHAR(10)  NOT NULL DEFAULT 'USD'"),
            ("server_api_host",          "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("server_pos_account",       "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("server_taxes_and_charges", "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("server_walk_in_customer",  "NVARCHAR(255) NOT NULL DEFAULT 'default'"),
            ("api_key",                  "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("api_secret",               "NVARCHAR(255) NOT NULL DEFAULT ''"),
        ]:
            add_col("company_defaults", col, defn)
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM company_defaults)
                INSERT INTO company_defaults DEFAULT VALUES
        """)

    # ==================================================================
    # 3. customer_groups
    # ==================================================================
    if not table_exists("customer_groups"):
        cur.execute("""
            CREATE TABLE customer_groups (
                id              INT           IDENTITY(1,1) PRIMARY KEY,
                name            NVARCHAR(120) NOT NULL UNIQUE,
                parent_group_id INT           NULL
            )
        """); ok("customer_groups")
    else:
        skip("customer_groups")

    # ==================================================================
    # 4. price_lists
    # ==================================================================
    if not table_exists("price_lists"):
        cur.execute("""
            CREATE TABLE price_lists (
                id      INT           IDENTITY(1,1) PRIMARY KEY,
                name    NVARCHAR(120) NOT NULL UNIQUE,
                selling BIT           NOT NULL DEFAULT 1
            )
        """); ok("price_lists")
    else:
        skip("price_lists")

    # ==================================================================
    # 5. warehouses
    # ==================================================================
    if not table_exists("warehouses"):
        cur.execute("""
            CREATE TABLE warehouses (
                id         INT           IDENTITY(1,1) PRIMARY KEY,
                name       NVARCHAR(120) NOT NULL,
                company_id INT           NOT NULL
            )
        """); ok("warehouses")
    else:
        skip("warehouses")

    # ==================================================================
    # 6. cost_centers
    # ==================================================================
    if not table_exists("cost_centers"):
        cur.execute("""
            CREATE TABLE cost_centers (
                id         INT           IDENTITY(1,1) PRIMARY KEY,
                name       NVARCHAR(120) NOT NULL,
                company_id INT           NOT NULL
            )
        """); ok("cost_centers")
    else:
        skip("cost_centers")

    # ==================================================================
    # 7. customers
    # ==================================================================
    if not table_exists("customers"):
        cur.execute("""
            CREATE TABLE customers (
                id                      INT           IDENTITY(1,1) PRIMARY KEY,
                customer_name           NVARCHAR(120) NOT NULL,
                customer_type           NVARCHAR(50)  NULL,
                customer_group_id       INT           NULL,
                custom_warehouse_id     INT           NULL,
                custom_cost_center_id   INT           NULL,
                default_price_list_id   INT           NULL,
                custom_trade_name       NVARCHAR(120) NULL,
                custom_telephone_number NVARCHAR(50)  NULL,
                custom_email_address    NVARCHAR(120) NULL,
                custom_city             NVARCHAR(80)  NULL,
                custom_house_no         NVARCHAR(40)  NULL,
                balance                 DECIMAL(12,2) NOT NULL DEFAULT 0,
                outstanding_amount      DECIMAL(12,2) NOT NULL DEFAULT 0,
                loyalty_points          DECIMAL(12,2) NOT NULL DEFAULT 0
            )
        """); ok("customers")
    else:
        skip("customers")
        for col, defn in [
            ("customer_type",           "NVARCHAR(50)  NULL"),
            ("custom_trade_name",       "NVARCHAR(120) NULL"),
            ("custom_telephone_number", "NVARCHAR(50)  NULL"),
            ("custom_email_address",    "NVARCHAR(120) NULL"),
            ("custom_city",             "NVARCHAR(80)  NULL"),
            ("custom_house_no",         "NVARCHAR(40)  NULL"),
            ("balance",                 "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("outstanding_amount",      "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("loyalty_points",          "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ]:
            add_col("customers", col, defn)
        # Fix any NOT NULL string columns that Frappe may send as NULL
        for nullable_col in [
            "custom_trade_name", "custom_telephone_number",
            "custom_email_address", "custom_city", "custom_house_no",
        ]:
            cur.execute(f"""
                IF EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME  = 'customers'
                      AND COLUMN_NAME = '{nullable_col}'
                      AND IS_NULLABLE = 'NO'
                )
                ALTER TABLE customers ALTER COLUMN [{nullable_col}] NVARCHAR(120) NULL
            """)
        print("    ~ customers nullable string columns enforced (Frappe sends NULL)")

    # ==================================================================
    # 8. products
    # ==================================================================
    if not table_exists("products"):
        cur.execute("""
            CREATE TABLE products (
                id                INT           IDENTITY(1,1) PRIMARY KEY,
                part_no           NVARCHAR(50)  NOT NULL DEFAULT '',
                name              NVARCHAR(120) NOT NULL,
                price             DECIMAL(12,2) NOT NULL DEFAULT 0,
                stock             DECIMAL(12,4) NOT NULL DEFAULT 0,
                category          NVARCHAR(80)  NOT NULL DEFAULT '',
                image_path        NVARCHAR(500) NULL,
                active            BIT           NULL DEFAULT NULL,
                uom               NVARCHAR(40)  NOT NULL DEFAULT 'Unit',
                conversion_factor DECIMAL(12,4) NOT NULL DEFAULT 1.0,
                order_1           BIT           NOT NULL DEFAULT 0,
                order_2           BIT           NOT NULL DEFAULT 0,
                order_3           BIT           NOT NULL DEFAULT 0,
                order_4           BIT           NOT NULL DEFAULT 0,
                order_5           BIT           NOT NULL DEFAULT 0,
                order_6           BIT           NOT NULL DEFAULT 0
            )
        """); ok("products")
    else:
        skip("products")
        for col, defn in [
            ("part_no",           "NVARCHAR(50)  NOT NULL DEFAULT ''"),
            ("category",          "NVARCHAR(80)  NOT NULL DEFAULT ''"),
            ("image_path",        "NVARCHAR(500) NULL"),
            ("active",            "BIT           NULL"),
            ("uom",               "NVARCHAR(40)  NOT NULL DEFAULT 'Unit'"),
            ("conversion_factor", "DECIMAL(12,4) NOT NULL DEFAULT 1.0"),
            ("order_1",           "BIT           NOT NULL DEFAULT 0"),
            ("order_2",           "BIT           NOT NULL DEFAULT 0"),
            ("order_3",           "BIT           NOT NULL DEFAULT 0"),
            ("order_4",           "BIT           NOT NULL DEFAULT 0"),
            ("order_5",           "BIT           NOT NULL DEFAULT 0"),
            ("order_6",           "BIT           NOT NULL DEFAULT 0"),
        ]:
            add_col("products", col, defn)
        # Fix active column if it was previously created as NOT NULL
        cur.execute("""
            IF EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME  = 'products'
                  AND COLUMN_NAME = 'active'
                  AND IS_NULLABLE = 'NO'
            )
            ALTER TABLE products ALTER COLUMN active BIT NULL
        """)
        print("    ~ products.active ensured nullable (Frappe sends NULL for some products)")

    # ==================================================================
    # 9. users
    # ==================================================================
    if not table_exists("users"):
        cur.execute("""
            CREATE TABLE users (
                id                 INT           IDENTITY(1,1) PRIMARY KEY,
                username           NVARCHAR(80)  NOT NULL UNIQUE,
                password           NVARCHAR(255) NOT NULL DEFAULT '',
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
                active             BIT           NOT NULL DEFAULT 1
            )
        """); ok("users")
    else:
        skip("users")
        for col, defn in [
            ("display_name",       "NVARCHAR(120) NULL"),
            ("email",              "NVARCHAR(120) NULL"),
            ("full_name",          "NVARCHAR(120) NULL"),
            ("first_name",         "NVARCHAR(80)  NULL"),
            ("last_name",          "NVARCHAR(80)  NULL"),
            ("pin",                "NVARCHAR(20)  NULL"),
            ("cost_center",        "NVARCHAR(140) NULL"),
            ("warehouse",          "NVARCHAR(140) NULL"),
            ("frappe_user",        "NVARCHAR(120) NULL"),
            ("synced_from_frappe", "BIT           NOT NULL DEFAULT 0"),
            ("active",             "BIT           NOT NULL DEFAULT 1"),
        ]:
            add_col("users", col, defn)

    # ==================================================================
    # 10. sales
    # ==================================================================
    if not table_exists("sales"):
        cur.execute("""
            CREATE TABLE sales (
                id                INT           IDENTITY(1,1) PRIMARY KEY,
                invoice_number    INT           NOT NULL DEFAULT 0,
                invoice_no        NVARCHAR(40)  NOT NULL DEFAULT '',
                invoice_date      NVARCHAR(20)  NOT NULL DEFAULT '',
                total             DECIMAL(12,2) NOT NULL DEFAULT 0,
                tendered          DECIMAL(12,2) NOT NULL DEFAULT 0,
                method            NVARCHAR(30)  NOT NULL DEFAULT 'Cash',
                cashier_id        INT           NULL,
                cashier_name      NVARCHAR(120) NOT NULL DEFAULT '',
                customer_name     NVARCHAR(120) NOT NULL DEFAULT '',
                customer_contact  NVARCHAR(80)  NOT NULL DEFAULT '',
                company_name      NVARCHAR(120) NOT NULL DEFAULT '',
                kot               NVARCHAR(40)  NOT NULL DEFAULT '',
                currency          NVARCHAR(10)  NOT NULL DEFAULT 'USD',
                subtotal          DECIMAL(12,2) NOT NULL DEFAULT 0,
                total_vat         DECIMAL(12,2) NOT NULL DEFAULT 0,
                discount_amount   DECIMAL(12,2) NOT NULL DEFAULT 0,
                receipt_type      NVARCHAR(30)  NOT NULL DEFAULT 'Invoice',
                footer            NVARCHAR(MAX) NOT NULL DEFAULT '',
                created_at        DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
                total_items       DECIMAL(12,4) NOT NULL DEFAULT 0,
                change_amount     DECIMAL(12,2) NOT NULL DEFAULT 0,
                synced            INT           NOT NULL DEFAULT 0,
                frappe_ref        NVARCHAR(80)  NULL,
                payment_entry_ref NVARCHAR(80)  NULL,
                payment_synced    BIT           NOT NULL DEFAULT 0
            )
        """); ok("sales")
    else:
        skip("sales")
        for col, defn in [
            ("invoice_number",    "INT           NOT NULL DEFAULT 0"),
            ("invoice_no",        "NVARCHAR(40)  NOT NULL DEFAULT ''"),
            ("invoice_date",      "NVARCHAR(20)  NOT NULL DEFAULT ''"),
            ("tendered",          "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("cashier_name",      "NVARCHAR(120) NOT NULL DEFAULT ''"),
            ("customer_contact",  "NVARCHAR(80)  NOT NULL DEFAULT ''"),
            ("company_name",      "NVARCHAR(120) NOT NULL DEFAULT ''"),
            ("kot",               "NVARCHAR(40)  NOT NULL DEFAULT ''"),
            ("currency",          "NVARCHAR(10)  NOT NULL DEFAULT 'USD'"),
            ("subtotal",          "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("total_vat",         "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("discount_amount",   "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("receipt_type",      "NVARCHAR(30)  NOT NULL DEFAULT 'Invoice'"),
            ("footer",            "NVARCHAR(MAX) NOT NULL DEFAULT ''"),
            ("total_items",       "DECIMAL(12,4) NOT NULL DEFAULT 0"),
            ("change_amount",     "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("synced",            "INT           NOT NULL DEFAULT 0"),
            ("frappe_ref",        "NVARCHAR(80)  NULL"),
            ("payment_entry_ref", "NVARCHAR(80)  NULL"),
            ("payment_synced",    "BIT           NOT NULL DEFAULT 0"),
        ]:
            add_col("sales", col, defn)

    # ==================================================================
    # 11. sale_items
    # ==================================================================
    if not table_exists("sale_items"):
        cur.execute("""
            CREATE TABLE sale_items (
                id           INT           IDENTITY(1,1) PRIMARY KEY,
                sale_id      INT           NOT NULL
                                 REFERENCES sales(id) ON DELETE CASCADE,
                part_no      NVARCHAR(50)  NOT NULL DEFAULT '',
                product_name NVARCHAR(120) NOT NULL DEFAULT '',
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
        """); ok("sale_items")
    else:
        skip("sale_items")
        for col, defn in [
            ("part_no",    "NVARCHAR(50)  NOT NULL DEFAULT ''"),
            ("discount",   "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("tax",        "NVARCHAR(20)  NOT NULL DEFAULT ''"),
            ("tax_type",   "NVARCHAR(20)  NOT NULL DEFAULT ''"),
            ("tax_rate",   "DECIMAL(8,4)  NOT NULL DEFAULT 0"),
            ("tax_amount", "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("remarks",    "NVARCHAR(MAX) NOT NULL DEFAULT ''"),
            ("order_1",    "BIT           NOT NULL DEFAULT 0"),
            ("order_2",    "BIT           NOT NULL DEFAULT 0"),
            ("order_3",    "BIT           NOT NULL DEFAULT 0"),
            ("order_4",    "BIT           NOT NULL DEFAULT 0"),
            ("order_5",    "BIT           NOT NULL DEFAULT 0"),
            ("order_6",    "BIT           NOT NULL DEFAULT 0"),
        ]:
            add_col("sale_items", col, defn)

    # ==================================================================
    # 12. shifts
    # ==================================================================
    if not table_exists("shifts"):
        cur.execute("""
            CREATE TABLE shifts (
                id           INT           IDENTITY(1,1) PRIMARY KEY,
                shift_number INT           NOT NULL DEFAULT 1,
                station      INT           NOT NULL DEFAULT 1,
                cashier_id   INT           NULL,
                date         NVARCHAR(20)  NOT NULL DEFAULT '',
                start_time   NVARCHAR(20)  NOT NULL DEFAULT '',
                end_time     NVARCHAR(20)  NULL,
                door_counter INT           NOT NULL DEFAULT 0,
                customers    INT           NOT NULL DEFAULT 0,
                notes        NVARCHAR(MAX) NOT NULL DEFAULT '',
                created_at   DATETIME2     NOT NULL DEFAULT SYSDATETIME()
            )
        """); ok("shifts")
    else:
        skip("shifts")
        for col, defn in [
            ("station",      "INT           NOT NULL DEFAULT 1"),
            ("date",         "NVARCHAR(20)  NOT NULL DEFAULT ''"),
            ("start_time",   "NVARCHAR(20)  NOT NULL DEFAULT ''"),
            ("end_time",     "NVARCHAR(20)  NULL"),
            ("door_counter", "INT           NOT NULL DEFAULT 0"),
            ("customers",    "INT           NOT NULL DEFAULT 0"),
            ("notes",        "NVARCHAR(MAX) NOT NULL DEFAULT ''"),
        ]:
            add_col("shifts", col, defn)

    # ==================================================================
    # 13. shift_rows
    # ==================================================================
    if not table_exists("shift_rows"):
        cur.execute("""
            CREATE TABLE shift_rows (
                id          INT           IDENTITY(1,1) PRIMARY KEY,
                shift_id    INT           NOT NULL
                                REFERENCES shifts(id) ON DELETE CASCADE,
                method      NVARCHAR(50)  NOT NULL DEFAULT '',
                start_float DECIMAL(12,2) NOT NULL DEFAULT 0,
                income      DECIMAL(12,2) NOT NULL DEFAULT 0,
                counted     DECIMAL(12,2) NOT NULL DEFAULT 0
            )
        """); ok("shift_rows")
    else:
        skip("shift_rows")
        for col, defn in [
            ("method",      "NVARCHAR(50)  NOT NULL DEFAULT ''"),
            ("start_float", "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("income",      "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("counted",     "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ]:
            add_col("shift_rows", col, defn)

    # ==================================================================
    # 14. payment_entries
    # ==================================================================
    if not table_exists("payment_entries"):
        cur.execute("""
            CREATE TABLE payment_entries (
                id                       INT           IDENTITY(1,1) PRIMARY KEY,
                sale_id                  INT           NULL,
                sale_invoice_no          NVARCHAR(80)  NULL,
                frappe_invoice_ref       NVARCHAR(80)  NULL,
                party                    NVARCHAR(120) NULL,
                party_name               NVARCHAR(120) NULL,
                paid_amount              DECIMAL(12,2) NOT NULL DEFAULT 0,
                received_amount          DECIMAL(12,2) NOT NULL DEFAULT 0,
                source_exchange_rate     DECIMAL(12,6) NOT NULL DEFAULT 1,
                paid_to_account_currency NVARCHAR(10)  NULL,
                currency                 NVARCHAR(10)  NULL,
                paid_to                  NVARCHAR(255) NULL,
                mode_of_payment          NVARCHAR(80)  NULL,
                reference_no             NVARCHAR(80)  NULL,
                reference_date           DATE          NULL,
                remarks                  NVARCHAR(255) NULL,
                payment_type             NVARCHAR(20)  NOT NULL DEFAULT 'Receive',
                synced                   BIT           NOT NULL DEFAULT 0,
                frappe_payment_ref       NVARCHAR(80)  NULL,
                created_at               DATETIME2     NOT NULL DEFAULT SYSDATETIME()
            )
        """); ok("payment_entries")
    else:
        skip("payment_entries")
        for col, defn in [
            ("remarks",      "NVARCHAR(255) NULL"),
            ("payment_type", "NVARCHAR(20)  NOT NULL DEFAULT 'Receive'"),
        ]:
            add_col("payment_entries", col, defn)

    # ==================================================================
    # 15. credit_notes
    # ==================================================================
    if not table_exists("credit_notes"):
        cur.execute("""
            CREATE TABLE credit_notes (
                id                  INT           IDENTITY(1,1) PRIMARY KEY,
                cn_number           NVARCHAR(40)  NOT NULL DEFAULT '',
                original_sale_id    INT           NOT NULL,
                original_invoice_no NVARCHAR(40)  NOT NULL DEFAULT '',
                frappe_ref          NVARCHAR(80)  NULL,
                frappe_cn_ref       NVARCHAR(80)  NULL,
                total               DECIMAL(12,2) NOT NULL DEFAULT 0,
                currency            NVARCHAR(10)  NOT NULL DEFAULT 'USD',
                cashier_name        NVARCHAR(120) NOT NULL DEFAULT '',
                customer_name       NVARCHAR(120) NOT NULL DEFAULT '',
                cn_status           NVARCHAR(20)  NOT NULL DEFAULT 'pending_sync',
                created_at          DATETIME2     NOT NULL DEFAULT SYSDATETIME()
            )
        """); ok("credit_notes")
    else:
        skip("credit_notes")

    # ==================================================================
    # 16. credit_note_items
    # ==================================================================
    if not table_exists("credit_note_items"):
        cur.execute("""
            CREATE TABLE credit_note_items (
                id             INT           IDENTITY(1,1) PRIMARY KEY,
                credit_note_id INT           NOT NULL
                                   REFERENCES credit_notes(id) ON DELETE CASCADE,
                part_no        NVARCHAR(50)  NOT NULL DEFAULT '',
                product_name   NVARCHAR(120) NOT NULL DEFAULT '',
                qty            DECIMAL(12,4) NOT NULL DEFAULT 0,
                price          DECIMAL(12,2) NOT NULL DEFAULT 0,
                total          DECIMAL(12,2) NOT NULL DEFAULT 0,
                reason         NVARCHAR(255) NOT NULL DEFAULT 'Customer Return'
            )
        """); ok("credit_note_items")
    else:
        skip("credit_note_items")

    # ==================================================================
    # 17. gl_accounts
    # ==================================================================
    if not table_exists("gl_accounts"):
        cur.execute("""
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
        """); ok("gl_accounts")
    else:
        skip("gl_accounts")
        for col, defn in [
            ("account_name",   "NVARCHAR(140) NOT NULL DEFAULT ''"),
            ("account_number", "NVARCHAR(80)  NULL"),
            ("parent_account", "NVARCHAR(140) NOT NULL DEFAULT ''"),
            ("updated_at",     "DATETIME2     NOT NULL DEFAULT SYSDATETIME()"),
        ]:
            add_col("gl_accounts", col, defn)

    # ==================================================================
    # 18. exchange_rates
    # ==================================================================
    if not table_exists("exchange_rates"):
        cur.execute("""
            CREATE TABLE exchange_rates (
                id            INT           IDENTITY(1,1) PRIMARY KEY,
                from_currency NVARCHAR(10)  NOT NULL,
                to_currency   NVARCHAR(10)  NOT NULL,
                rate          DECIMAL(18,6) NOT NULL DEFAULT 1,
                rate_date     NVARCHAR(20)  NOT NULL,
                updated_at    DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
                CONSTRAINT UQ_exchange_rates
                    UNIQUE (from_currency, to_currency, rate_date)
            )
        """); ok("exchange_rates")
    else:
        skip("exchange_rates")

    # ==================================================================
    # 19. item_groups
    # ==================================================================
    if not table_exists("item_groups"):
        cur.execute("""
            CREATE TABLE item_groups (
                id                INT           IDENTITY(1,1) PRIMARY KEY,
                name              NVARCHAR(100) NOT NULL UNIQUE,
                item_group_name   NVARCHAR(100) NOT NULL DEFAULT '',
                parent_item_group NVARCHAR(100) NOT NULL DEFAULT '',
                synced_from_api   BIT           NOT NULL DEFAULT 0,
                created_at        DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
                updated_at        DATETIME2     NOT NULL DEFAULT SYSDATETIME()
            )
        """); ok("item_groups")
    else:
        skip("item_groups")
        for col, defn in [
            ("item_group_name",   "NVARCHAR(100) NOT NULL DEFAULT ''"),
            ("parent_item_group", "NVARCHAR(100) NOT NULL DEFAULT ''"),
            ("synced_from_api",   "BIT           NOT NULL DEFAULT 0"),
            ("updated_at",        "DATETIME2     NOT NULL DEFAULT SYSDATETIME()"),
        ]:
            add_col("item_groups", col, defn)

    # ==================================================================
    # 20. customer_payments
    # ==================================================================
    if not table_exists("customer_payments"):
        cur.execute("""
            CREATE TABLE customer_payments (
                id          INT           IDENTITY(1,1) PRIMARY KEY,
                customer_id INT           NOT NULL,
                amount      DECIMAL(12,2) NOT NULL DEFAULT 0,
                method      NVARCHAR(30)  NOT NULL DEFAULT '',
                reference   NVARCHAR(100) NULL,
                cashier_id  INT           NULL,
                created_at  DATETIME2     NOT NULL DEFAULT SYSDATETIME()
            )
        """); ok("customer_payments")
    else:
        skip("customer_payments")

    # ==================================================================
    # Commit all DDL
    # ==================================================================
    conn.commit()
    print("\n  All tables ready.")

    # ==================================================================
    # SEED: default admin user if users table is empty
    # ==================================================================
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO users
                (username, password, role, display_name,
                 full_name, active, synced_from_frappe)
            VALUES (?, ?, 'admin', 'Administrator', 'Administrator', 1, 0)
        """, ("admin", _hash("admin123")))
        conn.commit()
        print("\n  [+] Default admin user created:")
        print("      Username : admin")
        print("      Password : admin123")
        print("      ** Change this password after first login! **")
    else:
        print("\n  Users already present - skipping seed.")

    conn.close()
    print("\n======================================")
    print("  Setup complete!")
    print("======================================\n")


if __name__ == "__main__":
    run()
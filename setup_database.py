import sys
import os
import hashlib


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# run() is the only public entry-point.
# main.py calls:  from setup_database import run; run()
# ---------------------------------------------------------------------------
def run():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    try:
        from database.db import get_connection
    except Exception as e:
        print(f"[setup_database] Cannot import database.db: {e}")
        return

    try:
        conn = get_connection()
    except Exception as e:
        print(f"[setup_database] Cannot open DB connection: {e}")
        return

    cur = conn.cursor()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def table_exists(name: str) -> bool:
        try:
            cur.execute(
                "SELECT 1 FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=?", (name,))
            return cur.fetchone() is not None
        except Exception:
            return False

    def col_exists(table: str, col: str) -> bool:
        try:
            cur.execute(
                "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=? AND COLUMN_NAME=?",
                (table, col))
            return cur.fetchone() is not None
        except Exception:
            return False

    def add_col(table: str, col: str, definition: str):
        if not col_exists(table, col):
            try:
                cur.execute(
                    f"ALTER TABLE [dbo].[{table}] ADD [{col}] {definition}")
                print(f"    + added column  {table}.{col}")
            except Exception as e:
                print(f"    ! could not add {table}.{col}: {e}")

    def fk_exists(name: str) -> bool:
        try:
            cur.execute(
                "SELECT 1 FROM sys.foreign_keys WHERE name=?", (name,))
            return cur.fetchone() is not None
        except Exception:
            return False

    def ok(name):   print(f"  [+] created  : {name}")
    def skip(name): print(f"  [ ] exists   : {name}")

    print("\n======================================")
    print("  Havano POS - Database Setup")
    print("======================================\n")

    # ==================================================================
    # 1. companies
    # ==================================================================
    if not table_exists("companies"):
        cur.execute("""
            CREATE TABLE [dbo].[companies] (
                [id]               INT           IDENTITY(1,1) NOT NULL,
                [name]             NVARCHAR(120) NOT NULL,
                [abbreviation]     NVARCHAR(40)  NOT NULL,
                [default_currency] NVARCHAR(10)  NOT NULL DEFAULT 'USD',
                [country]          NVARCHAR(80)  NOT NULL,
                PRIMARY KEY CLUSTERED ([id] ASC),
                UNIQUE NONCLUSTERED ([name] ASC)
            )
        """)
        ok("companies")
    else:
        skip("companies")
        add_col("companies", "abbreviation",     "NVARCHAR(40)  NOT NULL DEFAULT ''")
        add_col("companies", "default_currency", "NVARCHAR(10)  NOT NULL DEFAULT 'USD'")
        add_col("companies", "country",          "NVARCHAR(80)  NOT NULL DEFAULT ''")

   
    # ==================================================================
    # 2. company_defaults
    # ==================================================================
    if not table_exists("company_defaults"):
        cur.execute("""
            CREATE TABLE [dbo].[company_defaults] (
                [id]                       INT           IDENTITY(1,1) NOT NULL,
                [company_name]             NVARCHAR(200) NOT NULL DEFAULT '',
                [address_1]                NVARCHAR(200) NOT NULL DEFAULT '',
                [address_2]                NVARCHAR(200) NOT NULL DEFAULT '',
                [email]                    NVARCHAR(200) NOT NULL DEFAULT '',
                [phone]                    NVARCHAR(100) NOT NULL DEFAULT '',
                [vat_number]               NVARCHAR(100) NOT NULL DEFAULT '',
                [tin_number]               NVARCHAR(100) NOT NULL DEFAULT '',
                [footer_text]              NVARCHAR(500) NOT NULL DEFAULT '',
                [terms_and_conditions]     NVARCHAR(MAX) NOT NULL DEFAULT '',
                [zimra_serial_no]          NVARCHAR(100) NOT NULL DEFAULT '',
                [zimra_device_id]          NVARCHAR(100) NOT NULL DEFAULT '',
                [zimra_api_key]            NVARCHAR(500) NOT NULL DEFAULT '',
                [zimra_api_url]            NVARCHAR(300) NOT NULL DEFAULT '',
                [server_company]           NVARCHAR(200) NOT NULL DEFAULT '',
                [server_warehouse]         NVARCHAR(200) NOT NULL DEFAULT '',
                [server_cost_center]       NVARCHAR(200) NOT NULL DEFAULT '',
                [server_username]          NVARCHAR(200) NOT NULL DEFAULT '',
                [server_email]             NVARCHAR(200) NOT NULL DEFAULT '',
                [server_role]              NVARCHAR(100) NOT NULL DEFAULT '',
                [server_full_name]         NVARCHAR(200) NOT NULL DEFAULT '',
                [updated_at]               DATETIME      NOT NULL DEFAULT GETDATE(),
                [server_first_name]        NVARCHAR(100) NOT NULL DEFAULT '',
                [server_last_name]         NVARCHAR(100) NOT NULL DEFAULT '',
                [server_mobile]            NVARCHAR(100) NOT NULL DEFAULT '',
                [server_profile]           NVARCHAR(100) NOT NULL DEFAULT '',
                [server_vat_enabled]       NVARCHAR(10)  NOT NULL DEFAULT '',
                [api_key]                  NVARCHAR(200) NOT NULL DEFAULT '',
                [api_secret]               NVARCHAR(200) NOT NULL DEFAULT '',
                [invoice_prefix]           NVARCHAR(6)   NOT NULL DEFAULT '',
                [invoice_start_number]     INT           NOT NULL DEFAULT 0,
                [allow_credit_sales]       NVARCHAR(10)  NOT NULL DEFAULT '0',
                [server_company_currency]  NVARCHAR(10)  NOT NULL DEFAULT 'USD',
                [server_api_host]          NVARCHAR(255) NOT NULL DEFAULT '',
                [server_pos_account]       NVARCHAR(255) NOT NULL DEFAULT '',
                [server_taxes_and_charges] NVARCHAR(255) NOT NULL DEFAULT '',
                [server_walk_in_customer]  NVARCHAR(255) NOT NULL DEFAULT 'default',
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        # Always seed one blank row so the app has a settings row to read
        try:
            cur.execute("INSERT INTO [dbo].[company_defaults] DEFAULT VALUES")
        except Exception:
            pass
        ok("company_defaults")
    else:
        skip("company_defaults")
        # Migration loop for existing databases
        for col, defn in [
            ("phone",                    "NVARCHAR(100) NOT NULL DEFAULT ''"),
            ("zimra_serial_no",          "NVARCHAR(100) NOT NULL DEFAULT ''"),
            ("zimra_device_id",          "NVARCHAR(100) NOT NULL DEFAULT ''"),
            ("zimra_api_key",            "NVARCHAR(500) NOT NULL DEFAULT ''"),
            ("zimra_api_url",            "NVARCHAR(300) NOT NULL DEFAULT ''"),
            ("invoice_prefix",           "NVARCHAR(6)   NOT NULL DEFAULT ''"),
            ("invoice_start_number",     "INT           NOT NULL DEFAULT 0"),
            ("allow_credit_sales",       "NVARCHAR(10)  NOT NULL DEFAULT '0'"),
            ("server_company_currency",  "NVARCHAR(10)  NOT NULL DEFAULT 'USD'"),
            ("server_api_host",          "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("server_pos_account",       "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("server_taxes_and_charges", "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("server_walk_in_customer",  "NVARCHAR(255) NOT NULL DEFAULT 'default'"),
            ("server_first_name",        "NVARCHAR(100) NOT NULL DEFAULT ''"),
            ("server_last_name",         "NVARCHAR(100) NOT NULL DEFAULT ''"),
            ("server_mobile",            "NVARCHAR(100) NOT NULL DEFAULT ''"),
            ("server_profile",           "NVARCHAR(100) NOT NULL DEFAULT ''"),
            ("server_vat_enabled",       "NVARCHAR(10)  NOT NULL DEFAULT ''"),
            ("api_key",                  "NVARCHAR(200) NOT NULL DEFAULT ''"),
            ("api_secret",               "NVARCHAR(200) NOT NULL DEFAULT ''"),
            ("terms_and_conditions",     "NVARCHAR(MAX) NOT NULL DEFAULT ''"),
        ]:
            add_col("company_defaults", col, defn)
        
        # Ensure at least one settings row exists
        try:
            cur.execute("SELECT COUNT(*) FROM [dbo].[company_defaults]")
            if cur.fetchone()[0] == 0:
                cur.execute("INSERT INTO [dbo].[company_defaults] DEFAULT VALUES")
        except Exception:
            pass
    # ==================================================================
    # 3. customer_groups
    # ==================================================================
    if not table_exists("customer_groups"):
        cur.execute("""
            CREATE TABLE [dbo].[customer_groups] (
                [id]              INT           IDENTITY(1,1) NOT NULL,
                [name]            NVARCHAR(120) NOT NULL,
                [parent_group_id] INT           NULL,
                PRIMARY KEY CLUSTERED ([id] ASC),
                UNIQUE NONCLUSTERED ([name] ASC)
            )
        """)
        ok("customer_groups")
    else:
        skip("customer_groups")
        add_col("customer_groups", "parent_group_id", "INT NULL")

    # ==================================================================
    # 4. price_lists
    # ==================================================================
    if not table_exists("price_lists"):
        cur.execute("""
            CREATE TABLE [dbo].[price_lists] (
                [id]      INT           IDENTITY(1,1) NOT NULL,
                [name]    NVARCHAR(120) NOT NULL,
                [selling] BIT           NULL DEFAULT 1,
                PRIMARY KEY CLUSTERED ([id] ASC),
                UNIQUE NONCLUSTERED ([name] ASC)
            )
        """)
        ok("price_lists")
    else:
        skip("price_lists")
        add_col("price_lists", "selling", "BIT NULL DEFAULT 1")

    # ==================================================================
    # 5. warehouses  (FK -> companies added after all tables exist)
    # ==================================================================
    if not table_exists("warehouses"):
        cur.execute("""
            CREATE TABLE [dbo].[warehouses] (
                [id]         INT           IDENTITY(1,1) NOT NULL,
                [name]       NVARCHAR(120) NOT NULL,
                [company_id] INT           NOT NULL,
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("warehouses")
    else:
        skip("warehouses")
        add_col("warehouses", "company_id", "INT NOT NULL DEFAULT 0")

    # ==================================================================
    # 6. cost_centers  (FK -> companies added later)
    # ==================================================================
    if not table_exists("cost_centers"):
        cur.execute("""
            CREATE TABLE [dbo].[cost_centers] (
                [id]         INT           IDENTITY(1,1) NOT NULL,
                [name]       NVARCHAR(120) NOT NULL,
                [company_id] INT           NOT NULL,
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("cost_centers")
    else:
        skip("cost_centers")
        add_col("cost_centers", "company_id", "INT NOT NULL DEFAULT 0")

        # ==================================================================
    # 7. customers
    # ==================================================================
    if not table_exists("customers"):
        cur.execute("""
            CREATE TABLE [dbo].[customers] (
                [id]                      INT           IDENTITY(1,1) NOT NULL,
                [customer_name]           NVARCHAR(120) NOT NULL,
                [customer_group_id]       INT           NULL,
                [customer_type]           NVARCHAR(20)  NULL,
                [custom_trade_name]       NVARCHAR(120) NULL,
                [custom_telephone_number] NVARCHAR(120) NULL,
                [custom_email_address]    NVARCHAR(120) NULL,
                [custom_city]             NVARCHAR(120) NULL,
                [custom_house_no]         NVARCHAR(120) NULL,
                [custom_warehouse_id]     INT           NULL,
                [custom_cost_center_id]   INT           NULL,
                [default_price_list_id]   INT           NULL,
                [balance]                 DECIMAL(18,2) NULL DEFAULT 0,
                [outstanding_amount]      DECIMAL(18,2) NULL DEFAULT 0,
                [laybye_balance]          DECIMAL(18,2) NULL DEFAULT 0,
                [loyalty_points]          INT           NULL DEFAULT 0,
                [frappe_synced]           BIT           NOT NULL DEFAULT 0,
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("customers")
    else:
        skip("customers")
        for col, defn in [
            ("customer_group_id",       "INT           NULL"),
            ("customer_type",           "NVARCHAR(20)  NULL"),
            ("custom_trade_name",       "NVARCHAR(120) NULL"),
            ("custom_telephone_number", "NVARCHAR(120) NULL"),
            ("custom_email_address",    "NVARCHAR(120) NULL"),
            ("custom_city",             "NVARCHAR(120) NULL"),
            ("custom_house_no",         "NVARCHAR(120) NULL"),
            ("custom_warehouse_id",     "INT           NULL"),
            ("custom_cost_center_id",   "INT           NULL"),
            ("default_price_list_id",   "INT           NULL"),
            ("balance",                 "DECIMAL(18,2) NULL DEFAULT 0"),
            ("outstanding_amount",      "DECIMAL(18,2) NULL DEFAULT 0"),
            ("laybye_balance",          "DECIMAL(18,2) NULL DEFAULT 0"),
            ("loyalty_points",          "INT           NULL DEFAULT 0"),
            ("frappe_synced",           "BIT           NOT NULL DEFAULT 0"),
        ]:
            add_col("customers", col, defn)
    
    # ==================================================================
    # 8. users
    # ==================================================================
    if not table_exists("users"):
        cur.execute("""
            CREATE TABLE [dbo].[users] (
                [id]                   INT           IDENTITY(1,1) NOT NULL,
                [username]             NVARCHAR(80)  NOT NULL,
                [password]             NVARCHAR(255) NOT NULL,
                [display_name]         NVARCHAR(120) NULL,
                [active]               BIT           NOT NULL DEFAULT 1,
                [role]                 NVARCHAR(20)  NULL  DEFAULT 'cashier',
                [email]                NVARCHAR(120) NULL,
                [full_name]            NVARCHAR(120) NULL,
                [first_name]           NVARCHAR(80)  NULL,
                [last_name]            NVARCHAR(80)  NULL,
                [pin]                  NVARCHAR(20)  NULL,
                [cost_center]          NVARCHAR(140) NULL,
                [warehouse]            NVARCHAR(140) NULL,
                [frappe_user]          NVARCHAR(120) NULL,
                [synced_from_frappe]   BIT           NOT NULL DEFAULT 0,
                [allow_discount]       BIT           NOT NULL DEFAULT 1,
                [allow_receipt]        BIT           NOT NULL DEFAULT 1,
                [allow_credit_note]    BIT           NOT NULL DEFAULT 1,
                [allow_reprint]        BIT           NOT NULL DEFAULT 1,
                [allow_laybye]         BIT           NOT NULL DEFAULT 1,
                [allow_quote]          BIT           NOT NULL DEFAULT 1,
                [discount_expiry_date] NVARCHAR(50)  NULL,
                [company]              NVARCHAR(140) NULL  DEFAULT '',
                [max_discount_percent] INT           NULL  DEFAULT 0,
                PRIMARY KEY CLUSTERED ([id] ASC),
                UNIQUE NONCLUSTERED ([username] ASC)
            )
        """)
        ok("users")
    else:
        skip("users")
        for col, defn in [
            ("display_name",         "NVARCHAR(120) NULL"),
            ("email",                "NVARCHAR(120) NULL"),
            ("full_name",            "NVARCHAR(120) NULL"),
            ("first_name",           "NVARCHAR(80)  NULL"),
            ("last_name",            "NVARCHAR(80)  NULL"),
            ("pin",                  "NVARCHAR(20)  NULL"),
            ("cost_center",          "NVARCHAR(140) NULL"),
            ("warehouse",            "NVARCHAR(140) NULL"),
            ("frappe_user",          "NVARCHAR(120) NULL"),
            ("synced_from_frappe",   "BIT           NOT NULL DEFAULT 0"),
            ("allow_discount",       "BIT           NOT NULL DEFAULT 1"),
            ("allow_receipt",        "BIT           NOT NULL DEFAULT 1"),
            ("allow_credit_note",    "BIT           NOT NULL DEFAULT 1"),
            ("allow_reprint",        "BIT           NOT NULL DEFAULT 1"),
            ("allow_laybye",         "BIT           NOT NULL DEFAULT 1"),   #← ADD THIS
            ("allow_quote",          "BIT           NOT NULL DEFAULT 1"),  # ← ADD THIS
            ("discount_expiry_date", "NVARCHAR(50)  NULL"),
            ("company",              "NVARCHAR(140) NULL DEFAULT ''"),
            ("max_discount_percent", "INT           NULL DEFAULT 0"),
        ]:
            add_col("users", col, defn)

    # ==================================================================
    # 9. products
    # ==================================================================
    if not table_exists("products"):
        cur.execute("""
            CREATE TABLE [dbo].[products] (
                [id]                INT           IDENTITY(1,1) NOT NULL,
                [part_no]           NVARCHAR(50)  NOT NULL,
                [name]              NVARCHAR(120) NOT NULL,
                [price]             DECIMAL(12,2) NOT NULL,
                [stock]             INT           NOT NULL,
                [category]          NVARCHAR(80)  NOT NULL,
                [active]            BIT           NULL,
                [image_path]        NVARCHAR(500) NULL,
                [order_1]           BIT           NOT NULL DEFAULT 0,
                [order_2]           BIT           NOT NULL DEFAULT 0,
                [order_3]           BIT           NOT NULL DEFAULT 0,
                [order_4]           BIT           NOT NULL DEFAULT 0,
                [order_5]           BIT           NOT NULL DEFAULT 0,
                [order_6]           BIT           NOT NULL DEFAULT 0,
                [uom]               NVARCHAR(20)  NULL,
                [conversion_factor] DECIMAL(12,4) NULL,
                [tax_rate]          DECIMAL(8,4)  NULL,
                [tax_type]          NVARCHAR(50)  NULL,
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("products")
    else:
        skip("products")
        for col, defn in [
            ("active",            "BIT           NULL"),
            ("image_path",        "NVARCHAR(500) NULL"),
            ("order_1",           "BIT           NOT NULL DEFAULT 0"),
            ("order_2",           "BIT           NOT NULL DEFAULT 0"),
            ("order_3",           "BIT           NOT NULL DEFAULT 0"),
            ("order_4",           "BIT           NOT NULL DEFAULT 0"),
            ("order_5",           "BIT           NOT NULL DEFAULT 0"),
            ("order_6",           "BIT           NOT NULL DEFAULT 0"),
            ("uom",               "NVARCHAR(20)  NULL"),
            ("conversion_factor", "DECIMAL(12,4) NULL"),
            ("tax_rate",          "DECIMAL(8,4)  NULL"),
            ("tax_type",          "NVARCHAR(50)  NULL"),
        ]:
            add_col("products", col, defn)

    # ==================================================================
    # 10. sales
    # ==================================================================
    # ==================================================================
    # 10. sales
    # ==================================================================
    if not table_exists("sales"):
        cur.execute("""
            CREATE TABLE [dbo].[sales] (
                [id]                INT           IDENTITY(1,1) NOT NULL,
                [invoice_number]    INT           NOT NULL,
                [invoice_no]        NVARCHAR(40)  NOT NULL,
                [invoice_date]      DATETIME2(7)  NOT NULL,
                [total]             DECIMAL(12,2) NOT NULL,
                [tendered]          DECIMAL(12,2) NOT NULL,
                [method]            NVARCHAR(30)  NOT NULL,
                [cashier_id]        INT           NULL,
                [cashier_name]      NVARCHAR(120) NOT NULL,
                [customer_name]     NVARCHAR(120) NOT NULL,
                [customer_contact]  NVARCHAR(80)  NOT NULL,
                [kot]               NVARCHAR(40)  NOT NULL,
                [currency]          NVARCHAR(10)  NOT NULL,
                [subtotal]          DECIMAL(12,2) NOT NULL,
                [total_vat]         DECIMAL(12,2) NOT NULL,
                [discount_amount]   DECIMAL(12,2) NOT NULL,
                [is_on_account]     BIT           NOT NULL DEFAULT 0,
                [receipt_type]      NVARCHAR(30)  NOT NULL,
                [footer]            NVARCHAR(MAX) NOT NULL,
                [synced]            BIT           NOT NULL DEFAULT 0,
                [syncing]           BIT           NOT NULL DEFAULT 0,
                [sync_error]        NVARCHAR(MAX) NULL,
                [total_items]       DECIMAL(12,4) NOT NULL,
                [change_amount]     DECIMAL(12,2) NOT NULL,
                [company_name]      NVARCHAR(120) NOT NULL,
                [frappe_ref]        NVARCHAR(80)  NULL,
                [created_at]        DATETIME2(7)  NULL DEFAULT SYSDATETIME(),
                [payment_entry_ref] NVARCHAR(80)  NULL,
                [payment_synced]    BIT           NOT NULL DEFAULT 0,
                [shift_id]          INT           NULL,
                [fiscal_status]               NVARCHAR(50)  NULL,
                [fiscal_qr_code]              NVARCHAR(MAX) NULL,
                [fiscal_verification_code]    NVARCHAR(255) NULL,
                [fiscal_receipt_counter]      INT           NULL,
                [fiscal_global_no]            NVARCHAR(100) NULL,
                [fiscal_sync_date]            DATETIME2(7)  NULL,
                [fiscal_error]                NVARCHAR(MAX) NULL,
                [total_tax_amount]            DECIMAL(12,2) NULL DEFAULT 0,
                [subtotal_before_tax]         DECIMAL(12,2) NULL DEFAULT 0,
                -- ── Multi-currency fields ──────────────────────────────────
                [total_usd]       DECIMAL(14,4) NULL DEFAULT 0,
                [total_zwd]       DECIMAL(14,4) NULL DEFAULT 0,
                [tendered_usd]    DECIMAL(14,4) NULL DEFAULT 0,
                [tendered_zwd]    DECIMAL(14,4) NULL DEFAULT 0,
                [exchange_rate]   DECIMAL(18,8) NULL DEFAULT 1,
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("sales")
    else:
        skip("sales")

    # Migration loop for sales
    for col, defn in [
        ("company_name",      "NVARCHAR(120) NOT NULL DEFAULT ''"),
        ("frappe_ref",        "NVARCHAR(80)  NULL"),
        ("created_at",        "DATETIME2(7)  NULL DEFAULT SYSDATETIME()"),
        ("payment_entry_ref", "NVARCHAR(80)  NULL"),
        ("payment_synced",    "BIT           NOT NULL DEFAULT 0"),
        ("synced",            "BIT           NOT NULL DEFAULT 0"),
        ("syncing",           "BIT           NOT NULL DEFAULT 0"),
        ("is_on_account",     "BIT           NOT NULL DEFAULT 0"),
        ("shift_id",                    "INT           NULL"),
        ("fiscal_status",               "NVARCHAR(50)  NULL"),
        ("fiscal_qr_code",              "NVARCHAR(MAX) NULL"),
        ("fiscal_verification_code",    "NVARCHAR(255) NULL"),
        ("fiscal_receipt_counter",      "INT           NULL"),
        ("fiscal_global_no",            "NVARCHAR(100) NULL"),
        ("fiscal_sync_date",            "DATETIME2(7)  NULL"),
        ("fiscal_error",                "NVARCHAR(MAX) NULL"),
        ("sync_error",                  "NVARCHAR(MAX) NULL"),
        ("total_tax_amount",            "DECIMAL(12,2) NULL DEFAULT 0"),
        ("subtotal_before_tax",         "DECIMAL(12,2) NULL DEFAULT 0"),
        # ── Multi-currency fields (migration) ──
        ("total_usd",     "DECIMAL(14,4) NULL DEFAULT 0"),
        ("total_zwd",     "DECIMAL(14,4) NULL DEFAULT 0"),
        ("tendered_usd",  "DECIMAL(14,4) NULL DEFAULT 0"),
        ("tendered_zwd",  "DECIMAL(14,4) NULL DEFAULT 0"),
        ("exchange_rate", "DECIMAL(18,8) NULL DEFAULT 1"),
    ]:
        add_col("sales", col, defn)

    # ==================================================================
    # 11. sale_items  (FK -> sales added later)
    # ==================================================================
    if not table_exists("sale_items"):
        cur.execute("""
            CREATE TABLE [dbo].[sale_items] (
                [id]           INT           IDENTITY(1,1) NOT NULL,
                [sale_id]      INT           NOT NULL,
                [part_no]      NVARCHAR(50)  NOT NULL,
                [product_name] NVARCHAR(120) NOT NULL,
                [qty]          DECIMAL(12,4) NOT NULL,
                [price]        DECIMAL(12,2) NOT NULL,
                [discount]     DECIMAL(12,2) NOT NULL,
                [tax]          NVARCHAR(20)  NOT NULL,
                [total]        DECIMAL(12,2) NOT NULL,
                [tax_type]     NVARCHAR(20)  NOT NULL,
                [tax_rate]     DECIMAL(8,4)  NOT NULL,
                [tax_amount]   DECIMAL(12,2) NOT NULL,
                [remarks]      NVARCHAR(MAX) NOT NULL DEFAULT '',
                
                [order_1]      BIT           NOT NULL DEFAULT 0,
                [order_2]      BIT           NOT NULL DEFAULT 0,
                [order_3]      BIT           NOT NULL DEFAULT 0,
                [order_4]      BIT           NOT NULL DEFAULT 0,
                [order_5]      BIT           NOT NULL DEFAULT 0,
                [order_6]      BIT           NOT NULL DEFAULT 0,
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("sale_items")
    else:
        skip("sale_items")
        for col, defn in [
            ("remarks", "NVARCHAR(MAX) NOT NULL DEFAULT ''"),
            ("order_1", "BIT           NOT NULL DEFAULT 0"),
            ("order_2", "BIT           NOT NULL DEFAULT 0"),
            ("order_3", "BIT           NOT NULL DEFAULT 0"),
            ("order_4", "BIT           NOT NULL DEFAULT 0"),
            ("order_5", "BIT           NOT NULL DEFAULT 0"),
            ("order_6", "BIT           NOT NULL DEFAULT 0"),
            ("is_on_account",     "BIT           NOT NULL DEFAULT 0"),
        ]:
            add_col("sale_items", col, defn)

    # ==================================================================
    # 12. shifts
    # ==================================================================
    if not table_exists("shifts"):
        cur.execute("""
            CREATE TABLE [dbo].[shifts] (
                [id]           INT           IDENTITY(1,1) NOT NULL,
                [shift_number] INT           NOT NULL,
                [station]      INT           NOT NULL,
                [cashier_id]   INT           NULL,
                [date]         DATE          NOT NULL,
                [start_time]   DATETIME2(7)  NOT NULL,
                [end_time]     DATETIME2(7)  NULL,
                [door_counter] INT           NOT NULL DEFAULT 0,
                [customers]    INT           NOT NULL DEFAULT 0,
                [notes]        NVARCHAR(MAX) NULL,
                [created_at]   DATETIME2(7)  NULL DEFAULT SYSDATETIME(),
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("shifts")
    else:
        skip("shifts")
        for col, defn in [
            ("door_counter", "INT           NOT NULL DEFAULT 0"),
            ("customers",    "INT           NOT NULL DEFAULT 0"),
            ("notes",        "NVARCHAR(MAX) NULL"),
            ("created_at",   "DATETIME2(7)  NULL DEFAULT SYSDATETIME()"),
        ]:
            add_col("shifts", col, defn)

    # ==================================================================
    # 13. shift_rows  (FK -> shifts added later)
    # ==================================================================
    if not table_exists("shift_rows"):
        cur.execute("""
            CREATE TABLE [dbo].[shift_rows] (
                [id]          INT           IDENTITY(1,1) NOT NULL,
                [shift_id]    INT           NOT NULL,
                [method]      NVARCHAR(50)  NOT NULL,
                [start_float] DECIMAL(12,2) NOT NULL,
                [income]      DECIMAL(12,2) NOT NULL,
                [counted]     DECIMAL(12,2) NOT NULL,
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("shift_rows")
    else:
        skip("shift_rows")

    # ==================================================================
    # 14. payment_entries
    # ==================================================================
    if not table_exists("payment_entries"):
        cur.execute("""
            CREATE TABLE [dbo].[payment_entries] (
                [id]                       INT           IDENTITY(1,1) NOT NULL,
                [sale_id]                  INT           NULL,
                [sale_invoice_no]          NVARCHAR(80)  NULL,
                [frappe_invoice_ref]       NVARCHAR(80)  NULL,
                [party]                    NVARCHAR(120) NULL,
                [party_name]               NVARCHAR(120) NULL,
                [paid_amount]              DECIMAL(12,2) NOT NULL DEFAULT 0,
                [received_amount]          DECIMAL(12,2) NOT NULL DEFAULT 0,
                [source_exchange_rate]     DECIMAL(12,6) NOT NULL DEFAULT 1,
                [paid_to_account_currency] NVARCHAR(10)  NULL,
                [currency]                 NVARCHAR(10)  NULL,
                [paid_to]                  NVARCHAR(255) NULL,
                [mode_of_payment]          NVARCHAR(80)  NULL,
                [reference_no]             NVARCHAR(80)  NULL,
                [reference_date]           DATE          NULL,
                [remarks]                  NVARCHAR(255) NULL,
                [payment_type]             NVARCHAR(20)  NOT NULL DEFAULT 'Receive',
                [synced]                   BIT           NOT NULL DEFAULT 0,
                [syncing]                  BIT           NOT NULL DEFAULT 0,
                [frappe_payment_ref]       NVARCHAR(80)  NULL,
                [created_at]               DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
                [frappe_so_ref]            NVARCHAR(255) NULL,
                [sync_attempts]            INT           NOT NULL DEFAULT 0,
                [last_error]               NVARCHAR(MAX) NULL,
                [amount_usd]               DECIMAL(14,4) NULL DEFAULT 0,
                [amount_zwd]               DECIMAL(14,4) NULL DEFAULT 0,
                [amount_zwg]               DECIMAL(14,4) NULL DEFAULT 0,
                [exchange_rate]            DECIMAL(18,8) NULL DEFAULT 1,
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("payment_entries")
    else:
        skip("payment_entries")
        for col, defn in [
            ("frappe_invoice_ref",       "NVARCHAR(80)  NULL"),
            ("party",                    "NVARCHAR(120) NULL"),
            ("party_name",               "NVARCHAR(120) NULL"),
            ("paid_to_account_currency", "NVARCHAR(10)  NULL"),
            ("currency",                 "NVARCHAR(10)  NULL"),
            ("paid_to",                  "NVARCHAR(255) NULL"),
            ("mode_of_payment",          "NVARCHAR(80)  NULL"),
            ("reference_no",             "NVARCHAR(80)  NULL"),
            ("reference_date",           "DATE          NULL"),
            ("remarks",                  "NVARCHAR(255) NULL"),
            ("frappe_payment_ref",       "NVARCHAR(80)  NULL"),
            ("frappe_so_ref",            "NVARCHAR(255) NULL"),
            ("sync_attempts",            "INT           NOT NULL DEFAULT 0"),
            ("syncing",                  "BIT           NOT NULL DEFAULT 0"),
            ("last_error",               "NVARCHAR(MAX) NULL"),
            ("amount_usd",    "DECIMAL(14,4) NULL DEFAULT 0"),
            ("amount_zwd",    "DECIMAL(14,4) NULL DEFAULT 0"),
            ("amount_zwg",    "DECIMAL(14,4) NULL DEFAULT 0"),
            ("exchange_rate", "DECIMAL(18,8) NULL DEFAULT 1"),
        ]:
            add_col("payment_entries", col, defn)

    # ==================================================================
    # 15. credit_notes
    # ==================================================================
    if not table_exists("credit_notes"):
        cur.execute("""
            CREATE TABLE [dbo].[credit_notes] (
                [id]                  INT           IDENTITY(1,1) NOT NULL,
                [cn_number]           NVARCHAR(40)  NOT NULL DEFAULT '',
                [original_sale_id]    INT           NOT NULL,
                [original_invoice_no] NVARCHAR(40)  NOT NULL DEFAULT '',
                [frappe_ref]          NVARCHAR(80)  NULL,
                [frappe_cn_ref]       NVARCHAR(80)  NULL,
                [total]               DECIMAL(12,2) NOT NULL DEFAULT 0,
                [currency]            NVARCHAR(10)  NOT NULL DEFAULT 'USD',
                [cashier_name]        NVARCHAR(120) NOT NULL DEFAULT '',
                [customer_name]       NVARCHAR(120) NOT NULL DEFAULT '',
                [cn_status]           NVARCHAR(20)  NOT NULL DEFAULT 'pending_sync',
                [created_at]          DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("credit_notes")
    else:
        skip("credit_notes")
        add_col("credit_notes", "frappe_ref",    "NVARCHAR(80) NULL")
        add_col("credit_notes", "frappe_cn_ref", "NVARCHAR(80) NULL")
        add_col("credit_notes", "sync_error",    "NVARCHAR(MAX) NULL")

    # ==================================================================
    # 16. credit_note_items  (FK -> credit_notes added later)
    # ==================================================================
    if not table_exists("credit_note_items"):
        cur.execute("""
            CREATE TABLE [dbo].[credit_note_items] (
                [id]             INT           IDENTITY(1,1) NOT NULL,
                [credit_note_id] INT           NOT NULL,
                [part_no]        NVARCHAR(50)  NOT NULL DEFAULT '',
                [product_name]   NVARCHAR(120) NOT NULL DEFAULT '',
                [qty]            DECIMAL(12,4) NOT NULL DEFAULT 0,
                [price]          DECIMAL(12,2) NOT NULL DEFAULT 0,
                [total]          DECIMAL(12,2) NOT NULL DEFAULT 0,
                [reason]         NVARCHAR(255) NOT NULL DEFAULT 'Customer Return',
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("credit_note_items")
    else:
        skip("credit_note_items")

    # ==================================================================
    # 17. gl_accounts
    # ==================================================================
    if not table_exists("gl_accounts"):
        cur.execute("""
            CREATE TABLE [dbo].[gl_accounts] (
                [id]               INT           IDENTITY(1,1) NOT NULL,
                [name]             NVARCHAR(140) NOT NULL,
                [account_name]     NVARCHAR(140) NOT NULL DEFAULT '',
                [account_number]   NVARCHAR(80)  NULL,
                [company]          NVARCHAR(120) NOT NULL DEFAULT '',
                [parent_account]   NVARCHAR(140) NOT NULL DEFAULT '',
                [account_type]     NVARCHAR(80)  NOT NULL DEFAULT '',
                [account_currency] NVARCHAR(10)  NOT NULL DEFAULT 'USD',
                [is_group]         BIT           NOT NULL DEFAULT 0,
                [updated_at]       DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
                PRIMARY KEY CLUSTERED ([id] ASC),
                UNIQUE NONCLUSTERED ([name] ASC)
            )
        """)
        ok("gl_accounts")
    else:
        skip("gl_accounts")

    # Migration loop for gl_accounts (ensure all columns exist)
    for col, defn in [
        ("account_number",   "NVARCHAR(80)  NULL"),
        ("account_currency", "NVARCHAR(10)  NOT NULL DEFAULT 'USD'"),
        ("is_group",         "BIT           NOT NULL DEFAULT 0"),
        ("updated_at",       "DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME()"),
    ]:
        add_col("gl_accounts", col, defn)

    # ==================================================================
    # 18. exchange_rates
    # ==================================================================
    if not table_exists("exchange_rates"):
        cur.execute("""
            CREATE TABLE [dbo].[exchange_rates] (
                [id]            INT           IDENTITY(1,1) NOT NULL,
                [from_currency] NVARCHAR(10)  NOT NULL,
                [to_currency]   NVARCHAR(10)  NOT NULL,
                [rate]          DECIMAL(18,6) NOT NULL DEFAULT 1,
                [rate_date]     NVARCHAR(20)  NOT NULL,
                [updated_at]    DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
                PRIMARY KEY CLUSTERED ([id] ASC),
                CONSTRAINT [UQ_exchange_rates]
                    UNIQUE NONCLUSTERED ([from_currency],[to_currency],[rate_date])
            )
        """)
        ok("exchange_rates")
    else:
        skip("exchange_rates")
        add_col("exchange_rates", "updated_at",
                "DATETIME2(7) NOT NULL DEFAULT SYSDATETIME()")

    # ==================================================================
    # 19. item_groups
    # ==================================================================
    if not table_exists("item_groups"):
        cur.execute("""
            CREATE TABLE [dbo].[item_groups] (
                [id]                INT           IDENTITY(1,1) NOT NULL,
                [name]              NVARCHAR(100) NOT NULL,
                [item_group_name]   NVARCHAR(100) NOT NULL DEFAULT '',
                [parent_item_group] NVARCHAR(100) NOT NULL DEFAULT '',
                [synced_from_api]   BIT           NOT NULL DEFAULT 0,
                [created_at]        DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
                [updated_at]        DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
                PRIMARY KEY CLUSTERED ([id] ASC),
                UNIQUE NONCLUSTERED ([name] ASC)
            )
        """)
        ok("item_groups")
    else:
        skip("item_groups")
        for col, defn in [
            ("item_group_name",   "NVARCHAR(100) NOT NULL DEFAULT ''"),
            ("parent_item_group", "NVARCHAR(100) NOT NULL DEFAULT ''"),
            ("synced_from_api",   "BIT           NOT NULL DEFAULT 0"),
            ("created_at",        "DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME()"),
            ("updated_at",        "DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME()"),
        ]:
            add_col("item_groups", col, defn)

    # ==================================================================
    # 20. customer_payments
    # ==================================================================
    if not table_exists("customer_payments"):
        cur.execute("""
            CREATE TABLE [dbo].[customer_payments] (
                [id]           INT           IDENTITY(1,1) NOT NULL,
                [customer_id]  INT           NOT NULL,
                [amount]       DECIMAL(12,2) NOT NULL DEFAULT 0,
                [method]       NVARCHAR(30)  NOT NULL DEFAULT '',
                [reference]    NVARCHAR(100) NULL,
                [cashier_id]   INT           NULL,
                [created_at]   DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
                [currency]     NVARCHAR(10)  NULL DEFAULT 'USD',
                [account_name] NVARCHAR(100) NULL,
                [payment_date] DATE          NULL,
                [sync_error]   NVARCHAR(MAX) NULL,
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("customer_payments")
    else:
        skip("customer_payments")

    # Migration loop for customer_payments
    for col, defn in [
        ("reference",    "NVARCHAR(100) NULL"),
        ("cashier_id",   "INT           NULL"),
        ("currency",     "NVARCHAR(10)  NULL DEFAULT 'USD'"),
        ("account_name", "NVARCHAR(100) NULL"),
        ("payment_date", "DATE          NULL"),
        ("sync_error",   "NVARCHAR(MAX) NULL"),
    ]:
        add_col("customer_payments", col, defn)

    # ==================================================================
    # 21. product_uom_prices
    # ==================================================================
    if not table_exists("product_uom_prices"):
        cur.execute("""
            CREATE TABLE [dbo].[product_uom_prices] (
                [id]      INT           IDENTITY(1,1) NOT NULL,
                [part_no] NVARCHAR(50)  NOT NULL,
                [uom]     NVARCHAR(40)  NOT NULL,
                [price]   DECIMAL(12,2) NOT NULL DEFAULT 0,
                PRIMARY KEY CLUSTERED ([id] ASC),
                CONSTRAINT [UQ_product_uom]
                    UNIQUE NONCLUSTERED ([part_no],[uom])
            )
        """)
        ok("product_uom_prices")
    else:
        skip("product_uom_prices")

    # ==================================================================
    # 22. sales_order
    # ==================================================================
    # ==================================================================
    # 22. sales_order
    # ==================================================================
    if not table_exists("sales_order"):
        cur.execute("""
            CREATE TABLE [dbo].[sales_order] (
                [id]             INT           IDENTITY(1,1) NOT NULL,
                [order_no]       NVARCHAR(100) NULL,
                [customer_id]    INT           NULL,
                [customer_name]  NVARCHAR(255) NULL,
                [company]        NVARCHAR(255) NULL,
                [order_date]     NVARCHAR(50)  NULL,
                [delivery_date]  NVARCHAR(50)  NOT NULL DEFAULT '',
                [order_type]     NVARCHAR(50)  NOT NULL DEFAULT 'Sales',
                [total]          FLOAT         NOT NULL DEFAULT 0,
                [deposit_amount] FLOAT         NOT NULL DEFAULT 0,
                [deposit_method] NVARCHAR(100) NOT NULL DEFAULT '',
                [balance_due]    FLOAT         NOT NULL DEFAULT 0,
                [status]         NVARCHAR(50)  NOT NULL DEFAULT 'Draft',
                [synced]         INT           NOT NULL DEFAULT 0,
                [frappe_ref]     NVARCHAR(255) NOT NULL DEFAULT '',
                [created_at]     NVARCHAR(50)  NULL,
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("sales_order")
    else:
        skip("sales_order")
        for col, defn in [
            ("order_no",       "NVARCHAR(100) NULL"),
            ("customer_id",    "INT           NULL"),
            ("customer_name",  "NVARCHAR(255) NULL"),
            ("company",        "NVARCHAR(255) NULL"),
            ("order_date",     "NVARCHAR(50)  NULL"),
            ("delivery_date",  "NVARCHAR(50)  NOT NULL DEFAULT ''"),
            ("order_type",     "NVARCHAR(50)  NOT NULL DEFAULT 'Sales'"),
            ("total",          "FLOAT         NOT NULL DEFAULT 0"),
            ("deposit_amount", "FLOAT         NOT NULL DEFAULT 0"),
            ("deposit_method", "NVARCHAR(100) NOT NULL DEFAULT ''"),
            ("balance_due",    "FLOAT         NOT NULL DEFAULT 0"),
            ("status",         "NVARCHAR(50)  NOT NULL DEFAULT 'Draft'"),
            ("synced",         "INT           NOT NULL DEFAULT 0"),
            ("frappe_ref",     "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("created_at",     "NVARCHAR(50)  NULL"),
        ]:
            add_col("sales_order", col, defn)

    # ==================================================================
    # 23. sales_order_item  (FK -> sales_order added later)
    # ==================================================================
    if not table_exists("sales_order_item"):
        cur.execute("""
            CREATE TABLE [dbo].[sales_order_item] (
                [id]             INT           IDENTITY(1,1) NOT NULL,
                [sales_order_id] INT           NOT NULL,
                [item_code]      NVARCHAR(100) NULL,
                [item_name]      NVARCHAR(255) NULL,
                [qty]            FLOAT         NOT NULL DEFAULT 1,
                [rate]           FLOAT         NOT NULL DEFAULT 0,
                [amount]         FLOAT         NOT NULL DEFAULT 0,
                [warehouse]      NVARCHAR(255) NOT NULL DEFAULT '',
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("sales_order_item")
    else:
        skip("sales_order_item")
        for col, defn in [
            ("item_code", "NVARCHAR(100) NULL"),
            ("item_name", "NVARCHAR(255) NULL"),
            ("qty",       "FLOAT         NOT NULL DEFAULT 1"),
            ("rate",      "FLOAT         NOT NULL DEFAULT 0"),
            ("amount",    "FLOAT         NOT NULL DEFAULT 0"),
            ("warehouse", "NVARCHAR(255) NOT NULL DEFAULT ''"),
        ]:
            add_col("sales_order_item", col, defn)

    # ==================================================================
    # 24. laybye_payment_entries
    # ==================================================================
    if not table_exists("laybye_payment_entries"):
        cur.execute("""
            CREATE TABLE [dbo].[laybye_payment_entries] (
                [id]               INT           IDENTITY(1,1) NOT NULL,
                [sales_order_id]   INT           NOT NULL,
                [order_no]         NVARCHAR(100) NOT NULL DEFAULT '',
                [customer_id]      NVARCHAR(255) NOT NULL DEFAULT '',
                [customer_name]    NVARCHAR(255) NOT NULL DEFAULT '',
                [deposit_amount]   FLOAT         NOT NULL DEFAULT 0,
                [deposit_method]   NVARCHAR(100) NOT NULL DEFAULT '',
                [account_paid_to]  NVARCHAR(255) NOT NULL DEFAULT '',
                [account_currency] NVARCHAR(20)  NOT NULL DEFAULT 'USD',
                [frappe_so_ref]    NVARCHAR(255) NOT NULL DEFAULT '',
                [frappe_pe_ref]    NVARCHAR(255) NOT NULL DEFAULT '',
                [status]           NVARCHAR(50)  NOT NULL DEFAULT 'pending',
                [sync_attempts]    INT           NOT NULL DEFAULT 0,
                [created_at]       NVARCHAR(50)  NOT NULL DEFAULT '',
                [last_attempt_at]  NVARCHAR(50)  NOT NULL DEFAULT '',
                [error_message]    NVARCHAR(MAX) NOT NULL DEFAULT '',
                [sync_error]       NVARCHAR(MAX) NULL,
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("laybye_payment_entries")
    else:
        skip("laybye_payment_entries")

    # Migration loop for laybye_payment_entries
    for col, defn in [
        ("order_no",         "NVARCHAR(100) NOT NULL DEFAULT ''"),
        ("customer_id",      "NVARCHAR(255) NOT NULL DEFAULT ''"),
        ("customer_name",    "NVARCHAR(255) NOT NULL DEFAULT ''"),
        ("deposit_amount",   "FLOAT         NOT NULL DEFAULT 0"),
        ("deposit_method",   "NVARCHAR(100) NOT NULL DEFAULT ''"),
        ("account_paid_to",  "NVARCHAR(255) NOT NULL DEFAULT ''"),
        ("account_currency", "NVARCHAR(20)  NOT NULL DEFAULT 'USD'"),
        ("frappe_so_ref",    "NVARCHAR(255) NOT NULL DEFAULT ''"),
        ("frappe_pe_ref",    "NVARCHAR(255) NOT NULL DEFAULT ''"),
        ("status",           "NVARCHAR(50)  NOT NULL DEFAULT 'pending'"),
        ("sync_attempts",    "INT           NOT NULL DEFAULT 0"),
        ("created_at",       "NVARCHAR(50)  NOT NULL DEFAULT ''"),
        ("last_attempt_at",  "NVARCHAR(50)  NOT NULL DEFAULT ''"),
        ("error_message",    "NVARCHAR(MAX) NOT NULL DEFAULT ''"),
        ("sync_error",       "NVARCHAR(MAX) NULL"),
    ]:
        add_col("laybye_payment_entries", col, defn)

    # ==================================================================
    # 25. pos_settings
    # ==================================================================
    if not table_exists("pos_settings"):
        cur.execute("""
            CREATE TABLE [dbo].[pos_settings] (
                [setting_key]   NVARCHAR(80)  NOT NULL,
                [setting_value] NVARCHAR(255) NOT NULL DEFAULT '0',
                PRIMARY KEY CLUSTERED ([setting_key] ASC)
            )
        """)
        ok("pos_settings")
    else:
        skip("pos_settings")

    # ==================================================================
    # 26. shift_reports
    # ==================================================================
    if not table_exists("shift_reports"):
        cur.execute("""
            CREATE TABLE [dbo].[shift_reports] (
                [id]             INT           IDENTITY(1,1) NOT NULL,
                [cashier_id]     INT           NULL,
                [cashier_name]   NVARCHAR(100) NULL,
                [shift_number]   INT           NULL,
                [total_expected] DECIMAL(18,2) NULL,
                [total_actual]   DECIMAL(18,2) NULL,
                [total_variance] DECIMAL(18,2) NULL,
                [report_date]    DATE          NULL,
                [created_at]     DATETIME2(7)  NULL DEFAULT SYSDATETIME(),
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("shift_reports")
    else:
        skip("shift_reports")
        for col, defn in [
            ("cashier_name",   "NVARCHAR(100) NULL"),
            ("shift_number",   "INT           NULL"),
            ("total_expected", "DECIMAL(18,2) NULL"),
            ("total_actual",   "DECIMAL(18,2) NULL"),
            ("total_variance", "DECIMAL(18,2) NULL"),
            ("report_date",    "DATE          NULL"),
            ("created_at",     "DATETIME2(7)  NULL DEFAULT SYSDATETIME()"),
        ]:
            add_col("shift_reports", col, defn)

    # ==================================================================
    # 27. shift_report_details
    # ==================================================================
    if not table_exists("shift_report_details"):
        cur.execute("""
            CREATE TABLE [dbo].[shift_report_details] (
                [id]               INT           IDENTITY(1,1) NOT NULL,
                [report_id]        INT           NULL,
                [payment_method]   NVARCHAR(50)  NULL,
                [amount_expected]  DECIMAL(18,2) NULL,
                [amount_available] DECIMAL(18,2) NULL,
                [variance]         DECIMAL(18,2) NULL,
                [created_at]       DATETIME2(7)  NULL DEFAULT SYSDATETIME(),
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("shift_report_details")
    else:
        skip("shift_report_details")
        for col, defn in [
            ("report_id",        "INT           NULL"),
            ("payment_method",   "NVARCHAR(50)  NULL"),
            ("amount_expected",  "DECIMAL(18,2) NULL"),
            ("amount_available", "DECIMAL(18,2) NULL"),
            ("variance",         "DECIMAL(18,2) NULL"),
            ("created_at",       "DATETIME2(7)  NULL DEFAULT SYSDATETIME()"),
        ]:
            add_col("shift_report_details", col, defn)

    # ==================================================================
    # 28. sync_errors
    # ==================================================================
    if not table_exists("sync_errors"):
        cur.execute("""
            CREATE TABLE [dbo].[sync_errors] (
                [id]          INT           IDENTITY(1,1) NOT NULL,
                [doc_type]    NVARCHAR(20)  NOT NULL DEFAULT '',
                [doc_ref]     NVARCHAR(100) NOT NULL DEFAULT '',
                [customer]    NVARCHAR(255) NOT NULL DEFAULT '',
                [amount]      FLOAT         NOT NULL DEFAULT 0,
                [error_code]  NVARCHAR(50)  NOT NULL DEFAULT '',
                [error_msg]   NVARCHAR(MAX) NOT NULL DEFAULT '',
                [occurred_at] NVARCHAR(50)  NOT NULL DEFAULT '',
                [resolved]    BIT           NOT NULL DEFAULT 0,
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("sync_errors")
    else:
        skip("sync_errors")
        # Migrate existing installs — add any columns that may be missing
        add_col("sync_errors", "doc_type",    "NVARCHAR(20)  NOT NULL DEFAULT ''")
        add_col("sync_errors", "doc_ref",     "NVARCHAR(100) NOT NULL DEFAULT ''")
        add_col("sync_errors", "customer",    "NVARCHAR(255) NOT NULL DEFAULT ''")
        add_col("sync_errors", "amount",      "FLOAT         NOT NULL DEFAULT 0")
        add_col("sync_errors", "error_code",  "NVARCHAR(50)  NOT NULL DEFAULT ''")
        add_col("sync_errors", "error_msg",   "NVARCHAR(MAX) NOT NULL DEFAULT ''")
        add_col("sync_errors", "occurred_at", "NVARCHAR(50)  NOT NULL DEFAULT ''")
        add_col("sync_errors", "resolved",    "BIT           NOT NULL DEFAULT 0")

    # ==================================================================
    # 29. fiscal_settings
    # ==================================================================
    if not table_exists("fiscal_settings"):
        cur.execute("""
            CREATE TABLE [dbo].[fiscal_settings] (
                [id]                    INT           IDENTITY(1,1) NOT NULL,
                [enabled]               BIT           NOT NULL DEFAULT 0,
                [base_url]              NVARCHAR(500) NOT NULL DEFAULT '',
                [api_key]               NVARCHAR(200) NOT NULL DEFAULT '',
                [api_secret]            NVARCHAR(200) NOT NULL DEFAULT '',
                [device_sn]             NVARCHAR(100) NOT NULL DEFAULT '',
                [ping_interval_minutes] INT           NOT NULL DEFAULT 5,
                [device_status]         NVARCHAR(20)  NOT NULL DEFAULT 'unknown',
                [last_ping_time]        DATETIME2(7)  NULL,
                [reporting_frequency]   INT           NULL,
                [operation_id]          NVARCHAR(100) NULL,
                [created_at]            DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
                [updated_at]            DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("fiscal_settings")
    else:
        skip("fiscal_settings")
        for col, defn in [
            ("enabled",               "BIT           NOT NULL DEFAULT 0"),
            ("base_url",              "NVARCHAR(500) NOT NULL DEFAULT ''"),
            ("api_key",               "NVARCHAR(200) NOT NULL DEFAULT ''"),
            ("api_secret",            "NVARCHAR(200) NOT NULL DEFAULT ''"),
            ("device_sn",             "NVARCHAR(100) NOT NULL DEFAULT ''"),
            ("ping_interval_minutes", "INT           NOT NULL DEFAULT 5"),
            ("device_status",         "NVARCHAR(20)  NOT NULL DEFAULT 'unknown'"),
            ("last_ping_time",        "DATETIME2(7)  NULL"),
            ("reporting_frequency",   "INT           NULL"),
            ("operation_id",          "NVARCHAR(100) NULL"),
            ("created_at",            "DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME()"),
            ("updated_at",            "DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME()"),
        ]:
            add_col("fiscal_settings", col, defn)

    # ==================================================================
    # 30. invoice_counter
    # ==================================================================
    if not table_exists("invoice_counter"):
        cur.execute("""
            CREATE TABLE [dbo].[invoice_counter] (
                [counter_name] NVARCHAR(50)  NOT NULL,
                [last_number]  INT           NOT NULL DEFAULT 0,
                [updated_at]   DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
                PRIMARY KEY CLUSTERED ([counter_name] ASC)
            )
        """)
        ok("invoice_counter")
    else:
        skip("invoice_counter")
        for col, defn in [
            ("last_number", "INT          NOT NULL DEFAULT 0"),
            ("updated_at",  "DATETIME2(7) NOT NULL DEFAULT SYSDATETIME()"),
        ]:
            add_col("invoice_counter", col, defn)

    # ==================================================================
    # 31. product_taxes
    # ==================================================================
    if not table_exists("product_taxes"):
        cur.execute("""
            CREATE TABLE [dbo].[product_taxes] (
                [id]                INT           IDENTITY(1,1) NOT NULL,
                [part_no]           NVARCHAR(50)  NOT NULL,
                [item_tax_template] NVARCHAR(100) NULL,
                [tax_category]      NVARCHAR(50)  NULL,
                [valid_from]        DATE          NULL,
                [minimum_net_rate]  DECIMAL(8,4)  NULL,
                [maximum_net_rate]  DECIMAL(8,4)  NULL,
                [created_at]        DATETIME2(7)  NULL DEFAULT SYSDATETIME(),
                [updated_at]        DATETIME2(7)  NULL DEFAULT SYSDATETIME(),
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("product_taxes")
    else:
        skip("product_taxes")
        for col, defn in [
            ("item_tax_template", "NVARCHAR(100) NULL"),
            ("tax_category",      "NVARCHAR(50)  NULL"),
            ("valid_from",        "DATE          NULL"),
            ("minimum_net_rate",  "DECIMAL(8,4)  NULL"),
            ("maximum_net_rate",  "DECIMAL(8,4)  NULL"),
            ("created_at",        "DATETIME2(7)  NULL DEFAULT SYSDATETIME()"),
            ("updated_at",        "DATETIME2(7)  NULL DEFAULT SYSDATETIME()"),
        ]:
            add_col("product_taxes", col, defn)

    # ==================================================================
    # 32. quotations
    # ==================================================================
    if not table_exists("quotations"):
        cur.execute("""
            CREATE TABLE [dbo].[quotations] (
                [id]               INT           IDENTITY(1,1) NOT NULL,
                [name]             NVARCHAR(100) NOT NULL,
                [transaction_date] NVARCHAR(20)  NOT NULL DEFAULT '',
                [valid_till]       NVARCHAR(20)  NULL,
                [grand_total]      DECIMAL(12,2) NOT NULL DEFAULT 0,
                [docstatus]        INT           NOT NULL DEFAULT 0,
                [company]          NVARCHAR(120) NOT NULL DEFAULT '',
                [reference_number] NVARCHAR(80)  NULL,
                [status]           NVARCHAR(50)  NOT NULL DEFAULT 'Draft',
                [customer]         NVARCHAR(120) NOT NULL DEFAULT '',
                [synced]           BIT           NOT NULL DEFAULT 0,
                [frappe_ref]       NVARCHAR(80)  NULL,
                [sync_date]        DATETIME2(7)  NULL,
                [raw_data]         NVARCHAR(MAX) NULL,
                [created_at]       DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
                [updated_at]       DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("quotations")
    else:
        skip("quotations")
        for col, defn in [
            ("transaction_date", "NVARCHAR(20)  NOT NULL DEFAULT ''"),
            ("valid_till",       "NVARCHAR(20)  NULL"),
            ("grand_total",      "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("docstatus",        "INT           NOT NULL DEFAULT 0"),
            ("company",          "NVARCHAR(120) NOT NULL DEFAULT ''"),
            ("reference_number", "NVARCHAR(80)  NULL"),
            ("status",           "NVARCHAR(50)  NOT NULL DEFAULT 'Draft'"),
            ("customer",         "NVARCHAR(120) NOT NULL DEFAULT ''"),
            ("synced",           "BIT           NOT NULL DEFAULT 0"),
            ("frappe_ref",       "NVARCHAR(80)  NULL"),
            ("sync_date",        "DATETIME2(7)  NULL"),
            ("raw_data",         "NVARCHAR(MAX) NULL"),
            ("created_at",       "DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME()"),
            ("updated_at",       "DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME()"),
        ]:
            add_col("quotations", col, defn)

    # ==================================================================
    # 33. quotation_items  (FK -> quotations ON DELETE CASCADE)
    # ==================================================================
    if not table_exists("quotation_items"):
        cur.execute("""
            CREATE TABLE [dbo].[quotation_items] (
                [id]           INT           IDENTITY(1,1) NOT NULL,
                [quotation_id] INT           NOT NULL,
                [item_code]    NVARCHAR(50)  NOT NULL DEFAULT '',
                [item_name]    NVARCHAR(200) NOT NULL DEFAULT '',
                [description]  NVARCHAR(MAX) NULL,
                [qty]          DECIMAL(12,4) NOT NULL DEFAULT 1,
                [rate]         DECIMAL(12,2) NOT NULL DEFAULT 0,
                [amount]       DECIMAL(12,2) NOT NULL DEFAULT 0,
                [uom]          NVARCHAR(20)  NOT NULL DEFAULT '',
                [product_id]   INT           NULL,
                [part_no]      NVARCHAR(50)  NULL,
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("quotation_items")
    else:
        skip("quotation_items")
        for col, defn in [
            ("item_code",   "NVARCHAR(50)  NOT NULL DEFAULT ''"),
            ("item_name",   "NVARCHAR(200) NOT NULL DEFAULT ''"),
            ("description", "NVARCHAR(MAX) NULL"),
            ("qty",         "DECIMAL(12,4) NOT NULL DEFAULT 1"),
            ("rate",        "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("amount",      "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("uom",         "NVARCHAR(20)  NOT NULL DEFAULT ''"),
            ("product_id",  "INT           NULL"),
            ("part_no",     "NVARCHAR(50)  NULL"),
        ]:
            add_col("quotation_items", col, defn)

    # ==================================================================
    # 34. shift_reconciliations
    # ==================================================================
    if not table_exists("shift_reconciliations"):
        cur.execute("""
            CREATE TABLE [dbo].[shift_reconciliations] (
                [id]                   INT           IDENTITY(1,1) NOT NULL,
                [shift_id]             INT           NOT NULL,
                [shift_number]         INT           NOT NULL,
                [shift_date]           NVARCHAR(20)  NOT NULL DEFAULT '',
                [start_time]           NVARCHAR(20)  NOT NULL DEFAULT '',
                [end_time]             NVARCHAR(20)  NOT NULL DEFAULT '',
                [closing_cashier_id]   INT           NULL,
                [closing_cashier_name] NVARCHAR(100) NULL,
                [total_expected]       DECIMAL(12,2) NOT NULL DEFAULT 0,
                [total_counted]        DECIMAL(12,2) NOT NULL DEFAULT 0,
                [total_variance]       DECIMAL(12,2) NOT NULL DEFAULT 0,
                [reconciliation_json]  NVARCHAR(MAX) NOT NULL DEFAULT '',
                [printed_at]           DATETIME2(7)  NULL,
                [created_at]           DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("shift_reconciliations")
    else:
        skip("shift_reconciliations")
        for col, defn in [
            ("shift_number",         "INT           NOT NULL DEFAULT 0"),
            ("shift_date",           "NVARCHAR(20)  NOT NULL DEFAULT ''"),
            ("start_time",           "NVARCHAR(20)  NOT NULL DEFAULT ''"),
            ("end_time",             "NVARCHAR(20)  NOT NULL DEFAULT ''"),
            ("closing_cashier_id",   "INT           NULL"),
            ("closing_cashier_name", "NVARCHAR(100) NULL"),
            ("total_expected",       "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("total_counted",        "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("total_variance",       "DECIMAL(12,2) NOT NULL DEFAULT 0"),
            ("reconciliation_json",  "NVARCHAR(MAX) NOT NULL DEFAULT ''"),
            ("printed_at",           "DATETIME2(7)  NULL"),
            ("created_at",           "DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME()"),
        ]:
            add_col("shift_reconciliations", col, defn)

    # ==================================================================
    # 35. transaction_hashes
    # ==================================================================
    if not table_exists("transaction_hashes"):
        cur.execute("""
            CREATE TABLE [dbo].[transaction_hashes] (
                [id]               INT          IDENTITY(1,1) NOT NULL,
                [transaction_hash] NVARCHAR(64) NOT NULL,
                [sale_id]          INT          NULL,
                [created_at]       DATETIME2(7) NOT NULL DEFAULT SYSDATETIME(),
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("transaction_hashes")
    else:
        skip("transaction_hashes")
        for col, defn in [
            ("transaction_hash", "NVARCHAR(64) NOT NULL DEFAULT ''"),
            ("sale_id",          "INT          NULL"),
            ("created_at",       "DATETIME2(7) NOT NULL DEFAULT SYSDATETIME()"),
        ]:
            add_col("transaction_hashes", col, defn)

    # ==================================================================
    # 36. transaction_tracking
    # ==================================================================
    if not table_exists("transaction_tracking"):
        cur.execute("""
            CREATE TABLE [dbo].[transaction_tracking] (
                [id]             INT           IDENTITY(1,1) NOT NULL,
                [transaction_id] NVARCHAR(100) NOT NULL,
                [sale_id]        INT           NULL,
                [created_at]     DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
                [total]          DECIMAL(12,2) NULL,
                [item_count]     INT           NULL,
                PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        ok("transaction_tracking")
    else:
        skip("transaction_tracking")
        for col, defn in [
            ("transaction_id", "NVARCHAR(100) NOT NULL DEFAULT ''"),
            ("sale_id",        "INT           NULL"),
            ("created_at",     "DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME()"),
            ("total",          "DECIMAL(12,2) NULL"),
            ("item_count",     "INT           NULL"),
        ]:
            add_col("transaction_tracking", col, defn)

    # ==================================================================
    # 37. modes_of_payment
    # ==================================================================
    if not table_exists("modes_of_payment"):
        cur.execute("""
            CREATE TABLE [dbo].[modes_of_payment] (
                [id]               INT           IDENTITY(1,1) NOT NULL,
                [name]             NVARCHAR(120) NOT NULL,
                [type]             NVARCHAR(50)  NOT NULL DEFAULT 'General',
                [mop_type]         NVARCHAR(50)  NOT NULL DEFAULT 'General',
                [enabled]          BIT           NOT NULL DEFAULT 1,
                [account]          NVARCHAR(255) NULL,
                [gl_account]       NVARCHAR(255) NULL,
                [account_currency] NVARCHAR(10)  NOT NULL DEFAULT 'USD',
                [gl_account_name]  NVARCHAR(255) NULL,
                [company]          NVARCHAR(255) NOT NULL DEFAULT '',
                [synced_from_api]  BIT           NOT NULL DEFAULT 0,
                [created_at]       DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
                [updated_at]       DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME(),
                PRIMARY KEY CLUSTERED ([id] ASC),
                UNIQUE NONCLUSTERED ([name] ASC)
            )
        """)
        ok("modes_of_payment")
    else:
        skip("modes_of_payment")
        for col, defn in [
            ("type",             "NVARCHAR(50)  NOT NULL DEFAULT 'General'"),
            ("mop_type",         "NVARCHAR(50)  NOT NULL DEFAULT 'General'"),
            ("enabled",          "BIT           NOT NULL DEFAULT 1"),
            ("account",          "NVARCHAR(255) NULL"),
            ("gl_account",       "NVARCHAR(255) NULL"),
            ("account_currency", "NVARCHAR(10)  NOT NULL DEFAULT 'USD'"),
            ("gl_account_name",  "NVARCHAR(255) NULL"),
            ("company",          "NVARCHAR(255) NOT NULL DEFAULT ''"),
            ("synced_from_api",  "BIT           NOT NULL DEFAULT 0"),
            ("created_at",       "DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME()"),
            ("updated_at",       "DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME()"),
        ]:
            add_col("modes_of_payment", col, defn)

    # ==================================================================
    # 38. payment_entries
    # ==================================================================
    if not table_exists("payment_entries"):
        cur.execute("""
            CREATE TABLE [dbo].[payment_entries] (
                [id]                      INT           IDENTITY(1,1) PRIMARY KEY,
                [sale_id]                 INT           NULL,
                [sale_invoice_no]         NVARCHAR(80)  NULL,
                [frappe_invoice_ref]      NVARCHAR(80)  NULL,
                [party]                   NVARCHAR(120) NULL,
                [paid_amount]             DECIMAL(12,2) NOT NULL DEFAULT 0,
                [received_amount]         DECIMAL(12,2) NOT NULL DEFAULT 0,
                [source_exchange_rate]    DECIMAL(12,6) NOT NULL DEFAULT 1,
                [currency]                NVARCHAR(10)  NULL,
                [mode_of_payment]         NVARCHAR(80)  NULL,
                [reference_no]            NVARCHAR(80)  NULL,
                [payment_type]            NVARCHAR(20)  NOT NULL DEFAULT 'Receive',
                [synced]                  BIT           NOT NULL DEFAULT 0,
                [frappe_payment_ref]      NVARCHAR(80)  NULL,
                [sync_attempts]           INT           NOT NULL DEFAULT 0,
                [sync_error]              NVARCHAR(MAX) NULL,
                [created_at]              DATETIME2(7)  NOT NULL DEFAULT SYSDATETIME()
            )
        """)
        ok("payment_entries")
    else:
        skip("payment_entries")
        for col, defn in [
            ("sync_attempts", "INT           NOT NULL DEFAULT 0"),
            ("sync_error",    "NVARCHAR(MAX) NULL"),
            ("last_error",    "NVARCHAR(MAX) NULL"),
        ]:
            add_col("payment_entries", col, defn)

    # ------------------------------------------------------------------
    # Commit all table DDL before foreign keys
    # ------------------------------------------------------------------
    conn.commit()
    print("\n  Adding foreign key constraints...")

    fk_defs = [
        ("FK_cost_centers_companies",
         "ALTER TABLE [dbo].[cost_centers] WITH CHECK "
         "ADD CONSTRAINT [FK_cost_centers_companies] "
         "FOREIGN KEY ([company_id]) REFERENCES [dbo].[companies]([id])"),

        ("FK_warehouses_companies",
         "ALTER TABLE [dbo].[warehouses] WITH CHECK "
         "ADD CONSTRAINT [FK_warehouses_companies] "
         "FOREIGN KEY ([company_id]) REFERENCES [dbo].[companies]([id])"),

        ("FK_customers_customer_groups",
         "ALTER TABLE [dbo].[customers] WITH CHECK "
         "ADD CONSTRAINT [FK_customers_customer_groups] "
         "FOREIGN KEY ([customer_group_id]) "
         "REFERENCES [dbo].[customer_groups]([id])"),

        ("FK_customers_warehouses",
         "ALTER TABLE [dbo].[customers] WITH CHECK "
         "ADD CONSTRAINT [FK_customers_warehouses] "
         "FOREIGN KEY ([custom_warehouse_id]) "
         "REFERENCES [dbo].[warehouses]([id])"),

        ("FK_customers_cost_centers",
         "ALTER TABLE [dbo].[customers] WITH CHECK "
         "ADD CONSTRAINT [FK_customers_cost_centers] "
         "FOREIGN KEY ([custom_cost_center_id]) "
         "REFERENCES [dbo].[cost_centers]([id])"),

        ("FK_customers_price_lists",
         "ALTER TABLE [dbo].[customers] WITH CHECK "
         "ADD CONSTRAINT [FK_customers_price_lists] "
         "FOREIGN KEY ([default_price_list_id]) "
         "REFERENCES [dbo].[price_lists]([id])"),

        ("FK_sale_items_sales",
         "ALTER TABLE [dbo].[sale_items] WITH CHECK "
         "ADD CONSTRAINT [FK_sale_items_sales] "
         "FOREIGN KEY ([sale_id]) REFERENCES [dbo].[sales]([id]) "
         "ON DELETE CASCADE"),

        ("FK_shift_rows_shifts",
         "ALTER TABLE [dbo].[shift_rows] WITH CHECK "
         "ADD CONSTRAINT [FK_shift_rows_shifts] "
         "FOREIGN KEY ([shift_id]) REFERENCES [dbo].[shifts]([id]) "
         "ON DELETE CASCADE"),

        ("FK_credit_note_items_credit_notes",
         "ALTER TABLE [dbo].[credit_note_items] WITH CHECK "
         "ADD CONSTRAINT [FK_credit_note_items_credit_notes] "
         "FOREIGN KEY ([credit_note_id]) "
         "REFERENCES [dbo].[credit_notes]([id]) ON DELETE CASCADE"),

        ("FK_sales_order_item_sales_order",
         "ALTER TABLE [dbo].[sales_order_item] WITH CHECK "
         "ADD CONSTRAINT [FK_sales_order_item_sales_order] "
         "FOREIGN KEY ([sales_order_id]) "
         "REFERENCES [dbo].[sales_order]([id])"),

        ("FK_quotation_items_quotations",
         "ALTER TABLE [dbo].[quotation_items] WITH CHECK "
         "ADD CONSTRAINT [FK_quotation_items_quotations] "
         "FOREIGN KEY ([quotation_id]) "
         "REFERENCES [dbo].[quotations]([id]) ON DELETE CASCADE"),
    ]

    for fk_name, fk_sql in fk_defs:
        if not fk_exists(fk_name):
            try:
                cur.execute(fk_sql)
                print(f"  [+] {fk_name}")
            except Exception as e:
                print(f"  [!] {fk_name}: {e}")
        else:
            print(f"  [ ] {fk_name} already exists")

    conn.commit()
    print("\n  All tables and constraints ready.")

    # ==================================================================
    # Seed: one default admin user when the users table is empty
    # ==================================================================
    try:
        cur.execute("SELECT COUNT(*) FROM [dbo].[users]")
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO [dbo].[users]
                    (username, password, role, display_name, full_name,
                     active, synced_from_frappe,
                     allow_discount, allow_receipt,
                     allow_credit_note, allow_reprint,
                     allow_laybye, allow_quote,
                     company, max_discount_percent)
                VALUES (?, ?, 'admin', 'Administrator', 'Administrator',
                        1, 0, 1, 1, 1, 1, 1, 1, '', 0)
            """, ("admin", _hash("admin123")))
            conn.commit()
            print("\n  [+] Default admin user created:")
            print("      Username : admin")
            print("      Password : admin123")
            print("      *** Change this password after first login! ***")
        else:
            print("\n  [ ] Users already present - skipping seed.")
    except Exception as e:
        print(f"[setup_database] ! Error seeding admin user: {e}")
    print("======================================\n")

    # Apply migrate.py schema additions (doctors, dosages, product_batches,
    # pharmacy columns on products/customers/quote-items/sale-items,
    # quotations.cashier_name, sale_items.uom). All calls are idempotent
    # (IF NOT EXISTS guards), so this is safe to run on every boot.
    try:
        from migrate import migrate as _apply_migrations
        _apply_migrations()
    except Exception as e:
        print(f"[setup_database] ! migrate.py additions failed: {e}")


if __name__ == "__main__":
    run()
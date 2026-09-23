import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pyodbc
from database.db import _load_settings, _best_driver

def apply_optimizations():
    cfg = _load_settings()
    server = cfg.get("server") or ".\\SQLEXPRESS"
    db_name = cfg.get("database") or "havano_posop0797880890"
    auth_mode = cfg.get("auth_mode", "windows")
    driver = _best_driver()

    print(f"Connecting to {server}, database={db_name}...")
    
    # 1. RCSI must be set in autocommit mode, ideally connecting to master or the db directly
    master_conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE=master;"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
        "Encrypt=no;"
    ) if auth_mode == "windows" else (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE=master;"
        f"UID={cfg.get('username', '')};"
        f"PWD={cfg.get('password', '')};"
        "TrustServerCertificate=yes;"
        "Encrypt=no;"
    )

    try:
        conn = pyodbc.connect(master_conn_str, autocommit=True)
        cursor = conn.cursor()
        print(f"Enabling READ_COMMITTED_SNAPSHOT on [{db_name}]...")
        cursor.execute(f"ALTER DATABASE [{db_name}] SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;")
        cursor.execute(f"ALTER DATABASE [{db_name}] SET ALLOW_SNAPSHOT_ISOLATION ON;")
        conn.close()
        print("RCSI & Snapshot Isolation successfully enabled!")
    except Exception as e:
        print(f"Warning / Notice while enabling RCSI: {e}")

    # 2. Connect to database and create indexes
    db_conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={db_name};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
        "Encrypt=no;"
    ) if auth_mode == "windows" else (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={db_name};"
        f"UID={cfg.get('username', '')};"
        f"PWD={cfg.get('password', '')};"
        "TrustServerCertificate=yes;"
        "Encrypt=no;"
    )

    conn = pyodbc.connect(db_conn_str, autocommit=True)
    cursor = conn.cursor()

    indexes = [
        (
            "IX_product_barcodes_barcode",
            "product_barcodes",
            """
            IF EXISTS (SELECT * FROM sys.tables WHERE name = 'product_barcodes')
            AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_product_barcodes_barcode')
            BEGIN
                CREATE NONCLUSTERED INDEX [IX_product_barcodes_barcode]
                ON [dbo].[product_barcodes] ([barcode]) INCLUDE ([part_no]);
            END
            """
        ),
        (
            "IX_products_part_no_active",
            "products",
            """
            IF EXISTS (SELECT * FROM sys.tables WHERE name = 'products')
            AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_products_part_no_active')
            BEGIN
                CREATE NONCLUSTERED INDEX [IX_products_part_no_active]
                ON [dbo].[products] ([part_no], [active]) INCLUDE ([price], [cost_price], [stock], [name]);
            END
            """
        ),
        (
            "IX_sales_synced_created",
            "sales",
            """
            IF EXISTS (SELECT * FROM sys.tables WHERE name = 'sales')
            AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_sales_synced_created')
            BEGIN
                CREATE NONCLUSTERED INDEX [IX_sales_synced_created]
                ON [dbo].[sales] ([synced], [created_at]) INCLUDE ([id], [amount], [invoice_no]);
            END
            """
        ),
        (
            "IX_credit_notes_status",
            "credit_notes",
            """
            IF EXISTS (SELECT * FROM sys.tables WHERE name = 'credit_notes')
            AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_credit_notes_status')
            BEGIN
                CREATE NONCLUSTERED INDEX [IX_credit_notes_status]
                ON [dbo].[credit_notes] ([cn_status], [created_at]);
            END
            """
        )
    ]

    for idx_name, tbl, sql in indexes:
        try:
            print(f"Applying index {idx_name} on {tbl}...")
            cursor.execute(sql)
            print(f"  -> Done.")
        except Exception as e:
            print(f"  -> Error applying {idx_name}: {e}")

    conn.close()
    print("Database performance migration complete.")

if __name__ == "__main__":
    apply_optimizations()

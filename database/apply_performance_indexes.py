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
    db_name = str(cfg.get("database") or "").strip()
    if not db_name:
        raise ValueError("No database configured (strict no-fallback policy)")
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
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT is_read_committed_snapshot_on, snapshot_isolation_state, is_auto_close_on "
                "FROM sys.databases WHERE name = ?",
                (db_name,)
            )
            row = cursor.fetchone()
            rcsi_on = bool(row[0]) if row else False
            snapshot_on = (row[1] == 1) if row else False
            auto_close_on = bool(row[2]) if row and len(row) > 2 else False

            if auto_close_on:
                print(f"Disabling AUTO_CLOSE on [{db_name}] to prevent sleep/wake disconnections...")
                try:
                    cursor.execute(f"ALTER DATABASE [{db_name}] SET AUTO_CLOSE OFF WITH ROLLBACK IMMEDIATE;")
                    print(f"AUTO_CLOSE successfully disabled on [{db_name}].")
                except Exception as _ace:
                    print(f"Warning disabling AUTO_CLOSE on [{db_name}]: {_ace}")

            if not rcsi_on or not snapshot_on:
                print(f"Enabling READ_COMMITTED_SNAPSHOT on [{db_name}]...")
                if not rcsi_on:
                    cursor.execute(f"ALTER DATABASE [{db_name}] SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;")
                if not snapshot_on:
                    cursor.execute(f"ALTER DATABASE [{db_name}] SET ALLOW_SNAPSHOT_ISOLATION ON;")
                print("RCSI & Snapshot Isolation successfully enabled!")
                try:
                    from database.db import reset_connection
                    reset_connection()
                except Exception:
                    pass
            else:
                print(f"RCSI and Snapshot Isolation already enabled on [{db_name}].")

            # Disable AUTO_CLOSE across all user databases (database_id > 4) to protect all company databases
            try:
                cursor.execute("SELECT name FROM sys.databases WHERE database_id > 4 AND is_auto_close_on = 1")
                ac_dbs = [r[0] for r in cursor.fetchall()]
                for ac_db in ac_dbs:
                    try:
                        print(f"Disabling AUTO_CLOSE on user database [{ac_db}]...")
                        cursor.execute(f"ALTER DATABASE [{ac_db}] SET AUTO_CLOSE OFF WITH ROLLBACK IMMEDIATE;")
                    except Exception:
                        pass
            except Exception as _all_ac_err:
                print(f"Notice during bulk AUTO_CLOSE check: {_all_ac_err}")
        finally:
            conn.close()
    except Exception as e:
        print(f"Warning / Notice while enabling RCSI / configuring database settings: {e}")

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

    try:
        conn = pyodbc.connect(db_conn_str, autocommit=True)
        try:
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
                        ON [dbo].[sales] ([synced], [created_at]) INCLUDE ([id], [total], [invoice_no]);
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
        finally:
            conn.close()
        print("Database performance migration complete.")
    except Exception as e:
        print(f"Database performance migration error connecting to {db_name}: {e}")

if __name__ == "__main__":
    apply_optimizations()

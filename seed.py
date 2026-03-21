# =============================================================================
# migrate_credit_notes.py
#
# Run this once to create the credit_notes and credit_note_items tables.
#
# Usage:
#   cd C:\Users\DELL\Desktop\Pos Pyside6\pos_system
#   python migrate_credit_notes.py
# =============================================================================

import sys
import os

# Make sure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import get_connection

def migrate():
    conn = get_connection()
    cur  = conn.cursor()

    print("Creating credit_notes table...")
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'credit_notes'
        )
        CREATE TABLE credit_notes (
            id                  INT           IDENTITY(1,1) PRIMARY KEY,
            cn_number           NVARCHAR(40)  NOT NULL DEFAULT '',
            original_sale_id    INT           NOT NULL,
            original_invoice_no NVARCHAR(40)  NOT NULL DEFAULT '',
            frappe_ref          NVARCHAR(80)  NULL,
            frappe_cn_ref       NVARCHAR(80)  NULL,
            reason              NVARCHAR(255) NOT NULL DEFAULT 'Customer Return',
            total               DECIMAL(12,2) NOT NULL DEFAULT 0,
            currency            NVARCHAR(10)  NOT NULL DEFAULT 'USD',
            cashier_name        NVARCHAR(120) NOT NULL DEFAULT '',
            customer_name       NVARCHAR(120) NOT NULL DEFAULT '',
            cn_status           NVARCHAR(20)  NOT NULL DEFAULT 'pending_sync',
            created_at          DATETIME2     NOT NULL DEFAULT SYSDATETIME()
        )
    """)
    print("  credit_notes: OK")

    print("Creating credit_note_items table...")
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'credit_note_items'
        )
        CREATE TABLE credit_note_items (
            id             INT           IDENTITY(1,1) PRIMARY KEY,
            credit_note_id INT           NOT NULL
                               REFERENCES credit_notes(id) ON DELETE CASCADE,
            part_no        NVARCHAR(50)  NOT NULL DEFAULT '',
            product_name   NVARCHAR(120) NOT NULL DEFAULT '',
            qty            DECIMAL(12,4) NOT NULL DEFAULT 0,
            price          DECIMAL(12,2) NOT NULL DEFAULT 0,
            total          DECIMAL(12,2) NOT NULL DEFAULT 0,
            tax_type       NVARCHAR(20)  NOT NULL DEFAULT '',
            tax_rate       DECIMAL(8,4)  NOT NULL DEFAULT 0,
            tax_amount     DECIMAL(12,2) NOT NULL DEFAULT 0,
            reason         NVARCHAR(255) NOT NULL DEFAULT ''
        )
    """)
    print("  credit_note_items: OK")

    conn.commit()
    conn.close()
    print("\nDone. Both tables are ready.")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
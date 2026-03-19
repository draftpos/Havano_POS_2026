"""
migrate_frappe_ref.py
---------------------
Adds the frappe_ref column to the sales table.

This column stores the Frappe Sales Invoice document name
(e.g. ACC-SINV-2026-00565) after a local sale is successfully
pushed to Frappe. invoice_no is also overwritten with this value
so both columns hold the authoritative Frappe reference.

Run once:
    py migrate_frappe_ref.py
"""

from database.db import get_connection


def run():
    conn = get_connection()
    cur  = conn.cursor()

    print("Starting migration...\n")

    # ── 1. Add frappe_ref column ──────────────────────────────────────────────
    print("  Checking column: frappe_ref")
    cur.execute("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'sales' AND COLUMN_NAME = 'frappe_ref'
    """)
    if cur.fetchone()[0]:
        print("    Already exists — skipping.\n")
    else:
        cur.execute("ALTER TABLE sales ADD frappe_ref NVARCHAR(80) NULL")
        conn.commit()
        cur.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'sales' AND COLUMN_NAME = 'frappe_ref'
        """)
        if cur.fetchone()[0]:
            print("    Added frappe_ref NVARCHAR(80) NULL. ✅\n")
        else:
            print("    WARNING: Column may not have been added. Check manually. ⚠️\n")

    # ── 2. Back-fill: for already-synced sales that have no frappe_ref,
    #       copy invoice_no → frappe_ref so existing records are consistent.
    #       Only copies values that look like Frappe doc names (contain 'SINV').
    print("  Back-filling frappe_ref from invoice_no for already-synced sales...")
    cur.execute("""
        UPDATE sales
        SET frappe_ref = invoice_no
        WHERE synced = 1
          AND (frappe_ref IS NULL OR frappe_ref = '')
          AND invoice_no LIKE '%SINV%'
    """)
    conn.commit()
    print(f"    {cur.rowcount} row(s) back-filled. ✅\n")

    conn.close()
    print("Migration complete. Restart your POS application.")


if __name__ == "__main__":
    run()
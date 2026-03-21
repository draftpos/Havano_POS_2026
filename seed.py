# =============================================================================
# wipe_sales.py  —  Havano POS
#
# Wipes all sales-related data cleanly in the correct order
# (respects foreign key constraints).
#
# Tables cleared:
#   payment_entries, credit_note_items, credit_notes,
#   sale_items, sales
#
# Tables NOT touched:
#   products, users, customers, company_defaults,
#   shifts, shift_rows, gl_accounts, exchange_rates, etc.
#
# Usage:
#   python wipe_sales.py
# =============================================================================

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run():
    try:
        from database.db import get_connection
    except Exception as e:
        print(f"[ERROR] Cannot import database.db: {e}")
        sys.exit(1)

    print("\n======================================")
    print("  Havano POS — Wipe Sales Data")
    print("======================================\n")
    print("  This will permanently delete:")
    print("    - All payment entries")
    print("    - All credit notes and credit note items")
    print("    - All sales and sale items")
    print("\n  Products, customers, users and settings")
    print("  will NOT be affected.\n")

    confirm = input("  Type YES to confirm: ").strip()
    if confirm != "YES":
        print("\n  Cancelled.\n")
        sys.exit(0)

    conn = get_connection()
    cur  = conn.cursor()

    steps = [
        ("payment_entries",   "DELETE FROM payment_entries"),
        ("credit_note_items", "DELETE FROM credit_note_items"),
        ("credit_notes",      "DELETE FROM credit_notes"),
        ("sale_items",        "DELETE FROM sale_items"),
        ("sales",             "DELETE FROM sales"),
    ]

    total = 0
    for table, sql in steps:
        try:
            cur.execute(sql)
            n = cur.rowcount
            total += n
            print(f"  [+] {table:<22} {n} rows deleted")
        except Exception as e:
            print(f"  [!] {table:<22} ERROR: {e}")
            conn.rollback()
            conn.close()
            print("\n  Rolled back. No data was changed.\n")
            sys.exit(1)

    # Reset invoice number sequence so next sale starts fresh
    try:
        cur.execute("""
            IF EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='company_defaults')
            UPDATE company_defaults SET invoice_start_number = '0'
        """)
        print(f"  [+] invoice_start_number     reset to 0")
    except Exception:
        pass

    conn.commit()
    conn.close()

    print(f"\n  Done. {total} total rows deleted.")
    print("\n======================================")
    print("  Wipe complete!")
    print("======================================\n")


if __name__ == "__main__":
    run()
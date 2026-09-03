import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from database.db import get_connection

def update_mop():
    conn = get_connection()
    cur = conn.cursor()
    
    # Update modes_of_payment account_currency to ZAR for Cash and Card
    cur.execute("UPDATE modes_of_payment SET account_currency = 'ZAR' WHERE LOWER(name) IN ('cash', 'card') OR account_currency IS NULL OR account_currency = 'USD'")
    print(f"Updated {cur.rowcount} mode(s) of payment to ZAR.")
    
    # Also update shift_rows for active open shift to ZAR
    cur.execute("""
        UPDATE shift_rows
        SET currency = 'ZAR'
        WHERE shift_id IN (SELECT id FROM shifts WHERE end_time IS NULL)
          AND (currency IS NULL OR currency = 'USD')
    """)
    print(f"Updated {cur.rowcount} open shift row(s) to ZAR.")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_mop()

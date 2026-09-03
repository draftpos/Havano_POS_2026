
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from database.db import get_connection

def check_sales():
    conn = get_connection()
    cur = conn.cursor()
    print("--- Recent Sales Sync Status ---")
    # Check for sales with errors
    cur.execute("SELECT TOP 5 invoice_no, customer_name, total, sync_error FROM sales WHERE synced = 0 AND sync_error IS NOT NULL ORDER BY id DESC")
    rows = cur.fetchall()
    if not rows:
        print("No unsynced sales with error messages found in 'sales' table.")
    else:
        for row in rows:
            print(f"Invoice: {row[0]}")
            print(f"Customer: {row[1]}")
            print(f"Total: {row[2]}")
            print(f"Error: {row[3]}")
            print("-" * 20)
    conn.close()

if __name__ == "__main__":
    check_sales()

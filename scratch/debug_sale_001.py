
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from database.db import get_connection

def debug_sale():
    conn = get_connection()
    cur = conn.cursor()
    print("--- Debug Sale 000000001 ---")
    cur.execute("SELECT id, invoice_no, customer_name, total, synced, syncing, sync_error FROM sales WHERE invoice_no = '000000001'")
    row = cur.fetchone()
    if row:
        cols = [d[0] for d in cur.description]
        data = dict(zip(cols, row))
        for k, v in data.items():
            print(f"{k}: {v}")
    else:
        print("Sale 000000001 not found.")
    conn.close()

if __name__ == "__main__":
    debug_sale()

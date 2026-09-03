
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from database.db import get_connection, fetchall_dicts

def check_sales():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT TOP 5 id, invoice_no, total, method, synced, syncing, sync_error FROM sales ORDER BY id DESC")
    rows = fetchall_dicts(cur)
    for r in rows:
        print(r)
    conn.close()

if __name__ == "__main__":
    check_sales()

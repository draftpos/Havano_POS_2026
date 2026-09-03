
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from database.db import get_connection

def check_errors():
    conn = get_connection()
    cur = conn.cursor()
    print("--- Recent Sync Errors ---")
    cur.execute("SELECT TOP 5 doc_ref, error_msg, occurred_at FROM sync_errors ORDER BY id DESC")
    for row in cur.fetchall():
        print(f"Ref: {row[0]}")
        print(f"Error: {row[1]}")
        print(f"Time: {row[2]}")
        print("-" * 20)
    conn.close()

if __name__ == "__main__":
    check_errors()

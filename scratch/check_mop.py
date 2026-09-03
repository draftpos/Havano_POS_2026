
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from database.db import get_connection, fetchall_dicts

def check_mop():
    conn = get_connection()
    cur = conn.cursor()
    print("--- modes_of_payment columns ---")
    cur.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='modes_of_payment'")
    for row in cur.fetchall():
        print(f"{row[0]} ({row[1]})")
    
    print("\n--- current data ---")
    cur.execute("SELECT * FROM modes_of_payment")
    rows = fetchall_dicts(cur)
    for r in rows:
        print(r)
    conn.close()

if __name__ == "__main__":
    check_mop()

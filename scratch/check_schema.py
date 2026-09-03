
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from database.db import get_connection

def check_schema():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'sales'")
    for r in cur.fetchall():
        print(r[0])
    conn.close()

if __name__ == "__main__":
    check_schema()

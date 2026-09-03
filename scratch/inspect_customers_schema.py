import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection, fetchall_dicts

conn = get_connection()
cur = conn.cursor()

cur.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'customers'")
for r in cur.fetchall():
    print(f"{r[0]}: {r[1]}")

conn.close()

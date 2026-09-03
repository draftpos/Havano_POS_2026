import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT * FROM item_prices WHERE part_no LIKE 'TRIATIX 2L%'")
cols = [c[0] for c in cur.description]
print("Columns:", cols)
for r in cur.fetchall():
    print(" ", dict(zip(cols, r)))

conn.close()

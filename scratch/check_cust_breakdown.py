import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection, fetchall_dicts

conn = get_connection()
cur = conn.cursor()

cur.execute("""
    SELECT DISTINCT cu.default_price_list_id, pl.name AS price_list_name, COUNT(*) as count
    FROM customers cu
    LEFT JOIN price_lists pl ON pl.id = cu.default_price_list_id
    GROUP BY cu.default_price_list_id, pl.name
""")
rows = fetchall_dicts(cur)
print("Customer price list breakdown:")
for r in rows:
    print(" ", r)

cur.execute("SELECT * FROM price_lists")
print("\nAll rows in price_lists table:")
for pl in fetchall_dicts(cur):
    print(" ", pl)

conn.close()

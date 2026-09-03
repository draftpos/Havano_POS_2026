import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection, fetchall_dicts

conn = get_connection()
cur = conn.cursor()

cur.execute("""
    SELECT cu.id, cu.customer_name, cu.default_price_list_id, pl.name AS price_list_name, cu.custom_warehouse_id, cu.custom_cost_center_id, cu.balance
    FROM customers cu
    LEFT JOIN price_lists pl ON pl.id = cu.default_price_list_id
    ORDER BY cu.id ASC
""")
rows = fetchall_dicts(cur)
print(f"Total customers in DB: {len(rows)}")
for r in rows[:15]:
    print(" ", r)

cur.execute("SELECT COUNT(*) FROM customers WHERE default_price_list_id IS NULL")
print("Customers with NULL price list:", cur.fetchone()[0])

conn.close()

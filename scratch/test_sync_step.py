import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.customer_sync_service import sync_customers
from database.db import get_connection, fetchall_dicts

res = sync_customers()
print("sync_customers result:", res)

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT id, customer_name, default_price_list_id, custom_warehouse_id, custom_cost_center_id, balance FROM customers WHERE default_price_list_id IS NOT NULL")
rows = fetchall_dicts(cur)
print(f"Customers with price list set ({len(rows)}):")
for r in rows[:10]:
    print(" ", r)
conn.close()

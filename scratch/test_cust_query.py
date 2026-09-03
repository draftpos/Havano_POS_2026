import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.customer import get_all_customers, search_customers
from database.db import get_connection, fetchall_dicts

print("--- TESTING get_all_customers() ---")
try:
    custs = get_all_customers()
    print(f"get_all_customers returned: {len(custs)} customers")
    for c in custs[:10]:
        print(" ", c.get("customer_name"), "| Price list:", c.get("price_list_name"))
except Exception as e:
    print("Error in get_all_customers:", e)

print("\n--- DIRECT DB QUERY ---")
try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM customers")
    cnt = cur.fetchone()[0]
    print(f"Raw count in dbo.customers: {cnt}")
    conn.close()
except Exception as e:
    print("Error in direct DB query:", e)

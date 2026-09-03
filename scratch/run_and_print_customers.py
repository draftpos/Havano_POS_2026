import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.customer_sync_service import sync_customers
from models.customer import get_all_customers
from database.db import get_connection, fetchall_dicts

print("1. Running customer sync service...")
res = sync_customers()
print("   Sync result:", res)

print("\n2. Fetching all customers from local DB...")
custs = get_all_customers()
print(f"   Total customers in database: {len(custs)}")

print("\n3. Customers and their Price Lists:")
print(f"{'#':<4} | {'Customer Name':<38} | {'Price List':<22} | {'Warehouse'}")
print("-" * 80)
for idx, c in enumerate(custs, start=1):
    pl = c.get("price_list_name") or "None"
    wh = c.get("warehouse_name") or "None"
    print(f"{idx:<4} | {c.get('customer_name', ''):<38} | {pl:<22} | {wh}")

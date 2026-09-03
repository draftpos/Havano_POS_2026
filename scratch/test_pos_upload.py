import sys
import os
import json

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

print("=== CHECKING SALES TABLE IN DB ===")
from database.db import get_connection, fetchall_dicts

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT TOP 10 id, invoice_no, synced, syncing, fiscal_status, created_at, sync_error FROM sales ORDER BY id DESC")
rows = fetchall_dicts(cur)
conn.close()

print(f"Total recent sales in DB: {len(rows)}")
for r in rows:
    print(r)

print("\n=== TESTING get_unsynced_sales() ===")
from models.sale import get_unsynced_sales
unsynced = get_unsynced_sales()
print(f"Unsynced sales returned by get_unsynced_sales(): {len(unsynced)}")
for u in unsynced:
    print(f"  - Sale ID {u.get('id')}, Invoice: {u.get('invoice_no')}, Fiscal: {u.get('fiscal_status')}")

print("\n=== TESTING push_unsynced_sales() ===")
from services.pos_upload_service import push_unsynced_sales
res = push_unsynced_sales()
print("push_unsynced_sales() Result:", res)

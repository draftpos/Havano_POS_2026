import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection

conn = get_connection()
cur = conn.cursor()

print("=== Warehouses ===")
cur.execute("SELECT id, name, company_id, is_default FROM warehouses")
for r in cur.fetchall():
    print(" ", r)

print("\n=== Company Defaults (Branch / Profile config) ===")
cur.execute("SELECT id, company_name, server_company, server_warehouse, server_profile, server_shop_id, default_price_list_id, server_walk_in_customer, system_mode FROM company_defaults")
for r in cur.fetchall():
    print(" ", r)

print("\n=== Price Lists ===")
cur.execute("SELECT id, name, selling FROM price_lists")
for r in cur.fetchall():
    print(" ", r)

conn.close()

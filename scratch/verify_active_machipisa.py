import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.company_defaults import get_defaults
from database.db import get_connection

defs = get_defaults() or {}
print("=== Active Company Defaults in DB ===")
print(f"  Company / Warehouse : '{defs.get('company_name')}' / '{defs.get('server_warehouse')}'")
print(f"  Shop ID             : '{defs.get('server_shop_id')}'")
print(f"  Terminal            : '{defs.get('server_terminal_name')}' (ID: {defs.get('server_terminal_id')})")
print(f"  Default Price List ID: {defs.get('default_price_list_id')}")

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT id, name FROM price_lists WHERE id = ?", (defs.get("default_price_list_id") or 0,))
row = cur.fetchone()
print(f"  Price List Name     : '{row[1] if row else 'None'}'")

cur.execute("SELECT customer_name, default_price_list_id FROM customers WHERE customer_name LIKE '%Cash%'")
print("  Cash Customer       :", cur.fetchone())

conn.close()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection
from models.company_defaults import get_defaults

conn = get_connection()
cur = conn.cursor()

print("=== 1. Active Company Defaults ===")
defs = get_defaults() or {}
print(f"  Warehouse / Branch : '{defs.get('server_warehouse')}'")
print(f"  Shop ID            : '{defs.get('server_shop_id')}'")
print(f"  Default Price List ID: {defs.get('default_price_list_id')}")

cur.execute("SELECT id, name, selling FROM price_lists WHERE id = ?", (defs.get("default_price_list_id") or 0,))
row = cur.fetchone()
print(f"  Resolved Branch Default Price List: {row[1] if row else 'None'}")

print("\n=== 2. All Price Lists in Local DB ===")
cur.execute("SELECT id, name, selling FROM price_lists")
for r in cur.fetchall():
    print(f"  ID: {r[0]} | Name: '{r[1]}' | Selling: {r[2]}")

print("\n=== 3. Customers in Local DB ===")
cur.execute("""
    SELECT c.id, c.customer_name, c.default_price_list_id, pl.name as price_list_name
    FROM customers c
    LEFT JOIN price_lists pl ON c.default_price_list_id = pl.id
""")
for r in cur.fetchall():
    print(f"  Customer '{r[1]}' -> Price List ID: {r[2]} ({r[3]})")

conn.close()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection

conn = get_connection()
cur = conn.cursor()

print("=== 1. Company Defaults (Branch / POS Profile Default Price List) ===")
cur.execute("""
    SELECT cd.id, cd.company_name, cd.server_warehouse, cd.server_profile, 
           cd.default_price_list_id, pl.name as default_price_list_name
    FROM company_defaults cd
    LEFT JOIN price_lists pl ON cd.default_price_list_id = pl.id
""")
for r in cur.fetchall():
    print(f"  Branch: '{r[2]}' | Default Price List ID: {r[4]} -> '{r[5]}'")

print("\n=== 2. All Price Lists in DB ===")
cur.execute("SELECT id, name, selling FROM price_lists")
for r in cur.fetchall():
    print(f"  ID: {r[0]} | Name: '{r[1]}' | Selling: {r[2]}")

print("\n=== 3. Walk-in / Cash Customer Price List ===")
cur.execute("""
    SELECT c.id, c.customer_name, c.default_price_list_id, pl.name as customer_price_list_name
    FROM customers c
    LEFT JOIN price_lists pl ON c.default_price_list_id = pl.id
    WHERE c.customer_name LIKE '%Cash%'
""")
for r in cur.fetchall():
    print(f"  Customer: '{r[1]}' | Price List ID: {r[2]} -> '{r[3]}'")

print("\n=== 4. Other Customers with Assigned Price Lists ===")
cur.execute("""
    SELECT c.id, c.customer_name, c.default_price_list_id, pl.name as customer_price_list_name
    FROM customers c
    LEFT JOIN price_lists pl ON c.default_price_list_id = pl.id
    WHERE c.customer_name NOT LIKE '%Cash%'
""")
for r in cur.fetchall():
    print(f"  Customer: '{r[1]}' | Price List ID: {r[2]} -> '{r[3]}'")

conn.close()

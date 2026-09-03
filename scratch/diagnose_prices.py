import sys, os, logging
sys.path.append(os.getcwd())
logging.basicConfig(level=logging.INFO)

from models.company_defaults import get_defaults
from database.db import get_connection

d = get_defaults() or {}
pl_id = d.get("default_price_list_id")
print(f"default_price_list_id: {pl_id}")

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT id, name FROM price_lists")
rows = cur.fetchall()
print(f"price_lists: {rows}")

# Now run product sync
from services.odoo.sync_service import sync_products_odoo
r = sync_products_odoo()
print(f"\nsync result: {r}")

cur.execute("SELECT COUNT(*) FROM item_prices")
print(f"item_prices after sync: {cur.fetchone()[0]} rows")

cur.execute("SELECT TOP 5 part_no, price_list, uom, price FROM item_prices")
for row in cur.fetchall():
    print(f"  {row}")

conn.close()

from database.db import get_connection
from models.product_bundle import get_bundle_prices_map

print("--- DEBUG BUNDLE PRICES ---")
prices = get_bundle_prices_map()
print(f"Total bundles with prices: {len(prices)}")
for name, price in prices.items():
    print(f"  Bundle: '{name}' | Price: {price}")

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT id, name FROM product_bundles")
bundles = cur.fetchall()
print(f"\nAll bundles in product_bundles table: {len(bundles)}")
for b in bundles:
    print(f"  ID: {b[0]} | Name: '{b[1]}'")

cur.execute("SELECT bundle_id, item_code, quantity, rate FROM bundle_items")
items = cur.fetchall()
print(f"\nAll bundle items in bundle_items table: {len(items)}")
for i in items:
    print(f"  BID: {i[0]} | Code: '{i[1]}' | Qty: {i[2]} | Rate: {i[3]}")
conn.close()

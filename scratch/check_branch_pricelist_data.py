import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection

conn = get_connection()
cur = conn.cursor()

print("=== 1. Check all price lists in DB ===")
cur.execute("SELECT id, name, selling FROM price_lists")
for r in cur.fetchall():
    print(" ", r)

print("\n=== 2. Check item_prices breakdown by price_list ===")
cur.execute("""
    SELECT price_list, COUNT(*) as total_items, MIN(price) as min_price, MAX(price) as max_price
    FROM item_prices
    GROUP BY price_list
""")
for r in cur.fetchall():
    print(" ", r)

print("\n=== 3. Sample items priced in 'Retail' ===")
cur.execute("""
    SELECT TOP 10 part_no, uom, price_list, price
    FROM item_prices
    WHERE price_list = 'Retail'
""")
for r in cur.fetchall():
    print(" ", r)

print("\n=== 4. Sample items priced in 'Standard Selling' ===")
cur.execute("""
    SELECT TOP 10 part_no, uom, price_list, price
    FROM item_prices
    WHERE price_list = 'Standard Selling'
""")
for r in cur.fetchall():
    print(" ", r)

conn.close()

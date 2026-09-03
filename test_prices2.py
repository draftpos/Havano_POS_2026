import sys
sys.path.insert(0, '.')
from database.db import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT customer_name, default_price_list_id FROM customers WHERE customer_name LIKE '%Cash Customer%'")
print('Cash Customer:', cur.fetchall())

cur.execute("SELECT part_no FROM item_prices GROUP BY part_no HAVING COUNT(DISTINCT price) > 1")
diff_prices = cur.fetchall()
test_part = diff_prices[0][0] if diff_prices else None

if test_part:
    cur.execute("SELECT name FROM products WHERE part_no = ?", (test_part,))
    prod_row = cur.fetchone()
    prod_name = prod_row[0] if prod_row else "Unknown"
    cur.execute("SELECT price_list, price FROM item_prices WHERE part_no = ?", (test_part,))
    prices = cur.fetchall()
    print(f'Test Product: {prod_name} ({test_part}) -> {prices}')
else:
    print("No product found with different prices across pricelists.")
conn.close()

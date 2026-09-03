import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection

conn = get_connection()
cur = conn.cursor()
print("=== Customers Table Schema ===")
cur.execute("SELECT TOP 1 * FROM customers")
print("Columns in customers:", [col[0] for col in cur.description])
row = cur.fetchone()
print("Sample row:", dict(zip([col[0] for col in cur.description], row)))

cur.execute("SELECT id, customer_name, default_price_list_id FROM customers")
for r in cur.fetchall():
    print(f"Customer: id={r[0]}, name={r[1]}, default_price_list_id={r[2]}")

cur.execute("SELECT id, name FROM price_lists")
for r in cur.fetchall():
    print(f"Price List: id={r[0]}, name={r[1]}")

cur.execute("SELECT part_no, uom, price_list, price FROM item_prices WHERE part_no LIKE 'TRIATIX 2L%'")
for r in cur.fetchall():
    print(f"Item Price: part_no={r[0]}, uom={r[1]}, price_list={r[2]}, price={r[3]}")

conn.close()

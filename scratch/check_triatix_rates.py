import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection

conn = get_connection()
cur = conn.cursor()

cur.execute("SELECT part_no, name, price FROM products WHERE part_no LIKE '%TRIATIX%'")
for r in cur.fetchall():
    print("Product:", r)

print("--- item_prices table for TRIATIX ---")
cur.execute("SELECT id, part_no, uom, price_list, price_type, price FROM item_prices WHERE part_no LIKE '%TRIATIX%'")
for r in cur.fetchall():
    print("Item Price:", r)

conn.close()

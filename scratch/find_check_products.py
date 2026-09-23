import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection

conn = get_connection()
cur = conn.cursor()

cur.execute("""
    SELECT r.part_no, p.name, r.uom, r.price
    FROM item_prices r
    INNER JOIN products p ON r.part_no = p.part_no
    WHERE r.price_list = 'Retail'
      AND r.part_no NOT IN (SELECT part_no FROM item_prices WHERE price_list = 'Standard Selling')
""")
rows = cur.fetchall()
print(f"Found {len(rows)} items that ONLY exist in Retail:")
for r in rows:
    print(f"Item: '{r[0]}' | Name: '{r[1]}' | UOM: '{r[2]}' -> Retail: ${float(r[3]):.2f}")

conn.close()

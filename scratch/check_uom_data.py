import sys, os
sys.path.append(os.getcwd())
from database.db import get_connection

conn = get_connection()
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM product_uom_prices")
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(DISTINCT part_no) FROM product_uom_prices")
parts = cur.fetchone()[0]
print(f"Total UOM rows: {total}, Distinct products: {parts}, Per product: {total/parts:.1f}")

cur.execute("SELECT DISTINCT uom, price FROM product_uom_prices ORDER BY uom")
print(f"Distinct (uom, price) combos:")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

# Check a product that should NOT have crate UOMs
cur.execute("SELECT p.part_no, p.name FROM products p WHERE p.name LIKE '%board%' OR p.name LIKE '%White%'")
for r in cur.fetchall():
    part = r[0]
    print(f"\nProduct: {r[0]} - {r[1]}")
    cur.execute("SELECT uom, price FROM product_uom_prices WHERE part_no=?", (part,))
    for u in cur.fetchall():
        print(f"  UOM: {u[0]}, Price: {u[1]}")

conn.close()

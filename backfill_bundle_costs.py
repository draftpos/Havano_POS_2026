import sys, json
sys.path.append(r"c:\Users\DELL\New_POS\Havano_POS_2026")
from database.db import get_connection

conn = get_connection()
cur = conn.cursor()

# Fetch all bundles
cur.execute("SELECT part_no, bundle_lines, price FROM products WHERE is_product_bundle = 1")
bundles = cur.fetchall()

updated = 0
for part_no, lines_json, price in bundles:
    try:
        items = json.loads(lines_json or "[]")
        total_cost = 0.0
        for item in items:
            code = (item.get("item_code") or item.get("part_no") or "").strip()
            qty  = float(item.get("quantity") or 0)
            if code and qty > 0:
                cur.execute("SELECT cost_price FROM products WHERE part_no = ?", (code,))
                row = cur.fetchone()
                if row and row[0]:
                    total_cost += qty * float(row[0])
        
        cur.execute("""
            UPDATE products
            SET bundle_cost_total = ?, bundle_sale_total = ?,
                cost_price = CASE WHEN cost_price = 0 OR cost_price IS NULL THEN ? ELSE cost_price END
            WHERE part_no = ?
        """, (total_cost, float(price or 0), total_cost, part_no))
        print(f"  {part_no}: cost=${total_cost:.2f}, sale=${price:.2f}")
        updated += 1
    except Exception as e:
        print(f"  ERROR for {part_no}: {e}")

conn.commit()
conn.close()
print(f"\nBackfilled {updated} bundles with cost totals.")

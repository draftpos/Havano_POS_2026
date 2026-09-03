import sys
sys.path.append(r"c:\Users\DELL\New_POS\Havano_POS_2026")
from database.db import get_connection

conn = get_connection()
cur = conn.cursor()

try:
    # If a product is a bundle, and it has a row in item_prices where price <= 0,
    # we should update it to the parent product's calculated price.
    cur.execute("""
        UPDATE item_prices
        SET price = p.price
        FROM item_prices ip
        INNER JOIN products p ON ip.part_no = p.part_no
        WHERE p.is_product_bundle = 1
          AND ip.price <= 0
    """)
    conn.commit()
    print(f"Updated item_prices for bundles: {cur.rowcount} rows.")
except Exception as e:
    print(f"Error: {e}")
    conn.rollback()
finally:
    conn.close()

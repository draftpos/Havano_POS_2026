import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection, fetchall_dicts

def check_database():
    try:
        conn = get_connection()
        cur = conn.cursor()
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        return

    print("=== 1. PRICE_LISTS TABLE ===")
    try:
        cur.execute("SELECT * FROM price_lists")
        pls = fetchall_dicts(cur)
        print(f"Total price_lists found: {len(pls)}")
        for pl in pls:
            print("  ", pl)
    except Exception as e:
        print(f"Error querying price_lists: {e}")

    print("\n=== 2. ITEM_PRICES TABLE ===")
    try:
        cur.execute("SELECT COUNT(*) FROM item_prices")
        count = cur.fetchone()[0]
        print(f"Total rows in item_prices: {count}")
        cur.execute("SELECT DISTINCT price_list FROM item_prices")
        dist_pls = cur.fetchall()
        print("Distinct price_list names in item_prices:", [r[0] for r in dist_pls])
        
        cur.execute("SELECT TOP 10 * FROM item_prices")
        sample = fetchall_dicts(cur)
        print("Sample 10 item_prices rows:")
        for r in sample:
            print("  ", r)
    except Exception as e:
        print(f"Error querying item_prices: {e}")

    print("\n=== 3. PRODUCT_UOM_PRICES TABLE (if exists) ===")
    try:
        cur.execute("SELECT COUNT(*) FROM product_uom_prices")
        count = cur.fetchone()[0]
        print(f"Total rows in product_uom_prices: {count}")
        cur.execute("SELECT TOP 5 * FROM product_uom_prices")
        print("Sample product_uom_prices:", fetchall_dicts(cur))
    except Exception as e:
        print(f"product_uom_prices check: {e}")

    print("\n=== 4. CUSTOMERS TABLE (PRICE LIST FIELDS) ===")
    try:
        # Check columns on customers
        cur.execute("""
            SELECT COLUMN_NAME, DATA_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'customers'
        """)
        cols = [r[0] for r in cur.fetchall()]
        pl_cols = [c for c in cols if 'price' in c.lower() or 'list' in c.lower()]
        print(f"Price-related columns in customers table: {pl_cols}")

        cur.execute("SELECT COUNT(*) FROM customers")
        total_cust = cur.fetchone()[0]
        print(f"Total customers: {total_cust}")

        cur.execute("SELECT TOP 10 id, name, default_price_list_id, price_list_name FROM customers WHERE price_list_name IS NOT NULL OR default_price_list_id IS NOT NULL")
        rows = fetchall_dicts(cur)
        print(f"Sample customers with price lists set ({len(rows)} found):")
        for r in rows:
            print("  ", r)
        
        if not rows:
            cur.execute("SELECT TOP 5 id, name, default_price_list_id, price_list_name FROM customers")
            print("Sample 5 customers overall:")
            for r in fetchall_dicts(cur):
                print("  ", r)
    except Exception as e:
        print(f"Error checking customers: {e}")

    print("\n=== 5. PRODUCTS TABLE (PRICE & FIELDS) ===")
    try:
        cur.execute("SELECT COUNT(*) FROM products")
        total_prod = cur.fetchone()[0]
        print(f"Total products: {total_prod}")
        cur.execute("SELECT TOP 5 part_no, name, price, cost_price, uom FROM products")
        for r in fetchall_dicts(cur):
            print("  ", r)
    except Exception as e:
        print(f"Error checking products: {e}")

    conn.close()

if __name__ == "__main__":
    check_database()

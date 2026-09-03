import os
import sys
import json

# Ensure correct path
project_dir = r"c:\Users\DELL\New_POS\Havano_POS_2026"
sys.path.append(project_dir)

from database.db import get_connection

def update_bundle_prices():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT part_no, bundle_lines FROM products WHERE is_product_bundle = 1 AND bundle_lines IS NOT NULL AND bundle_lines != ''")
        bundles = cur.fetchall()
        
        updated = 0
        for part_no, lines_str in bundles:
            try:
                lines = json.loads(lines_str)
            except:
                continue
            
            total_price = 0.0
            total_cost = 0.0
            
            for item in lines:
                c_code = item.get('item_code')
                qty = float(item.get('quantity', 0))
                
                cur.execute("SELECT cost_price, price FROM products WHERE part_no = ?", (c_code,))
                crow = cur.fetchone()
                if crow:
                    c_cost = float(crow[0] or 0)
                    c_price = float(crow[1] or 0)
                    if c_price <= 0:
                        c_price = float(item.get('rate', 0))
                else:
                    c_cost = 0.0
                    c_price = float(item.get('rate', 0))
                
                total_cost += qty * c_cost
                total_price += qty * c_price
                
            cur.execute("""
                UPDATE products 
                SET price = ?, cost_price = ? 
                WHERE part_no = ?
            """, (total_price, total_cost, part_no))
            updated += cur.rowcount
            
        conn.commit()
        print(f"Updated {updated} bundles.")
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_bundle_prices()

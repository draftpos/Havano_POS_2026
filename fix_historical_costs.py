import os
import sys

# Ensure correct path
project_dir = r"c:\Users\DELL\New_POS\Havano_POS_2026"
sys.path.append(project_dir)

from database.db import get_connection

def fix_historical_costs():
    conn = get_connection()
    cur = conn.cursor()
    try:
        print("Backfilling historical cost prices...")
        cur.execute("""
            UPDATE sale_items
            SET cost_price = COALESCE((SELECT TOP 1 cost_price FROM products WHERE products.part_no = sale_items.part_no), 0)
            WHERE cost_price = 0 OR cost_price IS NULL
        """)
        affected = cur.rowcount
        conn.commit()
        print(f"Fixed {affected} sale items!")
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_historical_costs()

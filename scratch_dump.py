import sys
import os

sys.path.insert(0, r"C:\Users\DELL\New_POS\Havano_POS_2026")
from database.db import get_connection

def dump():
    conn = get_connection()
    cur = conn.cursor()
    
    print("--- product_batches ---")
    try:
        cur.execute("SELECT * FROM product_batches")
        rows = cur.fetchall()
        for r in rows:
            print(tuple(r))
    except Exception as e:
        print(f"Error: {e}")
        
    print("\n--- stock_entry_items ---")
    try:
        cur.execute("SELECT TOP 5 id, product_id, batch_no, expiry_date FROM stock_entry_items ORDER BY id DESC")
        rows = cur.fetchall()
        for r in rows:
            print(tuple(r))
    except Exception as e:
        print(f"Error: {e}")

    conn.close()

if __name__ == "__main__":
    dump()

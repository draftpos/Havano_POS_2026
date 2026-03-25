import sys
import os

# Add current directory to path so it can find 'database' folder
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from database.db import get_connection
except ImportError:
    print("❌ Error: Could not find database/db.py. Run this from the root folder.")
    sys.exit(1)

def wipe_sales_data():
    print("--- SQL Server Sales Wipe ---")
    print("This will delete ALL Sales Orders and ALL Order Items.")
    confirm = input("Type 'WIPE' to proceed: ")
    
    if confirm != "WIPE":
        print("Aborted.")
        return

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # 1. Wipe CHILD table first (Items)
        print("Cleaning sales_order_item...")
        cur.execute("DELETE FROM sales_order_item")
        cur.execute("DBCC CHECKIDENT ('sales_order_item', RESEED, 0)")
        
        # 2. Wipe PARENT table (Orders)
        print("Cleaning sales_order...")
        cur.execute("DELETE FROM sales_order")
        cur.execute("DBCC CHECKIDENT ('sales_order', RESEED, 0)")

        conn.commit()
        print("✅ SUCCESS: Sales data wiped and ID counters reset.")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    wipe_sales_data()
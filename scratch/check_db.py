
import pyodbc
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.db import get_connection

def check_db():
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        print("--- PRICE LISTS ---")
        cur.execute("SELECT id, name FROM price_lists")
        for row in cur.fetchall():
            print(f"ID: {row[0]}, Name: '{row[1]}'")
            
        print("\n--- DEFAULT CUSTOMER ---")
        cur.execute("SELECT id, customer_name, default_price_list_id FROM customers WHERE customer_name = 'Default'")
        row = cur.fetchone()
        if row:
            print(f"ID: {row[0]}, Name: '{row[1]}', PriceListID: {row[2]}")
            if row[2]:
                cur.execute("SELECT name FROM price_lists WHERE id = ?", (row[2],))
                pl = cur.fetchone()
                if pl:
                    print(f"   Price List Name: '{pl[0]}'")
        else:
            print("Default customer not found.")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()

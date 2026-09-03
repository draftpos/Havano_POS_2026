import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from database.db import get_connection

def check_mode():
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        print("--- Checking pos_settings table ---")
        try:
            cur.execute("SELECT setting_key, setting_value FROM pos_settings")
            for row in cur.fetchall():
                print(f"Key: {row[0]}, Value: {row[1]}")
        except Exception as e:
            print("Error querying pos_settings:", e)
            
        print("\n--- Checking company_defaults table ---")
        try:
            cur.execute("SELECT system_mode, server_database FROM company_defaults")
            for row in cur.fetchall():
                print(f"system_mode: {row[0]}, server_database: {row[1]}")
        except Exception as e:
            print("Error querying company_defaults:", e)
            
        conn.close()
    except Exception as e:
        print("Database connection error:", e)

if __name__ == "__main__":
    check_mode()

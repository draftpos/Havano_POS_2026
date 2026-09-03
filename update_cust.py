import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from database.db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE customers SET customer_name = 'Cash Customer' WHERE customer_name = 'Default'")
    conn.commit()
    conn.close()
    print("Updated Database Customers.")
except Exception as e:
    print("Error:", e)

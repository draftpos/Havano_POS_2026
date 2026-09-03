import sys
from database.db import get_connection

def test():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT TOP 1 COALESCE(butchery_mode, '0') FROM company_defaults")
    row = cur.fetchone()
    print("butchery_mode:", row)
    
    cur.execute("SELECT id, part_no, is_butchery_product FROM products")
    print("Products:", cur.fetchall())

if __name__ == "__main__":
    test()

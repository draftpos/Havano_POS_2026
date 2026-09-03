import sys
import os

sys.path.append(os.path.dirname(__file__))

from database.db import get_connection

conn = get_connection()
cur = conn.cursor()

cur.execute("SELECT part_no, name, is_butchery_product FROM products WHERE name LIKE '%Chicken%'")
print("Chicken products:")
for row in cur.fetchall():
    print(row)

cur.execute("SELECT TOP 1 COALESCE(butchery_mode, '0') FROM company_defaults")
print("Butchery mode:", cur.fetchone())

conn.close()

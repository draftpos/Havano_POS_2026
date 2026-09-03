import sys
sys.path.append('.')
from database.db import get_connection, fetchall_dicts

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT part_no, name FROM products WHERE part_no='35454'")
print("Products:", fetchall_dicts(cur))

cur.execute("SELECT * FROM item_prices WHERE part_no='35454'")
print("Prices:", fetchall_dicts(cur))

cur.execute("SELECT part_no, name FROM products WHERE name='Sugar'")
print("Sugar:", fetchall_dicts(cur))

cur.execute("SELECT * FROM item_prices WHERE part_no='92341'") # assuming 92341 is Sugar
print("Sugar Prices:", fetchall_dicts(cur))

import sys
sys.path.append('.')
from database.db import get_connection, fetchall_dicts
conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT * FROM item_prices WHERE part_no='52400'")
print(fetchall_dicts(cur))

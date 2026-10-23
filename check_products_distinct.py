import sys
sys.path.append('c:/Users/user/Desktop/Havano_POS_2026-main')
from database.db import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT DISTINCT print_after_order FROM products")
print('Distinct values for print_after_order:', cur.fetchall())

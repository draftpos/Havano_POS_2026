import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection

conn = get_connection()
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM customers WHERE default_price_list_id IS NOT NULL")
not_null_pl = cur.fetchone()[0]
print(f"Customers with default_price_list_id NOT NULL: {not_null_pl}")

cur.execute("SELECT COUNT(*) FROM customers WHERE default_price_list_id IS NULL")
null_pl = cur.fetchone()[0]
print(f"Customers with default_price_list_id IS NULL: {null_pl}")

conn.close()

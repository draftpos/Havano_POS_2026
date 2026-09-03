import sys, os
sys.path.insert(0, os.path.abspath("."))
import json
from database.db import get_connection, fetchone_dict

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT TOP 1 * FROM sales")
row = fetchone_dict(cur)
print("COLUMNS in sales table:")
print(list(row.keys()))
print("\nSAMPLE SALE ROW:")
print(json.dumps(row, indent=2, default=str))
conn.close()

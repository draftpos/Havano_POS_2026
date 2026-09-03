import sys, os
sys.path.append(os.getcwd())
from database.db import get_connection

conn = get_connection()
cur = conn.cursor()

# Schema
cur.execute("""
    SELECT COLUMN_NAME, DATA_TYPE 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME='modes_of_payment'
    ORDER BY ORDINAL_POSITION
""")
print("=== modes_of_payment columns ===")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

# Data
cur.execute("SELECT TOP 5 * FROM modes_of_payment")
cols = [d[0] for d in cur.description]
rows = cur.fetchall()
print(f"\n=== modes_of_payment data ({len(rows)} rows shown) ===")
print(f"  Columns: {cols}")
for r in rows:
    print(f"  {dict(zip(cols, r))}")

# Also check payment_methods
cur.execute("SELECT TOP 5 * FROM payment_methods")
cols2 = [d[0] for d in cur.description]
rows2 = cur.fetchall()
print(f"\n=== payment_methods data ({len(rows2)} rows shown) ===")
print(f"  Columns: {cols2}")
for r in rows2:
    print(f"  {dict(zip(cols2, r))}")

conn.close()

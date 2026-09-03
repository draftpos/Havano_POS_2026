import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection, fetchall_dicts

conn = get_connection()
cur = conn.cursor()

print("Connected to:", conn)

# 1. Check customers table
print("\n--- CUSTOMERS TABLE ---")
cur.execute("SELECT COUNT(*) FROM customers")
total_c = cur.fetchone()[0]
print(f"Total customers: {total_c}")

cur.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'customers'")
cols = [r[0] for r in cur.fetchall()]
print(f"Columns in customers: {cols}")

cur.execute("SELECT TOP 20 * FROM customers")
cust_sample = fetchall_dicts(cur)
print(f"Sample customers ({len(cust_sample)}):")
for c in cust_sample:
    print(c)

# 2. Check price_lists table
print("\n--- PRICE_LISTS TABLE ---")
cur.execute("SELECT COUNT(*) FROM price_lists")
total_pl = cur.fetchone()[0]
print(f"Total price_lists: {total_pl}")
cur.execute("SELECT * FROM price_lists")
for pl in fetchall_dicts(cur):
    print(pl)

# 3. Check item_prices table
print("\n--- ITEM_PRICES TABLE ---")
cur.execute("SELECT COUNT(*) FROM item_prices")
total_ip = cur.fetchone()[0]
print(f"Total item_prices: {total_ip}")

cur.execute("SELECT DISTINCT price_list FROM item_prices")
print("Distinct price lists in item_prices:", [r[0] for r in cur.fetchall()])

cur.execute("SELECT TOP 10 * FROM item_prices")
for ip in fetchall_dicts(cur):
    print(ip)

# 4. Check company_defaults / company settings
print("\n--- COMPANY DEFAULTS ---")
try:
    cur.execute("SELECT * FROM company_defaults")
    print("company_defaults rows:", fetchall_dicts(cur))
except Exception as e:
    print("company_defaults:", e)

# 5. Check products
print("\n--- PRODUCTS TABLE ---")
cur.execute("SELECT COUNT(*) FROM products")
total_p = cur.fetchone()[0]
print(f"Total products: {total_p}")

conn.close()

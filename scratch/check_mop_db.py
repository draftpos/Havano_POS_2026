import sys
sys.path.insert(0, ".")

print("Running fetch_and_cache()...")
from services.saas_mop_rates import fetch_and_cache
mops = fetch_and_cache()
print(f"Fetched {len(mops)} MOPs")

from database.db import get_connection
conn = get_connection()
cur  = conn.cursor()

cur.execute("SELECT from_currency, to_currency, rate, rate_date FROM exchange_rates ORDER BY from_currency")
rows = cur.fetchall()
print(f"\nexchange_rates table now has {len(rows)} row(s):")
for r in rows:
    print(f"  {r[0]} -> {r[1]}  rate={r[2]}  date={r[3]}")

cur.execute("SELECT name, account_currency, synced_from_api FROM modes_of_payment ORDER BY id")
rows2 = cur.fetchall()
print(f"\nmodes_of_payment synced status:")
for r in rows2:
    flag = "YES" if r[2] else "no"
    print(f"  {str(r[0]):<20} {str(r[1]):<6} synced={flag}")

conn.close()
print("\nDone.")

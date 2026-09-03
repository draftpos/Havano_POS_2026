import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from database.db import get_connection, fetchall_dicts
from models.exchange_rate import get_rate

conn = get_connection()
cur = conn.cursor()

print("=== MODES OF PAYMENT ===")
cur.execute("SELECT name, gl_account, account_currency FROM modes_of_payment")
for r in fetchall_dicts(cur):
    print(" ", r)

print("\n=== EXCHANGE RATES TABLE ===")
cur.execute("SELECT from_currency, to_currency, rate FROM exchange_rates")
for r in fetchall_dicts(cur):
    print(" ", r)

print("\n=== MOP RATES TABLE ===")
try:
    cur.execute("SELECT mop_name, currency, rate FROM mop_rates")
    for r in fetchall_dicts(cur):
        print(" ", r)
except Exception as e:
    print("  (mop_rates table exception:", e, ")")

conn.close()

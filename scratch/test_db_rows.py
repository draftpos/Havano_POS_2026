import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from database.db import get_connection, fetchall_dicts
from models.shift import refresh_income, get_shift_by_id

refresh_income(3)

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT id, method, currency FROM shift_rows WHERE shift_id = 3")
rows = fetchall_dicts(cur)
print("Raw DB rows in shift_rows:")
for r in rows:
    print(" ", r)
conn.close()

shift = get_shift_by_id(3)
print("\n_get_shift_rows output:")
for r in shift.get("rows", []):
    print(" ", r["method"], "->", r["currency"])

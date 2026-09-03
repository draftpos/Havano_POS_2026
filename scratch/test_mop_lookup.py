import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from database.db import get_connection, fetchone_dict
from models.shift import get_payment_method_currency

conn = get_connection()
cur = conn.cursor()

m = "CBZ RANDS"
print(f"Testing lookup for '{m}':")
cur.execute("SELECT account_currency, gl_account FROM modes_of_payment WHERE LOWER(name) = LOWER(?)", (m,))
row = fetchone_dict(cur)
print("  modes_of_payment row:", row)

cur.execute("SELECT account_currency FROM gl_accounts WHERE LOWER(name) = LOWER(?)", (m,))
gl_row = fetchone_dict(cur)
print("  gl_accounts row:", gl_row)

print("  get_payment_method_currency('CBZ RANDS') ->", get_payment_method_currency("CBZ RANDS"))
print("  get_payment_method_currency('CBZ Rands') ->", get_payment_method_currency("CBZ Rands"))

conn.close()

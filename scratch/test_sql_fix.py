import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from database.db import get_connection, fetchall_dicts

conn = get_connection()
cur = conn.cursor()

cur.execute("""
    SELECT 
        LTRIM(RTRIM(pe.mode_of_payment)) AS payment_method,
        pe.received_amount,
        pe.currency as pe_currency,
        m.account_currency as mop_currency,
        gl.account_currency as gl_currency,
        COALESCE(NULLIF(m.account_currency, ''), NULLIF(pe.currency, ''), gl.account_currency, '') as resolved_currency
    FROM payment_entries pe
    LEFT JOIN modes_of_payment m ON LOWER(m.name) = LOWER(LTRIM(RTRIM(pe.mode_of_payment)))
    LEFT JOIN gl_accounts gl ON pe.paid_to = gl.name
    WHERE pe.shift_id = 3
""")
rows = fetchall_dicts(cur)
print("Resolved payment entries for shift #3:")
for r in rows:
    print(" ", r)

conn.close()

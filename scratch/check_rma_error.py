import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT TOP 5 id, doc_type, doc_ref, customer, amount, error_code, error_msg, occurred_at FROM sync_errors ORDER BY id DESC")
rows = cur.fetchall()
for r in rows:
    print(f"ID: {r[0]} | Type: {r[1]} | Ref: {r[2]} | Cust: {r[3]} | Amt: {r[4]} | Code: {r[5]} | Time: {r[7]}")
    print("Error Msg:\n", r[6])
    print("-" * 60)

cur.execute("SELECT * FROM credit_notes WHERE cn_number LIKE '%165228%'")
cols = [c[0] for c in cur.description]
cn_row = cur.fetchone()
if cn_row:
    print("Credit Note Data:")
    for c, val in zip(cols, cn_row):
        print(f"  {c}: {val}")
else:
    print("No credit note found matching 165228")

cur.close()
conn.close()

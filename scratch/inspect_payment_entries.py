import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection, fetchall_dicts

conn = get_connection()
cur = conn.cursor()

cur.execute("SELECT id, invoice_no, customer_name, total, tendered, method, payment_splits, payments FROM sales ORDER BY id DESC")
sales = fetchall_dicts(cur)
print("--- LATEST SALES ---")
for s in sales[:5]:
    print(" ", s)

cur.execute("SELECT id, sale_id, sale_invoice_no, party_name, paid_amount, mode_of_payment, synced, sync_error, created_at FROM payment_entries ORDER BY id DESC")
pes = fetchall_dicts(cur)
print("\n--- LATEST PAYMENT ENTRIES ---")
for pe in pes[:10]:
    print(" ", pe)

conn.close()

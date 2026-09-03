import logging
from services.odoo.sync_service import sync_payment_methods_odoo
from database.db import get_connection, fetchall_dicts

logging.basicConfig(level=logging.INFO)

print("Running sync_payment_methods_odoo...")
sync_payment_methods_odoo()

print("\n--- Content of modes_of_payment table ---")
conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT id, name, type, gl_account FROM modes_of_payment")
for row in fetchall_dicts(cur):
    print(row)

print("\n--- Content of payment_methods table ---")
cur.execute("SELECT id, name, code, payment_type FROM payment_methods")
for row in fetchall_dicts(cur):
    print(row)
conn.close()

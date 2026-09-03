import sys, os
sys.path.insert(0, os.path.abspath("."))
import json
from database.db import get_connection, fetchall_dicts, fetchone_dict

conn = get_connection()
cur = conn.cursor()

print("--- 1. USERS TABLE ---")
cur.execute("SELECT id, username, full_name, email, frappe_user, pin, role, active, company, warehouse FROM users")
users = fetchall_dicts(cur)
print(json.dumps(users, indent=2, default=str))

print("\n--- 2. COMPANY_DEFAULTS TABLE ---")
cur.execute("SELECT TOP 1 id, server_company, server_warehouse, server_cost_center, server_username, server_email, server_role, server_full_name, server_terminal_id, server_terminal_name, api_key, system_mode FROM company_defaults")
defaults = fetchone_dict(cur)
print(json.dumps(defaults, indent=2, default=str))

print("\n--- 3. RECENT SALES (LAST 10) ---")
cur.execute("SELECT TOP 10 id, invoice_no, receipt_type, total, cashier, waiter, synced, sync_error, created_at FROM sales ORDER BY id DESC")
sales = fetchall_dicts(cur)
print(json.dumps(sales, indent=2, default=str))

conn.close()

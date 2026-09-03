import sys
import os
sys.path.insert(0, os.path.abspath("."))

from services.credentials import get_system_mode, set_system_mode
from database.db import get_connection

init_mode = get_system_mode()
print(f"[TEST] System mode before change: {init_mode!r}")

target = "frappe" if init_mode != "frappe" else "saas"

# Switch mode with confirm_wipe=False to execute automatic database drop and re-migration
set_system_mode(target, confirm_wipe=False)
print(f"[TEST] System mode after change: {get_system_mode()!r}")

# Check sales count
conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM sales")
sales_cnt = cur.fetchone()[0]
conn.close()
print(f"[TEST] Sales row count after full drop & migration: {sales_cnt}")
assert sales_cnt == 0, "Sales table should be 0 after drop!"

# Revert back
set_system_mode(init_mode, confirm_wipe=False)
print(f"[TEST] System mode reverted to: {get_system_mode()!r}")

print("[SUCCESS] Full database drop and re-migration test passed 100%!")

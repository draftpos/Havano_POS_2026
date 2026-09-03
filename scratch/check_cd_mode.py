import sys
import os
sys.path.insert(0, os.path.abspath("."))

from database.db import get_connection
from services.credentials import get_system_mode

print(f"[TEST] get_system_mode() returns: {get_system_mode()!r}")

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, system_mode, api_key, company_name FROM company_defaults")
    rows = cur.fetchall()
    print(f"[TEST] company_defaults rows: {rows}")
    conn.close()
except Exception as e:
    print(f"[TEST] company_defaults read error: {e}")

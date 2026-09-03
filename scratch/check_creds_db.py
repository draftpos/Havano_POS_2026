
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from database.db import get_connection

def check():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT api_key, api_secret, system_mode, odoo_token FROM company_defaults')
    row = cur.fetchone()
    if row:
        print(f"API Key: {row[0]}")
        print(f"Secret Length: {len(str(row[1])) if row[1] else 0}")
        print(f"System Mode: {row[2]}")
        print(f"Odoo Token: {row[3]}")
    else:
        print("No company_defaults found.")
    conn.close()

if __name__ == "__main__":
    check()


import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from database.db import get_connection, fetchall_dicts

def check_products():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT part_no, name, stock, uom FROM products WHERE part_no IN ('604', '605', 'ODOO-604', 'ODOO-605')")
    rows = fetchall_dicts(cur)
    for r in rows:
        print(r)
    conn.close()

if __name__ == "__main__":
    check_products()

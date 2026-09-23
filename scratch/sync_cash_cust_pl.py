import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection
from models.company_defaults import get_defaults

defs = get_defaults() or {}
branch_pl_id = defs.get("default_price_list_id")

conn = get_connection()
cur = conn.cursor()

if branch_pl_id:
    cur.execute("UPDATE customers SET default_price_list_id = ? WHERE LOWER(customer_name) LIKE '%cash%'", (branch_pl_id,))
    conn.commit()
    print(f"Updated Cash Customer default_price_list_id to {branch_pl_id}")

cur.execute("""
    SELECT c.id, c.customer_name, c.default_price_list_id, pl.name as price_list_name
    FROM customers c
    LEFT JOIN price_lists pl ON c.default_price_list_id = pl.id
""")
for r in cur.fetchall():
    print(f"  Customer '{r[1]}' -> Price List ID: {r[2]} ({r[3]})")

conn.close()

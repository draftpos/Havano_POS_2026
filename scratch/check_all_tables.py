import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_connection, fetchall_dicts
import models.customer as cust_model

conn = get_connection()
cur = conn.cursor()

# List all tables in pos_db
cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME")
tables = [r[0] for r in cur.fetchall()]
print("Tables in pos_db:")
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM [{t}]")
    cnt = cur.fetchone()[0]
    print(f"  {t}: {cnt} rows")

conn.close()

print("\nCalling models.customer.get_all_customers():")
all_custs = cust_model.get_all_customers()
print(f"Returned {len(all_custs)} customers.")

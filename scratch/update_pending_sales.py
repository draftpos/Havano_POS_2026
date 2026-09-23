import sys, os
sys.path.insert(0, os.path.abspath("."))
from database.db import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("""
    UPDATE sales 
    SET fiscal_status = 'PENDING_SYNC', 
        fiscal_error = 'Offline signed - pending ZIMRA transmission' 
    WHERE id IN (6, 7, 8)
""")
conn.commit()
print(f"Updated {cur.rowcount} rows to PENDING_SYNC")
cur.execute("SELECT id, invoice_no, fiscal_status, fiscal_verification_code, fiscal_global_no FROM sales WHERE id IN (6, 7, 8)")
print(cur.fetchall())
conn.close()

import sys
sys.path.insert(0, r'c:\Users\DELL\New_POS\Havano_POS_2026')
from database.db import get_connection
conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT sync_error FROM sales WHERE invoice_no = 'PKR-0001'")
row = cur.fetchone()
print('SYNC ERROR IN SALES TABLE:', row[0] if row else 'No sale found')

import sys
sys.path.append('c:/Users/user/Desktop/Havano_POS_2026-main')
from database.db import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'credit_notes'")
cols = [r[0] for r in cur.fetchall()]
print('Columns in credit_notes:', cols)

if 'sync_error' in cols:
    cur.execute("SELECT sync_error, id, frappe_ref FROM credit_notes WHERE sync_error IS NOT NULL AND sync_error != ''")
    print('Errors:', cur.fetchall())
conn.close()

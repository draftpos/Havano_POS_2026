import sys
sys.path.append('c:/Users/user/Desktop/Havano_POS_2026-main')
from database.db import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM pos_settings WHERE setting_key LIKE '%expense%'")
    print('pos_settings:', cur.fetchall())
    
    cur.execute("SELECT * FROM company_defaults")
    cols = [column[0] for column in cur.description]
    print('company_defaults keys:', [c for c in cols if 'expense' in c.lower()])
    
    conn.close()
except Exception as e:
    print('Error:', e)

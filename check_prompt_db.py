import sys
sys.path.append('c:/Users/user/Desktop/Havano_POS_2026-main')
from database.db import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM pos_settings WHERE setting_key = 'takeaway_or_sitin'")
    print('pos_settings:', cur.fetchall())
    conn.close()
except Exception as e:
    print('Error:', e)

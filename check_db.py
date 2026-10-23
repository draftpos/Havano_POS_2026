import sys
sys.path.append('c:/Users/user/Desktop/Havano_POS_2026-main')
from database.db import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT setting_key, setting_value FROM pos_settings WHERE setting_key IN ('enable_kds_websocket', 'takeaway_monitors')")
    rows = cur.fetchall()
    print('DB Settings:', rows)
    conn.close()
except Exception as e:
    print('Error:', e)

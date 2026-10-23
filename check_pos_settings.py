import sys
sys.path.append('c:/Users/user/Desktop/Havano_POS_2026-main')
from database.db import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT * FROM pos_settings WHERE setting_key LIKE '%print%' OR setting_key LIKE '%after%'")
print('POS Settings:', cur.fetchall())

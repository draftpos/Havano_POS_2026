import sys
sys.path.insert(0, '.')
from database.db import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM pos_settings WHERE setting_key='offline_license_token'")
    conn.commit()
    conn.close()
    print("DB cleared")
except Exception as e:
    print(e)

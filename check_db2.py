import sys
sys.path.append('C:\\Users\\DELL\\New_POS\\Havano_POS_2026')
from database.db import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT setting_key, setting_value FROM pos_settings WHERE setting_key='require_pin_to_remove'")
print("DB:", cur.fetchone())
conn.close()

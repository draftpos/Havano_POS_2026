import sys
sys.path.append('c:\\Users\\DELL\\New_POS\\Havano_POS_2026')
from database.db import get_connection, fetchone_dict

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT id, odoo_token, api_key, api_secret FROM company_defaults")
row = fetchone_dict(cur)
print("company_defaults row:", row)
conn.close()

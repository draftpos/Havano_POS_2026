from database.db import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT TOP 1 system_mode, company_name, server_api_host FROM company_defaults")
    print("company_defaults:", cur.fetchone())
    
    cur.execute("SELECT setting_key, setting_value FROM pos_settings")
    print("pos_settings:", cur.fetchall())
except Exception as e:
    print("Error:", e)
finally:
    conn.close()

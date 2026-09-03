import json
import pyodbc
import sys

try:
    with open('C:\\Users\\DELL\\New_POS\\Havano_POS_2026\\app_data\\sql_settings.json') as f:
        config = json.load(f)
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={config.get('server', '')};"
        f"DATABASE={config.get('database', '')};"
    )
    if config.get('mode') == 'windows':
        conn_str += "Trusted_Connection=yes;"
    else:
        conn_str += f"UID={config.get('username', '')};PWD={config.get('password', '')};"

    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()
    cur.execute("SELECT setting_key, setting_value FROM pos_settings WHERE setting_key='require_pin_to_remove'")
    row = cur.fetchone()
    print("DB Row:", row)
except Exception as e:
    print("Error:", e)

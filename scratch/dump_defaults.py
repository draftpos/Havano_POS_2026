import pyodbc
import json
import sys
from pathlib import Path

def _load_settings():
    path = Path(r"C:\Users\DELL\New_POS\Havano_POS_2026\app_data\sql_settings.json")
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def dump_defaults():
    try:
        cfg = _load_settings()
        if not cfg:
            print("No settings found")
            return
            
        driver = "ODBC Driver 17 for SQL Server"
        if cfg.get("auth_mode") == "windows":
            conn_str = f"DRIVER={{{driver}}};SERVER={cfg['server']};DATABASE={cfg['database']};Trusted_Connection=yes;TrustServerCertificate=yes;Encrypt=no;"
        else:
            conn_str = f"DRIVER={{{driver}}};SERVER={cfg['server']};DATABASE={cfg['database']};UID={cfg['username']};PWD={cfg['password']};TrustServerCertificate=yes;Encrypt=no;"
            
        conn = pyodbc.connect(conn_str)
        cur = conn.cursor()
        cur.execute("SELECT * FROM company_defaults")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        for r in rows:
            print(json.dumps(dict(zip(cols, r)), default=str))
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    dump_defaults()

if __name__ == "__main__":
    dump_defaults()

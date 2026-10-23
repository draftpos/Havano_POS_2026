import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
from database.db import get_connection, get_app_data_dir
from services.credentials import get_system_mode

conn = get_connection()
cur = conn.cursor()

# Test 1: DB has 'saas', sql_settings.json has 'offline'
cur.execute("UPDATE company_defaults SET system_mode = 'saas' WHERE id = 1")
conn.commit()

p = get_app_data_dir() / "sql_settings.json"
d = json.loads(p.read_text(encoding="utf-8"))
d["system_mode"] = "offline"
p.write_text(json.dumps(d, indent=4), encoding="utf-8")

print("[Test 1: DB='saas', JSON='offline']")
mode1 = get_system_mode()
print(f"  get_system_mode() returned: {mode1}")
print(f"  sql_settings.json updated to: {json.loads(p.read_text()).get('system_mode')}")

# Test 2: DB has 'offline', sql_settings.json has ''
cur.execute("UPDATE company_defaults SET system_mode = 'offline' WHERE id = 1")
conn.commit()

d = json.loads(p.read_text(encoding="utf-8"))
d["system_mode"] = ""
p.write_text(json.dumps(d, indent=4), encoding="utf-8")

print("\n[Test 2: DB='offline', JSON='']")
mode2 = get_system_mode()
print(f"  get_system_mode() returned: {mode2}")
print(f"  sql_settings.json updated to: {json.loads(p.read_text()).get('system_mode')}")

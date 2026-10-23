from database.db import get_app_data_dir, get_connection
import json

app_data_dir = get_app_data_dir()
settings_file = app_data_dir / "sql_settings.json"

# Tamper JSON to 'offline'
disk_data = json.loads(settings_file.read_text(encoding="utf-8"))
disk_data["system_mode"] = "offline"
settings_file.write_text(json.dumps(disk_data, indent=4), encoding="utf-8")

print("[TEST] sql_settings.json tampered to offline.")

# Execute startup guard logic
_saved_mode = None
_disk_data: dict = {}
if settings_file.exists():
    try:
        _disk_data = json.loads(settings_file.read_text(encoding="utf-8"))
        _saved_mode = _disk_data.get("system_mode")
    except Exception:
        pass

_db_mode = None
try:
    _c = get_connection()
    _cur = _c.cursor()
    _cur.execute("SELECT TOP 1 system_mode FROM company_defaults ORDER BY id ASC")
    _row = _cur.fetchone()
    _c.close()
    if _row and _row[0]:
        _db_mode = str(_row[0]).strip().lower()
except Exception as _db_ex:
    print(f"[startup] Could not read company_defaults: {_db_ex}")

_has_saas_bindings = bool(
    (_disk_data.get("server_terminal_id") or _disk_data.get("server_shop_id")) and
    (_disk_data.get("bound_device_id") or _disk_data.get("user_email") or _disk_data.get("active_user_email"))
)

if _db_mode == "saas":
    _saved_mode = "saas"
    print("[startup] Confirmed SaaS mode from company_defaults database table.")
elif _has_saas_bindings and _saved_mode != "saas":
    _saved_mode = "saas"
    print(f"[startup] Enforced SaaS mode from active terminal bindings (Terminal: {_disk_data.get('server_terminal_id')}, Shop: {_disk_data.get('server_shop_id')}).")

if _disk_data.get("system_mode") != _saved_mode:
    _disk_data["system_mode"] = _saved_mode
    if _saved_mode == "saas" and not _disk_data.get("api_url"):
        _disk_data["api_url"] = "https://backoffice.havano.pro"
    settings_file.write_text(json.dumps(_disk_data, indent=4), encoding="utf-8")
    print(f"[startup] Repaired sql_settings.json -> system_mode='{_saved_mode}'.")

if _db_mode != _saved_mode:
    _conn = get_connection()
    _cur = _conn.cursor()
    _cur.execute("UPDATE company_defaults SET system_mode = ? WHERE id = (SELECT MIN(id) FROM company_defaults)", (_saved_mode,))
    _conn.commit()
    _conn.close()
    print(f"[startup] Synchronized company_defaults DB table -> system_mode='{_saved_mode}'.")

# Final check
final_json = json.loads(settings_file.read_text(encoding="utf-8")).get("system_mode")
print(f"[TEST RESULT] final sql_settings.json mode: {final_json}")

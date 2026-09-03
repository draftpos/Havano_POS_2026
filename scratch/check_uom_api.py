import sys, os, json, urllib.request
sys.path.append(os.getcwd())
from models.company_defaults import get_defaults
from services.credentials import get_all_credentials
from services.network_utils import safe_urlopen

defaults = get_defaults() or {}
creds = get_all_credentials()
host = defaults.get("server_api_host")
session_id = defaults.get("odoo_token") or creds.get("odoo_token")
db_name = defaults.get("server_database") or "showline_odoo"

url = f"{host.rstrip('/')}/api/v1/products/"
req = urllib.request.Request(url, headers={
    "User-Agent": "PostmanRuntime/7.54.0",
    "Cookie": f"session_id={session_id}; db={db_name}"
})

with safe_urlopen(req, timeout=60) as resp:
    data = json.loads(resp.read().decode())

items = data.get("data", {}).get("items") or []

# Check allow_multi_uom across products and see if available_uoms differs
multi_true = 0
multi_false = 0
unique_uom_sets = set()

for item in items[:20]:  # Sample first 20
    name = item.get("name", "?")
    allow = item.get("allow_multi_uom", False)
    uoms = item.get("available_uoms") or []
    uom_key = tuple(sorted((u.get("name"), u.get("fixed_price")) for u in uoms))
    unique_uom_sets.add(uom_key)
    
    if allow:
        multi_true += 1
    else:
        multi_false += 1
    
    print(f"  [{name}] allow_multi_uom={allow}, uom_count={len(uoms)}")
    for u in uoms:
        print(f"    - {u.get('name')}: fixed_price={u.get('fixed_price')}, factor={u.get('factor')}")

print(f"\nSummary (first 20): allow_multi_uom True={multi_true}, False={multi_false}")
print(f"Unique UOM sets: {len(unique_uom_sets)}")

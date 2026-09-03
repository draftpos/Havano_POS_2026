import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.credentials import build_auth_header
from services.site_config import get_host

host = get_host()
headers = {"Authorization": build_auth_header(), "Accept": "application/json"}

resp = requests.get(f"{host.rstrip('/')}/api/method/havano_pos_integration.api.get_customer?page=1&limit=10", headers=headers)
data = resp.json()
customers = data.get("message", {}).get("customers", [])
print(f"Fetched {len(customers)} customers from get_customer API:")
for c in customers:
    print(f"  Customer: '{c.get('customer_name')}' -> default_price_list: '{c.get('default_price_list')}'")

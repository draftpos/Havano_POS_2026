import sys
import json
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.credentials import build_auth_header
from services.site_config import get_host
from services.network_utils import safe_urlopen

base_url = get_host()
auth_hdr = build_auth_header()

req = urllib.request.Request(f"{base_url}/api/method/havano_pos_integration.api.get_customer?page=1&limit=50")
req.add_header("Authorization", auth_hdr)

with safe_urlopen(req) as r:
    data = json.loads(r.read().decode())
    custs = data.get("message", {}).get("customers", [])
    print(f"Fetched {len(custs)} customers from API:")
    for c in custs:
        print(f"  Customer: {c.get('customer_name')} | default_price_list from Cloud: {c.get('default_price_list')}")

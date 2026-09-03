import sys
import json
import urllib.request
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.credentials import build_auth_header
from services.site_config import get_host
from services.network_utils import safe_urlopen

base_url = get_host()
auth_hdr = build_auth_header()

print(f"Connecting to Cloud: {base_url}...")

# 1. Fetch Price Lists available on Cloud
req_pl = urllib.request.Request(f"{base_url}/api/resource/Price%20List?fields=[\"name\",\"selling\",\"buying\"]")
req_pl.add_header("Authorization", auth_hdr)

print("\n--- AVAILABLE PRICE LISTS ON CLOUD ---")
with safe_urlopen(req_pl) as r:
    pl_data = json.loads(r.read().decode())
    for pl in pl_data.get("data", []):
        print(" ", pl)

# 2. Fetch Customers across pages to check default_price_list
page = 1
all_custs = []
pl_counts = Counter()

print("\n--- FETCHING ALL CUSTOMERS FROM CLOUD ---")
while True:
    url = f"{base_url}/api/method/havano_pos_integration.api.get_customer?page={page}&limit=100"
    req = urllib.request.Request(url)
    req.add_header("Authorization", auth_hdr)
    
    with safe_urlopen(req) as r:
        data = json.loads(r.read().decode())
        custs = data.get("message", {}).get("customers", [])
        if not custs:
            break
        all_custs.extend(custs)
        for c in custs:
            pl = c.get("default_price_list")
            pl_counts[str(pl)] += 1
        if len(custs) < 100:
            break
        page += 1

print(f"\nTotal Customers fetched from Cloud: {len(all_custs)}")
print("\nBreakdown of Customer Price Lists on Cloud:")
for pl_name, count in pl_counts.items():
    print(f"  Price List: '{pl_name}' -> {count} customer(s)")

print("\nSample Customers and their Cloud Price Lists:")
for c in all_custs[:10]:
    print(f"  Name: {c.get('customer_name'):<30} | Price List: {c.get('default_price_list')}")

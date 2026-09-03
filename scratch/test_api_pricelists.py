import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.credentials import get_credentials, build_auth_header, get_system_mode
from services.site_config import get_host

host = get_host() or "https://greencroft.havano.cloud"
api_key, api_secret = get_credentials()
auth_hdr = build_auth_header()

print(f"Host: {host}")
print(f"Auth Header: {auth_hdr[:25]}...")
print(f"System Mode: {get_system_mode()}")

headers = {
    "Authorization": auth_hdr,
    "Accept": "application/json",
}

def test_endpoint(name, url):
    print(f"\n==========================================")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        print(f"Status Code: {resp.status_code}")
        try:
            data = resp.json()
            if isinstance(data, dict):
                msg = data.get("message")
                if isinstance(msg, dict):
                    print(f"Message keys: {list(msg.keys())}")
                    for k in ("products", "customers", "items", "data"):
                        if k in msg and isinstance(msg[k], list):
                            print(f"Found msg['{k}'] with {len(msg[k])} records.")
                            if len(msg[k]) > 0:
                                print(f"Sample item from msg['{k}']:\n", json.dumps(msg[k][0], indent=2))
                    if "total_pages" in msg or "count" in msg:
                        print("Pagination info:", {k: v for k, v in msg.items() if not isinstance(v, list)})
                elif isinstance(msg, list):
                    print(f"Message is list (len={len(msg)})")
                    if len(msg) > 0:
                        print(f"Sample record from message:\n", json.dumps(msg[0], indent=2))
                elif "data" in data:
                    print(f"data key (len={len(data['data']) if isinstance(data['data'], list) else 'non-list'}):")
                    if isinstance(data['data'], list) and len(data['data']) > 0:
                        print(f"Sample from data:\n", json.dumps(data['data'][0], indent=2))
                else:
                    print("Top-level dict preview:", json.dumps(data, indent=2)[:500])
            elif isinstance(data, list):
                print(f"Response is list of length {len(data)}")
                if len(data) > 0:
                    print(f"Sample from list:\n", json.dumps(data[0], indent=2))
        except Exception as e:
            print("Could not parse JSON:", e, "Raw text:", resp.text[:300])
    except Exception as e:
        print(f"Request error: {e}")

# 1. Product endpoint (where prices live)
test_endpoint("1. get_products (page=1&limit=2)", f"{host.rstrip('/')}/api/method/havano_pos_integration.api.get_products?page=1&limit=2")

# 2. Customer endpoint
test_endpoint("2. get_customer (page=1&limit=2)", f"{host.rstrip('/')}/api/method/havano_pos_integration.api.get_customer?page=1&limit=2")

# 3. Dedicated Price List endpoint
test_endpoint("3. get_price_lists (custom method)", f"{host.rstrip('/')}/api/method/havano_pos_integration.api.get_price_lists")

# 4. Standard Frappe REST API for Price List DocType
test_endpoint("4. /api/resource/Price List", f"{host.rstrip('/')}/api/resource/Price%20List?fields=[\"name\",\"price_list_name\",\"selling\",\"buying\",\"currency\",\"enabled\"]")

# 5. Standard Frappe REST API for Item Price DocType
test_endpoint("5. /api/resource/Item Price", f"{host.rstrip('/')}/api/resource/Item%20Price?limit_page_length=3&fields=[\"name\",\"item_code\",\"price_list\",\"price_list_rate\",\"uom\",\"currency\"]")

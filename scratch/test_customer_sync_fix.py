import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.credentials import build_auth_header
from services.site_config import get_host
from services.network_utils import safe_urlopen

base_url = get_host()
auth_hdr = build_auth_header()

# Test 1: Resource Customer with default_price_list field
fields = ["name", "customer_name", "customer_group", "territory", "custom_cost_center", "custom_warehouse", "default_price_list", "mobile_no", "email_id", "tax_id", "credit_limit", "is_cash_customer"]
fields_url = f"{base_url}/api/resource/Customer?fields={urllib.parse.quote(json.dumps(fields))}&limit_start=0&limit_page_length=5"

req = urllib.request.Request(fields_url)
req.add_header("Authorization", auth_hdr)

print("--- TEST 1: /api/resource/Customer with default_price_list ---")
try:
    with safe_urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        for c in data.get("data", []):
            print(" ", c)
except Exception as e:
    print("Error:", e)

# Test 2: havano_pos_integration.api.get_customer
get_cust_url = f"{base_url}/api/method/havano_pos_integration.api.get_customer?page=1&limit=5"
req2 = urllib.request.Request(get_cust_url)
req2.add_header("Authorization", auth_hdr)

print("\n--- TEST 2: havano_pos_integration.api.get_customer ---")
try:
    with safe_urlopen(req2, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        custs = data.get("message", {}).get("customers", [])
        for c in custs:
            print("  Name:", c.get("customer_name"), "| default_price_list:", c.get("default_price_list"), "| warehouse:", c.get("custom_warehouse"), "| balance:", c.get("balance"))
except Exception as e:
    print("Error:", e)

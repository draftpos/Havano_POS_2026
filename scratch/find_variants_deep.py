import urllib.request
import urllib.error
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

base_url = "https://backoffice.havano.pro"
token = "YWJjNEBnbWFpbC5jb206SjFtNDkzMHdyMQ=="  # from previous login

# Check multiple potential endpoints
candidate_endpoints = [
    f"{base_url}/api/method/havano_pos_integration.api.get_products?page=1&limit=100",
    f"{base_url}/api/method/saas_api.www.api.get_products?page=1&limit=100",
    f"{base_url}/api/method/saas_api.www.api.get_items?page=1&limit=100",
    f"{base_url}/api/method/saas_api.www.api.get_item?page=1&limit=100",
    f"{base_url}/api/method/saas_api.www.api.items?page=1&limit=100",
    f"{base_url}/api/method/saas_api.www.api.get_my_products?page=1&limit=100",
    f"{base_url}/api/method/saas_api.www.api.get_my_items?page=1&limit=100",
    f"{base_url}/api/method/saas_api.api.get_products?page=1&limit=100",
    f"{base_url}/api/method/saas_api.api.get_items?page=1&limit=100",
]

hdr = {"Authorization": f"token {token}", "Accept": "application/json"}

print("Checking endpoints...")
for ep in candidate_endpoints:
    req = urllib.request.Request(ep, headers=hdr, method="GET")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            msg = data.get("message", {})
            prods = msg.get("products", []) if isinstance(msg, dict) else (data if isinstance(data, list) else [])
            print(f"SUCCESS: {ep} -> {len(prods)} products")
            if prods:
                # print first item keys
                print("  Keys:", list(prods[0].keys()) if isinstance(prods[0], dict) else type(prods[0]))
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {ep}")
    except Exception as e:
        print(f"ERR: {ep} -> {e}")

# Now let's page through havano_pos_integration.api.get_products to search for Nike or any variants or is_variant
print("\nPaging through havano_pos_integration.api.get_products...")
page = 1
found_variant_prods = []
found_nike = []
total_seen = 0

while page <= 10:
    url = f"{base_url}/api/method/havano_pos_integration.api.get_products?page={page}&limit=50"
    req = urllib.request.Request(url, headers=hdr, method="GET")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            msg = data.get("message", {})
            prods = msg.get("products", []) if isinstance(msg, dict) else []
            if not prods:
                break
            total_seen += len(prods)
            for p in prods:
                name_code = f"{p.get('itemname', '')} {p.get('itemcode', '')} {p.get('name', '')} {p.get('item_code', '')}".lower()
                if "nike" in name_code or "air" in name_code or "nk-" in name_code:
                    found_nike.append(p)
                if p.get("variants") or p.get("is_variant") or p.get("has_variants") or "variant" in str(p).lower():
                    found_variant_prods.append(p)
            pagination = msg.get("pagination", {}) if isinstance(msg, dict) else {}
            if not pagination.get("has_next_page"):
                break
            page += 1
    except Exception as e:
        print(f"Error page {page}: {e}")
        break

print(f"Total products scanned: {total_seen}")
print(f"Found {len(found_nike)} matching 'Nike/Air':")
for p in found_nike:
    print(json.dumps(p, indent=2))

print(f"\nFound {len(found_variant_prods)} with variant info:")
for p in found_variant_prods[:3]:
    print(json.dumps(p, indent=2))

import urllib.request
import urllib.error
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

base_url = "https://backoffice.havano.pro"
login_url = f"{base_url}/api/method/saas_api.www.api.login"

login_payload = json.dumps({
    "usr": "abc4@gmail.com",
    "pwd": "Admin@123",
    "timezone": "Africa/Harare"
}).encode("utf-8")

login_headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "app_version": "1.0.0",
    "device_hardware_id": "TEST-DEVICE-ID"
}

print(f"Logging in to {login_url} as abc4@gmail.com...")
req = urllib.request.Request(login_url, data=login_payload, headers=login_headers, method="POST")

try:
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        raw_body = resp.read().decode("utf-8")
        print("Raw response body:", raw_body[:300])
        res_data = json.loads(raw_body)
        print("Parsed type:", type(res_data))
        if isinstance(res_data, dict):
            print("Keys:", list(res_data.keys()))
            if "message" in res_data:
                print("message type:", type(res_data["message"]))
                if isinstance(res_data["message"], str):
                    try:
                        res_data["message"] = json.loads(res_data["message"])
                    except:
                        pass
                if isinstance(res_data["message"], dict):
                    print("message keys:", list(res_data["message"].keys()))
except urllib.error.HTTPError as e:
    err_body = e.read().decode("utf-8", errors="replace")
    print(f"Login failed: HTTP {e.code}: {err_body}")
    exit(1)
except Exception as e:
    print(f"Login error: {e}")
    exit(1)

token = res_data.get("token") or res_data.get("message", {}).get("token") or res_data.get("data", {}).get("token")
print(f"Extracted token: {token[:15] if token else 'None'}...")

# Also check cookies or api_key / api_secret in res_data
user_data = res_data.get("user") or res_data.get("message", {}).get("user") or res_data.get("data", {}).get("user")
api_key = res_data.get("api_key") or (user_data.get("api_key") if isinstance(user_data, dict) else None)
api_secret = res_data.get("api_secret") or (user_data.get("api_secret") if isinstance(user_data, dict) else None)
print(f"api_key: {api_key}, api_secret: {bool(api_secret)}")

# Let's test get_my_products with token or authorization
endpoints_to_test = [
    f"{base_url}/api/method/saas_api.www.api.get_my_products?page=1&limit=50",
    f"{base_url}/api/method/havano_pos_integration.api.get_products?page=1&limit=50"
]

auth_headers_to_try = []
if token:
    auth_headers_to_try.append({"Authorization": f"token {token}"})
    auth_headers_to_try.append({"Authorization": f"Bearer {token}"})
if api_key and api_secret:
    auth_headers_to_try.append({"Authorization": f"token {api_key}:{api_secret}"})

for endpoint in endpoints_to_test:
    print(f"\n--- Testing: {endpoint} ---")
    success = False
    for hdr in auth_headers_to_try:
        req = urllib.request.Request(endpoint, headers=hdr, method="GET")
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                print(f"Success with header {list(hdr.keys())[0]} = {list(hdr.values())[0][:20]}...!")
                success = True
                
                # Analyze products
                msg = data.get("message", {})
                products = msg.get("products", []) if isinstance(msg, dict) else (data if isinstance(data, list) else [])
                print(f"Total products returned on page: {len(products)}")
                
                variant_items = []
                for p in products:
                    if p.get("variants") or p.get("is_variant") or p.get("has_variants") or "variant" in str(p).lower():
                        variant_items.append(p)
                
                print(f"\nProducts containing variant fields/data: {len(variant_items)}")
                for idx, vp in enumerate(variant_items[:5]):
                    print(f"\n[Variant Product #{idx+1}]:")
                    print(json.dumps(vp, indent=2))
                    
                if not variant_items and products:
                    print("\nNo products with variants found in the first batch. First 2 products are:")
                    for p in products[:2]:
                        print(json.dumps(p, indent=2))
                break
        except urllib.error.HTTPError as e:
            err_b = e.read().decode("utf-8", errors="replace")
            print(f"Header {list(hdr.values())[0][:20]}... failed: HTTP {e.code}: {err_b[:120]}")
        except Exception as e:
            print(f"Header failed: {e}")
    if success:
        break

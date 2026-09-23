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
    "device_hardware_id": "BF36-F6BF-4927-7EAD"
}

req = urllib.request.Request(login_url, data=login_payload, headers=login_headers, method="POST")
with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
    res_data = json.loads(resp.read().decode("utf-8"))

token = res_data.get("token") or res_data.get("access_token")
print("User info:", res_data.get("user"))
print("Subscription:", res_data.get("subscription"))

url = f"{base_url}/api/method/havano_pos_integration.api.get_products?page=1&limit=100"
req2 = urllib.request.Request(url, headers={"Authorization": f"token {token}", "Accept": "application/json"}, method="GET")

with urllib.request.urlopen(req2, context=ctx, timeout=15) as resp:
    data = json.loads(resp.read().decode("utf-8"))
    prods = data.get("message", {}).get("products", [])
    print(f"\nTotal products: {len(prods)}")
    for i, p in enumerate(prods):
        code = p.get("itemcode") or p.get("item_code") or p.get("name")
        name = p.get("itemname") or p.get("name")
        has_v = p.get("has_variants")
        is_v = p.get("is_variant")
        variants = p.get("variants")
        print(f"{i+1}. Code: {code} | Name: {name} | is_variant: {is_v} | has_variants: {has_v} | variants: {variants}")

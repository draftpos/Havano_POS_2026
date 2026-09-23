import urllib.request
import urllib.error
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

base = "https://backoffice.havano.pro"
token = "YWJjNEBnbWFpbC5jb206SjFtNDkzMHdyMQ=="
hdr = {"Authorization": f"token {token}", "Accept": "application/json"}

endpoints = [
    "/api/method/saas_api.www.api.get_products",
    "/api/method/saas_api.www.api.get_items",
    "/api/method/saas_api.www.api.get_my_products",
    "/api/method/saas_api.www.api.get_item_variants",
    "/api/method/saas_api.www.api.get_variants",
    "/api/method/saas_api.www.api.sync_products",
    "/api/method/saas_api.www.api.product_list",
    "/api/method/saas_api.api.get_products",
    "/api/method/havano_pos_integration.api.get_products",
    "/api/method/havano_pos_integration.api.get_items",
    "/api/method/havano_pos_integration.api.get_variants",
    "/api/method/havano_pos_integration.api.get_item_variants",
    "/api/method/havano_pos_integration.api.get_product_variants",
    "/api/resource/Item?fields=[\"name\",\"item_code\",\"item_name\",\"is_stock_item\",\"has_variants\",\"variant_of\"]&limit_page_length=10",
]

for ep in endpoints:
    url = f"{base}{ep}"
    req = urllib.request.Request(url, headers=hdr, method="GET")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[200 OK] {ep}")
            # print sample
            sample = str(data)[:200]
            print(f"   Response: {sample}")
    except urllib.error.HTTPError as e:
        print(f"[{e.code}] {ep}")
    except Exception as e:
        print(f"[ERR] {ep}: {e}")

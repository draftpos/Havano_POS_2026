import urllib.request
import urllib.error
import json
import ssl
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.credentials import get_credentials, get_system_mode
from services.product_sync_windows_service import _get_host

k, s = get_credentials()
host = _get_host()
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Test endpoints
endpoints = [
    f"{host}/api/method/saas_api.www.api.get_my_products?item_code=162",
    f"{host}/api/method/saas_api.www.api.get_item?item_code=162",
    f"{host}/api/method/saas_api.www.api.get_item_details?item_code=162",
    f"{host}/api/method/saas_api.www.api.get_variants?item_code=162",
    f"{host}/api/method/saas_api.www.api.get_item_variants?item_code=162",
]

import base64
hdr_val = base64.b64encode(f"{k}:{s}".encode()).decode()
headers_to_try = [
    {"Authorization": f"token {hdr_val}"},
    {"Authorization": f"token {k}:{s}"}
]

for ep in endpoints:
    print(f"\n--- {ep} ---")
    for hdr in headers_to_try:
        req = urllib.request.Request(ep, headers=hdr, method="GET")
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                print(f"SUCCESS: {str(data)[:300]}")
                break
        except urllib.error.HTTPError as e:
            print(f"HTTP {e.code}")
        except Exception as e:
            print(f"ERR: {e}")

import sys
import os
import json
import urllib.request
import urllib.parse
import base64

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.product_sync_windows_service import _load_credentials

user, pwd = _load_credentials()

url = "https://greencroft.havano.cloud/api/method/pos_intergration_latest.api.get_products?page_no=1&page_size=20&search=TRIATIX"
req = urllib.request.Request(url)
auth_header = "Basic " + base64.b64encode(f"{user}:{pwd}".encode()).decode()
req.add_header("Authorization", auth_header)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        msg = data.get("message", {})
        products = msg.get("products", []) if isinstance(msg, dict) else msg
        print(f"Total products returned: {len(products)}")
        for p in products:
            if "TRIATIX 2L" in str(p.get("itemcode", "")):
                print("Item:", p.get("itemcode"), p.get("itemname"))
                print("Prices from cloud API:", json.dumps(p.get("prices"), indent=2))
except Exception as e:
    print("API error:", e)

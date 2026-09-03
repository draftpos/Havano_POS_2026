import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.product_sync_windows_service import _load_credentials, _get

user, pwd = _load_credentials()
host = "https://greencroft.havano.cloud"

for page in range(1, 10):
    url = f"{host}/api/method/havano_pos_integration.api.get_products?page={page}&limit=100"
    data = _get(url, user, pwd)
    msg = data.get("message", {})
    products = msg.get("products", [])
    for p in products:
        if "TRIATIX" in str(p.get("itemcode", "")).upper() or "TRIATIX" in str(p.get("itemname", "")).upper():
            print("Found:", p.get("itemcode"), "|", p.get("itemname"))
            print(json.dumps(p.get("prices"), indent=2))
    if not msg.get("pagination", {}).get("has_next_page", False):
        break

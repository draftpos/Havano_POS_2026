import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from services.product_sync_windows_service import _load_credentials, _get_host, _get
import json

k, s = _load_credentials()
h = _get_host()
url = f"{h}/api/method/havano_pos_integration.api.get_products?page=1&limit=100"
try:
    data = _get(url, k, s)
    msg = data.get("message", {})
    products = msg.get("products", []) if isinstance(msg, dict) else (data if isinstance(data, list) else [])
    print(f"havano_pos_integration.api.get_products returned {len(products)} products")
    iphone = [p for p in products if 'iphone' in str(p.get('itemname','')).lower() or '162' in str(p.get('itemcode','')) or '162' in str(p.get('variant_of',''))]
    for p in iphone:
        print(json.dumps(p, indent=2))
except Exception as e:
    print(f"Error calling havano_pos_integration: {e}")

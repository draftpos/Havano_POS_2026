import urllib.request
import json
from services.odoo.sync_service import _get_host, get_defaults
from services.credentials import get_all_credentials
from services.network_utils import safe_urlopen

host = get_defaults().get("server_api_host") or _get_host()
sid = get_defaults().get("odoo_token") or get_all_credentials().get("odoo_token")

for path in ["/api/v1/payment-method-lines"]:
    url = f"{host.rstrip('/')}{path}"
    req = urllib.request.Request(url)
    req.add_header("Cookie", f"session_id={sid}")
    try:
        with safe_urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
            print(f"Path: {path}")
            print(f"Success: {data.get('success')}")
            if data.get('success'):
                items = data.get("data", {}).get("items") or []
                print(f"Items count: {len(items)}")
                if items:
                    print(f"First item: {items[0]}")
    except Exception as e:
        print(f"Failed {path}: {e}")

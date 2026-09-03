import urllib.request
import json
from services.odoo.sync_service import _get_host, get_defaults
from services.credentials import get_all_credentials
from services.network_utils import safe_urlopen

host = get_defaults().get("server_api_host") or _get_host()
sid = get_defaults().get("odoo_token") or get_all_credentials().get("odoo_token")

url = f"{host.rstrip('/')}/api/v1/payment-method-lines"
req = urllib.request.Request(url)
req.add_header("Cookie", f"session_id={sid}")
try:
    print(f"Connecting to {url}...")
    with safe_urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode())
        print("Success!")
        print(json.dumps(data, indent=2)[:1000])
except Exception as e:
    print(f"Failed: {e}")

import logging, urllib.request, json
from services.odoo.sync_service import _get_host, get_defaults
from services.credentials import get_all_credentials
from services.network_utils import safe_urlopen

host = _get_host()
sid = get_all_credentials().get("odoo_token")
url = f"{host.rstrip('/')}/api/v1/sales"
payload = {
    "pos_reference": "TEST-03", 
    "customer_name": "Cash Customer", 
    "lines": [{"product_id": "P1002", "quantity": 1.0, "price_unit": 0.0}]
}
req = urllib.request.Request(
    url, 
    data=json.dumps(payload).encode(), 
    method="POST", 
    headers={"Content-Type": "application/json", "Cookie": f"session_id={sid}"}
)

try:
    with safe_urlopen(req, timeout=30) as r:
        print("Success:", r.read().decode())
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code, e.read().decode())
except Exception as e:
    print("Error:", e)

import logging, urllib.request, json, time
from services.odoo.sync_service import _get_host
from services.credentials import get_all_credentials
from services.network_utils import safe_urlopen

host = _get_host()
sid = get_all_credentials().get("odoo_token")
url = f"{host.rstrip('/')}/api/v1/payments"
payload = {
    "invoice_id": 54, # from earlier test response
    "amount": 3.0,
    "payment_method": "cash",
    "reference": f"POS-PAY-{int(time.time())}",
    "payment_date": "2026-05-17"
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

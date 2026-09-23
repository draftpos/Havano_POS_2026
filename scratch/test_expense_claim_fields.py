import sys, os
sys.path.insert(0, os.path.abspath("."))
import urllib.request
import ssl
import json
from services.credentials import get_credentials, build_auth_header

api_key, api_secret = get_credentials()
auth_hdr = build_auth_header(api_key, api_secret)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    "https://backoffice.havano.pro/api/resource/Expense%20Claim/0001",
    headers={"Accept": "application/json", "Authorization": auth_hdr}
)
try:
    with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("Expense Claim 0001:", json.dumps(data, indent=2))
except Exception as e:
    print("Error:", e)

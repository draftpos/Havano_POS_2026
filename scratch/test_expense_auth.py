import sys, os
sys.path.insert(0, os.path.abspath("."))
import urllib.request
import ssl
import json
from services.credentials import get_credentials, build_auth_header

api_key, api_secret = get_credentials()
print("api_key:", api_key)
print("api_secret:", api_secret)
auth_hdr = build_auth_header(api_key, api_secret)
print("auth_hdr:", auth_hdr)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    "https://backoffice.havano.pro/api/resource/Expense%20Claim%20Type",
    headers={"Accept": "application/json", "Authorization": auth_hdr}
)
with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
    data = json.loads(resp.read().decode("utf-8"))
    print("Expense Claim Types:", json.dumps(data, indent=2))

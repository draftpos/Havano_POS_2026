import sys, os
sys.path.insert(0, os.path.abspath("."))
import urllib.request
import ssl
import json
from services.credentials import get_all_credentials, build_auth_header

creds = get_all_credentials()
api_key = creds.get("api_key", "")
api_secret = creds.get("api_secret", "")
auth_hdr = build_auth_header(api_key, api_secret)

host = "https://backoffice.havano.pro"

endpoints = [
    ("GET", "/api/resource/Expense%20Claim%20Type"),
    ("GET", "/api/resource/Expense%20Claim"),
    ("GET", "/api/resource/Expense"),
    ("GET", "/api/method/saas_api.www.api.get_account"),
    ("GET", "/api/method/saas_api.www.api.get_expenses"),
    ("POST", "/api/method/saas_api.www.api.create_expense"),
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for method, ep in endpoints:
    url = f"{host}{ep}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    if auth_hdr:
        headers["Authorization"] = auth_hdr
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = resp.read().decode("utf-8")
            print(f"[{method}] {ep} -> {resp.status}: {data[:120]}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")[:120]
        print(f"[{method}] {ep} -> HTTP {e.code}: {err_body}")
    except Exception as e:
        print(f"[{method}] {ep} -> ERROR: {e}")

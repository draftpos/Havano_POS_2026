import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, requests
from models.company_defaults import get_defaults

defaults = get_defaults()
api_host = defaults.get("server_api_host", "https://backoffice.havano.pro")
api_key = defaults.get("api_key")
api_secret = defaults.get("api_secret")

headers = {
    "Authorization": f"token {api_key}:{api_secret}",
    "Content-Type": "application/json"
}

print(f"Testing select_terminal API on {api_host} for user {api_key}...")

# Test 1: POST to /api/method/saas_api.www.api.select_terminal
try:
    url = f"{api_host}/api/method/saas_api.www.api.select_terminal"
    resp = requests.post(url, json={"terminal_id": 58, "terminal": 58, "shop_id": 68}, headers=headers)
    print("select_terminal POST status:", resp.status_code)
    print("select_terminal POST text:", resp.text)
except Exception as e:
    print("POST error:", e)

# Test 2: POST to /api/method/saas_api.www.api.select_shop
try:
    url = f"{api_host}/api/method/saas_api.www.api.select_shop"
    resp = requests.post(url, json={"shop_id": 68}, headers=headers)
    print("select_shop POST status:", resp.status_code)
    print("select_shop POST text:", resp.text)
except Exception as e:
    print("select_shop error:", e)

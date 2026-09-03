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

# GET Sales Invoice S634 to inspect all field names on the server
url = f"{api_host}/api/resource/Sales Invoice/S634"
print(f"GETting {url}...")
resp = requests.get(url, headers=headers)
print("Status Code:", resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    print("KEYS in S634:", list((data.get("data") or {}).keys()))
    print("S634 DATA:")
    print(json.dumps(data.get("data") or {}, indent=2, default=str))
else:
    print("GET failed:", resp.text)

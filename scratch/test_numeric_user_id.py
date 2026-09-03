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

# Fetch users list from server saas_api.www.api.get_users
url_users = f"{api_host}/api/method/saas_api.www.api.get_users"
resp_u = requests.get(url_users, headers=headers)
print("get_users Status:", resp_u.status_code)
if resp_u.status_code == 200:
    u_data = resp_u.json()
    print("USERS FROM SERVER:")
    print(json.dumps(u_data, indent=2, default=str))

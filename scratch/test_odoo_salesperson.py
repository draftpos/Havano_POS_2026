import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, requests

host = "https://backoffice.havano.pro"
url = f"{host}/api/method/saas_api.www.api.login"

resp = requests.post(url, json={"usr": "abbm@gmail.com", "pwd": "Admin@23", "timezone": "Africa/Harare"})
data = resp.json()
print("FULL LOGIN RESPONSE:")
print(json.dumps(data, indent=2, default=str))

import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, requests

host = "https://backoffice.havano.pro"
url = f"{host}/api/method/saas_api.www.api.login"

# Test logging in as cashiernew
payload = {
    "usr": "cashiernew@abcholdings.com",
    "pwd": "1234", # or cashier password
    "timezone": "Africa/Harare"
}

resp = requests.post(url, json=payload)
print("Login status:", resp.status_code)
print("Login response text:", resp.text[:1000])

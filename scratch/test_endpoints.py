import sys, os
sys.path.insert(0, os.path.abspath("."))
import requests

host = "https://backoffice.havano.pro"
headers = {
    "Authorization": "token abbm@gmail.com:Admin@23",
    "Content-Type": "application/json"
}

endpoints = [
    "/api/method/saas_api.www.api.select_terminal",
    "/api/method/saas_api.www.api.select_shop",
    "/api/method/havano_company.apis.company.select_terminal",
    "/api/method/havano_pos_integration.api.select_terminal",
    "/api/method/saas_manager.sass_manager.api.select_terminal",
    "/api/method/havano_company.apis.terminal.select_terminal",
]

for ep in endpoints:
    url = f"{host}{ep}"
    resp = requests.post(url, json={"terminal_id": 58, "shop_id": 68}, headers=headers)
    print(f"Endpoint {ep} -> Status {resp.status_code}: {resp.text[:120]}")

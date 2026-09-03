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

cashier_email = "cashiernew@abcholdings.com"

# Base payload matching Mobile
base = {
  "customer": "Cash Customer",
  "trade_name": "Cash Customer",
  "company": "ABC Holdings",
  "set_warehouse": "ABC Holdings",
  "cost_center": "ABC Holdings",
  "update_stock": 1,
  "posting_date": "2026-08-13",
  "posting_time": "12:13:00",
  "set_posting_time": 1,
  "reference_number": "TEST-CASHIER-FIELD-1004",
  "currency": "USD",
  "conversion_rate": 1.0,
  "docstatus": 1,
  "items": [
    {
      "item_code": "727",
      "item_name": "Mint Sweets Toffee",
      "description": "Mint Sweets Toffee",
      "qty": 1.0,
      "rate": 20.0,
      "uom": "Nos"
    }
  ]
}

url = f"{api_host}/api/resource/Sales Invoice"

field_tests = [
    {"cashier": cashier_email},
    {"sales_person": cashier_email},
    {"pos_cashier": cashier_email},
    {"custom_cashier": cashier_email},
    {"custom_waiter": cashier_email},
]

for ft in field_tests:
    p = dict(base)
    p.update(ft)
    resp = requests.post(url, json=p, headers=headers)
    print(f"Test {ft} -> Status {resp.status_code}: {resp.text[:120]}")

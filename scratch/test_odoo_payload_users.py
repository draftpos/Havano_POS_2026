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

# Base payload
base = {
  "customer": "Cash Customer",
  "trade_name": "Cash Customer",
  "company": "ABC Holdings",
  "set_warehouse": "ABC Holdings",
  "cost_center": "ABC Holdings",
  "update_stock": 1,
  "posting_date": "2026-08-13",
  "posting_time": "14:25:00",
  "set_posting_time": 1,
  "reference_number": "TEST-ODOO-USER-ID-01",
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

# Test different salesperson field names used by Odoo
field_tests = [
    {"user_id": 72},
    {"user_id": "New Cashier 01"},
    {"invoice_user_id": 72},
    {"salesperson": "New Cashier 01"},
    {"sales_person": "New Cashier 01"},
    {"seller": "New Cashier 01"},
]

for ft in field_tests:
    p = dict(base)
    p.update(ft)
    p["reference_number"] = f"TEST-ODOO-{list(ft.keys())[0]}-100"
    resp = requests.post(url, json=p, headers=headers)
    print(f"Test {ft} -> Status {resp.status_code}: {resp.text[:120]}")

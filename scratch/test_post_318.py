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

# Test posting invoice with cashier 318's user ID / email
payload = {
  "customer": "Cash Customer",
  "trade_name": "Cash Customer",
  "company": "Legends Chisipiti",
  "set_warehouse": "Legends Chisipiti",
  "cost_center": "Legends Chisipiti",
  "update_stock": 1,
  "posting_date": "2026-08-13",
  "posting_time": "14:26:00",
  "set_posting_time": 1,
  "reference_number": "TEST-CASHIER-318-NEW-01",
  "currency": "USD",
  "conversion_rate": 1.0,
  "docstatus": 1,
  "user_id": 318,
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
print(f"Testing POST with user_id=318 (New Cashier 01) to {url}...")
resp = requests.post(url, json=payload, headers=headers)
print("Status Code:", resp.status_code)
print("Response Text:", resp.text)

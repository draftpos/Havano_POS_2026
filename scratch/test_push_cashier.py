import sys, os
sys.path.insert(0, os.path.abspath("."))
import json
from models.company_defaults import get_defaults
from services.pos_upload_service import _build_payload_usd

defaults = get_defaults()

sample_sale = {
    "id": 999,
    "invoice_no": "TEST-CASHIER-318-CHECKOUT-01",
    "customer_name": "Cash Customer",
    "method": "Cash",
    "cashier_name": "New Cashier 01",
    "waiter_name": "New Cashier 01",
}

sample_items = [
    {
        "part_no": "727",
        "product_name": "Mint Sweets Toffee",
        "qty": 1.0,
        "price": 20.0,
        "uom": "Nos"
    }
]

payload = _build_payload_usd(sample_sale, sample_items, defaults)
print("GENERATED PAYLOAD:")
print(json.dumps(payload, indent=2, default=str))

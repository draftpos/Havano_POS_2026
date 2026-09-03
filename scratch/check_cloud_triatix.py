import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.frappe_client import FrappeClient

fc = FrappeClient()
print("Fetching Item Price from Frappe Cloud for TRIATIX 2L...")
try:
    prices = fc.get_list(
        "Item Price",
        fields=["name", "item_code", "price_list", "price_list_rate", "selling", "buying", "uom", "modified"],
        filters=[["item_code", "=", "TRIATIX 2L"]]
    )
    for p in prices:
        print("Cloud Item Price:", p)
except Exception as e:
    print(f"Cloud fetch error: {e}")

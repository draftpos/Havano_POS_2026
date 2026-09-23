import os
import sys

sys.path.insert(0, ".")

from services.expense_sync_service import is_saas_mode, _get_api_context, fetch_cloud_expense_categories

print("is_saas_mode():", is_saas_mode())
host, token, store_id = _get_api_context()
print("host:", host)
print("token:", token[:10] + "..." if token else "None")
print("store_id:", store_id)

try:
    cats = fetch_cloud_expense_categories()
    print("Fetched categories:", len(cats), cats)
except Exception as e:
    print("Error fetching categories:", e)

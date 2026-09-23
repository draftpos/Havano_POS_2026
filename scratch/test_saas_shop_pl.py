import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.auth_service import _fetch_and_apply_saas_shops
from database.db import get_connection

mock_user_block = {
    "warehouse": "Legends Xuls",
    "selected_shop_id": 225,
    "shops": [
        {
            "id": 225,
            "name": "Legends Xuls",
            "pricelist_ids": [131],
            "pricelist_names": ["Retail"],
            "default_pricelist_id": 131,
            "default_pricelist_name": "Retail"
        },
        {
            "id": 226,
            "name": "Legends Machipisa",
            "pricelist_ids": [131],
            "pricelist_names": ["Retail"],
            "default_pricelist_id": 131,
            "default_pricelist_name": "Retail"
        }
    ]
}

print("Running _fetch_and_apply_saas_shops with mock shops data...")
_fetch_and_apply_saas_shops(host="", auth_token="", user_block=mock_user_block)

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT default_price_list_id FROM company_defaults")
print("company_defaults default_price_list_id:", cur.fetchone()[0])

cur.execute("SELECT id, name FROM price_lists WHERE id = (SELECT default_price_list_id FROM company_defaults)")
print("Active branch default price list:", cur.fetchone())

cur.execute("SELECT customer_name, default_price_list_id FROM customers WHERE customer_name LIKE '%Cash%'")
print("Cash customer price list ID:", cur.fetchone())

conn.close()

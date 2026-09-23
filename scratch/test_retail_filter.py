import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.product import get_all_products, search_products

print("=== Testing with price_list_name='Retail' ===")
retail_products = get_all_products(price_list_name="Retail")
print(f"Total products returned under 'Retail': {len(retail_products)}")
for p in retail_products[:10]:
    print(f"  Item: {p['part_no']} | Name: {p['name']} | Price (Retail): ${p['price']:.2f}")

print("\n=== Testing Search for '110' with 'Retail' ===")
s_res = search_products("110", min_len=1, price_list_name="Retail")
for p in s_res:
    print(f"  Found: {p['part_no']} - {p['name']} -> Price: ${p['price']:.2f}")

print("\n=== Testing Search for '110' with 'Standard Selling' ===")
s_std = search_products("110", min_len=1, price_list_name="Standard Selling")
for p in s_std:
    print(f"  Found: {p['part_no']} - {p['name']} -> Price: ${p['price']:.2f}")

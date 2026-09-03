import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.product import search_products

print("--- Testing search_products with 'Standard Selling' ---")
res_std = search_products("TRIATIX", price_list_name="Standard Selling")
for p in res_std:
    print(f"  {p['part_no']:<15} | {p['name']:<25} | Price: ${p['price']:.2f}")

print("\n--- Testing search_products with 'Sunshine Price List' ---")
res_sun = search_products("TRIATIX", price_list_name="Sunshine Price List")
for p in res_sun:
    print(f"  {p['part_no']:<15} | {p['name']:<25} | Price: ${p['price']:.2f}")

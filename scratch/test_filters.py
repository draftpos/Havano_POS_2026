import os
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from models.product import get_all_products

print("Testing get_all_products()...")
all_p = get_all_products()
print(f"Total products (no warehouse): {len(all_p)}")

if all_p:
    print(f"Sample product: {all_p[0]}")

print("\nTesting get_all_products(warehouse_id=1)...")
wh_p = get_all_products(warehouse_id=1)
print(f"Total products (warehouse=1): {len(wh_p)}")

if wh_p:
    print(f"Sample product: {wh_p[0]}")

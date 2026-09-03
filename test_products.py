import sys
import os
sys.path.insert(0, r"c:\Users\DELL\New_POS\Havano_POS_2026")
from models.product import get_all_products

try:
    products = get_all_products()
    print(f"Loaded {len(products)} products.")
    if len(products) > 0:
        print(products[0])
except Exception as e:
    import traceback
    traceback.print_exc()

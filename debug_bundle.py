import sys
sys.path.append(r"c:\Users\DELL\New_POS\Havano_POS_2026")
from models.product import get_product_by_part_no
from models.item_price import get_prices_map
import json

part_no = '52323'
price_list = 'Standard Selling'

product = get_product_by_part_no(part_no)
is_bundle = product.get("is_product_bundle")

print("is_bundle:", is_bundle)
lines_json = product.get("bundle_lines") or "[]"
print("lines_json:", lines_json)
b_items = json.loads(lines_json)
pm = get_prices_map(price_list)
bundle_total = 0.0

for b_item in b_items:
    i_code = (b_item.get("item_code") or b_item.get("product_code") or b_item.get("code") or b_item.get("part_no") or "").upper().strip()
    i_qty  = float(b_item.get("quantity") or 0)
    i_rate = float(b_item.get("rate") or b_item.get("sale_price") or 0)
    print("Item:", i_code, "Qty:", i_qty, "Rate:", i_rate)
    if i_rate <= 0:
        i_rate = float(pm.get(i_code, 0) or 0)
        print("Fallback rate from pm:", i_rate)
    bundle_total += (i_qty * i_rate)

print("bundle_total:", bundle_total)

import re

with open("views/main_window.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines in views/main_window.py: {len(lines)}")

# Look for customer selection or price list handling
patterns = [
    r"def .*customer",
    r"def .*pricelist",
    r"_active_pricelist",
    r"_current_pricelist",
    r"get_customer_price",
    r"item_prices",
    r"default_price_list"
]

for idx, line in enumerate(lines):
    for pat in patterns:
        if re.search(pat, line, re.IGNORECASE):
            print(f"Line {idx+1}: {line.strip()}")

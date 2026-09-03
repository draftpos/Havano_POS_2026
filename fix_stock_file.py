import os

path = 'views/dialogs/stock_file_dialog.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

import re

old_sql = r"""            # Load components if bundle
            if self\.product\.get\('is_product_bundle'\):
                cur\.execute\(\"\"\"
                    SELECT pb\.child_product_id as product_id, pb\.quantity,
                           p\.part_no, p\.name \s*
                    FROM product_bundle_items pb
                    JOIN products p ON p\.id = pb\.child_product_id
                    WHERE pb\.parent_product_id = \?
                \"\"\", \(self\.product\['id'\],\)
                comps = fetchall_dicts\(cur\)
                for comp in comps:
                    self\._add_component_row\(comp\['part_no'\], comp\['part_no'\], comp\['name'\], comp\['quantity'\]\)"""

# Let's just use string replace for the exact lines up to the for loop.
old_lines = [
    "            if self.product.get('is_product_bundle'):",
    '                cur.execute("""',
    "                    SELECT pb.child_product_id as product_id, pb.quantity,",
    "                           p.part_no, p.name ",
    "                    FROM product_bundle_items pb",
    "                    JOIN products p ON p.id = pb.child_product_id",
    "                    WHERE pb.parent_product_id = ?",
    '                """, (self.product[\'id\'],))',
    "                comps = fetchall_dicts(cur)",
    "                for comp in comps:",
    "                    self._add_component_row(comp['part_no'], comp['part_no'], comp['name'], comp['quantity'])"
]
old_str = '\n'.join(old_lines)

new_str = """            if self.product.get('is_product_bundle'):
                bundle_lines = self.product.get('bundle_lines')
                if bundle_lines:
                    import json
                    try:
                        comps = json.loads(bundle_lines)
                        for comp in comps:
                            self._add_component_row(
                                comp.get('item_code', ''), 
                                comp.get('item_code', ''), 
                                comp.get('item_name', ''), 
                                float(comp.get('quantity', 1.0))
                            )
                    except Exception as e:
                        print(f"Failed to load bundle_lines: {e}")"""

if old_str in text:
    text = text.replace(old_str, new_str)
    print("Replaced!")
else:
    print("Not found! Trying regex...")
    # try regex just in case
    new_text = re.sub(
        r"            # Load components if bundle\n            if self\.product\.get\('is_product_bundle'\):.*?(?=            cur\.execute\(\"SELECT price_list, uom, price)",
        "            # Load components if bundle\n" + new_str + "\n                    \n",
        text, flags=re.DOTALL
    )
    if new_text != text:
        text = new_text
        print("Replaced with regex!")
    else:
        print("Regex also failed!")

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print("Done")

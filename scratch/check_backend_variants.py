import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from services.product_sync_windows_service import _load_credentials, _get_host, _fetch_all_pages
import json

k, s = _load_credentials()
h = _get_host()
products = _fetch_all_pages(k, s, h)
print(f"Total: {len(products)}")
for p in products:
    var_fields = {k: v for k, v in p.items() if "var" in k.lower() or "attr" in k.lower()}
    if any(var_fields.values()):
        print(f"Code: {p.get('itemcode')}, Name: {p.get('itemname')}, Fields: {var_fields}")
        if "attributes" in p or "variants" in p:
            print("  attributes:", p.get("attributes"))
            print("  variants:", p.get("variants"))

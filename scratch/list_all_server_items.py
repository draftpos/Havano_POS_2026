import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from services.product_sync_windows_service import _load_credentials, _get_host, _fetch_all_pages
k, s = _load_credentials()
h = _get_host()
products = _fetch_all_pages(k, s, h)
for i, p in enumerate(products, 1):
    print(f"{i}. Code: {p.get('itemcode')}, Name: {p.get('itemname')}, is_variant: {p.get('is_variant')}, has_variants: {p.get('has_variants')}, variant_of: {p.get('variant_of')}")

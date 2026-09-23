import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.product_sync_windows_service import _load_credentials, _get_host, _get

host = _get_host()
api_key, api_secret = _load_credentials()

print(f"Host: {host}")
print(f"API Key: {api_key[:10] if api_key else 'None'}...")

endpoints = [
    f"{host}/api/method/saas_api.www.api.get_my_products?page=1&limit=20",
    f"{host}/api/method/havano_pos_integration.api.get_products?page=1&limit=20"
]

for url in endpoints:
    print(f"\nTesting endpoint: {url}")
    try:
        data = _get(url, api_key, api_secret)
        msg = data.get("message", {})
        products = msg.get("products", []) if isinstance(msg, dict) else (data if isinstance(data, list) else [])
        print(f"Success! Found {len(products)} products.")
        
        # Check if any product has is_variant or variants or has_variants
        variant_products = []
        for p in products:
            if p.get("variants") or p.get("is_variant") or p.get("has_variants") or "variant" in str(p).lower():
                variant_products.append(p)
                
        print(f"Products with variant info: {len(variant_products)}")
        if variant_products:
            print("\nSample variant product from server:")
            print(json.dumps(variant_products[0], indent=2))
        elif products:
            print("\nSample product (first 1):")
            print(json.dumps(products[0], indent=2))
    except Exception as e:
        print(f"Error calling {url}: {e}")

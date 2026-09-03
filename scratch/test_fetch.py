import sys
import os
import json

# Add project root to sys.path
sys.path.insert(0, r"c:\Users\DELL\New_POS\Havano_POS_2026")

from services.product_sync_windows_service import _load_credentials, _get_host, _get

def main():
    try:
        api_key, api_secret = _load_credentials()
        host = _get_host()
        print(f"Host: {host}")
        
        # Test original endpoint
        url = f"{host}/api/method/havano_pos_integration.api.get_products?page=1&limit=5"
        try:
            data = _get(url, api_key, api_secret)
            print("Payload preview from havano_pos_integration.api.get_products:")
            print(json.dumps(data, indent=2)[:1000])
        except Exception as e:
            print(f"Error fetching from get_products: {e}")
            
        # Test saas_api endpoint if it exists
        url2 = f"{host}/api/method/saas_api.www.api.get_products?page=1&limit=5"
        try:
            data2 = _get(url2, api_key, api_secret)
            print("\nPayload preview from saas_api.www.api.get_products:")
            print(json.dumps(data2, indent=2)[:1000])
        except Exception as e:
            pass

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

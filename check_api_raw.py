import sys
sys.path.append('c:/Users/user/Desktop/Havano_POS_2026-main')
from services.credentials import get_all_credentials
from services.sync_service import _get_products_endpoint
import requests

try:
    creds = get_all_credentials()
    host = creds.get('host') or 'https://backoffice.havano.pro'
    api_key = creds.get('api_key')
    api_secret = creds.get('api_secret')
    
    headers = {
        'Authorization': f'token {api_key}:{api_secret}',
        'Accept': 'application/json'
    }
    
    url = f"{_get_products_endpoint()}?page=1&limit=5"
    print(f"Fetching from: {url}")
    resp = requests.get(url, headers=headers, timeout=10)
    print("Status:", resp.status_code)
    
    data = resp.json()
    items = data.get('message', data.get('data', []))
    
    if isinstance(items, dict) and 'data' in items:
        items = items['data']
        
    if not items:
        print("No items returned.")
        sys.exit(0)
        
    for i, item in enumerate(items):
        name = item.get("item_code") or item.get("name")
        pao = item.get("print_after_order")
        pao_i = item.get("print_after_order_item")
        custom_pao = item.get("custom_print_after_order")
        
        print(f"[{i+1}] {name}: print_after_order={pao}, print_after_order_item={pao_i}, custom_print_after_order={custom_pao}")

except Exception as e:
    print('Error:', e)

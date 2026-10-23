import sys
sys.path.append('c:/Users/user/Desktop/Havano_POS_2026-main')
from services.credentials import get_all_credentials
import requests

creds = get_all_credentials()
host = creds.get('host')
api_key = creds.get('api_key')
api_secret = creds.get('api_secret')

if not host:
    print('No host found.')
    sys.exit(0)

headers = {
    'Authorization': f'token {api_key}:{api_secret}',
    'Accept': 'application/json'
}

print(f'Fetching from {host}...')
try:
    if 'backoffice.havano.pro' in host:
        url = f'{host}/api/method/havano_app.api.products.get_all_products?page=1&limit=2'
    else:
        url = f'{host}/api/resource/Item?limit_page_length=2&fields=["*"]'
    
    resp = requests.get(url, headers=headers, timeout=10)
    print('Status:', resp.status_code)
    data = resp.json()
    
    items = data.get('message', data.get('data', []))
    if isinstance(items, dict) and 'data' in items:
        items = items['data']
        
    if items and len(items) > 0:
        first_item = items[0]
        print('print_after_order value:', first_item.get('print_after_order'))
        print('print_after_order_item value:', first_item.get('print_after_order_item'))
        print('custom_print_after_order value:', first_item.get('custom_print_after_order'))
        
        print_keys = [k for k in first_item.keys() if 'print' in k.lower()]
        print('Keys containing "print":', print_keys)
    else:
        print('No items found in response:', data)
except Exception as e:
    print('Error:', e)

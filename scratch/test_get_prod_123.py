import sys, os, json, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.company_defaults import get_defaults
from services.network_utils import safe_urlopen

defaults = get_defaults()
host = defaults.get('server_api_host', 'https://backoffice.havano.pro')
api_key = defaults.get('api_key')
db_name = defaults.get('server_database', '')

url = f"{host.rstrip('/')}/saas_api/get_products"
headers = {
    'User-Agent': 'PostmanRuntime/7.54.0',
    'Accept': '*/*',
    'Content-Type': 'application/json',
    'Authorization': api_key
}
body = json.dumps({'db': db_name}).encode('utf-8')

req = urllib.request.Request(url, data=body, headers=headers)
req.method = 'POST'
try:
    with safe_urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        print('Success calling /saas_api/get_products!')
        msg = data.get('message')
        items = msg if isinstance(msg, list) else (msg.get('products') if isinstance(msg, dict) else [])
        print(f'Found {len(items)} items!')
        for it in items:
            name = str(it.get('name') or it.get('item_name') or '')
            code = str(it.get('item_code') or it.get('part_no') or '')
            if '123' in name or '123' in code or code == '163':
                print('=== ITEM 123 FOUND ===')
                print(json.dumps(it, indent=2))
except Exception as e:
    print('Error:', e)

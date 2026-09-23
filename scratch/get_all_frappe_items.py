import sys, urllib.request, urllib.parse, json, ssl
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from services.credentials import get_credentials

k, s = get_credentials()
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

base = 'https://backoffice.havano.pro'
hdr = {'Authorization': f'token {k}:{s}', 'Accept': 'application/json'}

params = urllib.parse.urlencode({
    'fields': json.dumps(['name', 'item_code', 'item_name', 'has_variants', 'variant_of']),
    'limit_page_length': 200
})
url = f'{base}/api/resource/Item?{params}'
req = urllib.request.Request(url, headers=hdr, method='GET')
try:
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        items = data.get('data', [])
        print(f'Total items: {len(items)}')
        for it in items:
            if it.get('has_variants') or it.get('variant_of') or 'iphone' in it.get('item_name','').lower():
                print(it)
except Exception as e:
    print('Error:', e)

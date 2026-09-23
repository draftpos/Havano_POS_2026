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

# Check Item Variant Attribute
for doctype in ['Item Variant Attribute', 'Item Attribute', 'Item Attribute Value']:
    url = f'{base}/api/resource/{urllib.parse.quote(doctype)}?limit_page_length=20'
    req = urllib.request.Request(url, headers=hdr, method='GET')
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print(f"=== {doctype} ===")
            print(data.get('data', []))
    except Exception as e:
        print(f"Error for {doctype}: {e}")

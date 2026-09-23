import sys, urllib.request, json, ssl
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from services.credentials import get_credentials

k, s = get_credentials()
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

base = 'https://backoffice.havano.pro'
hdr = {'Authorization': f'token {k}:{s}', 'Accept': 'application/json'}

for code in ['162', '167']:
    url = f'{base}/api/resource/Item/{code}'
    req = urllib.request.Request(url, headers=hdr, method='GET')
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            item = data.get('data', {})
            print(f"=== Item {code} ===")
            print("has_variants:", item.get("has_variants"))
            print("variant_of:", item.get("variant_of"))
            print("variant_based_on:", item.get("variant_based_on"))
            print("attributes:", item.get("attributes"))
            print("variants:", item.get("variants"))
    except Exception as e:
        print(f"Error for {code}: {e}")

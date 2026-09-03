import urllib.request, json
from services.credentials import get_credentials
from services.site_config import get_host
from models.company_defaults import get_defaults

api_key, api_secret = get_credentials()
host = get_host()
d = get_defaults()

cc = urllib.parse.quote(d.get('server_cost_center') or '')
wh = urllib.parse.quote(d.get('server_warehouse') or '')
co = urllib.parse.quote(d.get('server_company') or '')

urls = [
    f"{host}/api/method/havano_pos_integration.api.get_customer?page=1&limit=200",
    f"{host}/api/method/havano_pos_integration.api.get_customer?page=1&limit=200&cost_center={cc}",
    f"{host}/api/method/havano_pos_integration.api.get_customer?page=1&limit=200&warehouse={wh}",
    f"{host}/api/method/havano_pos_integration.api.get_customer?page=1&limit=200&company={co}",
    f"{host}/api/method/saas_api.www.api.get_customers?cost_center={cc}&shop_id={wh}",
]

for url in urls:
    print(f"\n--- Trying {url} ---")
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'token {api_key}:{api_secret}')
    try:
        response = urllib.request.urlopen(req)
        print("Success:")
        print(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Failed ({e.code}):")
        try:
            print(e.read().decode())
        except Exception:
            print("Could not read body")
    except Exception as e:
        print("Error:", str(e))

import urllib.request, json
from services.credentials import get_credentials
from services.site_config import get_host

api_key, api_secret = get_credentials()
host = get_host()
url = f"{host}/api/method/saas_api.www.api.get_customers"

print(f"Trying {url}")
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

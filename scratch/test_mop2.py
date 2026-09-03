import urllib.request
import json
import sys
sys.path.insert(0, r"c:\Users\DELL\New_POS\Havano_POS_2026")
from services.network_utils import safe_urlopen

url = "https://backoffice.havano.pro/api/method/saas_api.www.api.get_account"
print(f"Testing {url}...")
try:
    req = urllib.request.Request(url)
    req.add_header("Authorization", "token dummy:dummy")
    with safe_urlopen(req, timeout=10) as response:
        data = response.read().decode()
        print("Response:", data)
except Exception as e:
    print("Error:", e)

import urllib.request
import json
import sys
sys.path.insert(0, r"c:\Users\DELL\New_POS\Havano_POS_2026")
from services.network_utils import safe_urlopen

url = "https://backoffice.havano.pro/api/method/havano_pos_integration.api.get_modes_of_payment"
try:
    req = urllib.request.Request(url)
    req.add_header("Authorization", "token dummy:dummy")
    with safe_urlopen(req, timeout=10) as response:
        print("Status:", response.status)
        print("Response:", response.read().decode()[:500])
except Exception as e:
    if hasattr(e, 'read'):
        print("HTTP Error:", e)
        try:
            print("Body:", e.read().decode()[:500])
        except:
            pass
    else:
        print("Error:", e)

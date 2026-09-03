import sys, os
sys.path.insert(0, os.path.abspath("."))
import json
from services.auth_service import _try_online_login

res = _try_online_login("abbm@gmail.com", "Admin@23")
print("Login success:", res.get("success"))
if res.get("raw_data"):
    print("KEYS in raw_data:", list(res["raw_data"].keys()))
    print("RAW DATA:")
    print(json.dumps(res["raw_data"], indent=2, default=str))

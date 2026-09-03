import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.credentials import build_auth_header
from services.site_config import get_host

host = get_host()
headers = {"Authorization": build_auth_header(), "Accept": "application/json"}

resp = requests.get(f"{host.rstrip('/')}/api/resource/Price%20List?fields=[\"name\",\"price_list_name\",\"selling\",\"buying\",\"currency\",\"enabled\"]", headers=headers)
print("All Price Lists on server:")
print(json.dumps(resp.json(), indent=2))

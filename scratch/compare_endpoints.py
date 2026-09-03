import sys
import json
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.credentials import build_auth_header
from services.site_config import get_host
from services.network_utils import safe_urlopen

base_url = get_host()
auth_hdr = build_auth_header()

# Check simple resource url
req1 = urllib.request.Request(f"{base_url}/api/resource/Customer?limit_page_length=2")
req1.add_header("Authorization", auth_hdr)
with safe_urlopen(req1) as r:
    print("Simple /api/resource/Customer output:")
    print(r.read().decode())

# Check havano_pos_integration.api.get_customer
req2 = urllib.request.Request(f"{base_url}/api/method/havano_pos_integration.api.get_customer?page=1&limit=2")
req2.add_header("Authorization", auth_hdr)
with safe_urlopen(req2) as r:
    print("\nget_customer output:")
    print(r.read().decode()[:1000])

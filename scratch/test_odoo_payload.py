
import json
import urllib.request
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from services.credentials import get_all_credentials
from services.site_config import get_host

def test_payload():
    creds = get_all_credentials()
    host = get_host()
    session_id = creds.get("odoo_token")
    if not session_id:
        print("Error: No Odoo token found. Please log in to the POS first.")
        return

    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    url = f"{host.rstrip('/')}/saas_api/get_products"
    import urllib.parse
    
    # Needs db in body
    from database.db import get_connection
    c = get_connection().cursor()
    c.execute("SELECT server_database FROM company_defaults")
    db_name = c.fetchone()[0] or ""

    body = json.dumps({"db": db_name}).encode('utf-8')
    req = urllib.request.Request(url, data=body)
    req.add_header("Authorization", session_id)
    req.add_header("Content-Type", "application/json")
    req.method = "POST"
    
    print(f"Fetching from: {url}")
    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read().decode())
            items = []
            if "data" in data and "items" in data["data"]:
                items = data["data"]["items"]
            
            if items:
                print("--- SAMPLE PRODUCT FROM ODOO ---")
                print(json.dumps(items[0], indent=2))
            else:
                print("No items found in response.")
                print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"Fetch failed: {e}")

if __name__ == "__main__":
    test_payload()

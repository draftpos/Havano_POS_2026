import urllib.request
import json
import ssl
from services.odoo.sync_service import get_defaults, get_all_credentials

def main():
    creds = get_all_credentials()
    defaults = get_defaults() or {}
    host = defaults.get("server_api_host", "http://localhost:8069").rstrip("/")
    api_key = defaults.get("odoo_token") or creds.get("odoo_token", "")
    db = defaults.get("server_database", "")
    
    url = f"{host}/saas_api/get_products"
    body = json.dumps({"db": db}).encode()
    
    req = urllib.request.Request(url, data=body)
    req.add_header("Authorization", api_key)
    req.add_header("Content-Type", "application/json")
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    print(f"Requesting: {url}")
    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as res:
            raw = res.read().decode()
            data = json.loads(raw)
            print("KEYS:", list(data.keys()))
            if "message" in data:
                print("TYPE OF MESSAGE:", type(data["message"]))
                if isinstance(data["message"], list) and len(data["message"]) > 0:
                    print("FIRST ITEM KEYS:", list(data["message"][0].keys()))
            else:
                print("RAW DATA:", data)
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    main()

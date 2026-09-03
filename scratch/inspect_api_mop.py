import json
import os
import urllib.request
import urllib.parse
import ssl

def inspect_api_mop():
    cfg_path = os.path.join("app_data", "sql_settings.json")
    api_key = ""
    api_secret = ""
    host = "https://backoffice.havano.pro"
    company = ""
    
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                api_key = cfg.get("api_key", "")
                api_secret = cfg.get("api_secret", "")
        except Exception as e:
            print("Error reading sql_settings.json:", e)

    print(f"Host: {host}")
    print(f"API Key present: {bool(api_key)}, API Secret present: {bool(api_secret)}")

    endpoints = [
        f"{host}/api/method/saas_api.www.api.get_modes_of_payment",
        f"{host}/api/method/saas_api.www.api.get_account",
    ]

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for ep in endpoints:
        print(f"\n--- Testing Endpoint: {ep} ---")
        try:
            req = urllib.request.Request(ep)
            if api_key and api_secret:
                req.add_header("Authorization", f"token {api_key}:{api_secret}")
            with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
                data = json.loads(r.read().decode("utf-8"))
                print("Response JSON:")
                print(json.dumps(data, indent=2)[:2000])
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")[:500]
            except Exception:
                pass
            print(f"HTTP {e.code}: {body}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    inspect_api_mop()

import urllib.request
import json
import ssl
import sys
import os

sys.path.insert(0, os.path.abspath("."))

def test_takeover_true():
    from database.db import get_connection
    from services.credentials import get_credentials

    api_key, api_secret = get_credentials()
    user_email = "abc4@gmail.com"

    host = "https://backoffice.havano.pro"
    endpoint = f"{host}/api/user/select-terminal"
    
    # Payload with take_over = True
    payload = {
        "terminal_id": 186,
        "user": user_email,
        "take_over": True,
        "device_hardware_id": "BF36-F6BF-4927-7EAD"
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    if api_key and api_secret:
        headers["Authorization"] = f"token {api_key}:{api_secret}"

    print(f"Sending POST to {endpoint} with take_over=True...")
    print("Payload:", json.dumps(payload, indent=2))

    req = urllib.request.Request(
        url=endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=headers
    )

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            resp_str = resp.read().decode("utf-8")
            res_json = json.loads(resp_str)
            print("\n==========================================")
            print("[TAKEOVER SUCCESSFUL - HTTP 200 OK]:")
            print("==========================================")
            print("Message:", res_json.get("message"))
            print("Sale ID Prefix:", res_json.get("sale_id_prefix"))
    except urllib.error.HTTPError as e:
        print(f"\n[HTTP ERROR {e.code}]:")
        try:
            print(e.read().decode("utf-8"))
        except Exception:
            print(e)
    except Exception as e:
        print("\n[ERROR]:", e)

if __name__ == "__main__":
    test_takeover_true()

import sys
import os
import urllib.request
import json
import ssl

sys.path.insert(0, os.path.abspath("."))

def test_live_select_terminal_with_auth():
    from database.db import get_connection
    from services.credentials import get_credentials

    api_key, api_secret = get_credentials()
    user_email = "abc4@gmail.com"

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT email, token_string FROM users WHERE current_user = 1 OR current_user = 'true' LIMIT 1")
        row = cur.fetchone()
        if row:
            if row[0]:
                user_email = str(row[0]).strip()
            if not api_key and row[1]:
                token_str = str(row[1]).strip()
                if ":" in token_str:
                    api_key, api_secret = token_str.split(":", 1)
        conn.close()
    except Exception as e:
        print("DB Lookup Warning:", e)

    host = "https://backoffice.havano.pro"
    endpoint = f"{host}/api/user/select-terminal"
    payload = {
        "terminal_id": 186,
        "user": user_email,
        "take_over": True,
        "device_hardware_id": "fortune0100"
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    if api_key and api_secret:
        headers["Authorization"] = f"token {api_key}:{api_secret}"

    print(f"Sending POST to {endpoint} with device_hardware_id='fortune0100'...")
    print("User Email:", user_email)
    print("Authorization:", headers.get("Authorization"))
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
            print("\n==========================================")
            print("[HTTP 200 SUCCESS RESPONSE FROM SERVER]:")
            print("==========================================")
            print(json.dumps(json.loads(resp_str), indent=2))
    except urllib.error.HTTPError as e:
        print(f"\n[HTTP ERROR {e.code}]:")
        try:
            err_str = e.read().decode("utf-8")
            print(err_str)
        except Exception:
            print(e)
    except Exception as e:
        print("\n[ERROR]:", e)

if __name__ == "__main__":
    test_live_select_terminal_with_auth()

import urllib.request
import urllib.error
import json

def test_login():
    host = "http://80.241.213.153:8069"
    db = "showline_odoo"
    user = "admin@showline.co.zw"
    # Note: We don't have the password, but we can try to see the error behavior (e.g. 401 vs 404 vs 500)
    # to understand if the endpoint actually exists and handles the request!
    # Let's try with a dummy password first to see if it gives HTTP 401 or if there is a routing difference.
    dummy_pwd = "dummy"

    endpoints = [
        f"{host}/api/v1/auth/login",
        f"{host}/api/v1/auth/login/",
    ]

    for ep in endpoints:
        print(f"\n--- Testing Endpoint: {ep} ---")
        payload = json.dumps({"db": db, "login": user, "password": dummy_pwd}).encode("utf-8")
        req = urllib.request.Request(
            ep, data=payload, method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "HavanoPOS/1.0"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                print(f"SUCCESS! Code: {resp.getcode()}")
                print(resp.read().decode())
        except urllib.error.HTTPError as e:
            print(f"HTTPError: {e.code}")
            try:
                body = e.read().decode()
                print(f"Body: {body}")
            except Exception as read_err:
                print(f"Could not read body: {read_err}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_login()

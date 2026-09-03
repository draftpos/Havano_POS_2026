
import urllib.request
import urllib.error
import json

def brute_force_endpoints():
    host = "http://80.241.213.153:8069"
    token = "XSho939h6xxUiOWMZ7Jx3utSdKmxIwvyX4C5bkxLaUhs0jFug7CPCqdfvY4-IZElpZp6qyJiuFEbWW0kHVXW"
    db_name = "showline_odoo"
    
    candidates = [
        "/api/v1/pos.payment.method",
        "/api/v1/pos_payment_method",
        "/api/v1/pos.payment.method/",
        "/api/v1/pos_payment_method/",
        "/api/v1/account.journal",
        "/api/v1/account_journal",
        "/api/v1/pos.payment",
        "/api/v1/pos_payment",
    ]
    
    for url_part in candidates:
        url = host.rstrip('/') + url_part
        print(f"Testing {url} ...")
        req = urllib.request.Request(url)
        req.add_header("Cookie", f"session_id={token}; db={db_name}")
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                print(f"  SUCCESS! Code: {resp.getcode()}")
                raw = resp.read().decode()
                data = json.loads(raw)
                if data.get("success"):
                    print(f"  FOUND DATA: {len(data.get('data', {}).get('items', []))} items")
                    return url_part
                else:
                    print(f"  API Error: {data.get('message')}")
        except urllib.error.HTTPError as e:
            print(f"  FAILED: {e.code}")
    return None

if __name__ == "__main__":
    brute_force_endpoints()

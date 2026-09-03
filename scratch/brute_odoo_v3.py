
import urllib.request
import urllib.error
import json

def brute_force_endpoints():
    host = "http://80.241.213.153:8069"
    token = "XSho939h6xxUiOWMZ7Jx3utSdKmxIwvyX4C5bkxLaUhs0jFug7CPCqdfvY4-IZElpZp6qyJiuFEbWW0kHVXW"
    db_name = "showline_odoo"
    
    models = [
        "account.journal",
        "account_journal",
        "pos.payment.method",
        "pos_payment_method",
        "account.payment.method",
        "account_payment_method",
        "payment.method",
        "payment_method",
        "payment.mode",
        "payment_mode",
        "journals",
        "payment_methods",
        "payment-methods",
    ]
    
    for m in models:
        for suffix in ["", "/"]:
            url_part = f"/api/v1/{m}{suffix}"
            url = host.rstrip('/') + url_part
            # print(f"Testing {url} ...")
            req = urllib.request.Request(url)
            req.add_header("Cookie", f"session_id={token}; db={db_name}")
            req.add_header("Accept", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.getcode() == 200:
                        raw = resp.read().decode()
                        data = json.loads(raw)
                        if data.get("success"):
                            items = data.get("data", {}).get("items", [])
                            print(f"  [FOUND] {url} - {len(items)} items")
                            if items:
                                print(f"  Sample: {items[0].get('name') or items[0].get('display_name')}")
                        else:
                            print(f"  [SUCCESS but error] {url}: {data.get('message')}")
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    print(f"  [ERROR {e.code}] {url}")
            except Exception as e:
                pass

if __name__ == "__main__":
    brute_force_endpoints()

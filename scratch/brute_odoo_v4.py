
import urllib.request
import urllib.error
import json

def brute_force_endpoints():
    host = "http://80.241.213.153:8069"
    token = "XSho939h6xxUiOWMZ7Jx3utSdKmxIwvyX4C5bkxLaUhs0jFug7CPCqdfvY4-IZElpZp6qyJiuFEbWW0kHVXW"
    db_name = "showline_odoo"
    
    models = [
        "payment_methods",
        "payment-methods",
        "payment_modes",
        "payment-modes",
        "journals",
        "account_journals",
    ]
    
    for m in models:
        for suffix in ["", "/"]:
            url_part = f"/api/v1/{m}{suffix}"
            url = host.rstrip('/') + url_part
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "PostmanRuntime/7.54.0")
            req.add_header("Accept", "application/json")
            req.add_header("Cookie", f"session_id={token}; db={db_name}")
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    print(f"  [SUCCESS] {url} - {resp.getcode()}")
                    raw = resp.read().decode()
                    data = json.loads(raw)
                    if data.get("success"):
                        items = data.get("data", {}).get("items", [])
                        print(f"    FOUND {len(items)} items")
            except urllib.error.HTTPError as e:
                print(f"  [FAILED {e.code}] {url}")
            except Exception as e:
                print(f"  [ERROR] {url}: {e}")

if __name__ == "__main__":
    brute_force_endpoints()

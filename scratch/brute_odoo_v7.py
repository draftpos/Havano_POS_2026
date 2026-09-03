
import urllib.request
import urllib.error
import json

def brute_force_endpoints():
    host = "http://80.241.213.153:8069"
    token = "XSho939h6xxUiOWMZ7Jx3utSdKmxIwvyX4C5bkxLaUhs0jFug7CPCqdfvY4-IZElpZp6qyJiuFEbWW0kHVXW"
    db_name = "showline_odoo"
    
    candidates = [
        "/api/v1/payment_methods/",
        "/api/v1/payment_methods",
        "/api/v1/pos/payment_methods/",
        "/api/v1/pos/payment_methods",
    ]
    
    for url_part in candidates:
        url = host.rstrip('/') + url_part + f"?db={db_name}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "PostmanRuntime/7.54.0")
        req.add_header("Accept", "application/json")
        req.add_header("Cookie", f"session_id={token}")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                print(f"  [SUCCESS] {url} - {resp.getcode()}")
                raw = resp.read().decode()
                data = json.loads(raw)
                if data.get("success"):
                    items = data.get("data", {}).get("items", [])
                    print(f"    FOUND {len(items)} items")
                    return url_part
        except urllib.error.HTTPError as e:
            print(f"  [FAILED {e.code}] {url}")
        except Exception as e:
            print(f"  [ERROR] {url}: {e}")
    return None

if __name__ == "__main__":
    brute_force_endpoints()

import urllib.request
import urllib.error
import json

def test_endpoints():
    host = "http://80.241.213.153:8069"
    token = "XSho939h6xxUiOWMZ7Jx3utSdKmxIwvyX4C5bkxLaUhs0jFug7CPCqdfvY4-IZElpZp6qyJiuFEbWW0kHVXW"
    db_name = "showline_odoo"
    
    endpoints = [
        "/api/v1/products/",
        "/api/v1/pos/products",
        "/api/v1/pos/get_products",
        "/api/v1/get_products",
        "/api/v1/pos/products/",
    ]
    
    for url_part in endpoints:
        url = host.rstrip('/') + url_part
        print(f"Testing {url} ...")
        req = urllib.request.Request(url)
        # Try both Cookie and Bearer
        req.add_header("Cookie", f"session_id={token}")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("X-Odoo-Db", db_name)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                print(f"  SUCCESS! Code: {resp.getcode()}")
                content = resp.read().decode()
                print(f"  Type: {resp.info().get_content_type()}")
                print(f"  Snippet: {content[:100]}")
        except urllib.error.HTTPError as e:
            print(f"  FAILED: {e.code}")
            try:
                body = e.read().decode()
                print(f"  Body: {body[:100]}")
            except:
                pass
        except Exception as e:
            print(f"  ERROR: {e}")

if __name__ == "__main__":
    test_endpoints()

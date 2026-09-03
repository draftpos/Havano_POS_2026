import sys
import json
import urllib.request
from database.db import get_connection

def run():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT TOP 1 api_key, api_secret, server_api_host FROM company_defaults")
    row = cur.fetchone()
    conn.close()
    if not row:
        print("No credentials found")
        return
    api_key, api_secret, base_url = row
    print("Base URL:", base_url)
    
    url = f"{base_url}/api/method/havano_pos_integration.api.get_products?page=1&limit=5"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"token {api_key}:{api_secret}"
    }
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            payload = json.loads(resp.read().decode())
            message = payload.get("message") or {}
            products = message.get("products") or []
            if not products:
                print("No products found in response")
                print("Payload:", payload)
                return
            
            # Print the structure of the first product
            sample = products[0]
            print("\nKeys in first product:", list(sample.keys()))
            print("\nFirst product sample:")
            print(json.dumps(sample, indent=2))
    except Exception as e:
        print("Error fetching product sample:", e)

if __name__ == "__main__":
    run()

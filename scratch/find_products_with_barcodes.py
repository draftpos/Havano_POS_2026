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
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"token {api_key}:{api_secret}"
    }
    
    print("Scanning products for barcodes...")
    
    for page in range(1, 20):  # scan first 20 pages
        url = f"{base_url}/api/method/havano_pos_integration.api.get_products?page={page}&limit=50"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode())
                message = payload.get("message") or {}
                products = message.get("products") or []
                if not products:
                    print(f"No more products on page {page}")
                    break
                
                for p in products:
                    bcs = p.get("barcodes") or []
                    if bcs:
                        print(f"Found product with barcodes: {p.get('itemcode')} -> {bcs}")
                        
        except Exception as e:
            print(f"Error page {page}: {e}")
            break

if __name__ == "__main__":
    run()

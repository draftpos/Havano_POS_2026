import json
import urllib.request
import urllib.parse
from database.db import get_connection

def test_endpoint():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT server_api_host FROM company_defaults")
    host = cur.fetchone()[0]
    
    cur.execute("SELECT name FROM companies WHERE id=(SELECT MIN(id) FROM companies)")
    company = cur.fetchone()[0]

    from services.credentials import get_credentials
    api_key, api_secret = get_credentials()
    
    if not api_key:
        print("Error: Could not get user API key from get_credentials()")
        return
    
    url = f"{host}/api/method/saas_api.www.api.get_my_products?page=1&limit=100"
    print(f"Testing URL: {url}")
    
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {api_key}:{api_secret}")
    
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            data = json.loads(resp.read().decode())
            message = data.get("message", {})
            products = message.get("products", [])
            paginator = message.get("pagination", {})
            
            print(f"Success! Found {len(products)} products in this page.")
            print(f"Paginator: {paginator}")
            
            # Print the last 3 products to see if the new one is there
            print("\nLast 3 products returned by API:")
            for p in products[-3:]:
                print(f"- {p.get('itemcode', 'UNKNOWN')} : {p.get('name', 'UNKNOWN')}")
                
    except Exception as e:
        print(f"Error fetching API: {e}")

if __name__ == '__main__':
    test_endpoint()

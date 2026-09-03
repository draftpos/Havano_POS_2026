import sys
import os

# Add the current directory to sys.path so we can import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db import get_connection
from models.sale import get_sale_by_id
from services.pos_upload_service import _push_sale, _get_credentials, _get_host, _get_defaults, _dumps

def run_test():
    conn = get_connection()
    cur = conn.cursor()
    # Let's find the latest sale that has a verification code
    cur.execute("SELECT id FROM sales WHERE fiscal_verification_code IS NOT NULL AND fiscal_verification_code != '' ORDER BY id DESC")
    row = cur.fetchone()
    conn.close()

    if not row:
        print("❌ No sales with a fiscal_verification_code found in the database.")
        print("Please do a successful sale first so it fiscalizes with ZIMRA.")
        return

    sale_id = row[0]
    sale = get_sale_by_id(sale_id)

    print("============================================================")
    print(f"✅ Testing with Sale ID: {sale_id}")
    print(f"Invoice Number: {sale.get('invoice_no')}")
    print(f"Verification Code in Database: '{sale.get('fiscal_verification_code')}'")
    print("============================================================\n")

    api_key, api_secret = _get_credentials()
    host = _get_host()
    defaults = _get_defaults()

    if not api_key:
        print("❌ No API credentials found.")
        return

    print("🚀 Calling _push_sale (this will print the payload)...\n")
    
    # We will temporarily mock the network request inside _push_sale to just print the payload and stop
    import urllib.request
    original_urlopen = urllib.request.urlopen

    def mock_urlopen(req, *args, **kwargs):
        print("\n" + "="*60)
        print("🌐 INTERCEPTED NETWORK REQUEST TO FRAPPE")
        print("URL:", req.full_url)
        print("PAYLOAD BODY (Decoded):")
        import json
        try:
            body_json = json.loads(req.data.decode('utf-8'))
            print(json.dumps(body_json, indent=2))
        except:
            print(req.data.decode('utf-8'))
        print("="*60 + "\n")
        
        # Abort the actual network call to prevent duplicate errors
        raise Exception("MOCK INTERCEPT: Stop actual upload for test.")

    import services.pos_upload_service
    services.pos_upload_service.safe_urlopen = mock_urlopen
    services.pos_upload_service._is_already_synced = lambda x: False

    try:
        _push_sale(sale, api_key, api_secret, defaults, host)
    except Exception as e:
        if "MOCK INTERCEPT" not in str(e):
            print(f"❌ Error during _push_sale: {e}")
        else:
            print("✅ Test script completed successfully.")

if __name__ == "__main__":
    run_test()

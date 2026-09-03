import sys
import logging
from database.db import get_connection

# Configure logging to stdout
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

def run():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT TOP 1 api_key, api_secret FROM company_defaults")
    row = cur.fetchone()
    conn.close()
    if not row:
        print("No credentials found")
        return
    api_key, api_secret = row
    
    print("Running sync_products_smart...")
    from services.product_sync_windows_service import sync_products_smart
    try:
        res = sync_products_smart(api_key, api_secret)
        print("Sync finished successfully. Result:")
        print(res)
    except Exception as e:
        print("Sync crashed:", e)

if __name__ == "__main__":
    run()

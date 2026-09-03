import logging
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

# Setup logging
logging.basicConfig(level=logging.INFO)

from services.odoo.sync_service import sync_all_odoo
from services.credentials import get_all_credentials

if __name__ == "__main__":
    print("Starting Odoo Sync Test...")
    creds = get_all_credentials()
    print(f"System Mode: {creds.get('system_mode')}")
    print(f"Has Token: {bool(creds.get('odoo_token'))}")
    
    try:
        sync_all_odoo()
        print("Sync Test Finished Successfully.")
    except Exception as e:
        print(f"Sync Test Failed: {e}")
        import traceback
        traceback.print_exc()

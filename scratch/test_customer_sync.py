
import sys
import logging
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

# Setup logging to console
logging.basicConfig(level=logging.INFO)

from services.odoo.customer_sync_service import sync_customers_odoo

if __name__ == "__main__":
    print("Testing Odoo Customer Sync...")
    sync_customers_odoo()
    print("Test finished.")

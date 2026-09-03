
import sys
import logging
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

# Setup logging to console
logging.basicConfig(level=logging.INFO)

from services.odoo.payment_method_sync_service import sync_payment_methods_odoo

if __name__ == "__main__":
    print("Starting manual Odoo Payment Method Sync...")
    sync_payment_methods_odoo()
    print("Sync finished.")

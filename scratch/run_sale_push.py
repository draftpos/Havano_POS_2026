
import sys
import logging
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

# Setup logging to console
logging.basicConfig(level=logging.INFO)

from services.odoo.sale_upload_service import push_unsynced_sales_odoo

if __name__ == "__main__":
    print("Starting manual Odoo Sale Push...")
    push_unsynced_sales_odoo()
    print("Push finished.")

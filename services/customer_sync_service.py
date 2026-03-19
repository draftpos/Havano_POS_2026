import json
import urllib.request
import logging
import time
from models.customer import upsert_from_frappe
from services.sync_service import _read_credentials

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CustomerSync] %(levelname)s: %(message)s"
)
log = logging.getLogger("CustomerSync")

CUSTOMER_SYNC_INTERVAL = 300 

def sync_customers():
    """Fetches customers and upserts them. No longer skips records with missing fields."""
    creds = _read_credentials()
    if not creds:
        log.error("No credentials found. Skipping customer sync.")
        return
        
    api_key, api_secret = creds
    # Note: Ensure the endpoint matches your Frappe API
    url = "https://apk.havano.cloud/api/method/havano_pos_integration.api.get_customer?page=1&limit=100"
    
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {api_key}:{api_secret}")

    try:
        log.info("Starting customer sync...")
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            # Handling both potential response structures
            msg = data.get("message", {})
            customer_list = msg.get("customers", []) if isinstance(msg, dict) else msg
            
            if not customer_list:
                log.info("No customers found in payload.")
                return

            success_count = 0
            error_count = 0

            for cust_dict in customer_list:
                try:
                    # =========================================================
                    # CLEANED: Mandatory field check removed. 
                    # We now trust the database NULL constraints and the Model 
                    # logic to handle missing data.
                    # =========================================================
                    upsert_from_frappe(cust_dict)
                    success_count += 1
                    
                except Exception as inner_e:
                    error_count += 1
                    log.error(f"Error processing {cust_dict.get('customer_name')}: {inner_e}")
            
            log.info(f"Sync Result: {success_count} synced, {error_count} errors.")

    except Exception as e:
        log.error(f"Network Error: {e}")

# =============================================================================
# BACKGROUND THREAD (PySide6)
# =============================================================================
try:
    from PySide6.QtCore import QObject, QThread, Signal

    class CustomerSyncWorker(QObject):
        finished = Signal()

        def run(self) -> None:
            while True:
                try:
                    sync_customers()
                except Exception as exc:
                    log.error("Worker loop error: %s", exc)
                
                # Sleep for the interval before the next sync
                time.sleep(CUSTOMER_SYNC_INTERVAL)

    def start_customer_sync_thread():
        """Creates and starts the background thread for customer syncing."""
        thread = QThread()
        worker = CustomerSyncWorker()
        worker.moveToThread(thread)
        
        # Keep references to prevent garbage collection
        thread.started.connect(worker.run)
        
        # Proper cleanup handling
        thread.worker = worker 
        
        thread.start()
        log.info("Customer sync thread started.")
        return thread

except ImportError:
    log.warning("PySide6 not found. Background thread functionality disabled.")

if __name__ == "__main__":
    sync_customers()
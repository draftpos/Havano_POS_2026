# =============================================================================
# services/quotation_sync_service.py
# Push local quotations → Frappe and fetch quotations from Frappe
# Uses same rate limiting and retry logic as pos_upload_service
# =============================================================================

from __future__ import annotations

import json
import logging
import time
import threading
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, date
from typing import Optional, List, Dict, Any

log = logging.getLogger("QuotationSync")

REQUEST_TIMEOUT   = 30
MAX_PER_MINUTE    = 20                      # Frappe rate limit guard
INTER_PUSH_DELAY  = 60 / MAX_PER_MINUTE    # 3 s between each push
SYNC_INTERVAL     = 300                     # 5 minutes between sync cycles


# =============================================================================
# JSON ENCODER  —  handles datetime / date objects
# =============================================================================

class _DateTimeEncoder(json.JSONEncoder):
    """Converts datetime/date objects to ISO strings before JSON serialisation."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def _dumps(obj) -> str:
    """json.dumps with automatic datetime serialisation."""
    return json.dumps(obj, cls=_DateTimeEncoder)


# =============================================================================
# CREDENTIALS / DEFAULTS
# =============================================================================

def _get_credentials() -> tuple[str, str]:
    try:
        from services.credentials import get_credentials
        return get_credentials()
    except Exception:
        pass
    return "", ""


def _get_defaults() -> dict:
    try:
        from models.company_defaults import get_defaults
        return get_defaults() or {}
    except Exception:
        return {}


from services.site_config import get_host as _get_host


# =============================================================================
# PUSH QUOTATION TO FRAPPE
# =============================================================================

def _build_quotation_payload(quotation: dict, defaults: dict) -> dict:
    """
    Build payload for creating a quotation in Frappe.
    Matches the expected format for saas_api.www.api.create_quotation
    Expected arguments: create_quotation(customer, items, reference_number, cost_center)
    """
    company = defaults.get("server_company", "")
    warehouse = defaults.get("server_warehouse", "")
    
    # IMPORTANT: Get reference_number and cost_center from company defaults
    # These are REQUIRED arguments for the Frappe API
    reference_number = defaults.get("server_reference_number", "") or defaults.get("reference_number", "") or "POS-REF"
    cost_center = defaults.get("server_cost_center", "") or defaults.get("cost_center", "") or "Main - APK"
    
    # Get customer name from quotation or fallback to walk-in customer
    customer = quotation.get("customer", "")
    if not customer:
        customer = defaults.get("server_walk_in_customer", "Walk-in Customer")
    
    # Format items for Frappe.
    # Pharmacy custom fields (custom_is_pharmacy, custom_dosage,
    # custom_batch_no, custom_expiry_date) live on Quotation Item in the
    # saas_api app (installed via fixtures). Sending them here means the
    # pharmacist's data survives a round-trip through the server — the
    # local snapshot fallback in save_quotation is a belt-and-braces layer
    # on top of this, not a replacement.
    items = []
    for item in quotation.get("items", []):
        items.append({
            "item_code":          item.get("item_code", ""),
            "item_name":          item.get("item_name", ""),
            "description":        item.get("description", ""),
            "qty":                float(item.get("qty", 1)),
            "rate":               float(item.get("rate", 0)),
            "amount":             float(item.get("amount", 0)),
            "uom":                item.get("uom", "Nos"),
            "custom_is_pharmacy": 1 if item.get("is_pharmacy") else 0,
            "custom_dosage":      item.get("dosage")      or "",
            "custom_batch_no":    item.get("batch_no")    or "",
            "custom_expiry_date": item.get("expiry_date") or None,
        })
    
    # Build payload with required arguments
    payload = {
        "customer": customer,
        "items": items,
        "reference_number": reference_number,  # REQUIRED argument - from company defaults
        "cost_center": cost_center,            # REQUIRED argument - from company defaults
        "transaction_date": quotation.get("transaction_date", datetime.today().strftime("%Y-%m-%d")),
        "grand_total": float(quotation.get("grand_total", 0)),
    }
    
    # Optional fields
    if company:
        payload["company"] = company
    if warehouse:
        payload["set_warehouse"] = warehouse
    if quotation.get("valid_till"):
        payload["valid_till"] = quotation.get("valid_till")
    if quotation.get("reference_number"):
        payload["customer_reference"] = quotation.get("reference_number")
    
    log.info(f"Built payload for quotation {quotation.get('name')}: customer={customer}, reference_number={reference_number}, cost_center={cost_center}, items={len(items)}")
    
    return payload


def _push_quotation_to_frappe(quotation: dict, api_key: str, api_secret: str, 
                               defaults: dict, host: str) -> Optional[str]:
    """
    Push ONE quotation to Frappe - returns Frappe doc name or None.
    Uses POST /api/method/saas_api.www.api.create_quotation
    """
    qtn_name = quotation.get("name", f"local_{quotation.get('local_id', 'unknown')}")
    customer = quotation.get("customer", "Unknown")
    
    try:
        payload = _build_quotation_payload(quotation, defaults)
        if not payload.get("items"):
            log.warning("Quotation %s — no valid items, skipping.", qtn_name)
            return "skipped"
        
        url = f"{host}/api/method/saas_api.www.api.create_quotation"
        
        body = _dumps(payload).encode("utf-8")
        
        log.debug(f"Request URL: {url}")
        log.debug(f"Request body: {body}")
        
        req = urllib.request.Request(
            url=url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"token {api_key}:{api_secret}",
            },
        )
        
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            response = json.loads(resp.read().decode())
            message = response.get("message", {})
            frappe_name = message.get("name") or message.get("quotation_name") or message.get("data", {}).get("name")
            
            if frappe_name:
                log.info("✅ Quotation %s → Frappe as %s (customer: %s, ref: %s, cost_center: %s)", 
                         qtn_name, frappe_name, customer, payload.get("reference_number"), payload.get("cost_center"))
                return frappe_name
            else:
                log.info("✅ Quotation %s pushed successfully to Frappe (customer: %s)", 
                         qtn_name, customer)
                return "success"
                
    except urllib.error.HTTPError as e:
        try:
            msg = e.read().decode("utf-8", errors="replace")
        except Exception:
            msg = f"HTTP {e.code}"
        
        if e.code == 409:
            log.info("Quotation %s already exists on Frappe — marking synced.", qtn_name)
            return "exists"
        
        log.warning("⚠️ Quotation %s — HTTP %s: %s", qtn_name, e.code, msg[:500])
        return None
        
    except urllib.error.URLError as e:
        log.warning("Network error pushing quotation %s: %s", qtn_name, e.reason)
        return None
        
    except Exception as e:
        log.error("Unexpected error pushing quotation %s: %s", qtn_name, e)
        return None


def push_unsynced_quotations() -> dict:
    """
    Push all unsynced local quotations to Frappe.
    Returns result stats.
    """
    result = {"pushed": 0, "failed": 0, "total": 0, "skipped": 0}
    
    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("No API credentials — skipping quotation upload cycle.")
        return result
    
    host = _get_host()
    defaults = _get_defaults()
    
    # Log what we're using from company defaults
    ref_num = defaults.get("server_reference_number", "") or defaults.get("reference_number", "NOT SET")
    cost_ctr = defaults.get("server_cost_center", "") or defaults.get("cost_center", "NOT SET")
    log.info(f"Using company defaults: reference_number={ref_num}, cost_center={cost_ctr}")
    
    try:
        from models.quotation import get_unsynced_quotations, mark_quotation_synced
        quotations = get_unsynced_quotations()
    except Exception as e:
        log.error("Could not read unsynced quotations: %s", e)
        return result
    
    result["total"] = len(quotations)
    if not quotations:
        log.debug("No unsynced quotations.")
        return result
    
    log.info("Pushing %d quotation(s) to Frappe", len(quotations))
    
    for idx, quotation in enumerate(quotations):
        if idx > 0 and idx % MAX_PER_MINUTE == 0:
            log.info("Rate limit pause — waiting 60s before next batch…")
            time.sleep(60)
        
        qtn_dict = quotation.to_dict()
        result_val = _push_quotation_to_frappe(qtn_dict, api_key, api_secret, defaults, host)
        
        if result_val:
            try:
                frappe_ref = result_val if isinstance(result_val, str) and result_val not in ("success", "exists", "skipped") else ""
                mark_quotation_synced(quotation.local_id, frappe_ref)
                result["pushed"] += 1
                log.info(f"✅ Quotation {quotation.name} marked as synced")
            except Exception as e:
                log.error("mark_quotation_synced failed for quotation %s: %s", quotation.name, e)
                result["failed"] += 1
        else:
            result["failed"] += 1
            log.warning(f"❌ Quotation {quotation.name} failed to sync")
        
        if idx < len(quotations) - 1:
            time.sleep(INTER_PUSH_DELAY)
    
    log.info("Quotation upload done — ✅ %d pushed  ❌ %d failed  (of %d)",
             result["pushed"], result["failed"], result["total"])
    return result


# =============================================================================
# FETCH QUOTATIONS FROM FRAPPE
# =============================================================================

def fetch_quotations_from_frappe(page: int = 1, limit: int = 100) -> dict:
    """
    Fetch quotations from Frappe using GET /api/method/saas_api.www.api.get_quotations
    Returns dict with quotations list and pagination info.
    """
    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("No API credentials — cannot fetch quotations.")
        return {"quotations": [], "total": 0, "page": page, "has_next": False}
    
    host = _get_host()
    
    url = f"{host}/api/method/saas_api.www.api.get_quotations?page={page}&limit={limit}"
    
    try:
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {api_key}:{api_secret}")
        req.add_header("Accept", "application/json")
        
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            message = data.get("message", {})
            
            # Handle different response structures
            if isinstance(message, dict):
                quotations = message.get("quotations", [])
                total = message.get("total", len(quotations))
                has_next = message.get("has_next", False)
            else:
                quotations = data.get("quotations", [])
                total = len(quotations)
                has_next = False
            
            return {
                "quotations": quotations,
                "total": total,
                "page": page,
                "has_next": has_next
            }
            
    except urllib.error.HTTPError as e:
        try:
            msg = e.read().decode("utf-8", errors="replace")
        except Exception:
            msg = f"HTTP {e.code}"
        log.error("Failed to fetch quotations: %s", msg[:200])
        return {"quotations": [], "total": 0, "page": page, "has_next": False, "error": msg}
        
    except urllib.error.URLError as e:
        log.error("Network error fetching quotations: %s", e.reason)
        return {"quotations": [], "total": 0, "page": page, "has_next": False, "error": str(e.reason)}
        
    except Exception as e:
        log.error("Unexpected error fetching quotations: %s", e)
        return {"quotations": [], "total": 0, "page": page, "has_next": False, "error": str(e)}


def sync_quotations_from_frappe() -> dict:
    """
    Fetch all quotations from Frappe and save to local database.
    Handles pagination automatically.
    Returns sync result stats.
    """
    result = {"synced": 0, "total": 0, "errors": 0, "pages": 0}
    
    try:
        from models.quotation import Quotation, save_quotation
        
        page = 1
        limit = 100
        has_next = True
        
        while has_next:
            log.info(f"Fetching quotations page {page}...")
            response = fetch_quotations_from_frappe(page, limit)
            
            if response.get("error"):
                log.error(f"Error fetching page {page}: {response['error']}")
                result["errors"] += 1
                break
            
            quotations_data = response.get("quotations", [])
            result["total"] += len(quotations_data)
            result["pages"] += 1
            
            for qtn_data in quotations_data:
                try:
                    quotation = Quotation.from_dict(qtn_data)
                    # Mark as synced since we fetched it from Frappe
                    quotation.synced = True
                    save_quotation(quotation)
                    result["synced"] += 1
                except Exception as e:
                    log.error(f"Failed to save quotation {qtn_data.get('name', 'unknown')}: {e}")
                    result["errors"] += 1
            
            has_next = response.get("has_next", False)
            page += 1
            
            # Small delay between pages
            if has_next:
                time.sleep(0.5)
        
        log.info(f"Quotation sync complete — {result['synced']} saved, {result['errors']} errors, {result['pages']} pages")
        
    except Exception as e:
        log.error(f"Quotation sync failed: {e}")
        result["errors"] += 1
    
    return result


# =============================================================================
# CANCEL QUOTATION IN FRAPPE
# =============================================================================

def cancel_quotation_in_frappe(quotation_name: str) -> bool:
    """
    Cancel a quotation in Frappe using POST /api/method/saas_api.www.api.cancel_quotation
    """
    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("No API credentials — cannot cancel quotation.")
        return False
    
    host = _get_host()
    url = f"{host}/api/method/saas_api.www.api.cancel_quotation"
    
    payload = {"name": quotation_name}
    
    try:
        req = urllib.request.Request(
            url=url,
            data=_dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"token {api_key}:{api_secret}",
            },
        )
        
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            success = data.get("message", {}).get("success", False)
            if success:
                log.info(f"✅ Quotation {quotation_name} cancelled in Frappe")
                return True
            else:
                log.warning(f"⚠️ Failed to cancel quotation {quotation_name}: {data.get('message', 'Unknown error')}")
                return False
                
    except Exception as e:
        log.error(f"Error cancelling quotation {quotation_name}: {e}")
        return False


# =============================================================================
# RETRY SYNC FOR FAILED QUOTATIONS
# =============================================================================

def retry_failed_quotations() -> dict:
    """
    Retry pushing quotations that have synced=False but were already attempted.
    Returns retry results.
    """
    result = {"retried": 0, "success": 0, "failed": 0}
    
    try:
        from models.quotation import get_unsynced_quotations
        
        quotations = get_unsynced_quotations()
        failed_quotations = [q for q in quotations if not q.synced]
        
        result["retried"] = len(failed_quotations)
        
        if failed_quotations:
            log.info(f"Retrying {len(failed_quotations)} failed quotations...")
            push_result = push_unsynced_quotations()
            result["success"] = push_result.get("pushed", 0)
            result["failed"] = push_result.get("failed", 0)
        
    except Exception as e:
        log.error(f"Failed to retry quotations: {e}")
        result["failed"] = result.get("retried", 0)
    
    return result


# =============================================================================
# SINGLE QUOTATION SYNC (called immediately after saving)
# =============================================================================

def sync_quotation_on_create(quotation_id: int, max_retries: int = 3) -> bool:
    """
    Sync a single quotation to Frappe immediately after creation.
    Retries up to max_retries times if failed.
    Returns True if synced successfully, False otherwise.
    """
    from models.quotation import get_all_quotations, mark_quotation_synced
    
    # Get the quotation from database
    all_quotations = get_all_quotations()
    quotation = None
    for q in all_quotations:
        if q.local_id == quotation_id:
            quotation = q
            break
    
    if not quotation:
        log.error(f"Quotation with ID {quotation_id} not found")
        return False
    
    api_key, api_secret = _get_credentials()
    if not api_key or not api_secret:
        log.warning("No API credentials — cannot sync quotation.")
        return False
    
    host = _get_host()
    defaults = _get_defaults()
    
    # Log what we're using
    ref_num = defaults.get("server_reference_number", "") or defaults.get("reference_number", "NOT SET")
    cost_ctr = defaults.get("server_cost_center", "") or defaults.get("cost_center", "NOT SET")
    log.info(f"Syncing quotation {quotation.name} with reference_number={ref_num}, cost_center={cost_ctr}")
    
    for attempt in range(max_retries):
        log.info(f"Syncing quotation {quotation.name} to Frappe (attempt {attempt + 1}/{max_retries})")
        
        result = _push_quotation_to_frappe(quotation.to_dict(), api_key, api_secret, defaults, host)
        
        if result:
            # Success
            frappe_ref = result if result not in ("success", "exists", "skipped") else ""
            mark_quotation_synced(quotation.local_id, frappe_ref)
            log.info(f"✅ Quotation {quotation.name} synced successfully")
            return True
        
        # Failed, wait before retry
        if attempt < max_retries - 1:
            wait_time = 5 * (attempt + 1)  # 5, 10, 15 seconds
            log.info(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
    
    log.error(f"❌ Failed to sync quotation {quotation.name} after {max_retries} attempts")
    return False


# =============================================================================
# QTHREAD WORKER
# =============================================================================

try:
    from PySide6.QtCore import QObject

    class QuotationSyncWorker(QObject):
        def run(self) -> None:
            log.info("Quotation sync worker started (interval=%ds, max=%d/min).",
                     SYNC_INTERVAL, MAX_PER_MINUTE)
            while True:
                try:
                    # First push unsynced local quotations to Frappe
                    push_unsynced_quotations()
                    
                    # Then fetch new quotations from Frappe
                    sync_quotations_from_frappe()
                    
                except Exception as exc:
                    log.error("Unhandled error in quotation sync worker: %s", exc)
                time.sleep(SYNC_INTERVAL)

except ImportError:
    class QuotationSyncWorker:
        def run(self) -> None:
            pass


def start_quotation_sync_thread() -> object:
    """Start the quotation sync background thread — call once from MainWindow.__init__."""
    try:
        from PySide6.QtCore import QThread
        thread = QThread()
        worker = QuotationSyncWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        thread._worker = worker
        thread.start()
        log.info("Quotation sync QThread started.")
        return thread
    except ImportError:
        def _loop():
            while True:
                try:
                    push_unsynced_quotations()
                    sync_quotations_from_frappe()
                except Exception as exc:
                    log.error("Unhandled error: %s", exc)
                time.sleep(SYNC_INTERVAL)
        t = threading.Thread(target=_loop, daemon=True, name="QuotationSyncThread")
        t.start()
        return t
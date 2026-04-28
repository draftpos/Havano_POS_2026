import json
import urllib.request
import urllib.parse
import logging
import traceback
import threading
import time
from typing import List, Dict

log = logging.getLogger(__name__)

# Enable debug printing for console
def debug_print(msg: str, data: any = None):
    print(f"[BUNDLE SYNC] {msg}")
    if data:
        print(f"[BUNDLE SYNC] Data: {json.dumps(data, indent=2, default=str)[:500]}")

def fetch_bundles_from_frappe(api_key: str, api_secret: str, host: str) -> List[Dict]:
    """GET /api/method/saas_api.www.api.get_my_product_bundles"""
    url = f"{host}/api/method/saas_api.www.api.get_my_product_bundles"
    debug_print(f"Fetching bundles from: {url}")
    
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {api_key}:{api_secret}")
    req.add_header("Accept", "application/json")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            debug_print(f"Response received", data)
            bundles = data.get("message", [])
            debug_print(f"Found {len(bundles)} bundle(s) from Frappe")
            return bundles
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode()[:500]
        except:
            pass
        debug_print(f"HTTP Error {e.code}: {error_body}")
        log.error(f"Failed to fetch bundles: HTTP {e.code} - {error_body}")
        return []
    except Exception as e:
        debug_print(f"Exception: {str(e)}")
        debug_print(traceback.format_exc())
        log.error(f"Failed to fetch bundles: {e}")
        return []
def push_bundle_to_frappe(bundle: Dict, api_key: str, api_secret: str, host: str) -> bool:
    """POST /api/resource/Product Bundle"""
    # URL encode the space in "Product Bundle"
    url = f"{host}/api/resource/Product%20Bundle"
    
    # Get bundle name and generate a unique new_item_code
    bundle_name = bundle.get('name') or bundle.get('bundle_name', '')
    # Create a unique ID for new_item_code (Frappe will auto-generate if not provided)
    # But we must include the field
    
    # Build payload matching Frappe Product Bundle doctype requirements
    payload = {
        "new_item_code": bundle_name,
        "parent_item": bundle_name,  # Frappe uses this as the bundle name in Product Bundle
        "description": bundle.get('description', ''),
        "items": []
    }
    
    # [HOTFIX] Frappe requires the Parent Item to exist as an 'Item' before 'Product Bundle' can link to it.
    item_payload = {
        "item_code": bundle_name,
        "item_name": bundle_name,
        "item_group": "Products", 
        "is_stock_item": 0,
        "include_item_in_manufacturing": 0,
        "description": bundle.get('description', '')
    }
    
    req_item = urllib.request.Request(f"{host}/api/resource/Item", data=json.dumps(item_payload).encode(), method="POST")
    req_item.add_header("Authorization", f"token {api_key}:{api_secret}")
    req_item.add_header("Content-Type", "application/json")
    req_item.add_header("Accept", "application/json")
    try:
        urllib.request.urlopen(req_item, timeout=10)
        debug_print(f"Created parent item '{bundle_name}' in Frappe successfully.")
    except Exception as e:
        # Ignore: It either exists already (409) or failed due to strict item groups. We will proceed to push the bundle regardless.
        debug_print(f"Parent Item creation skipped/failed (likely exists): {e}")
    
    # Handle items - format exactly as required
    items = bundle.get('items', [])
    for item in items:
        payload["items"].append({
            "item_code": item.get('item_code') or item.get('product_part_no', ''),
            "qty": float(item.get('quantity', 1))
        })
    
    # Check if items are empty - Frappe requires at least one item
    if not payload["items"]:
        debug_print(f"❌ Bundle has no items, cannot push: {bundle_name}")
        return False
    
    debug_print(f"Pushing bundle to Frappe via /api/resource/Product%20Bundle", payload)
    
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"token {api_key}:{api_secret}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            debug_print(f"Push response", result)
            # For resource API, success means we got a data object back
            success = result.get("data") is not None
            if success:
                debug_print(f"✅ Successfully pushed bundle: {payload['new_item_code']}")
            else:
                debug_print(f"❌ Push failed: {result.get('exception', result)}")
            return success
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode()[:500]
        except:
            pass
        debug_print(f"HTTP Error {e.code} pushing bundle: {error_body}")
        log.error(f"Failed to push bundle: HTTP {e.code} - {error_body}")
        return False
    except Exception as e:
        debug_print(f"Exception pushing bundle: {str(e)}")
        debug_print(traceback.format_exc())
        log.error(f"Failed to push bundle: {e}")
        return False

def sync_pending_bundles() -> Dict:
    """Sync local 'pending' bundles to Frappe"""
    debug_print("Starting sync_pending_bundles...")
    
    try:
        from models.product_bundle import get_bundles_pending_sync, update_bundle_sync_status
        from services.credentials import get_credentials
        from services.site_config import get_host
    except ImportError as e:
        debug_print(f"Import error: {e}")
        return {"synced": 0, "errors": 1, "message": f"Import error: {e}"}
    
    try:
        api_key, api_secret = get_credentials()
        host = get_host()
        debug_print(f"Host: {host}, API Key present: {bool(api_key)}")
    except Exception as e:
        debug_print(f"Credentials error: {e}")
        return {"synced": 0, "errors": 1, "message": f"Credentials error: {e}"}
    
    if not api_key or not api_secret:
        debug_print("No credentials available")
        return {"synced": 0, "errors": 0, "message": "No credentials"}
    
    try:
        bundles = get_bundles_pending_sync()
        debug_print(f"Found {len(bundles)} pending bundle(s) in local DB")
        
        synced = 0
        errors = 0
        
        for bundle in bundles:
            bundle_name = bundle.get('name') or bundle.get('bundle_name', 'Unknown')
            debug_print(f"Processing bundle: {bundle_name} (ID: {bundle.get('id')})")
            
            if push_bundle_to_frappe(bundle, api_key, api_secret, host):
                try:
                    update_bundle_sync_status(bundle['id'], 'synced')
                except:
                    pass
                synced += 1
            else:
                try:
                    update_bundle_sync_status(bundle['id'], 'failed')
                except:
                    pass
                errors += 1
        
        debug_print(f"Sync complete: {synced} synced, {errors} errors")
        return {"synced": synced, "errors": errors}
    except Exception as e:
        debug_print(f"Error in sync_pending_bundles: {e}")
        debug_print(traceback.format_exc())
        return {"synced": 0, "errors": 1, "message": str(e)}

def pull_all_bundles() -> Dict:
    """Fetch all bundles from Frappe and merge locally"""
    debug_print("Starting pull_all_bundles...")
    
    try:
        from models.product_bundle import create_bundle, update_bundle, get_bundle_by_name, update_bundle_sync_status
        from services.credentials import get_credentials
        from services.site_config import get_host
    except ImportError as e:
        debug_print(f"Import error: {e}")
        return {"saved": 0, "skipped": 0, "total": 0, "error": str(e)}
    
    try:
        api_key, api_secret = get_credentials()
        host = get_host()
        debug_print(f"Host: {host}, API Key present: {bool(api_key)}")
    except Exception as e:
        debug_print(f"Credentials error: {e}")
        return {"saved": 0, "skipped": 0, "total": 0, "error": str(e)}
    
    if not api_key or not api_secret:
        debug_print("No credentials available")
        return {"saved": 0, "skipped": 0, "total": 0, "message": "No credentials"}
    
    try:
        remote_bundles = fetch_bundles_from_frappe(api_key, api_secret, host)
        debug_print(f"Fetched {len(remote_bundles)} bundle(s) from Frappe")
        
        saved = 0
        skipped = 0
        
        for remote in remote_bundles:
            name = remote.get('name') or remote.get('new_item_code')
            debug_print(f"Processing remote bundle: {name}")
            
            if not name:
                debug_print("  Skipping: No name found")
                continue
            
            items = []
            for item in remote.get('items', []):
                items.append({
                    'item_code': item.get('item_code', ''),
                    'quantity': float(item.get('qty', 1)),
                    'rate': float(item.get('rate', 0)),
        
                    'uom': item.get('uom') or 'Nos'
                })
            
            debug_print(f"  Items: {len(items)} product(s)")
            
            try:
                existing = get_bundle_by_name(name)
                if existing:
                    debug_print(f"  Bundle exists, updating...")
                    update_bundle(existing['id'], name, items, remote.get('description', ''))
                    update_bundle_sync_status(existing['id'], 'synced')
                    skipped += 1
                    debug_print(f"  ✅ Updated bundle: {name}")
                else:
                    debug_print(f"  Bundle new, creating...")
                    new_id = create_bundle(name, items, remote.get('description', ''))
                    if new_id:
                        update_bundle_sync_status(new_id, 'synced')
                    saved += 1
                    debug_print(f"  ✅ Created bundle: {name}")
            except Exception as e:
                debug_print(f"  ❌ Error processing bundle {name}: {e}")
                debug_print(traceback.format_exc())
        
        debug_print(f"Pull complete: {saved} saved, {skipped} updated, {len(remote_bundles)} total")
        return {"saved": saved, "skipped": skipped, "total": len(remote_bundles)}
    except Exception as e:
        debug_print(f"Error in pull_all_bundles: {e}")
        debug_print(traceback.format_exc())
        return {"saved": 0, "skipped": 0, "total": 0, "error": str(e)}


# =============================================================================
# BUNDLE SYNC DAEMON (runs every 20 seconds in background thread)
# =============================================================================

class BundleSyncWorker:
    """Background thread worker that syncs bundles every 20 seconds"""
    
    def __init__(self):
        self._running = True
        self._interval = 20  # 20 seconds
        self._last_sync = 0
    
    def stop(self):
        """Stop the sync worker"""
        self._running = False
        print("[BundleSync] Worker stopped")
    
    def run(self):
        """Main sync loop"""
        print("[BundleSync] Worker started, syncing every 20 seconds")
        
        while self._running:
            try:
                now = time.time()
                
                if now - self._last_sync >= self._interval:
                    self._last_sync = now
                    self._do_sync()
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                print(f"[BundleSync] Error in loop: {e}")
                time.sleep(5)  # Back off on error
    
    def _do_sync(self):
        """Perform the actual sync (pull and push)"""
        try:
            print("[BundleSync] Running sync cycle...")
            
            # 1. Pull bundles from Frappe
            pull_result = pull_all_bundles()
            print(f"[BundleSync] Pull: {pull_result.get('saved', 0)} new, {pull_result.get('skipped', 0)} updated")
            
            # 2. Push pending bundles to Frappe
            push_result = sync_pending_bundles()
            print(f"[BundleSync] Push: {push_result.get('synced', 0)} synced, {push_result.get('errors', 0)} errors")
            
            print(f"[BundleSync] Sync cycle complete")
            
        except Exception as e:
            print(f"[BundleSync] Sync failed: {e}")
            traceback.print_exc()


def start_bundle_sync_daemon():
    """Start the bundle sync daemon in a background thread"""
    import threading
    
    worker = BundleSyncWorker()
    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    
    print("[BundleSync] Daemon started (runs every 20s)")
    
    return {
        "thread": thread,
        "worker": worker
    }
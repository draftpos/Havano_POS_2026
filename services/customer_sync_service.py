# =============================================================================
# services/customer_sync_service.py
# (credentials delegated to services.credentials)
# Robust customer synchronization for Frappe and SaaS modes
# =============================================================================

from __future__ import annotations

import json
import logging
import time
import urllib.request
import urllib.parse
from services.network_utils import safe_urlopen

log = logging.getLogger("CustomerSync")

CUSTOMER_SYNC_INTERVAL = 30    # 30-second customer sync interval
PAGE_LIMIT = 200               # pull up to 200 customers per page


def _get_credentials() -> tuple[str, str]:
    """Retrieves API keys from credentials service or fallback to DB."""
    try:
        from services.credentials import get_credentials
        k, s = get_credentials()
        if k and s:
            return k, s
    except Exception:
        pass
    try:
        from database.db import get_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "SELECT api_key, api_secret FROM company_defaults "
            "WHERE id=(SELECT MIN(id) FROM company_defaults)"
        )
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return str(row[0]), str(row[1] or "")
    except Exception:
        pass
    return "", ""


def _is_rich_customer_payload(cust_list: list) -> bool:
    """Verifies that the customer objects contain more than just bare {'name': '...'}."""
    if not cust_list or not isinstance(cust_list, list):
        return False
    sample = cust_list[0]
    if not isinstance(sample, dict):
        return False
    # If the object only contains 'name' and nothing else, it is a bare REST index
    keys = set(sample.keys()) - {"name"}
    return len(keys) > 0


def sync_customers() -> dict:
    """
    Fetches customers from Frappe/ERPNext in pages and upserts them into the local DB.
    Guarantees default_price_list, warehouse, cost center, and balances are preserved and updated.
    """
    api_key, api_secret = _get_credentials()
    if not api_key:
        log.warning("[customer-sync] No credentials - skipping.")
        return {"inserted": 0, "updated": 0, "total_api": 0, "errors": 0}

    from services.site_config import get_host as _gh
    base_url = _gh()
    if not base_url:
        log.warning("[customer-sync] No host configured - skipping.")
        return {"inserted": 0, "updated": 0, "total_api": 0, "errors": 0}

    ok = err = 0
    page = 1

    log.info("[customer-sync] Starting sync cycle...")

    from services.credentials import build_auth_header, get_system_mode
    auth_hdr = build_auth_header(api_key, api_secret)
    mode = (get_system_mode() or "frappe").lower()

    while True:
        # Determine endpoints based on system mode
        if mode == "saas":
            endpoints = [
                f"{base_url}/api/method/saas_api.www.api.get_customers?page={page}&limit={PAGE_LIMIT}",
                f"{base_url}/api/method/havano_pos_integration.api.get_customer?page={page}&limit={PAGE_LIMIT}",
                f"{base_url}/api/method/havano_pos_integration.api.get_customers?page={page}&limit={PAGE_LIMIT}",
            ]
        else:
            endpoints = [
                f"{base_url}/api/method/havano_pos_integration.api.get_customer?page={page}&limit={PAGE_LIMIT}",
                f"{base_url}/api/method/havano_pos_integration.api.get_customers?page={page}&limit={PAGE_LIMIT}",
                f"{base_url}/api/method/saas_api.www.api.get_customers?page={page}&limit={PAGE_LIMIT}",
            ]

        last_error = None
        customer_list = None

        for current_url in endpoints:
            req = urllib.request.Request(current_url)
            if auth_hdr:
                req.add_header("Authorization", auth_hdr)
            req.add_header("Accept", "application/json")

            try:
                endpoint_label = current_url.split('?')[0].split('/')[-1]
                log.debug("[customer-sync] Fetching page %d via %s...", page, endpoint_label)
                with safe_urlopen(req, timeout=30) as response:
                    raw_data = response.read().decode()
                    data = json.loads(raw_data)

                    candidates = []
                    if "data" in data and isinstance(data["data"], list):
                        candidates = data["data"]
                    else:
                        msg = data.get("message", {})
                        if isinstance(msg, dict):
                            candidates = msg.get("customers", [])
                        elif isinstance(msg, list):
                            candidates = msg

                    if candidates and _is_rich_customer_payload(candidates):
                        customer_list = candidates
                        break
                    elif candidates:
                        log.debug("[customer-sync] %s returned shallow payload, trying next endpoint...", endpoint_label)
                    elif isinstance(data.get("message"), dict) and "customers" in data.get("message", {}):
                        # Empty customer list on current page (end of pagination)
                        customer_list = []
                        break

            except urllib.error.HTTPError as e:
                log.debug("[customer-sync] Endpoint %s returned HTTP %d", current_url.split('?')[0].split('/')[-1], e.code)
                last_error = e
            except Exception as e:
                log.debug("[customer-sync] Error fetching via %s: %s", current_url.split('?')[0].split('/')[-1], e)
                last_error = e

        if customer_list is None:
            if last_error:
                log.error("[customer-sync] Network or Server error on page %d: %s", page, last_error)
            break

        if not customer_list:
            log.info("[customer-sync] Reached end of customer records on page %d.", page)
            break

        from models.customer import upsert_from_frappe

        for cust in customer_list:
            try:
                upsert_from_frappe(cust)
                ok += 1
            except Exception as e:
                err += 1
                log.error(
                    "[customer-sync] Error processing '%s': %s",
                    cust.get("customer_name", "Unknown"), e
                )

        if len(customer_list) < PAGE_LIMIT:
            break

        page += 1

    log.info("[customer-sync] Finished. Successfully synced: %d, Errors: %d", ok, err)
    return {
        "inserted": ok,
        "updated": 0,
        "total_api": ok + err,
        "errors": err
    }


# =============================================================================
# BACKGROUND THREAD (PySide6 / Threading Fallback)
# =============================================================================

_customer_sync_running = False

def start_customer_sync_thread() -> dict:
    global _customer_sync_running
    import threading
    def _loop():
        global _customer_sync_running
        _customer_sync_running = True
        while _customer_sync_running:
            try:
                sync_customers()
            except Exception as exc:
                log.error("[customer-sync] Error in sync loop: %s", exc)
            time.sleep(CUSTOMER_SYNC_INTERVAL)

    t = threading.Thread(target=_loop, daemon=True, name="CustomerSyncThread")
    t.start()
    log.info("[customer-sync] Background Thread started.")
    return {"thread": t, "worker": None}


def stop_customer_sync_thread():
    global _customer_sync_running
    _customer_sync_running = False
    log.info("Customer sync daemon stop requested.")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    import logging as _l
    _l.basicConfig(level=_l.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    sync_customers()
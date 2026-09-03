import json
import urllib.request
from database.db import get_connection
from services.credentials import get_all_credentials
from models.company_defaults import get_defaults
from services.network_utils import safe_urlopen
from services.site_config import get_host as _get_host
import logging

log = logging.getLogger("ShowLine")
REQUEST_TIMEOUT = 60

def sync_dosages_odoo():
    creds = get_all_credentials()
    defaults = get_defaults() or {}
    host = defaults.get("server_api_host") or _get_host()
    api_key = defaults.get("odoo_token") or creds.get("odoo_token")

    if not host or not api_key:
        print(f"[Odoo Dosage Sync] Skipping: Missing host or token! (Host: {bool(host)}, Token: {bool(api_key)})", flush=True)
        return

    db_name = defaults.get("server_database", "")
    url = f"{host.rstrip('/')}/saas_api/get_dosages"
    try:
        body = json.dumps({"db": db_name}).encode('utf-8')
        req = urllib.request.Request(url, data=body)
        req.add_header("Authorization", api_key)
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "PostmanRuntime/7.54.0")
        req.method = "POST"

        with safe_urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode())
        
        dosages = data.get("message", {}).get("dosages", [])
        if dosages:
            print(f"[Odoo Dosage Sync] Synced {len(dosages)} dosages from Odoo! (from old format)", flush=True)
            log.info(f"[Odoo Dosage Sync] Synced {len(dosages)} dosages from Odoo!")
            _upsert_dosages(dosages)
        elif data.get("success"):
            resp_data = data.get("data", {})
            items = resp_data.get("items") or []
            if items:
                print(f"[Odoo Dosage Sync] Synced {len(items)} dosages from Odoo! (from new format)", flush=True)
                log.info(f"[Odoo Dosage Sync] Synced {len(items)} dosages from Odoo!")
                _upsert_dosages(items)
        else:
            print(f"[Odoo Dosage Sync] No dosages found or sync failed. Response: {data.keys()}", flush=True)
            log.warning(f"[Odoo Dosage Sync] No dosages found or unsupported format: {data.keys()}")
    except Exception as e:
        log.error(f"[Odoo Dosage Sync] Sync failed: {e}")

def _upsert_dosages(items: list[dict]):
    conn = get_connection(); cur = conn.cursor()
    try:
        for item in items:
            # Fallback to name or ID if code is empty
            code = str(item.get("code") or item.get("name") or f"DOSAGE-{item.get('id')}").strip()
            if not code: continue
            
            frappe_name = f"ODOO-{item.get('id')}"
            description = str(item.get("description") or item.get("name") or "").strip()
            
            cur.execute("""
                MERGE dosages AS target
                USING (SELECT ? AS code) AS src ON target.code = src.code
                WHEN MATCHED THEN
                    UPDATE SET description = ?, frappe_name = ?, synced = 1, sync_date = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (frappe_name, code, description, synced, sync_date)
                    VALUES (?, ?, ?, 1, GETDATE());
            """, (code, description, frappe_name, frappe_name, code, description))
            
        conn.commit()
        print(f"[Odoo Dosage Sync] Successfully upserted {len(items)} dosages into database.", flush=True)
    except Exception as e:
        conn.rollback()
        print(f"[Odoo Dosage Sync] DB error in dosages: {e}", flush=True)
        log.error(f"[Odoo Dosage Sync] DB error in dosages: {e}")
    finally:
        conn.close()

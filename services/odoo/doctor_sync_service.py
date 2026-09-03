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

def sync_doctors_odoo():
    creds = get_all_credentials()
    defaults = get_defaults() or {}
    host = defaults.get("server_api_host") or _get_host()
    api_key = defaults.get("odoo_token") or creds.get("odoo_token")

    if not host or not api_key: return

    db_name = defaults.get("server_database", "")
    url = f"{host.rstrip('/')}/saas_api/get_doctors"
    try:
        body = json.dumps({"db": db_name}).encode('utf-8')
        req = urllib.request.Request(url, data=body)
        req.add_header("Authorization", api_key)
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "PostmanRuntime/7.54.0")
        req.method = "POST"

        with safe_urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode())
        
        doctors = data.get("message", {}).get("doctors", [])
        if doctors:
            _upsert_doctors(doctors)
        elif data.get("success"): # Fallback for old APIs
            _upsert_doctors(data.get("data", {}).get("items") or [])
    except Exception as e:
        log.error(f"[OdooSync] Doctor sync failed: {e}")

def _upsert_doctors(items: list[dict]):
    conn = get_connection(); cur = conn.cursor()
    try:
        for item in items:
            name = str(item.get("display_name") or item.get("name") or "").strip()
            if not name: continue
            
            frappe_name = f"ODOO-{item.get('id')}"
            practice_no = str(item.get("doctor_reg_no") or "").strip()
            phone = str(item.get("phone") or item.get("mobile") or "").strip()
            
            cert_filename = str(item.get("doctor_certificate_filename") or "").strip()
            cert_base64 = str(item.get("doctor_certificate") or "").strip()
            
            cur.execute("""
                MERGE doctors AS target
                USING (SELECT ? AS frappe_name) AS src ON target.frappe_name = src.frappe_name
                WHEN MATCHED THEN
                    UPDATE SET full_name = ?, practice_no = ?, phone = ?, doctor_certificate_filename = ?, doctor_certificate = ?, synced = 1
                WHEN NOT MATCHED THEN
                    INSERT (frappe_name, full_name, practice_no, phone, doctor_certificate_filename, doctor_certificate, synced)
                    VALUES (?, ?, ?, ?, ?, ?, 1);
            """, (frappe_name, name, practice_no, phone, cert_filename, cert_base64, 
                  frappe_name, name, practice_no, phone, cert_filename, cert_base64))
            
        conn.commit()
    except Exception as e:
        conn.rollback(); log.error(f"[OdooSync] DB error in doctors: {e}")
    finally:
        conn.close()

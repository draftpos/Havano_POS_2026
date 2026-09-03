import json
import logging
import urllib.request
from database.db import get_connection
from models.company_defaults import get_defaults
from services.credentials import get_all_credentials
from services.network_utils import safe_urlopen

log = logging.getLogger(__name__)

def sync_users_odoo() -> dict:
    """
    Sync users from Odoo SaaS API via /saas_api/get_users
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        defaults = get_defaults() or {}
        host = defaults.get("server_api_host", "").rstrip("/")
        api_key = get_all_credentials().get("odoo_token") or defaults.get("odoo_token") or ""
        db_name = defaults.get("server_database", "")
        
        if not host or not api_key:
            return {"error": "Missing host or token"}
            
        url = f"{host}/saas_api/get_users"
        body = json.dumps({"db": db_name}).encode('utf-8')
        
        req = urllib.request.Request(url, data=body)
        req.add_header("Authorization", api_key)
        req.add_header("Content-Type", "application/json")
        req.method = "POST"
        
        with safe_urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            
        items = data.get("message", {}).get("users", [])
        if not items:
            log.warning(f"[Odoo User Sync] No users found or unsupported format: {data.keys()}")
            return {"synced": 0}

        synced_count = 0
        for item in items:
            username = str(item.get("login", "")).strip()
            if not username:
                continue

            full_name = str(item.get("name", "")).strip()
            parts = full_name.split(' ', 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""
            email = str(item.get("email", "")).strip()
            active = 1 if item.get("active", True) else 0

            # Roles mapping
            is_pharmacist = 1 if item.get("is_pharmacist") else 0
            is_cashier = 1 if item.get("is_cashier") else 0
            is_admin = 1 if item.get("is_admin") else 0
            
            # Map role by prioritizing strict boolean flags from Odoo
            if is_admin:
                role = "admin"
            elif is_pharmacist:
                role = "Pharmacist"
            elif is_cashier:
                role = "cashier"
            else:
                # Fallback to the string role provided by Odoo
                raw_role = str(item.get("role", "")).strip().lower()
                if raw_role in ("pharmacist",): 
                    role = "Pharmacist"
                elif raw_role in ("admin", "administrator", "manager"): 
                    role = "admin"
                else:
                    # Anything else (like 'group_user', 'user', 'pos user') defaults to cashier
                    role = "cashier"
            
            # CRITICAL: Never demote the default admin user from the admin role!
            if username.lower() == "admin":
                role = "admin"

            cur.execute("""
                IF EXISTS (SELECT 1 FROM users WHERE username = ?)
                    UPDATE users SET 
                        first_name = ?, last_name = ?, email = ?, 
                        role = ?, active = ?
                    WHERE username = ?
                ELSE
                    INSERT INTO users (username, first_name, last_name, email, role, active, password)
                    VALUES (?, ?, ?, ?, ?, ?, '')
            """, (username, first_name, last_name, email, role, active, username,
                  username, first_name, last_name, email, role, active))
            synced_count += 1

        conn.commit()
        log.info(f"[Odoo User Sync] Synced {synced_count} users successfully.")
        return {"synced": synced_count}

    except Exception as e:
        conn.rollback()
        log.error(f"[Odoo User Sync] Sync failed: {e}")
        return {"error": str(e)}
    finally:
        conn.close()

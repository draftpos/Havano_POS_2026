# =============================================================================
# services/odoo/auth_service.py  -  Odoo Authentication
# =============================================================================
import json
import urllib.request
import urllib.error
from services.site_config import get_host as _site_get_host

# Settings
REQUEST_TIMEOUT = 60

_session = {
    "token":          None,
    "api_key":        None,
    "api_secret":     None,
    "source":         None,
    "raw_login_data": None,
    "database":       None,
}

# =============================================================================
# PUBLIC
# =============================================================================

def login(username: str, password: str, database: str) -> dict:
    """
    Attempts to login to Odoo. 
    1. Tries Online first to refresh the session token.
    2. Falls back to Offline if network is unavailable.
    """
    print(f"[odoo_auth] Attempting login for {username}...")
    
    # Attempt Online login first to ensure we get a fresh token for background sync
    online = _try_online_login(username, password, database)

    if online["success"]:
        api_key    = online.get("api_key") or online.get("token") or ""
        session_id = online.get("token") or ""
        
        _session["token"]          = api_key        # api_key is the long-lived credential
        _session["api_key"]        = api_key
        _session["source"]         = "online"
        _session["database"]       = database
        _session["raw_login_data"] = online.get("raw_data")

        user = online["user"]
        print(f"[odoo_auth] [OK] Online login OK - {user['username']} ({user['role']})")

        raw_data = online.get("raw_data", {})
        data_block = raw_data.get("data", {})

        try:
            from models.company_defaults import save_defaults, get_defaults

            def _str(val):
                if val is None or val is False: return ""
                if isinstance(val, dict): return str(list(val.values())[0]) if val else ""
                return str(val)

            # Get the enriched data from parsing
            # If api_key is empty, fallback to token (session_id) so we don't break entirely
            api_key    = online.get("api_key") or online.get("token") or ""
            api_secret = online.get("api_secret", "")
            # session_id kept for reference
            session_id = online.get("token", "")
            data_block = online.get("raw_data", {}).get("user", online.get("raw_data", {}).get("data", {}))

            existing = get_defaults()
            # Map Odoo data to Havano company defaults
            odoo_company = _str(data_block.get("company") or data_block.get("company_name"))
            existing["company_name"]            = odoo_company
            existing["server_company"]          = odoo_company
            
            # Warehouse and Cost Center
            existing["server_warehouse"]        = _str(data_block.get("warehouse") or data_block.get("server_warehouse"))
            existing["server_cost_center"]      = _str(data_block.get("cost_center") or data_block.get("server_cost_center"))
            
            existing["server_username"]         = _str(data_block.get("username") or data_block.get("full_name"))
            existing["server_email"]            = _str(data_block.get("email"))
            existing["server_full_name"]        = _str(data_block.get("full_name"))
            existing["server_api_host"]         = _str(_site_get_host())
            
            # Save credentials - api_key is the long-lived auth token
            existing["system_mode"]             = "odoo"
            existing["server_database"]         = _str(data_block.get("database") or database)
            existing["odoo_token"]              = _str(api_key)   # store api_key here so all sync services use it
            existing["api_key"]                 = _str(api_key)
            existing["api_secret"]              = _str(api_secret)
            
            save_defaults(existing)
            
            # Push to shared credentials module
            try:
                from services.credentials import set_session
                set_session(api_key, api_secret, system_mode="odoo", odoo_token=_str(api_key))
            except Exception as e:
                print(f"[odoo_auth] [!]  credentials.set_session failed: {e}")

            print(f"[odoo_auth] [OK] Company defaults saved for '{odoo_company}'.")
        except Exception as e:
            print(f"[odoo_auth] [!]  Could not save server defaults: {e}")

        try:
            from models.user import update_user_credentials_from_online
            u_block = {
                "username":  data_block.get("username"),
                "email":     _str(data_block.get("email")),
                "full_name": data_block.get("full_name"),
                "role":      user.get("role"),
                "warehouse": user.get("warehouse"),
                "company":   data_block.get("company", {}).get("name") if isinstance(data_block.get("company"), dict) else data_block.get("company")
            }
            persisted = update_user_credentials_from_online(username, password, u_block)
            if persisted:
                user.update(persisted)
                print(f"[odoo_auth] [OK] Local credentials persisted for {user['username']}")
        except Exception as e:
            print(f"[odoo_auth] [!]  Could not persist local credentials: {e}")

        # ── AUTO-SYNC (Moved to background or skipped as MainWindow starts background sync immediately) ──────────────────────
        sync_result = {"success": True, "note": "Sync deferred to background"}

        return {"success": True, "user": user, "source": "online", "sync_result": sync_result}

    # Fallback to offline if online failed (but NOT due to wrong credentials)
    if not online.get("auth_failed"):
        print(f"[odoo_auth] Online login failed ({online.get('error')}), trying offline fallback...")
        offline = _try_offline_login(username, password)
        if offline["success"]:
            _session["source"] = "offline"
            _session["database"] = database
            user = offline["user"]
            print(f"[odoo_auth] [OK] Offline fallback login OK - {user['username']}")
            return {"success": True, "user": user, "source": "offline", "sync_result": None}

    error_msg = online.get("error", "Wrong username or password.")
    return {"success": False, "error": error_msg, "source": "online" if online.get("auth_failed") else "offline"}

def get_session() -> dict:
    return dict(_session)

def is_online() -> bool:
    return _session.get("source") == "online"

def logout():
    for key in _session:
        _session[key] = None


# =============================================================================
# PRIVATE
# =============================================================================

def _try_online_login(username: str, password: str, database: str) -> dict:
    payload_dict = {
        "db": database,
        "usr": username,
        "pwd": password,
        "timezone": ""
    }
    payload = json.dumps(payload_dict).encode("utf-8")
    endpoint = f"{_site_get_host().rstrip('/')}/saas_api/login"
    req = urllib.request.Request(
        url=endpoint, data=payload, method="POST",
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/json",
            "User-Agent": "HavanoPOS/1.0"
        },
    )
    
    print(f"[odoo_auth] Attempting ONLINE login:")
    print(f"  - Endpoint: {endpoint}")
    print(f"  - Database: {database}")
    print(f"  - Username: {username}")
    print(f"  - System:   Odoo")
    
    try:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=ctx) as resp:
            # EXTRACT REAL SESSION ID FROM HEADERS (matching Test D)
            header_session = ""
            set_cookie = resp.headers.get("Set-Cookie", "")
            if "session_id=" in set_cookie:
                header_session = set_cookie.split("session_id=")[1].split(";")[0]
            
            data = json.loads(resp.read().decode("utf-8"))
            if "token" in data or "user" in data:
                # Pass the header_session forward
                return _parse_online_success(data, username, header_session=header_session)
            else:
                msg = data.get("message", data.get("error", "Authentication failed."))
                return {"success": False, "auth_failed": True, "error": msg}
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get("message", f"HTTP {e.code}")
        except Exception:
            msg = f"HTTP {e.code}"
        if e.code in (401, 403, 404):
            return {"success": False, "auth_failed": True, "error": msg}
        return {"success": False, "auth_failed": False, "error": f"Server error {e.code}"}
    except urllib.error.URLError as e:
        return {"success": False, "auth_failed": False, "error": f"Network error: {e.reason}"}
    except Exception as e:
        return {"success": False, "auth_failed": False, "error": str(e)}

def _parse_online_success(data: dict, username: str, header_session: str = "") -> dict:
    data_block = data.get("user", {})
    
    session_id = data.get("token", "")
    api_key = session_id
    api_secret = ""
    
    raw_username = data_block.get("username", username)
    raw_company = data_block.get("company", {}).get("name", "")
    raw_warehouse = data_block.get("warehouse", "")
        
    user = {
        "id":           None,
        "username":     raw_username,
        "display_name": data_block.get("full_name", raw_username),
        "warehouse":    raw_warehouse,
        "cost_center":  data_block.get("cost_center") or "",
        "company":      raw_company,
        "role":         "admin" if "admin" in raw_username.lower() else "cashier",
        "frappe_user":  data_block.get("email") or raw_username,
        "email":        data_block.get("email") or "",
    }
    
    # Inject API Key/Secret into the return block so login() can save them
    return {
        "success": True, 
        "user": user,
        "token": session_id,
        "api_key": api_key,
        "api_secret": api_secret,
        "raw_data": data,
    }

def _try_offline_login(username: str, password: str) -> dict:
    try:
        from models.user import authenticate
        user = authenticate(username, password)
        if user:
            return {"success": True, "user": user}
        return {"success": False, "error": "Wrong username or password (offline)."}
    except Exception as e:
        return {"success": False, "error": f"Local DB error: {e}"}

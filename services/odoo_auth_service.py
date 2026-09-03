# =============================================================================
# services/odoo_auth_service.py  -  Odoo Authentication
# =============================================================================
import json
import urllib.request
import urllib.error

from services.site_config import get_host as _site_get_host

# Settings
REQUEST_TIMEOUT = 60

_session = {
    "token":          None,
    "api_key":        None, # Not used in typical Odoo cookie auth unless token is given
    "api_secret":     None,
    "source":         None,
    "raw_login_data": None,
    "database":       None,
}

# =============================================================================
# PUBLIC
# =============================================================================

def login(username: str, password: str, database: str) -> dict:
    # Try local offline login first
    offline = _try_offline_login(username, password)

    if offline["success"]:
        _session["source"] = "offline"
        _session["database"] = database
        user = offline["user"]
        print(f"[odoo_auth] [OK] Offline login OK (Primary) - {user['username']} ({user['role']})")

        # In Odoo mode: silently refresh the API token from Odoo in background
        # so background sync services always have a valid token.
        try:
            from services.credentials import get_system_mode
            if get_system_mode() == "odoo":
                import threading
                def _refresh_token():
                    try:
                        import json, urllib.request, urllib.error
                        from services.site_config import get_host
                        host = get_host().rstrip("/")
                        endpoint = f"{host}/api/v1/auth/login"
                        payload = json.dumps({"login": username, "password": password, "generate_api_key": True}).encode("utf-8")
                        req = urllib.request.Request(endpoint, data=payload, method="POST")
                        req.add_header("Content-Type", "application/json")
                        req.add_header("Accept", "application/json")
                        import ssl
                        ctx = ssl.create_default_context()
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                            data = json.loads(resp.read().decode())
                        if data.get("success"):
                            api_key = data.get("data", {}).get("api_key", "")
                            if api_key:
                                from models.company_defaults import save_defaults, get_defaults
                                existing = get_defaults()
                                existing["odoo_token"] = api_key
                                save_defaults(existing)
                                from services.credentials import set_session
                                set_session(
                                    existing.get("api_key", ""),
                                    existing.get("api_secret", ""),
                                    odoo_token=api_key,
                                    system_mode="odoo",
                                )
                                print(f"[odoo_auth] [OK] Background Odoo token refreshed ({len(api_key)} chars)")
                            else:
                                print(f"[odoo_auth] [!] No api_key in login response: {data.get('data',{}).keys()}")
                        else:
                            print(f"[odoo_auth] [!] Background token refresh failed: {data.get('error')}")
                    except Exception as e:
                        print(f"[odoo_auth] [!] Background token refresh error: {e}")
                threading.Thread(target=_refresh_token, daemon=True, name="OdooTokenRefresh").start()
        except Exception:
            pass

        return {"success": True, "user": user, "source": "offline", "sync_result": None}

    print(f"[odoo_auth] [!] Offline failed/missing, trying online (Extended timeout)...")
    online = _try_online_login(username, password, database)

    if online["success"]:
        # Odoo usually returns a session_id
        session_id = online.get("token")
        
        _session["token"]          = session_id
        _session["source"]         = "online"
        _session["database"]       = database
        _session["raw_login_data"] = online.get("raw_data")

        user = online["user"]
        print(f"[odoo_auth] [OK] Online login OK - {user['username']} ({user['role']})")

        raw_data = online.get("raw_data", {})
        data_block = raw_data.get("user", {})

        # Save to company defaults so rest of system is happy
        try:
            from models.company_defaults import save_defaults, get_defaults

            def _str(val):
                if val is None: return ""
                if isinstance(val, dict): return str(list(val.values())[0]) if val else ""
                return str(val)

            existing = get_defaults()
            existing["server_company"]          = _str(data_block.get("company", {}).get("name"))
            existing["server_warehouse"]        = _str(user.get("warehouse"))
            existing["server_username"]         = _str(data_block.get("username"))
            existing["server_email"]            = _str(data_block.get("email"))
            existing["server_role"]             = _str(user.get("role"))
            existing["server_full_name"]        = _str(data_block.get("full_name"))
            existing["server_api_host"]         = _str(_site_get_host())
            existing["server_database"]         = _str(database)
            existing["odoo_token"]              = _str(session_id)
            save_defaults(existing)
            print("[odoo_auth] [OK] Server defaults saved.")
        except Exception as e:
            print(f"[odoo_auth] [!]  Could not save server defaults: {e}")

        # Local credential persistence
        try:
            from models.user import update_user_credentials_from_online
            # Create a mock user block compatible with the local DB sync function
            u_block = {
                "username": data_block.get("username"),
                "email": data_block.get("email"),
                "full_name": data_block.get("full_name"),
                "role": user.get("role"),
                "warehouse": user.get("warehouse"),
                "company": data_block.get("company", {}).get("name")
            }
            persisted = update_user_credentials_from_online(username, password, u_block)
            if persisted:
                user["id"] = persisted.get("id")
                print(f"[odoo_auth] [OK] Local credentials persisted for {user['username']}")
        except Exception as e:
            print(f"[odoo_auth] [!]  Could not persist local credentials: {e}")

        return {"success": True, "user": user, "source": "online", "sync_result": None}

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
    
    endpoint = f"{_site_get_host()}/saas_api/login"
    
    req = urllib.request.Request(
        url=endpoint, data=payload, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "token" in data:
                return _parse_online_success(data, username)
            else:
                msg = data.get("error", data.get("message", "Authentication failed."))
                return {"success": False, "auth_failed": True, "error": msg}
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get("error", f"HTTP {e.code}")
        except Exception:
            msg = f"HTTP {e.code}"
        if e.code in (401, 403, 404):
            return {"success": False, "auth_failed": True, "error": msg}
        return {"success": False, "auth_failed": False, "error": f"Server error {e.code}"}
    except urllib.error.URLError as e:
        return {"success": False, "auth_failed": False, "error": f"Network error: {e.reason}"}
    except Exception as e:
        return {"success": False, "auth_failed": False, "error": str(e)}

def _parse_online_success(data: dict, username: str) -> dict:
    user_data = data.get("user", {})
    
    token = data.get("token", "")
    api_key = token
    
    raw_username = user_data.get("username", username)
    raw_company = user_data.get("company", {}).get("name", "")
    raw_warehouse = user_data.get("warehouse", "")
    
    user = {
        "id":           None,
        "username":     raw_username,
        "display_name": user_data.get("full_name", raw_username),
        "warehouse":    raw_warehouse,
        "cost_center":  user_data.get("cost_center", ""),
        "company":      raw_company,
        "role":         "admin" if "admin" in raw_username.lower() else "cashier",
        "frappe_user":  user_data.get("email") or raw_username,
        "email":        user_data.get("email", ""),
    }
    
    return {
        "success": True, 
        "user": user,
        "token": token,
        "api_key": api_key,
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

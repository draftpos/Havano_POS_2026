# =============================================================================
# services/auth_service.py  —  Online/Offline Authentication
# =============================================================================
import json
import urllib.request
import urllib.error

from services.site_config import get_host as _site_get_host
API_BASE_URL    = _site_get_host()
LOGIN_ENDPOINT  = f"{_site_get_host()}/api/method/havano_pos_integration.auth.login"
TIMEZONE        = "Africa/Harare"
REQUEST_TIMEOUT = 8

_session = {
    "token":          None,
    "api_key":        None,
    "api_secret":     None,
    "source":         None,
    "raw_login_data": None,
}


# =============================================================================
# PUBLIC
# =============================================================================

def login(username: str, password: str) -> dict:
    online = _try_online_login(username, password)

    if online["success"]:
        api_key    = online.get("api_key")    or ""
        api_secret = online.get("api_secret") or ""

        _session["token"]          = online.get("token")
        _session["api_key"]        = api_key
        _session["api_secret"]     = api_secret
        _session["source"]         = "online"
        _session["raw_login_data"] = online.get("raw_data")

        # Push new token to shared credentials module (persists to DB too)
        if api_key and api_secret:
            try:
                from services.credentials import set_session
                set_session(api_key, api_secret)
                print(f"[auth] ✅ Token saved: {api_key[:8]}...")
            except Exception as _e:
                print(f"[auth] ⚠️  credentials.set_session failed: {_e}")

        user = online["user"]
        print(f"[auth] ✅ Online login OK — {user['username']} ({user['role']})")

        raw        = online.get("raw_data") or {}
        user_block = raw.get("user") or {}
        user_rights = user_block.get("user_rights") or {}

        try:
            from models.company_defaults import save_defaults, get_defaults

            def _str(val):
                if val is None: return ""
                if isinstance(val, dict): return str(list(val.values())[0]) if val else ""
                return str(val)

            existing = get_defaults()
            existing["server_company"]          = _str(user_block.get("company"))
            existing["server_warehouse"]        = _str(user_block.get("warehouse"))
            existing["server_cost_center"]      = _str(user_block.get("cost_center"))
            existing["server_username"]         = _str(user_block.get("username"))
            existing["server_email"]            = _str(user_block.get("email"))
            existing["server_role"]             = _str(user_block.get("role") or user_rights.get("profile_name"))
            existing["server_full_name"]        = _str(raw.get("full_name") or user_block.get("full_name"))
            existing["server_first_name"]       = _str(user_block.get("first_name"))
            existing["server_last_name"]        = _str(user_block.get("last_name"))
            existing["server_mobile"]           = _str(user_block.get("mobile_no"))
            existing["server_profile"]          = _str(user_rights.get("profile_name"))
            existing["server_vat_enabled"]      = _str(user_rights.get("is_additional_tax_enabled"))
            existing["server_taxes_and_charges"]= _str(user_block.get("taxes_and_charges") or user_rights.get("taxes_and_charges"))
            existing["server_api_host"]         = _str(raw.get("api_host") or API_BASE_URL)
            save_defaults(existing)
            print("[auth] ✅ Server defaults saved.")
        except Exception as e:
            print(f"[auth] ⚠️  Could not save server defaults: {e}")



        sync_result = None
        if online.get("raw_data"):
            try:
                from services.sync_service import sync_from_login_response
                sync_result = sync_from_login_response(online["raw_data"])
                print(f"[auth] 🔄 Auto-sync: {sync_result.get('products_synced', 0)} products synced.")
            except Exception as e:
                print(f"[auth] ⚠️  Auto-sync failed: {e}")
                sync_result = {"error": str(e)}

        return {"success": True, "user": user, "source": "online", "sync_result": sync_result}

    if online.get("auth_failed"):
        return {"success": False, "error": online["error"], "source": "online"}

    print(f"[auth] ⚠️  Online unavailable ({online['error']}), trying offline...")
    offline = _try_offline_login(username, password)

    if offline["success"]:
        _session["source"] = "offline"
        user = offline["user"]
        print(f"[auth] ✅ Offline login OK — {user['username']} ({user['role']})")
        return {"success": True, "user": user, "source": "offline", "sync_result": None}

    return {"success": False, "error": offline["error"], "source": "offline"}


def get_session() -> dict:
    return dict(_session)


def is_online() -> bool:
    return _session.get("source") == "online"


def logout():
    for key in _session:
        _session[key] = None
    try:
        from services.credentials import set_session
        set_session("", "")
    except Exception:
        pass


# =============================================================================
# PRIVATE — Online
# =============================================================================

def _try_online_login(username: str, password: str) -> dict:
    payload = json.dumps({"usr": username, "pwd": password, "timezone": TIMEZONE}).encode("utf-8")
    req = urllib.request.Request(
        url=LOGIN_ENDPOINT, data=payload, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return _parse_online_success(data, username)
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get("message", f"HTTP {e.code}")
        except Exception:
            msg = f"HTTP {e.code}"
        if e.code in (401, 403, 417):
            return {"success": False, "auth_failed": True, "error": "Wrong username or password."}
        return {"success": False, "auth_failed": False, "error": f"Server error {e.code}"}
    except urllib.error.URLError as e:
        return {"success": False, "auth_failed": False, "error": f"Network error: {e.reason}"}
    except Exception as e:
        return {"success": False, "auth_failed": False, "error": str(e)}


def _parse_online_success(data: dict, username: str) -> dict:
    token_string = data.get("token_string", "")
    token_b64    = data.get("token", "")
    api_key = api_secret = None
    if token_string and ":" in token_string:
        api_key, api_secret = token_string.split(":", 1)

    user_block = data.get("user") or {}
    raw_username = (user_block.get("username") or data.get("full_name") or username)
    raw_warehouse = (user_block.get("warehouse") or data.get("warehouse") or username)
    raw_company   = (user_block.get("company") or data.get("company") or "")
    raw_cost_center= (user_block.get("cost_center") or data.get("cost_center") or "")
    full_name    = user_block.get("full_name") or data.get("full_name") or raw_username
    roles        = user_block.get("roles") or []

    user = {
        "id":           None,
        "username":     raw_username,
        "display_name": full_name,
        "warehouse":    raw_warehouse,
        "cost_center":  raw_cost_center,
        "company":      raw_company, 
        "role":         _map_role(roles, raw_username),
    }
    return {
        "success": True, "user": user,
        "token": token_b64, "api_key": api_key, "api_secret": api_secret,
        "raw_data": data,
    }


def _map_role(roles: list, username: str) -> str:
    if roles:
        admin_kw = ("administrator", "system manager", "admin", "manager")
        if any(kw in r.lower() for r in roles for kw in admin_kw):
            return "admin"
        # Pharmacist role — preserved verbatim (title-case) so downstream
        # checks like utils.roles.is_pharmacist() can match it.
        if any("pharmacist" in r.lower() for r in roles):
            return "Pharmacist"
    if username.lower() in ("administrator", "admin"):
        return "admin"
    return "cashier"


# =============================================================================
# PRIVATE — Offline
# =============================================================================

def _try_offline_login(username: str, password: str) -> dict:
    try:
        from models.user import authenticate
        user = authenticate(username, password)
        if user:
            return {"success": True, "user": user}
        return {"success": False, "error": "Wrong username or password (offline)."}
    except Exception as e:
        return {"success": False, "error": f"Local DB error: {e}"}
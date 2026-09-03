# =============================================================================
# services/auth_service.py  -  Online/Offline Authentication
# =============================================================================
import json
import os
import urllib.request
import urllib.error

from services.site_config import get_host as _site_get_host

TIMEZONE        = "Africa/Harare"
REQUEST_TIMEOUT = 60

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
    print(f"[auth] Attempting online login first to fetch latest defaults/terminals...")
    online = _try_online_login(username, password)

    if online["success"]:
        user = online["user"]
        raw        = online.get("raw_data") or {}
        user_block = raw.get("user") or {}
        user_rights = user_block.get("user_rights") or {}

        def _str(val):
            if val is None: return ""
            if isinstance(val, dict): return str(list(val.values())[0]) if val else ""
            return str(val)

        # ── 1. Strict Tenant Isolation Check FIRST ─────────────────────────
        from services.credentials import get_system_mode
        if get_system_mode() == "saas":
            from models.company_defaults import get_defaults
            existing = get_defaults()
            bound_company = str(existing.get("server_company") or existing.get("company_name") or "").strip()
            bound_warehouse = str(existing.get("server_warehouse") or existing.get("warehouse") or "").strip()
            
            if bound_company or bound_warehouse:
                user_company = _str(user_block.get("company")).strip()
                user_warehouse = _str(user_block.get("warehouse")).strip()
                shops = user_block.get("shops") or raw.get("shops") or []

                is_same_tenant = False

                if bound_company and user_company and (bound_company.lower() in user_company.lower() or user_company.lower() in bound_company.lower()):
                    is_same_tenant = True
                elif bound_warehouse and user_warehouse and (bound_warehouse.lower() in user_warehouse.lower() or user_warehouse.lower() in bound_warehouse.lower()):
                    is_same_tenant = True
                elif shops and isinstance(shops, list):
                    for s in shops:
                        if isinstance(s, dict):
                            s_name = str(s.get("name") or s.get("shop_name") or "").strip().lower()
                            if bound_company and (bound_company.lower() in s_name or s_name in bound_company.lower()):
                                is_same_tenant = True
                                break
                            if bound_warehouse and (bound_warehouse.lower() in s_name or s_name in bound_warehouse.lower()):
                                is_same_tenant = True
                                break

                if not is_same_tenant:
                    tenant_name = bound_company or bound_warehouse
                    account_tenant = user_company or "another tenant"
                    username_str = _str(user_block.get("username") or user_block.get("email") or user.get("username"))
                    print(f"[auth] Tenant mismatch blocked BEFORE sync/token save! Bound to '{tenant_name}', user account '{username_str}' belongs to '{account_tenant}'")
                    return {
                        "success": False,
                        "error": f"Access Denied: This terminal is registered to tenant '{tenant_name}'. Account '{username_str}' belongs to '{account_tenant}'. You cannot log in across different tenants.",
                        "source": "online"
                    }

        api_key    = online.get("api_key")    or ""
        api_secret = online.get("api_secret") or ""

        _session["token"]          = online.get("token") or api_key
        _session["api_key"]        = api_key
        _session["api_secret"]     = api_secret
        _session["source"]         = "online"
        _session["raw_login_data"] = online.get("raw_data")
        _session["active_user_email"] = username

        # Push new token to shared credentials module (persists to DB too)
        if api_key:
            try:
                from services.credentials import set_session
                set_session(api_key, api_secret)
                print(f"[auth] [OK] Token saved: {api_key[:8]}...")
            except Exception as _e:
                print(f"[auth] [!]  credentials.set_session failed: {_e}")

        print(f"[auth] [OK] Online login OK - {user['username']} ({user['role']})")

        try:
            from models.company_defaults import save_defaults, get_defaults
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
            existing["server_api_host"]         = _str(_site_get_host())
            existing["server_default_customer"] = _str(user_block.get("default_customer"))
                
            # ── Base Currency & Symbol Extraction in SaaS mode ────────────────
            primary_ccy = _str(user_block.get("currency") or raw.get("currency")).strip()
            currencies_arr = user_block.get("currencies") or raw.get("currencies") or []
            primary_symbol = ""

            if isinstance(currencies_arr, list) and len(currencies_arr) > 0:
                for c_entry in currencies_arr:
                    if isinstance(c_entry, dict):
                        c_name = _str(c_entry.get("name")).strip()
                        c_sym  = _str(c_entry.get("symbol")).strip()
                        if primary_ccy and (c_name.upper() == primary_ccy.upper() or c_sym.upper() == primary_ccy.upper()):
                            primary_symbol = c_name or c_sym
                            if not primary_ccy:
                                primary_ccy = c_sym or c_name
                            break
                        elif not primary_ccy and (c_name or c_sym):
                            primary_ccy = c_sym or c_name
                            primary_symbol = c_name or c_sym
                            break

            if primary_ccy:
                existing["server_company_currency"] = primary_ccy
                existing["server_company_currency_symbol"] = primary_symbol or primary_ccy
                print(f"[auth_service] SaaS base currency set on login: '{primary_ccy}' (symbol: '{existing['server_company_currency_symbol']}')")

            # ── Sync Payment Methods from SaaS Login payload ─────────────────
            user_pms = user_block.get("payment_methods") or raw.get("payment_methods") or []
            if isinstance(user_pms, list) and len(user_pms) > 0:
                try:
                    from models.gl_account import migrate as _ensure_gl_and_mop
                    _ensure_gl_and_mop()
                except Exception as _ge:
                    print(f"[auth_service] Could not verify gl_account / modes_of_payment schema: {_ge}")

                try:
                    from database.db import get_connection
                    conn_mop = get_connection()
                    cur_mop = conn_mop.cursor()
                    synced_pm_names = []
                    base_ccy = str(existing.get("server_company_currency") or "").strip()
                    for pm in user_pms:
                        pm_name = _str(pm.get("name")).strip()
                        pm_type = _str(pm.get("type") or "Cash").strip()
                        raw_pm_ccy = _str(pm.get("account_currency") or pm.get("currency")).strip()
                        pm_ccy = raw_pm_ccy or base_ccy
                        if pm_name:
                            synced_pm_names.append(pm_name)
                            cur_mop.execute("""
                                IF EXISTS (SELECT 1 FROM modes_of_payment WHERE LOWER(name) = LOWER(?))
                                    UPDATE modes_of_payment SET enabled = 1, gl_account = ?, account_currency = ? WHERE LOWER(name) = LOWER(?)
                                ELSE
                                    INSERT INTO modes_of_payment (name, type, mop_type, enabled, gl_account, account_currency)
                                    VALUES (?, ?, ?, 1, ?, ?)
                            """, (pm_name, pm_name, pm_ccy, pm_name, pm_name, pm_type, pm_type, pm_name, pm_ccy))
                    
                    if synced_pm_names:
                        clean_names = [n.lower() for n in synced_pm_names]
                        placeholders = ",".join(["?"] * len(clean_names))
                        cur_mop.execute(f"DELETE FROM modes_of_payment WHERE LOWER(name) NOT IN ({placeholders})", clean_names)
                        # Also delete 0-float 0-income shift_rows for deleted methods in active open shifts
                        cur_mop.execute(f"""
                                DELETE FROM shift_rows
                                WHERE shift_id IN (SELECT id FROM shifts WHERE end_time IS NULL)
                                  AND start_float = 0 AND income = 0 AND counted = 0
                                  AND LOWER(method) NOT IN ({placeholders})
                            """, clean_names)
                        conn_mop.commit()
                        conn_mop.close()
                        print(f"[auth_service] Synced SaaS payment methods: {synced_pm_names} and purged obsolete local modes.")
                except Exception as pm_err:
                    print(f"[auth_service] Error syncing SaaS payment methods: {pm_err}")

                sub_info = raw.get("subscription") if isinstance(raw, dict) else {}
                if isinstance(sub_info, dict):
                    if sub_info.get("days_left") is not None:
                        existing["subscription_days_left"] = str(sub_info.get("days_left"))
                    if sub_info.get("end_date"):
                        existing["subscription_expiry"] = str(sub_info.get("end_date"))[:10]

                save_defaults(existing)
                print("[auth] [OK] Server defaults saved.")
        except Exception as e:
            print(f"[auth] [!]  Could not save server defaults: {e}")

        sync_result = None
        if online.get("raw_data"):
            try:
                from services.sync_service import sync_from_login_response
                sync_result = sync_from_login_response(online["raw_data"])
                print(f"[auth] Auto-sync: {sync_result.get('products_synced', 0)} products synced.")
            except Exception as e:
                print(f"[auth] [!]  Auto-sync failed: {e}")
                sync_result = {"error": str(e)}

        # ── PERSIST CREDENTIALS LOCALLY ──────────────────────────────────
        try:
            from models.user import update_user_credentials_from_online
            u_block = (online.get("raw_data") or {}).get("user") or {}
            persisted = update_user_credentials_from_online(username, password, u_block, api_key, api_secret)
            if persisted:
                user["id"] = persisted.get("id")
                user["pin"] = persisted.get("pin")
                print(f"[auth] [OK] Local credentials & API token persisted for {user['username']}")
        except Exception as e:
            print(f"[auth] [!] Could not persist local credentials: {e}")

        set_active_session_user(username)
        return {"success": True, "user": user, "source": "online", "sync_result": sync_result, "raw_data": online.get("raw_data")}

    print(f"[auth] [!] Online failed, falling back to offline login...")
    offline = _try_offline_login(username, password)
    if offline["success"]:
        _session["source"] = "offline"
        user = offline["user"]
        set_active_session_user(username)
        
        # --- Store Restriction Check ---
        try:
            from models.company_defaults import get_defaults
            existing = get_defaults() or {}
            term_warehouse = str(existing.get("server_warehouse") or existing.get("warehouse") or existing.get("company_name") or "").strip()
            user_warehouse = str(user.get("warehouse") or user.get("default_store") or user.get("allowed_stores") or "").strip()
            user_role      = str(user.get("role") or "").strip().lower()
            is_admin_user  = any(k in user_role for k in ("admin", "system manager", "tenant_admin", "super", "owner"))

            if term_warehouse and not is_admin_user:
                tw_low = term_warehouse.lower().strip()
                is_allowed = False

                if user_warehouse:
                    allowed_stores = [s.strip().lower() for s in user_warehouse.split(",") if s.strip()]
                    if any(tw_low in s or s in tw_low for s in allowed_stores):
                        is_allowed = True

                if not is_allowed:
                    u_email = str(user.get("email") or "").lower()
                    u_name = str(user.get("username") or user.get("full_name") or "").lower()
                    store_tokens = [t for t in tw_low.split() if len(t) > 3 and t not in ("store", "legends", "shop", "pos")]
                    for tok in store_tokens:
                        if tok in u_email or tok in u_name:
                            is_allowed = True
                            break

                if not is_allowed:
                    return {"success": False, "error": f"User does not belong to Store {term_warehouse}.", "source": "offline"}
        except Exception as e:
            print(f"[auth] [!] Offline store check warning: {e}")
        # ------------------------------------
        
        print(f"[auth] [OK] Offline login OK (Fallback) - {user['username']} ({user['role']})")
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
    # We do NOT call set_session("", "") here because the POS terminal 
    # needs to retain its API credentials in company_defaults to 
    # continue background syncing, even when cashiers are logged out 
    # or logging in via PIN.


def select_shop(shop_id: int | str) -> dict:
    """Select shop locally and persist choice matching Flutter AuthService."""
    print(f"[auth] Executing local shop assignment for shop '{shop_id}'.")
    return {"success": True, "data": {}, "skipped": True}


def get_active_session_user() -> str:
    """Return the active logged in cashier email from session, settings, or company_defaults."""
    active = str(_session.get("active_user_email") or "").strip()
    if active:
        return active
    try:
        cfg_path = os.path.join("app_data", "sql_settings.json")
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg_d = json.load(f)
                res = str(cfg_d.get("active_user_email") or cfg_d.get("user_email") or cfg_d.get("last_logged_in_user") or "").strip()
                if res:
                    return res
    except Exception:
        pass
    try:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
        return str(d.get("active_user_email") or d.get("server_email") or d.get("user_email") or "").strip()
    except Exception:
        pass
    return ""


def set_active_session_user(email: str):
    """Explicitly set the active logged in cashier email in session, settings, company_defaults, and SQLite."""
    if not email:
        return
    email = str(email).strip()
    
    # If email is a username/display name (e.g. "Machipisa Cashier"), resolve to SaaS email in DB
    if "@" not in email:
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            c_clean = email.lower()
            cur.execute("""
                SELECT TOP 1 email, frappe_user 
                FROM users 
                WHERE LOWER(username) = ? 
                   OR LOWER(full_name) = ? 
                   OR LOWER(display_name) = ?
            """, (c_clean, c_clean, c_clean))
            row = cur.fetchone()
            conn.close()
            if row:
                db_email = (row[0] or row[1] or "").strip()
                if db_email and "@" in db_email:
                    email = db_email
        except Exception:
            pass

    _session["active_user_email"] = email
    
    # 1. Update sql_settings.json
    try:
        cfg_path = os.path.join("app_data", "sql_settings.json")
        cfg_data = {}
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg_data = json.load(f)
        cfg_data["active_user_email"] = email
        cfg_data["user_email"] = email
        cfg_data["last_logged_in_user"] = email
        cfg_data["email"] = email
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg_data, f, indent=4)
    except Exception:
        pass

    # 2. Update company_defaults in SQLite
    try:
        from database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE company_defaults SET server_email = ?, server_username = ? WHERE id = (SELECT MIN(id) FROM company_defaults)", (email, email))
        conn.commit()
        conn.close()
    except Exception:
        pass


def select_terminal(terminal_id: int | str, takeover: bool = False, user_email: str = None) -> dict:
    """Call backend /api/user/select-terminal to assign or takeover terminal on the server matching Flutter AuthService."""
    from utils.hardware import get_machine_id
    dev_id = get_machine_id()
    
    endpoint = f"{_site_get_host().rstrip('/')}/api/user/select-terminal"
    
    from services.credentials import get_credentials
    api_key, api_secret = get_credentials()
    
    resolved_email = str(user_email or "").strip()
    
    # Convert username to email if necessary
    if resolved_email and "@" not in resolved_email:
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            c_clean = resolved_email.lower()
            cur.execute("""
                SELECT TOP 1 email, frappe_user 
                FROM users 
                WHERE LOWER(username) = ? 
                   OR LOWER(full_name) = ? 
                   OR LOWER(display_name) = ?
            """, (c_clean, c_clean, c_clean))
            row = cur.fetchone()
            conn.close()
            if row:
                db_e = (row[0] or row[1] or "").strip()
                if db_e and "@" in db_e:
                    resolved_email = db_e
        except Exception:
            pass

    if not resolved_email or "@" not in resolved_email:
        resolved_email = str(_session.get("active_user_email") or "").strip()

    if not resolved_email or "@" not in resolved_email:
        try:
            cfg_path = os.path.join("app_data", "sql_settings.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg_d = json.load(f)
                    resolved_email = str(cfg_d.get("active_user_email") or cfg_d.get("user_email") or cfg_d.get("last_logged_in_user") or "").strip()
        except Exception:
            pass

    if not resolved_email or "@" not in resolved_email:
        try:
            from models.company_defaults import get_defaults
            d = get_defaults() or {}
            resolved_email = str(d.get("active_user_email") or d.get("server_email") or d.get("user_email") or "").strip()
        except Exception:
            pass

    # Lock in active session user so future pings stay consistent
    if resolved_email and "@" in resolved_email:
        _session["active_user_email"] = resolved_email

    if takeover:
        print(f"[auth] Executing ONLINE terminal takeover on {endpoint} for terminal '{terminal_id}' (User: '{resolved_email}', Device: {dev_id})...")

    try:
        raw_tid = int(terminal_id) if str(terminal_id).isdigit() else terminal_id
    except Exception:
        raw_tid = terminal_id

    app_ver = "2.0.8.28"
    try:
        import main
        app_ver = getattr(main, "APP_VERSION", app_ver)
    except Exception:
        pass

    payload_dict = {
        "terminal_id": raw_tid,
        "take_over": True if takeover else False,
        "device_hardware_id": dev_id,
        "app_version": app_ver
    }
    if resolved_email and "@" in str(resolved_email):
        payload_dict["user"] = resolved_email

    if takeover:
        print(f"[auth] Executing ONLINE terminal takeover payload: {json.dumps(payload_dict)}")

    from services.credentials import build_auth_header
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    auth_hdr = build_auth_header(api_key, api_secret)
    if auth_hdr:
        headers["Authorization"] = auth_hdr
    elif _session.get("token"):
        tok = str(_session["token"]).strip()
        headers["Authorization"] = tok if tok.lower().startswith("token ") or tok.lower().startswith("bearer ") else f"token {tok}"

    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    def _post_payload(p_dict, attempt=1):
        p_bytes = json.dumps(p_dict).encode("utf-8")
        req = urllib.request.Request(url=endpoint, data=p_bytes, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as net_err:
            if attempt < 2:
                import time
                time.sleep(1.0)
                return _post_payload(p_dict, attempt=attempt + 1)
            raise net_err

    try:
        try:
            res_data = _post_payload(payload_dict)
        except urllib.error.HTTPError as he:
            # Fallback: if app_version or extra field caused rejection, retry with clean payload
            if "app_version" in payload_dict:
                clean_payload = dict(payload_dict)
                clean_payload.pop("app_version", None)
                res_data = _post_payload(clean_payload)
            else:
                raise he

        if takeover:
            print(f"[auth] [OK] Server acknowledged terminal takeover on endpoint {endpoint}")
        else:
            print(f"[auth] [OK] Server acknowledged terminal selection on endpoint {endpoint}")
            
        # ── PERSIST RETURNED PAYLOAD LOCALLY ─────────────────────
        try:
            # 1. Save sale_id_prefix (e.g., "TYBL" / "LBSY")
            res_dict = res_data if isinstance(res_data, dict) else {}
            prefix = res_dict.get("sale_id_prefix") or (res_dict.get("user") or {}).get("sale_id_prefix")
            user_obj = res_dict.get("user") or {}
            
            # Update sql_settings.json
            cfg_path = os.path.join("app_data", "sql_settings.json")
            cfg_data = {}
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg_data = json.load(f)
                except Exception:
                    pass
            
            if prefix:
                old_prefix = cfg_data.get("sale_id_prefix")
                if not old_prefix or takeover:
                    cfg_data["sale_id_prefix"] = str(prefix)
                    if old_prefix != str(prefix):
                        print(f"[auth] Saved sale_id_prefix locally: {prefix}")
            
            if isinstance(user_obj, dict):
                sel_shop = user_obj.get("selected_shop_id") or user_obj.get("default_shop_id")
                if sel_shop:
                    cfg_data["server_shop_id"] = str(sel_shop)
                sel_term = user_obj.get("selected_terminal_id")
                if sel_term and str(sel_term) != str(sel_shop):
                    cfg_data["server_terminal_id"] = str(sel_term)
                
                pl_id = user_obj.get("default_pricelist_id")
                pl_name = user_obj.get("default_pricelist_name")
                if pl_id:
                    cfg_data["default_pricelist_id"] = str(pl_id)
                if pl_name:
                    cfg_data["default_pricelist_name"] = str(pl_name)

            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg_data, f, indent=4)

            # Update company_defaults in SQL
            try:
                from database.db import get_connection
                conn = get_connection()
                cur = conn.cursor()
                if prefix:
                    cur.execute("UPDATE company_defaults SET sale_id_prefix = ? WHERE id = (SELECT MIN(id) FROM company_defaults)", (str(prefix),))
                if isinstance(user_obj, dict) and user_obj.get("selected_terminal_id") and str(user_obj.get("selected_terminal_id")) != str(sel_shop):
                    cur.execute("UPDATE company_defaults SET server_terminal_id = ? WHERE id = (SELECT MIN(id) FROM company_defaults)", (str(user_obj["selected_terminal_id"]),))
                conn.commit()
                conn.close()
            except Exception as _dbe:
                pass

        except Exception as _pe:
            print(f"[auth] Warning: Error persisting select_terminal response payload locally: {_pe}")

        return {"success": True, "data": res_data}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"[auth] select_terminal endpoint 404 on server - proceeding with local assignment.")
            return {"success": True, "data": {}, "skipped": True}
        err_body = ""
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            pass
        print(f"[auth] select_terminal failed: HTTP {e.code} - {err_body}")
        return {"success": False, "error": f"HTTP {e.code}: {err_body}"}
    except Exception as e:
        print(f"[auth] select_terminal error: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# PRIVATE - Online
# =============================================================================

def _try_online_login(username: str, password: str) -> dict:
    from utils.hardware import get_machine_id
    dev_id = get_machine_id()
    payload = json.dumps({
        "usr": username,
        "pwd": password,
        "timezone": TIMEZONE
    }).encode("utf-8")
    endpoint = f"{_site_get_host().rstrip('/')}/api/method/saas_api.www.api.login"
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "app_version": "1.0.0",
        "device_hardware_id": dev_id
    }
    
    req = urllib.request.Request(
        url=endpoint, data=payload, method="POST", headers=headers
    )
    print(f"[auth] Attempting ONLINE login (Frappe):")
    print(f"  - Endpoint: {endpoint}")
    print(f"  - User:     {username}")
    print(f"  - Device:   {dev_id}")

    try:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return _parse_online_success(data, username)
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get("message", f"HTTP {e.code}")
        except Exception:
            msg = f"HTTP {e.code}"
        if e.code in (401, 403, 417, 422):
            return {"success": False, "auth_failed": True, "error": msg}
        return {"success": False, "auth_failed": False, "error": f"Server error {e.code}"}
    except urllib.error.URLError as e:
        return {"success": False, "auth_failed": False, "error": f"Network error: {e.reason}"}
    except Exception as e:
        return {"success": False, "auth_failed": False, "error": str(e)}


def _parse_online_success(data: dict, username: str) -> dict:
    msg_block = data.get("message") if isinstance(data.get("message"), dict) else {}
    token_b64 = data.get("token") or data.get("access_token") or msg_block.get("token") or msg_block.get("access_token") or ""
    
    api_key = str(data.get("api_key") or msg_block.get("api_key") or "").strip()
    api_secret = str(data.get("api_secret") or msg_block.get("api_secret") or "").strip()

    # If the server returned a plain token_string (key:secret), extract it properly for Frappe mode!
    token_string = data.get("token_string") or msg_block.get("token_string") or ""
    if token_string and ":" in token_string:
        api_key, api_secret = token_string.split(":", 1)
    else:
        # SaaS mode: Store Base64 session token in api_key and keep api_secret empty
        if token_b64:
            api_key = token_b64
            api_secret = ""
        elif not (api_key and api_secret):
            if token_string:
                import base64
                api_key = base64.b64encode(token_string.encode("utf-8")).decode("utf-8")
                api_secret = ""


    user_block = data.get("user") or {}
    raw_username = (user_block.get("username") or data.get("full_name") or username)
    raw_warehouse = (user_block.get("warehouse") or data.get("warehouse") or username)
    raw_company   = (user_block.get("company") or data.get("company") or "")
    raw_cost_center= (user_block.get("cost_center") or data.get("cost_center") or "")
    full_name    = user_block.get("full_name") or data.get("full_name") or raw_username

    # Role priority:
    #   1. user.user_rights.profile_name - the authoritative User Rights
    #      Profile; this is what actually governs permissions in ERPNext.
    #   2. user.roles (list) - legacy havano_pos_integration shape.
    #   3. user.role (string) - role_select custom field on the User doc.
    # The profile takes precedence because role_select can drift from the
    # assigned profile; e.g. a user configured with the "Pharmacist" profile
    # may still have role_select="Admin" set, which would otherwise mis-map.
    user_rights = user_block.get("user_rights") or {}
    profile_name = user_rights.get("profile_name") if isinstance(user_rights, dict) else None
    if profile_name:
        roles = [profile_name]
    else:
        roles = user_block.get("roles") or []
        if not roles:
            single = user_block.get("role")
            if single:
                roles = [single]

    user = {
        "id":           None,
        "username":     raw_username,
        "display_name": full_name,
        "warehouse":    raw_warehouse,
        "cost_center":  raw_cost_center,
        "company":      raw_company,
        "role":         _map_role(roles, raw_username),
        "frappe_user":  user_block.get("name") or data.get("email") or raw_username,
        "email":        user_block.get("email") or data.get("email") or "",
    }
    return {
        "success": True, "user": user,
        "token": token_b64, "api_key": api_key, "api_secret": api_secret,
        "raw_data": data,
    }


def _map_role(roles: list, username: str) -> str:
    if roles:
        admin_kw = ("administrator", "system manager", "admin", "manager", "tenant_admin")
        if any(kw in r.lower() for r in roles for kw in admin_kw):
            return "admin"
        # Pharmacist role - preserved verbatim (title-case) so downstream
        # checks like utils.roles.is_pharmacist() can match it.
        if any("pharmacist" in r.lower() for r in roles):
            return "Pharmacist"
    if username.lower() in ("administrator", "admin"):
        return "admin"
    return "cashier"


# =============================================================================
# PRIVATE - Offline
# =============================================================================

def _try_offline_login(username: str, password: str) -> dict:
    try:
        from models.user import authenticate
        user = authenticate(username, password)
        if user:
            # Activate logged-in user's stored cloud API key & secret if available
            api_k = str(user.get("api_key") or "").strip()
            api_s = str(user.get("api_secret") or "").strip()
            try:
                from utils.crypto import decrypt_secret
                api_s = decrypt_secret(api_s)
            except Exception:
                pass

            from services.credentials import get_system_mode
            is_saas = (get_system_mode() == "saas")
            # In SaaS mode, api_s may be empty or password. In Frappe mode, both key and secret are required.
            if api_k and (api_s or is_saas):
                try:
                    from services.credentials import set_session
                    set_session(api_k, api_s)
                    print(f"[auth] Restored active user API token: {api_k[:8]}...")
                except Exception as _e:
                    print(f"[auth] set_session failed in offline login: {_e}")

            # Update logged-in user email/username in company_defaults
            try:
                from models.company_defaults import save_defaults, get_defaults
                defs = get_defaults()
                defs["server_email"] = user.get("email") or defs.get("server_email") or ""
                defs["server_username"] = user.get("username") or defs.get("server_username") or ""
                defs["server_full_name"] = user.get("full_name") or user.get("display_name") or defs.get("server_full_name") or ""
                save_defaults(defs)
            except Exception as _e:
                print(f"[auth] Could not update logged-in user defaults: {_e}")

            return {"success": True, "user": user}
        return {"success": False, "error": "Wrong username or password (offline)."}
    except Exception as e:
        return {"success": False, "error": f"Local DB error: {e}"}
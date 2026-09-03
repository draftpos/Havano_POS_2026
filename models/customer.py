# models/customer.py
from database.db import get_connection, fetchall_dicts, fetchone_dict


def _ensure_price_list_id(cur, name: str | None) -> int | None:
    """
    Resolve a price-list name to its local id, creating the row on miss.
    Returns None if name is empty or not specified.
    """
    nm = (name or "").strip()
    if not nm:
        return None

    cur.execute("SELECT id FROM price_lists WHERE LTRIM(RTRIM(name)) = ?", (nm,))
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        "INSERT INTO price_lists (name, selling) OUTPUT INSERTED.id VALUES (?, 1)",
        (nm,),
    )
    return int(cur.fetchone()[0])

_SELECT = """
    SELECT cu.id, cu.customer_name, cu.customer_group_id,
           cg.name AS customer_group_name, cu.customer_type,
           cu.custom_trade_name, cu.custom_telephone_number,
           cu.custom_email_address, cu.custom_city, cu.custom_house_no,
           cu.custom_warehouse_id, w.name AS warehouse_name,
           cu.custom_cost_center_id, cc.name AS cost_center_name,
           cu.default_price_list_id, pl.name AS price_list_name,
           cu.balance, cu.laybye_balance, cu.outstanding_amount, cu.loyalty_points,
           cu.frappe_synced,
           cu.doctor_id, cu.doctor_frappe_name
    FROM customers cu
    LEFT JOIN customer_groups cg ON cg.id = cu.customer_group_id
    LEFT JOIN warehouses       w  ON w.id  = cu.custom_warehouse_id
    LEFT JOIN cost_centers     cc ON cc.id = cu.custom_cost_center_id
    LEFT JOIN price_lists      pl ON pl.id = cu.default_price_list_id
"""

def get_all_customers() -> list[dict]:
    conn = get_connection(); cur = conn.cursor()
    cur.execute(_SELECT + " ORDER BY cu.customer_name")
    rows = fetchall_dicts(cur); conn.close()
    return [_to_dict(r) for r in rows]

def search_customers(query: str, limit: int = 30) -> list[dict]:
    query_clean = query.strip()
    if not query_clean:
        return []
    like = f"%{query_clean}%"
    conn = get_connection(); cur = conn.cursor()
    # Replace _SELECT with SELECT TOP limit ...
    sel = _SELECT.replace("SELECT ", f"SELECT TOP {limit} ", 1)
    cur.execute(sel +
        " WHERE cu.customer_name LIKE ? OR cu.custom_trade_name LIKE ?"
        " OR cu.custom_telephone_number LIKE ? ORDER BY cu.customer_name",
        (like, like, like))
    rows = fetchall_dicts(cur); conn.close()
    return [_to_dict(r) for r in rows]

def get_customer_by_id(customer_id: int) -> dict | None:
    conn = get_connection(); cur = conn.cursor()
    cur.execute(_SELECT + " WHERE cu.id = ?", (customer_id,))
    row = fetchone_dict(cur); conn.close()
    return _to_dict(row) if row else None

def get_customer_by_name(name: str) -> dict | None:
    conn = get_connection(); cur = conn.cursor()
    cur.execute(_SELECT + " WHERE cu.customer_name = ?", (name,))
    row = fetchone_dict(cur); conn.close()
    return _to_dict(row) if row else None

def upsert_from_frappe(c: dict):
    """
    Handles payload from Frappe. Matches existing customers by name.
    Preserves existing default_price_list_id, warehouse, and cost center if missing in payload.
    """
    conn = get_connection()
    cur = conn.cursor()

    # 1. Resolve Foreign Key IDs by Name (with Trim and Fallback)
    def find_id(table, name, fallback_name=None):
        if not name and not fallback_name: return None
        search_name = (name if name else fallback_name).strip()
        
        # Try matching by name (trimmed)
        cur.execute(f"SELECT id FROM {table} WHERE LTRIM(RTRIM(name)) = ?", (search_name,))
        row = cur.fetchone()
        
        return row[0] if row else None

    warehouse_id   = find_id("warehouses", c.get("custom_warehouse"))
    cost_center_id = find_id("cost_centers", c.get("custom_cost_center"))
    raw_pl_name    = (c.get("default_price_list") or c.get("price_list") or c.get("price_list_name") or "").strip()
    price_list_id  = _ensure_price_list_id(cur, raw_pl_name) if raw_pl_name else None
    group_id       = find_id("customer_groups", c.get("customer_group"))

    def _extract_num(val):
        if isinstance(val, dict):
            val = val.get("balance", 0)
        try:
            return float(val or 0)
        except (ValueError, TypeError):
            return 0.0

    bal_val = _extract_num(c.get("balance"))
    out_val = _extract_num(c.get("outstanding_amount"))
    loy_val = _extract_num(c.get("loyalty_points"))

    cust_name = str(c.get("customer_name") or c.get("name") or c.get("trade_name") or "").strip()
    if not cust_name:
        conn.close()
        return

    # 2. Check existence
    cur.execute("SELECT id, default_price_list_id, custom_warehouse_id, custom_cost_center_id, customer_group_id FROM customers WHERE customer_name = ?", (cust_name,))
    existing = cur.fetchone()

    if existing:
        # Non-destructive update: preserve existing IDs if not present in current payload
        final_pl_id = price_list_id if price_list_id is not None else existing[1]
        final_wh_id = warehouse_id if warehouse_id is not None else existing[2]
        final_cc_id = cost_center_id if cost_center_id is not None else existing[3]
        final_grp_id = group_id if group_id is not None else existing[4]

        cur.execute("""
            UPDATE customers SET
                customer_type = ISNULL(?, customer_type), 
                customer_group_id = ?,
                custom_warehouse_id = ?, 
                custom_cost_center_id = ?, 
                default_price_list_id = ?,
                balance = ?, 
                outstanding_amount = ?, 
                loyalty_points = ?,
                laybye_balance = ISNULL(laybye_balance, 0),
                custom_email_address = ISNULL(NULLIF(?, ''), custom_email_address),
                custom_telephone_number = ISNULL(NULLIF(?, ''), custom_telephone_number),
                custom_city = ISNULL(NULLIF(?, ''), custom_city),
                custom_house_no = ISNULL(NULLIF(?, ''), custom_house_no),
                custom_trade_name = ISNULL(NULLIF(?, ''), custom_trade_name),
                frappe_synced = 1
            WHERE customer_name = ?
        """, (
            c.get("customer_type"), final_grp_id, final_wh_id, final_cc_id, final_pl_id,
            bal_val, out_val, loy_val,
            c.get("email_id") or c.get("custom_email_address") or "",
            c.get("mobile_no") or c.get("custom_telephone_number") or "",
            c.get("primary_address") or c.get("custom_city") or "",
            c.get("custom_house_no") or "",
            c.get("tax_id") or c.get("vat_id") or c.get("custom_trade_name") or "",
            cust_name
        ))
    else:
        # INSERT: New record from Frappe.
        cur.execute("""
            INSERT INTO customers (
                customer_name, customer_type, customer_group_id,
                custom_warehouse_id, custom_cost_center_id, default_price_list_id,
                balance, outstanding_amount, loyalty_points, laybye_balance,
                custom_email_address, custom_telephone_number, custom_city, custom_house_no, custom_trade_name,
                frappe_synced
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 1)
        """, (
            cust_name, c.get("customer_type"), group_id,
            warehouse_id, cost_center_id, price_list_id,
            bal_val, out_val, loy_val,
            c.get("email_id") or c.get("custom_email_address") or "",
            c.get("mobile_no") or c.get("custom_telephone_number") or "",
            c.get("primary_address") or c.get("custom_city") or "",
            c.get("custom_house_no") or "",
            c.get("tax_id") or c.get("vat_id") or c.get("custom_trade_name") or ""
        ))
    
    conn.commit()
    conn.close()

def create_customer(customer_name: str, customer_group_id: int,
                    custom_warehouse_id: int, custom_cost_center_id: int,
                    default_price_list_id: int,
                    doctor_id: int | None = None,
                    doctor_frappe_name: str | None = None,
                    **kwargs) -> dict:
    """Manual creation helper.

    ``doctor_id`` / ``doctor_frappe_name`` are optional pharmacy-mode fields;
    they are always inserted (as NULL if not supplied) so pharmacy-label
    lookup can fall through frappe_name -> doctor_id resolution paths.
    """
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO customers (
            customer_name, customer_group_id, customer_type,
            custom_trade_name, custom_telephone_number, custom_email_address,
            custom_city, custom_house_no,
            custom_warehouse_id, custom_cost_center_id, default_price_list_id,
            doctor_id, doctor_frappe_name,
            laybye_balance, frappe_synced
        ) OUTPUT INSERTED.id VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
    """, (customer_name.strip(), customer_group_id, kwargs.get("customer_type", "Individual"),
          kwargs.get("custom_trade_name", ""), kwargs.get("custom_telephone_number", ""),
          kwargs.get("custom_email_address", ""), kwargs.get("custom_city", ""),
          kwargs.get("custom_house_no", ""),
          custom_warehouse_id, custom_cost_center_id, default_price_list_id,
          doctor_id, doctor_frappe_name))
    new_id = int(cur.fetchone()[0]); conn.commit(); conn.close()
    return get_customer_by_id(new_id)

def update_customer(customer_id: int,
                    doctor_id: int | None = None,
                    doctor_frappe_name: str | None = None,
                    **kwargs) -> dict | None:
    """Manual update helper.

    ``doctor_id`` / ``doctor_frappe_name`` are optional; if present in the
    kwargs/positional list they are included in the dynamic UPDATE set so
    callers who don't care about pharmacy fields aren't forced to pass them.
    """
    c = get_customer_by_id(customer_id)
    if not c: return None

    # Base update set - existing fields (unchanged behaviour)
    set_clauses = [
        "customer_name=?", "customer_group_id=?", "customer_type=?",
        "custom_trade_name=?", "custom_telephone_number=?", "custom_email_address=?",
        "custom_city=?", "custom_house_no=?",
        "custom_warehouse_id=?", "custom_cost_center_id=?", "default_price_list_id=?",
    ]
    params = [
        kwargs.get("customer_name", c["customer_name"]),
        kwargs.get("customer_group_id", c["customer_group_id"]),
        kwargs.get("customer_type", c["customer_type"]),
        kwargs.get("custom_trade_name", c["custom_trade_name"]),
        kwargs.get("custom_telephone_number", c["custom_telephone_number"]),
        kwargs.get("custom_email_address", c["custom_email_address"]),
        kwargs.get("custom_city", c["custom_city"]),
        kwargs.get("custom_house_no", c["custom_house_no"]),
        kwargs.get("custom_warehouse_id", c["custom_warehouse_id"]),
        kwargs.get("custom_cost_center_id", c["custom_cost_center_id"]),
        kwargs.get("default_price_list_id", c["default_price_list_id"]),
    ]

    # Pharmacy fields: only update when explicitly provided. Treat the
    # sentinel default (None + NOT in kwargs) as "leave untouched".
    if doctor_id is not None or "doctor_id" in kwargs:
        set_clauses.append("doctor_id=?")
        params.append(kwargs.get("doctor_id", doctor_id))
    if doctor_frappe_name is not None or "doctor_frappe_name" in kwargs:
        set_clauses.append("doctor_frappe_name=?")
        params.append(kwargs.get("doctor_frappe_name", doctor_frappe_name))

    params.append(customer_id)
    sql = f"UPDATE customers SET {', '.join(set_clauses)} WHERE id=?"

    conn = get_connection(); cur = conn.cursor()
    cur.execute(sql, tuple(params))
    conn.commit(); conn.close()
    return get_customer_by_id(customer_id)

def delete_customer(customer_id: int) -> bool:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    affected = cur.rowcount; conn.commit(); conn.close()
    return affected > 0

def _to_dict(row: dict) -> dict | None:
    if not row: return None
    # Standardize output: converts None to empty strings or 0.0 for safety
    d = dict(row)
    numeric_fields = [
        'balance', 'laybye_balance', 'outstanding_amount', 'loyalty_points',
        'id', 'customer_group_id', 'custom_warehouse_id',
        'custom_cost_center_id', 'default_price_list_id', 'frappe_synced',
        'doctor_id'
    ]
    for k, v in d.items():
        if v is None:
            if k in numeric_fields:
                d[k] = 0 if 'id' not in k else None
            else:
                d[k] = ""
    return d


# =============================================================================
# Frappe Sync-Check Service - INFINITE RETRY VERSION
# =============================================================================

def mark_frappe_synced(customer_id: int) -> None:
    """
    Called by the Frappe push worker on a successful POST.
    Flips frappe_synced = 1 so the retry thread skips re-pushing.
    """
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute(
            "UPDATE customers SET frappe_synced = 1 WHERE id = ?",
            (customer_id,)
        )
        conn.commit(); conn.close()
        print(f"[FrappeSyncCheck] [OK] Customer id={customer_id} marked as synced.")
    except Exception as e:
        print(f"[FrappeSyncCheck] mark_frappe_synced failed: {e}")


def _is_frappe_synced(customer_id: int) -> bool:
    """Returns True if frappe_synced flag is already set in the local DB."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute(
            "SELECT frappe_synced FROM customers WHERE id = ?",
            (customer_id,)
        )
        row = cur.fetchone(); conn.close()
        return bool(row and row[0])
    except Exception:
        return False


def _check_exists_on_frappe(customer_name: str) -> bool:
    """
    Hits Frappe's GET /api/resource/Customer/<name> to verify the record
    exists there.  Returns True on HTTP 200, False on 404 or any error.
    """
    import urllib.request, urllib.error, json, ssl
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        from services.credentials import get_credentials
        api_key, api_secret = get_credentials()
    except Exception:
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute(
                "SELECT api_key, api_secret FROM companies "
                "WHERE id=(SELECT MIN(id) FROM companies)"
            )
            row = cur.fetchone(); conn.close()
            api_key    = str(row[0]) if row and row[0] else ""
            api_secret = str(row[1]) if row and row[1] else ""
        except Exception:
            api_key = api_secret = ""

    if not api_key:
        print("[FrappeSyncCheck] No credentials - cannot verify.")
        return False

    try:
        from services.site_config import get_host as _gh
        base_url = _gh()
    except Exception as e:
        print(f"[FrappeSyncCheck] Could not get host: {e}")
        return False

    import urllib.parse
    encoded_name = urllib.parse.quote(customer_name, safe="")
    url = f"{base_url}/api/resource/Customer/{encoded_name}"
    req = urllib.request.Request(url, method="GET")
    from services.credentials import build_auth_header
    auth_hdr = build_auth_header(api_key, api_secret)
    if auth_hdr:
        req.add_header("Authorization", auth_hdr)
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            data = json.loads(resp.read().decode())
            exists = bool(data.get("data"))
            print(f"[FrappeSyncCheck] GET {url} -> exists={exists}")
            return exists
    except urllib.error.HTTPError as e:
        print(f"[FrappeSyncCheck] GET {url} -> HTTP {e.code}")
        return False
    except Exception as e:
        print(f"[FrappeSyncCheck] GET {url} -> error: {e}")
        return False


def _repush_to_frappe(
    customer_name: str,
    phone: str,
    city: str,
    defs: dict,
    customer_id: int,
) -> bool:
    """
    Re-sends the customer to Frappe using the same payload shape as
    QuickAddCustomerDialog._push_to_frappe.  Marks frappe_synced on success.
    Returns True if successful, False otherwise.
    """
    import urllib.request, urllib.error, json, ssl
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        from services.credentials import get_credentials
        api_key, api_secret = get_credentials()
    except Exception:
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute(
                "SELECT api_key, api_secret FROM companies "
                "WHERE id=(SELECT MIN(id) FROM companies)"
            )
            row = cur.fetchone(); conn.close()
            api_key    = str(row[0]) if row and row[0] else ""
            api_secret = str(row[1]) if row and row[1] else ""
        except Exception:
            api_key = api_secret = ""

    c = get_customer_by_id(customer_id) or {}
    cname = (c.get("customer_name") or "").strip().lower()
    if cname in ("cash customer", "default"):
        mark_frappe_synced(customer_id)
        return True

    if not api_key:
        print("[FrappeSyncCheck] Re-push skipped - no credentials configured.")
        return False
    
    try:
        from models.company_defaults import get_defaults
        fresh_defs = get_defaults()
    except Exception:
        fresh_defs = defs or {}

    try:
        from services.site_config import get_host as _gh
        base_url = _gh()
    except Exception as e:
        print(f"[FrappeSyncCheck] Could not get host in re-push: {e}")
        return False

    cost_center_val = c.get("cost_center_name")
    warehouse_val = c.get("warehouse_name")
    customer_group_val = c.get("customer_group_name") or "Individual"
    price_list_val = c.get("price_list_name") or "Standard Selling"

    if not cost_center_val or not warehouse_val:
        try:
            conn_ref = get_connection()
            cur_ref = conn_ref.cursor()
            cur_ref.execute("""
                SELECT TOP 1 
                       cc.name AS cost_center_name,
                       w.name AS warehouse_name,
                       cg.name AS customer_group_name,
                       pl.name AS price_list_name
                FROM customers cu
                LEFT JOIN customer_groups cg ON cg.id = cu.customer_group_id
                LEFT JOIN warehouses w ON w.id = cu.custom_warehouse_id
                LEFT JOIN cost_centers cc ON cc.id = cu.custom_cost_center_id
                LEFT JOIN price_lists pl ON pl.id = cu.default_price_list_id
                WHERE cu.frappe_synced = 1
                  AND cc.name IS NOT NULL AND LTRIM(RTRIM(cc.name)) <> ''
                  AND w.name IS NOT NULL AND LTRIM(RTRIM(w.name)) <> ''
                ORDER BY cu.id DESC
            """)
            row_ref = cur_ref.fetchone()
            if row_ref:
                if not cost_center_val: cost_center_val = row_ref[0]
                if not warehouse_val: warehouse_val = row_ref[1]
                if customer_group_val == "Individual" and row_ref[2]: customer_group_val = row_ref[2]
                if price_list_val == "Standard Selling" and row_ref[3]: price_list_val = row_ref[3]
            conn_ref.close()
        except Exception as e:
            print(f"[FrappeSyncCheck] Error querying reference synced customer fallback: {e}")

    payload = {
        "name":                     customer_name,
        "customer_name":            customer_name,
        "customer_type":            c.get("customer_type") or "Individual",
        "customer_group":           customer_group_val,
        "currency":                 "USD",
        "custom_customer_tin":      c.get("custom_customer_tin") or "00000000",
        "custom_customer_vat":      c.get("custom_customer_vat") or "11111111",
        "custom_trade_name":        c.get("custom_trade_name") or "None",
        "custom_email_address":     c.get("custom_email_address") or "no-email.havano.cloud",
        "custom_telephone_number":  phone or c.get("custom_telephone_number") or "0000000000",
        "custom_house_no":          c.get("custom_house_no") or "1",
        "custom_street":            "Unknown",
        "custom_customer_address":  "N/A",
        "custom_city":              city or c.get("custom_city") or "N/A",
        "custom_province":          "N/A",
        "default_warehouse":        warehouse_val,
        "warehouse":                warehouse_val,
        "custom_warehouse":         warehouse_val,
        "default_price_list":       price_list_val,
        "default_cost_center":      cost_center_val,
        "cost_center":              cost_center_val,
        "custom_cost_center":       cost_center_val,
        "is_active":                True,
    }
        
    print(f"[FrappeSyncCheck] Payload Cost Center evaluated to: '{payload.get('default_cost_center')}'")
    payload = {k: v for k, v in payload.items() if v}

    url  = f"{base_url}/api/method/saas_api.www.api.create_customer"
    body = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=body, method="POST")
    from services.credentials import build_auth_header
    auth_hdr = build_auth_header(api_key, api_secret)
    if auth_hdr:
        req.add_header("Authorization", auth_hdr)
    req.add_header("Content-Type",  "application/json")
    req.add_header("Accept",        "application/json")

    print(f"[FrappeSyncCheck] Re-push POST {url}")
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            result = json.loads(resp.read().decode())
            frappe_name = result.get("data", {}).get("name") or result.get("message", {}).get("customer_id") or "?"
            print(f"[FrappeSyncCheck] [OK] Re-push succeeded: {frappe_name}")
            mark_frappe_synced(customer_id)
            if frappe_name and frappe_name != "?":
                _create_customer_permissions_for_all_users(frappe_name)
            return True
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        print(f"[FrappeSyncCheck] Re-push HTTP {e.code}: {body_text}")
        
        # Fallback: if Frappe rejects due to missing Warehouse/Cost Center links, retry without them
        if e.code == 417 and "Could not find" in body_text:
            print("[FrappeSyncCheck] Retrying without Warehouse/Cost Center links...")
            keys_to_remove = ["warehouse", "custom_warehouse", "default_warehouse", 
                              "cost_center", "custom_cost_center", "default_cost_center"]
            if any(k in payload for k in keys_to_remove):
                for k in keys_to_remove:
                    payload.pop(k, None)
                
                body = json.dumps(payload).encode()
                req = urllib.request.Request(url, data=body, method="POST")
                if auth_hdr:
                    req.add_header("Authorization", auth_hdr)
                req.add_header("Content-Type",  "application/json")
                req.add_header("Accept",        "application/json")
                try:
                    with urllib.request.urlopen(req, timeout=20, context=ctx) as resp2:
                        result = json.loads(resp2.read().decode())
                        frappe_name = result.get("data", {}).get("name") or result.get("message", {}).get("customer_id") or "?"
                        print(f"[FrappeSyncCheck] [OK] Re-push (without links) succeeded: {frappe_name}")
                        mark_frappe_synced(customer_id)
                        if frappe_name and frappe_name != "?":
                            _create_customer_permissions_for_all_users(frappe_name)
                        return True
                except Exception as e2:
                    print(f"[FrappeSyncCheck] Re-push (without links) failed: {e2}")

        return False
    except Exception as e:
        print(f"[FrappeSyncCheck] Re-push failed: {e}")
        return False


def _create_customer_permissions_for_all_users(frappe_customer_id: str) -> None:
    """Grants User Permission for all local users to the newly created customer on Frappe."""
    import urllib.request, urllib.error, json, ssl
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    if not frappe_customer_id or frappe_customer_id == "?":
        return

    try:
        from services.credentials import get_credentials
        api_key, api_secret = get_credentials()
    except Exception:
        try:
            from database.db import get_connection
            conn = get_connection(); cur = conn.cursor()
            cur.execute(
                "SELECT api_key, api_secret FROM companies "
                "WHERE id=(SELECT MIN(id) FROM companies)"
            )
            row = cur.fetchone(); conn.close()
            api_key    = str(row[0]) if row and row[0] else ""
            api_secret = str(row[1]) if row and row[1] else ""
        except Exception:
            api_key = api_secret = ""

    if not api_key:
        return

    try:
        from services.site_config import get_host as _gh
        base_url = _gh()
    except Exception as e:
        return

    try:
        from models.user import get_all_users
        users = get_all_users()
    except Exception:
        return

    for user in users:
        user_email = user.get("email") or user.get("username")
        if not user_email or "@" not in user_email:
            continue
            
        payload = {
            "user": user_email,
            "allow": "Customer",
            "for_value": frappe_customer_id
        }
        url  = f"{base_url}/api/resource/User%20Permission"
        body = json.dumps(payload).encode()
        req  = urllib.request.Request(url, data=body, method="POST")
        from services.credentials import build_auth_header
        auth_hdr = build_auth_header(api_key, api_secret)
        if auth_hdr:
            req.add_header("Authorization", auth_hdr)
        req.add_header("Content-Type",  "application/json")
        req.add_header("Accept",        "application/json")

        try:
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                print(f"[FrappeSyncCheck] [OK] Permission created for {user_email} on {frappe_customer_id}")
        except urllib.error.HTTPError as e:
            print(f"[FrappeSyncCheck] Permission creation failed for {user_email}: HTTP {e.code}")
        except Exception as e:
            print(f"[FrappeSyncCheck] Permission creation failed for {user_email}: {e}")


def schedule_frappe_sync_check(
    customer_id: int,
    customer_name: str,
    phone: str,
    city: str,
    defs: dict,
    delay_seconds: int = 5,  # Changed from 30 to 5 seconds
) -> None:
    """
    Spawns a daemon thread that retries pushing the customer to Frappe FOREVER
    until it succeeds. Retries every 5 seconds regardless of network status.
    
    Each attempt:
      1. Checks the local frappe_synced flag - exits immediately if True.
      2. Checks Frappe directly via GET - marks synced locally if found.
      3. If still missing, calls _repush_to_frappe and marks synced on success.
      4. If all checks fail, waits 5 seconds and tries again (infinite loop).
    """
    import threading, time
    from services.credentials import get_system_mode
    
    if get_system_mode() == "odoo":
        # Do not attempt Frappe sync if we are in Odoo mode.
        return

    def _worker():
        attempt = 0
        while True:
            attempt += 1
            
            # 1. Fast-path: already synced
            if _is_frappe_synced(customer_id):
                print(
                    f"[FrappeSyncCheck] id={customer_id} '{customer_name}' "
                    f"already synced after {attempt} attempt(s) - exiting."
                )
                return

            # 2. Verify directly on Frappe
            if _check_exists_on_frappe(customer_name):
                print(
                    f"[FrappeSyncCheck] id={customer_id} found on Frappe "
                    f"(attempt {attempt}) - marking synced locally."
                )
                mark_frappe_synced(customer_id)
                return

            # 3. Not on Frappe - attempt a push
            print(
                f"[FrappeSyncCheck] id={customer_id} '{customer_name}' "
                f"NOT on Frappe (attempt {attempt}) - pushing …"
            )
            success = _repush_to_frappe(
                customer_name=customer_name,
                phone=phone,
                city=city,
                defs=defs,
                customer_id=customer_id,
            )

            if success:
                print(
                    f"[FrappeSyncCheck] id={customer_id} '{customer_name}' "
                    f"successfully synced on attempt {attempt}!"
                )
                return

            # 4. Failed - wait and retry forever
            print(
                f"[FrappeSyncCheck] id={customer_id} '{customer_name}' "
                f"failed on attempt {attempt} - retrying in {delay_seconds} seconds..."
            )
            time.sleep(delay_seconds)

    t = threading.Thread(
        target=_worker,
        daemon=True,
        name=f"FrappeSyncCheck-{customer_id}",
    )
    t.start()
    print(f"[FrappeSyncCheck] Started infinite retry thread for customer id={customer_id} '{customer_name}'")


def get_unsynced_customers() -> list[dict]:
    """
    Returns all customers where frappe_synced = 0.
    Used by retry_unsynced_customers() on app startup / reconnect.
    """
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            SELECT id, customer_name,
                   custom_telephone_number, custom_city
            FROM   customers
            WHERE  frappe_synced = 0
            ORDER  BY id ASC
        """)
        rows = cur.fetchall(); conn.close()
        return [
            {
                "id":            r[0],
                "customer_name": r[1],
                "phone":         r[2] or "",
                "city":          r[3] or "",
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[FrappeSyncCheck] get_unsynced_customers error: {e}")
        return []


def retry_unsynced_customers() -> None:
    """
    Scans for any customers still flagged frappe_synced=0 and starts an
    INFINITE retry thread for each one (retries every 5 seconds forever).

    Call once on app startup after the DB connection is confirmed, and
    optionally again whenever the app detects the network has come back.

    Each customer gets its own independent daemon thread so they don't
    block each other. The retry will continue until sync succeeds.
    """
    pending = get_unsynced_customers()
    if not pending:
        print("[FrappeSyncCheck] retry_unsynced_customers: nothing to retry.")
        return

    print(
        f"[FrappeSyncCheck] retry_unsynced_customers: "
        f"{len(pending)} customer(s) pending sync - starting infinite retry threads..."
    )

    try:
        from models.company_defaults import get_defaults
        defs = get_defaults()
    except Exception:
        defs = {}

    for c in pending:
        schedule_frappe_sync_check(
            customer_id=c["id"],
            customer_name=c["customer_name"],
            phone=c["phone"],
            city=c["city"],
            defs=defs,
            delay_seconds=5,   # Retry every 5 seconds forever
        )
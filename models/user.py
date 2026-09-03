# =============================================================================
# models/user.py  -  SQL Server version
# =============================================================================

import hashlib
from database.db import get_connection, fetchall_dicts, fetchone_dict


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ── Permission columns added to the users table ───────────────────────────────
_PERM_COLS = [
    "allow_discount",
    "allow_receipt",
    "allow_credit_note",
    "allow_reprint",
    "allow_laybye",
    "allow_quote",
    "allow_cancel_kot",
    "allow_pay_kot",
    "allow_close_table",
    "allow_prebill",
    "allow_edit_kot",
    "auto_logout",
    "allow_shift_reconciliation",
    "allow_pharmacist_pay",
    "allow_assign_waiter",
    "allow_backoffice",
    "allow_pos",
]

# Extra VARCHAR columns added after initial schema - auto-migrated on startup
_EXTRA_COLS = {
    "company": "NVARCHAR(140) NULL DEFAULT ''",
    "cost_center": "NVARCHAR(140) NULL DEFAULT ''",
    "warehouse": "NVARCHAR(140) NULL DEFAULT ''",
    "warehouse_id": "INT NULL",
    "cost_center_id": "INT NULL",
    "max_discount_percent": "INT NULL DEFAULT 0",
    "api_key": "NVARCHAR(255) NULL DEFAULT ''",
    "api_secret": "NVARCHAR(255) NULL DEFAULT ''",
}

def _ensure_perm_cols(cur, conn):
    """Add permission + extra columns to users table if they don't exist yet."""
    # allow_pos should default to 1 (everyone can use POS unless explicitly revoked)
    _col_defaults = {"allow_pos": 1}
    for col in _PERM_COLS:
        default_val = _col_defaults.get(col, 0)
        try:
            cur.execute(f"""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME='users' AND COLUMN_NAME='{col}'
                )
                ALTER TABLE users ADD {col} BIT NOT NULL DEFAULT {default_val}
            """)
            conn.commit()
        except Exception:
            pass
    for col, definition in _EXTRA_COLS.items():
        try:
            cur.execute(f"""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME='users' AND COLUMN_NAME='{col}'
                )
                ALTER TABLE users ADD {col} {definition}
            """)
            conn.commit()
        except Exception as e:
            print(f"Error migrating column {col}: {e}")


# =============================================================================
# AUTH
# =============================================================================

def authenticate(username: str, password: str) -> dict | None:
    """
    Returns full user dict if credentials match, else None.
    Accepts plain-text (legacy), hashed passwords, or PIN.
    """
    conn = get_connection()
    cur  = conn.cursor()
    u_clean = username.strip()
    cur.execute(
        "SELECT id, password, pin FROM users WHERE (username = ? OR email = ? OR frappe_user = ? OR full_name = ?) AND active = 1",
        (u_clean, u_clean, u_clean, u_clean)
    )
    row = fetchone_dict(cur)
    conn.close()

    if not row:
        return None

    stored = row["password"] or ""
    matched = (stored == password or stored == _hash(password))

    if not matched:
        stored_pin = (row.get("pin") or "").strip()
        if stored_pin and password.strip() == stored_pin:
            matched = True

    return get_user_by_id(row["id"]) if matched else None


def authenticate_by_pin(pin: str) -> dict | None:
    """Quick PIN login - returns full user dict."""
    if not pin or not pin.strip():
        return None
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT TOP 1 id FROM users WHERE pin = ? AND active = 1",
        (pin.strip(),)
    )
    row = cur.fetchone()
    conn.close()
    return get_user_by_id(row[0]) if row else None


# =============================================================================
# CRUD
# =============================================================================

def create_user(username: str, password: str, role: str = "cashier",
                email: str = "", full_name: str = "", first_name: str = "",
                last_name: str = "", pin: str = "",
                cost_center: str = "", warehouse: str = "",
                warehouse_id: int = None, cost_center_id: int = None,
                frappe_user: str = "", synced_from_frappe: bool = False,
                max_discount_percent: int = 0,
                allow_laybye: bool = True,
                allow_quote: bool = True,
                allow_cancel_kot: bool = False,
                allow_pay_kot: bool = True,
                allow_close_table: bool = True,
                allow_prebill: bool = True,
                allow_edit_kot: bool = True,
                auto_logout: bool = False,
                allow_shift_reconciliation: bool = True,
    allow_view_expected: bool = False,
                allow_assign_waiter: bool = False,
                allow_backoffice: bool = False,
                allow_pos: bool = True
                ) -> dict | None:
    if role not in ("admin", "cashier", "Pharmacist"):
        raise ValueError(f"Invalid role: {role!r}. Must be 'admin', 'cashier', or 'Pharmacist'.")

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO users
                (username, password, role, email, full_name, first_name, last_name,
                 pin, cost_center, warehouse, warehouse_id, cost_center_id, 
                 frappe_user, synced_from_frappe,
                 max_discount_percent, allow_laybye, allow_quote, allow_cancel_kot, allow_pay_kot,
                 allow_close_table, allow_prebill, allow_edit_kot, auto_logout, allow_shift_reconciliation, allow_assign_waiter, allow_view_expected, active, allow_pos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1)
        """, (
            username.strip(),
            _hash(password) if password else _hash("changeme"),
            role,
            (email or "").strip(),
            (full_name or "").strip(),
            (first_name or "").strip(),
            (last_name or "").strip(),
            (pin or "").strip(),
            (cost_center or "").strip(),
            (warehouse or "").strip(),
            warehouse_id,
            cost_center_id,
            (frappe_user or "").strip(),
            int(synced_from_frappe),
            max_discount_percent,
            int(allow_laybye),
            int(allow_quote),
            int(allow_cancel_kot),
            int(allow_pay_kot),
            int(allow_close_table),
            int(allow_prebill),
            int(allow_edit_kot),
            int(auto_logout),
            int(allow_shift_reconciliation),
        int(allow_view_expected),
            int(allow_assign_waiter),
        ))
        conn.commit()
        cur.execute("SELECT id FROM users WHERE username = ?", (username.strip(),))
        row = cur.fetchone()
        return get_user_by_id(row[0]) if row else None
    except Exception as e:
        print(f"[create_user] Error: {e}")
        return None
    finally:
        conn.close()


def update_user(user_id: int, **kwargs) -> dict | None:
    """
    Update any combination of user fields.
    Supported keys: username, role, display_name, active, pin,
                    full_name, email, cost_center, warehouse, max_discount_percent,
                    allow_discount, allow_receipt, allow_credit_note, allow_reprint,
                    allow_laybye, allow_quote
    """
    user = get_user_by_id(user_id)
    if not user:
        return None

    # Build SET clause dynamically from provided kwargs
    allowed = {
        "username", "role", "display_name", "active", "pin",
        "full_name", "email", "cost_center", "warehouse", 
        "warehouse_id", "cost_center_id", "max_discount_percent",
    "allow_view_expected",
        "allow_discount", "allow_receipt", "allow_credit_note", "allow_reprint",
        "allow_laybye",
        "allow_quote",
        "allow_cancel_kot",
        "allow_pay_kot",
        "allow_close_table",
        "allow_prebill",
        "allow_edit_kot",
        "auto_logout",
        "allow_shift_reconciliation",
        "allow_pharmacist_pay",
        "allow_assign_waiter",
    "allow_backoffice",
    "allow_pos",
        "allowed_payment_methods",
    }
    sets = []; params = []
    for k, v in kwargs.items():
        if k not in allowed:
            continue
        sets.append(f"{k} = ?")
        if isinstance(v, str):
            params.append(v.strip() or None)
        elif isinstance(v, bool):
            params.append(int(v))
        else:
            params.append(v)

    if not sets:
        return user

    params.append(user_id)
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            f"UPDATE users SET {', '.join(sets)} WHERE id = ?",
            params
        )
        conn.commit()
        return get_user_by_id(user_id)
    finally:
        conn.close()


def update_user_password(user_id: int, new_password: str) -> bool:
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (_hash(new_password), user_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def set_user_pin(user_id: int, pin: str) -> bool:
    """Save or update a user's PIN by their local DB id. Enforces uniqueness."""
    if not pin or not pin.strip().isdigit():
        return False
    
    pin = pin.strip()
    conn = get_connection()
    cur  = conn.cursor()
    try:
        # Check if another user already has this PIN
        cur.execute("SELECT id FROM users WHERE pin = ? AND id <> ?", (pin, user_id))
        if cur.fetchone():
            print(f"[user] PIN {pin} is already in use by another account.")
            return False

        cur.execute("UPDATE users SET pin = ? WHERE id = ?", (pin, user_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def upsert_frappe_user(u: dict) -> dict | None:
    """Insert or update a user coming from Frappe sync."""
    frappe_name = (u.get("name") or u.get("frappe_user") or "").strip()
    email       = (u.get("email")       or frappe_name).strip()
    full_name   = (u.get("full_name")   or "").strip()
    first_name  = (u.get("first_name")  or "").strip()
    last_name   = (u.get("last_name")   or "").strip()
    # Extract PIN from cloud payload if present
    user_pin = str(u.get("pin") or u.get("user_pin") or "").strip()
    company     = (u.get("company")     or "").strip()
    cost_center = (u.get("cost_center") or "").strip()
    warehouse   = (u.get("warehouse")   or "").strip()
    user_shops  = u.get("shops") or []
    if isinstance(user_shops, list) and len(user_shops) > 0:
        shop_names = [str(s.get("name") or s.get("shop_name") or "").strip() for s in user_shops if (s.get("name") or s.get("shop_name"))]
        if shop_names:
            warehouse = ", ".join(shop_names)

    from services.credentials import get_system_mode
    if get_system_mode() == "saas" and warehouse:
        cost_center = warehouse
    # Prefer user_rights_profile (authoritative) over role_select (legacy).
    raw_role = (u.get("user_rights_profile") or u.get("role_select") or u.get("role") or "Cashier").strip().lower()
    if raw_role in ("admin", "administrator", "system manager", "tenant_admin"):
        role = "admin"
    elif raw_role == "pharmacist":
        # Preserve title-case so utils.roles.is_pharmacist() can match it
        role = "Pharmacist"
    else:
        role = "cashier"
    cloud_id    = u.get("id")
    raw_username = (u.get("username") or u.get("name") or u.get("email") or full_name).strip()
    username = raw_username if raw_username else (email if email else full_name)

    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("SELECT id FROM users WHERE (frappe_user = ? AND frappe_user <> '')", (frappe_name,))
    existing = cur.fetchone()

    if not existing and email:
        cur.execute("SELECT id FROM users WHERE (email = ? AND email <> '')", (email,))
        existing = cur.fetchone()
    
    if not existing and username:
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        existing = cur.fetchone()

    u_api_key    = str(u.get("api_key")    or "").strip()
    u_api_secret = str(u.get("api_secret") or "").strip()

    if existing:
        user_id = existing[0]
        if user_pin:
            if u_api_key and u_api_secret:
                cur.execute("""
                    UPDATE users SET
                        username=?, role=?, email=?, full_name=?, first_name=?,
                        last_name=?, company=?, cost_center=?, warehouse=?,
                        frappe_user=?, pin=?, cloud_user_id=?, api_key=?, api_secret=?, active=1, allow_pos=1, synced_from_frappe=1
                    WHERE id=?
                """, (username, role, email, full_name, first_name,
                        last_name, company, cost_center, warehouse, frappe_name, user_pin, cloud_id, u_api_key, u_api_secret, user_id))
            else:
                cur.execute("""
                    UPDATE users SET
                        username=?, role=?, email=?, full_name=?, first_name=?,
                        last_name=?, company=?, cost_center=?, warehouse=?,
                        frappe_user=?, pin=?, cloud_user_id=?, active=1, allow_pos=1, synced_from_frappe=1
                    WHERE id=?
                """, (username, role, email, full_name, first_name,
                        last_name, company, cost_center, warehouse, frappe_name, user_pin, cloud_id, user_id))
        else:
            if u_api_key and u_api_secret:
                cur.execute("""
                    UPDATE users SET
                        username=?, role=?, email=?, full_name=?, first_name=?,
                        last_name=?, company=?, cost_center=?, warehouse=?,
                        frappe_user=?, cloud_user_id=?, api_key=?, api_secret=?, active=1, allow_pos=1, synced_from_frappe=1
                    WHERE id=?
                """, (username, role, email, full_name, first_name,
                        last_name, company, cost_center, warehouse, frappe_name, cloud_id, u_api_key, u_api_secret, user_id))
            else:
                cur.execute("""
                    UPDATE users SET
                        username=?, role=?, email=?, full_name=?, first_name=?,
                        last_name=?, company=?, cost_center=?, warehouse=?,
                        frappe_user=?, cloud_user_id=?, active=1, allow_pos=1, synced_from_frappe=1
                    WHERE id=?
                """, (username, role, email, full_name, first_name,
                        last_name, company, cost_center, warehouse, frappe_name, cloud_id, user_id))
        conn.commit()
    else:
        # Compute defaults based on role
        is_admin = (role == "admin")
        a_disc = 1 if is_admin else 0
        a_rec = 1
        a_cn = 1 if is_admin else 0
        a_rep = 1 if is_admin else 0
        a_lay = 1 if is_admin else 0
        a_quo = 1 if is_admin else 0
        a_recon = 1
        a_vexp = 1 if is_admin else 0
        a_bo = 1 if is_admin else 0
        a_pos = 1
        a_ct = 1
        a_pre = 1
        a_pkot = 1
        a_ekot = 1
        a_ckot = 1
        a_autol = 0 if is_admin else 1
        a_aw = 1
        
        cur.execute("""
            INSERT INTO users
                (username, password, role, email, full_name, first_name, last_name,
                 pin, company, cost_center, warehouse, frappe_user, cloud_user_id, synced_from_frappe, active,
                 allow_discount, allow_receipt, allow_credit_note, allow_reprint,
                 allow_laybye, allow_quote, allow_shift_reconciliation, allow_view_expected,
                 allow_backoffice, allow_pos, allow_close_table, allow_prebill,
                 allow_pay_kot, allow_edit_kot, allow_cancel_kot, auto_logout, allow_assign_waiter)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (username, _hash("changeme"),
              role, email, full_name, first_name, last_name,
              user_pin, company, cost_center, warehouse, frappe_name, cloud_id,
              a_disc, a_rec, a_cn, a_rep, a_lay, a_quo, a_recon, a_vexp,
              a_bo, a_pos, a_ct, a_pre, a_pkot, a_ekot, a_ckot, a_autol, a_aw))
        conn.commit()
        cur.execute("SELECT id FROM users WHERE frappe_user=? OR username=?", (frappe_name, username))
        row = cur.fetchone()
        user_id = row[0] if row else None

    conn.close()
    return get_user_by_id(user_id) if user_id else None


def update_user_credentials_from_online(username_or_email: str, password: str, u: dict, api_key: str = "", api_secret: str = "") -> dict | None:
    """
    Called after a successful online login. Updates the local password hash,
    profile data, and API credentials so the user can login offline next time.
    """
    try:
        migrate()
    except Exception as _me:
        print(f"[user] Could not verify users schema: {_me}")

    conn = get_connection()
    cur  = conn.cursor()

    email       = (u.get("email")       or username_or_email).strip()
    frappe_name = (u.get("name")        or u.get("username") or email).strip()
    full_name   = (u.get("full_name")   or "").strip()
    first_name  = (u.get("first_name")  or "").strip()
    last_name   = (u.get("last_name")   or "").strip()
    company     = (u.get("company")     or "").strip()
    cost_center = (u.get("cost_center") or "").strip()
    warehouse   = (u.get("warehouse")   or "").strip()
    if not warehouse and isinstance(u.get("shops"), list) and len(u.get("shops")) > 0:
        shop_names = [str(s.get("name") or s.get("shop_name") or "").strip() for s in u.get("shops") if (s.get("name") or s.get("shop_name"))]
        warehouse = ", ".join(shop_names)
    user_pin    = str(u.get("pin") or u.get("user_pin") or "").strip()

    db_secret = api_secret
    if api_secret:
        try:
            from services.credentials import get_system_mode
            from utils.crypto import encrypt_secret
            if get_system_mode().lower() == "saas":
                db_secret = encrypt_secret(api_secret)
        except Exception:
            pass

    cur.execute(
        "SELECT id FROM users WHERE (username = ? OR email = ? OR frappe_user = ?)",
        (username_or_email.strip(), email, frappe_name)
    )
    row = fetchone_dict(cur)

    if not row:
        cur.execute("""
            INSERT INTO users (
                username, password, email, full_name, first_name,
                last_name, role, active, company, cost_center, warehouse,
                frappe_user, pin, api_key, api_secret, synced_from_frappe
            ) VALUES (?, ?, ?, ?, ?, ?, 'cashier', 1, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            username_or_email, _hash(password), email, full_name, first_name,
            last_name, company, cost_center, warehouse, frappe_name, user_pin,
            api_key, db_secret
        ))
        conn.commit()
        cur.execute("SELECT @@IDENTITY")
        user_id = int(cur.fetchone()[0])
    else:
        user_id = row["id"]
        if user_pin:
            cur.execute("""
                UPDATE users SET
                    password=?, email=?, full_name=?, first_name=?,
                    last_name=?, company=?, cost_center=?, warehouse=?,
                    frappe_user=?, pin=?, api_key=?, api_secret=?, synced_from_frappe=1
                WHERE id=?
            """, (
                _hash(password), email, full_name, first_name,
                last_name, company, cost_center, warehouse, frappe_name, user_pin,
                api_key, db_secret, user_id
            ))
        else:
            cur.execute("SELECT pin, role, username FROM users WHERE id=?", (user_id,))
            u_row = fetchone_dict(cur) or {}
            existing_pin = str(u_row.get("pin") or "").strip()
            u_name = str(u_row.get("username") or "").strip().lower()
            u_role = str(u_row.get("role") or "").strip().lower()
            
            if not existing_pin and (u_name == "admin" or u_role == "admin" or username_or_email.lower() == "admin"):
                pin_to_set = "7878"
                cur.execute("""
                    UPDATE users SET
                        password=?, email=?, full_name=?, first_name=?,
                        last_name=?, company=?, cost_center=?, warehouse=?,
                        frappe_user=?, pin=?, api_key=?, api_secret=?, synced_from_frappe=1
                    WHERE id=?
                """, (
                    _hash(password), email, full_name, first_name,
                    last_name, company, cost_center, warehouse, frappe_name, pin_to_set,
                    api_key, db_secret, user_id
                ))
            else:
                cur.execute("""
                    UPDATE users SET
                        password=?, email=?, full_name=?, first_name=?,
                        last_name=?, company=?, cost_center=?, warehouse=?,
                        frappe_user=?, api_key=?, api_secret=?, synced_from_frappe=1
                    WHERE id=?
                """, (
                    _hash(password), email, full_name, first_name,
                    last_name, company, cost_center, warehouse, frappe_name,
                    api_key, db_secret, user_id
                ))
        conn.commit()
    conn.close()
    
    return get_user_by_id(user_id)


def delete_user(user_id: int) -> bool:
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# =============================================================================
# QUERIES
# =============================================================================

def get_all_users() -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT * FROM users ORDER BY role, username
    """)
    rows = fetchall_dicts(cur)
    conn.close()
    return [_to_dict(r) for r in rows]


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT * FROM users WHERE id = ?
    """, (user_id,))
    row = fetchone_dict(cur)
    conn.close()
    return _to_dict(row) if row else None


def is_admin(user: dict) -> bool:
    """Checks if the provided user dictionary has an admin role."""
    return bool(user and user.get("role") == "admin")


# =============================================================================
# MIGRATION
# =============================================================================

def migrate():
    """Create users table and add any missing columns."""
    conn = get_connection()
    cur  = conn.cursor()

    # Create table if it doesn't exist
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='users'
        )
        CREATE TABLE users (
            id                 INT           IDENTITY(1,1) PRIMARY KEY,
            username           NVARCHAR(80)  NOT NULL UNIQUE,
            password           NVARCHAR(255) NOT NULL,
            role               NVARCHAR(20)  NOT NULL DEFAULT 'cashier',
            display_name       NVARCHAR(120) NULL,
            email              NVARCHAR(120) NULL,
            full_name          NVARCHAR(120) NULL,
            first_name         NVARCHAR(80)  NULL,
            last_name          NVARCHAR(80)  NULL,
            pin                NVARCHAR(20)  NULL,
            company            NVARCHAR(140) NULL,
            cost_center        NVARCHAR(140) NULL,
            warehouse          NVARCHAR(140) NULL,
            frappe_user        NVARCHAR(120) NULL,
            synced_from_frappe BIT           NOT NULL DEFAULT 0,
            active             BIT           NOT NULL DEFAULT 1,
            max_discount_percent INT         NOT NULL DEFAULT 0,
            allow_discount     BIT           NOT NULL DEFAULT 1,
            allow_receipt      BIT           NOT NULL DEFAULT 1,
            allow_credit_note  BIT           NOT NULL DEFAULT 1,
            allow_reprint      BIT           NOT NULL DEFAULT 1,
            allow_laybye       BIT           NOT NULL DEFAULT 1,
            allow_quote        BIT           NOT NULL DEFAULT 1,
            allow_cancel_kot   BIT           NOT NULL DEFAULT 0,
            allow_pay_kot      BIT           NOT NULL DEFAULT 1,
            allow_close_table  BIT           NOT NULL DEFAULT 1,
            allow_prebill      BIT           NOT NULL DEFAULT 1,
            allow_edit_kot     BIT           NOT NULL DEFAULT 1,
            auto_logout        BIT           NOT NULL DEFAULT 0,
            allow_shift_reconciliation BIT   NOT NULL DEFAULT 1,
                allow_view_expected BIT         NOT NULL DEFAULT 0,
            allow_pharmacist_pay BIT         NOT NULL DEFAULT 0,
            allow_assign_waiter  BIT         NOT NULL DEFAULT 0,
            allow_backoffice     BIT         NOT NULL DEFAULT 0,
            allow_pos            BIT         NOT NULL DEFAULT 1
        )
    """)
    conn.commit()

    # Add permission columns to existing tables (forward-compat)
    _ensure_perm_cols(cur, conn)

    # Inject default admin user with PIN 7878 if it does not exist (All Modes)
    try:
        cur.execute("SELECT id FROM users WHERE username = 'admin'")
        if not cur.fetchone():
            import hashlib
            default_hash = hashlib.sha256("admin123!".encode()).hexdigest()
            cur.execute("""
                INSERT INTO users (username, password, role, display_name, pin, active)
                VALUES ('admin', ?, 'admin', 'System Admin', '7878', 1)
            """, (default_hash,))
            conn.commit()
            print("[user] Default 'admin' (PIN: 7878) automatically created.")
        else:
            # Ensure admin user has role 'admin' and PIN 7878 if unconfigured
            cur.execute("UPDATE users SET role = 'admin' WHERE username = 'admin'")
            cur.execute("UPDATE users SET pin = '7878' WHERE username = 'admin' AND (pin IS NULL OR pin = '')")
            conn.commit()
    except Exception as e:
        print(f"[user] Failed to inject default admin: {e}")

    conn.close()
    print("[user] migrate() complete - table ready.")


# =============================================================================
# INTERNAL
# =============================================================================

def _to_dict(row: dict) -> dict | None:
    if not row:
        return None
    return {
        "id":                   row["id"],
        "username":             row.get("username")          or "",
        "role":                 row.get("role")              or "cashier",
        "display_name":         row.get("display_name")      or "",
        "email":                row.get("email")             or "",
        "full_name":            row.get("full_name")         or "",
        "first_name":           row.get("first_name")        or "",
        "last_name":            row.get("last_name")         or "",
        "pin":                  row.get("pin")               or "",
        "company":              row.get("company")           or "",
        "cost_center":          row.get("cost_center")       or "",
        "warehouse":            row.get("warehouse")         or "",
        "warehouse_id":         row.get("warehouse_id"),
        "cost_center_id":       row.get("cost_center_id"),
        "frappe_user":          row.get("frappe_user")       or "",
        "synced_from_frappe":   bool(row.get("synced_from_frappe", 0)),
        "active":               bool(row.get("active", 1)),
        "max_discount_percent": row.get("max_discount_percent", 0),
        "allow_view_expected": row.get("allow_view_expected", 0),
        # Permission flags - default True for backward compat
        "allow_discount":       bool(row.get("allow_discount",    1)),
        "allow_receipt":        bool(row.get("allow_receipt",     1)),
        "allow_credit_note":    bool(row.get("allow_credit_note", 1)),
        "allow_reprint":        bool(row.get("allow_reprint",     1)),
        "allow_laybye":         bool(row.get("allow_laybye",      1)),
        "allow_quote":          bool(row.get("allow_quote",       1)),
        "allow_cancel_kot":     bool(row.get("allow_cancel_kot",  0)),
        "allow_pay_kot":        bool(row.get("allow_pay_kot",     1)),
        "allow_close_table":    bool(row.get("allow_close_table", 1)),
        "allow_prebill":        bool(row.get("allow_prebill",     1)),
        "allow_edit_kot":       bool(row.get("allow_edit_kot",    1)),
        "auto_logout":          bool(row.get("auto_logout",       0)),
        "allow_shift_reconciliation": bool(row.get("allow_shift_reconciliation", 1)),
        "allow_view_expected":  bool(row.get("allow_view_expected", 0)),
        "allow_pharmacist_pay": bool(row.get("allow_pharmacist_pay", 0)),
        "allow_assign_waiter":  bool(row.get("allow_assign_waiter", 0)),
        "allow_backoffice":     bool(row.get("allow_backoffice", 0)),   # default OFF - must be granted
        "allow_pos":            bool(row.get("allow_pos", 1)),          # default ON - everyone can use POS
        "allowed_payment_methods": row.get("allowed_payment_methods") or "ALL",
    }

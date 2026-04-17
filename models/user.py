# =============================================================================
# models/user.py  —  SQL Server version
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
    "allow_laybye",   # ← ADDED
    "allow_quote",    # ← ADDED
]

# Extra VARCHAR columns added after initial schema — auto-migrated on startup
_EXTRA_COLS = {
    "company": "NVARCHAR(140) NULL DEFAULT ''",
    "cost_center": "NVARCHAR(140) NULL DEFAULT ''",
    "warehouse": "NVARCHAR(140) NULL DEFAULT ''",
    "max_discount_percent": "INT NULL DEFAULT 0",
}

def _ensure_perm_cols(cur, conn):
    """Add permission + extra columns to users table if they don't exist yet."""
    for col in _PERM_COLS:
        try:
            cur.execute(f"""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME='users' AND COLUMN_NAME='{col}'
                )
                ALTER TABLE users ADD {col} BIT NOT NULL DEFAULT 1
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
    _ensure_perm_cols(cur, conn)
    cur.execute(
        "SELECT id, password, pin FROM users WHERE username = ?",
        (username,)
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
    """Quick PIN login — returns full user dict."""
    if not pin or not pin.strip():
        return None
    conn = get_connection()
    cur  = conn.cursor()
    _ensure_perm_cols(cur, conn)
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
                frappe_user: str = "", synced_from_frappe: bool = False,
                max_discount_percent: int = 0,
                allow_laybye: bool = True,    # ← ADDED
                allow_quote: bool = True      # ← ADDED
                ) -> dict | None:
    if role not in ("admin", "cashier"):
        raise ValueError(f"Invalid role: {role!r}. Must be 'admin' or 'cashier'.")

    conn = get_connection()
    cur  = conn.cursor()
    try:
        _ensure_perm_cols(cur, conn)
        cur.execute("""
            INSERT INTO users
                (username, password, role, email, full_name, first_name, last_name,
                 pin, cost_center, warehouse, frappe_user, synced_from_frappe,
                 max_discount_percent, allow_laybye, allow_quote)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            (frappe_user or "").strip(),
            int(synced_from_frappe),
            max_discount_percent,
            int(allow_laybye),    # ← ADDED
            int(allow_quote),     # ← ADDED
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
        "full_name", "email", "cost_center", "warehouse", "max_discount_percent",
        "allow_discount", "allow_receipt", "allow_credit_note", "allow_reprint",
        "allow_laybye",   # ← ADDED
        "allow_quote",    # ← ADDED
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
        _ensure_perm_cols(cur, conn)
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
    """Save or update a user's PIN by their local DB id."""
    if not pin or not pin.strip().isdigit():
        return False
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("UPDATE users SET pin = ? WHERE id = ?", (pin.strip(), user_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def upsert_frappe_user(u: dict) -> dict | None:
    """Insert or update a user coming from Frappe sync."""
    frappe_name = (u.get("name")        or "").strip()
    email       = (u.get("email")       or frappe_name).strip()
    full_name   = (u.get("full_name")   or "").strip()
    first_name  = (u.get("first_name")  or "").strip()
    last_name   = (u.get("last_name")   or "").strip()
    pin         = (u.get("pin")         or "").strip()
    company     = (u.get("company")     or "").strip()
    cost_center = (u.get("cost_center") or "").strip()
    warehouse   = (u.get("warehouse")   or "").strip()
    role_select = (u.get("role_select") or "Cashier").strip().lower()
    role        = "admin" if role_select == "admin" else "cashier"
    username    = full_name if full_name else email

    conn = get_connection()
    cur  = conn.cursor()
    _ensure_perm_cols(cur, conn)

    cur.execute("SELECT id FROM users WHERE frappe_user = ?", (frappe_name,))
    existing = cur.fetchone()

    if existing:
        # Never wipe a locally-set PIN with an empty value from Frappe.
        # Only update pin if Frappe actually sent one.
        if pin:
            cur.execute("""
                UPDATE users SET
                    username=?, role=?, email=?, full_name=?, first_name=?,
                    last_name=?, pin=?, company=?, cost_center=?, warehouse=?,
                    synced_from_frappe=1
                WHERE frappe_user=?
            """, (username, role, email, full_name, first_name,
                  last_name, pin, company, cost_center, warehouse, frappe_name))
        else:
            # Preserve the existing local PIN — do not overwrite with empty
            cur.execute("""
                UPDATE users SET
                    username=?, role=?, email=?, full_name=?, first_name=?,
                    last_name=?, company=?, cost_center=?, warehouse=?,
                    synced_from_frappe=1
                WHERE frappe_user=?
            """, (username, role, email, full_name, first_name,
                  last_name, company, cost_center, warehouse, frappe_name))
        conn.commit()
        user_id = existing[0]
    else:
        cur.execute("""
            INSERT INTO users
                (username, password, role, email, full_name, first_name, last_name,
                 pin, company, cost_center, warehouse, frappe_user, synced_from_frappe)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (username, _hash(pin) if pin else _hash("changeme"),
              role, email, full_name, first_name, last_name,
              pin, company, cost_center, warehouse, frappe_name))
        conn.commit()
        cur.execute("SELECT id FROM users WHERE frappe_user=?", (frappe_name,))
        row = cur.fetchone()
        user_id = row[0] if row else None

    conn.close()
    return get_user_by_id(user_id) if user_id else None


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
    _ensure_perm_cols(cur, conn)
    cur.execute("""
        SELECT * FROM users ORDER BY role, username
    """)
    rows = fetchall_dicts(cur)
    conn.close()
    return [_to_dict(r) for r in rows]


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_connection()
    cur  = conn.cursor()
    _ensure_perm_cols(cur, conn)
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
            allow_quote        BIT           NOT NULL DEFAULT 1
        )
    """)
    conn.commit()

    # Add permission columns to existing tables (forward-compat)
    _ensure_perm_cols(cur, conn)

    conn.close()
    print("[user] migrate() complete — table ready.")


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
        "frappe_user":          row.get("frappe_user")       or "",
        "synced_from_frappe":   bool(row.get("synced_from_frappe", 0)),
        "active":               bool(row.get("active", 1)),
        "max_discount_percent": row.get("max_discount_percent", 0),
        # Permission flags — default True for backward compat
        "allow_discount":       bool(row.get("allow_discount",    1)),
        "allow_receipt":        bool(row.get("allow_receipt",     1)),
        "allow_credit_note":    bool(row.get("allow_credit_note", 1)),
        "allow_reprint":        bool(row.get("allow_reprint",     1)),
        "allow_laybye":         bool(row.get("allow_laybye",      1)),   # ← ADDED
        "allow_quote":          bool(row.get("allow_quote",       1)),   # ← ADDED
    }
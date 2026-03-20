# =============================================================================
# models/user.py  —  SQL Server version
# =============================================================================

import hashlib
from database.db import get_connection, fetchall_dicts, fetchone_dict


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# =============================================================================
# AUTH
# =============================================================================

def authenticate(username: str, password: str) -> dict | None:
    """
    Returns user dict if credentials match, else None.
    Accepts both plain-text (legacy) and hashed passwords.
    Also accepts PIN if password is 4-6 digits and matches the stored pin.
    """
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT id, username, role, password, pin FROM users WHERE username = ?",
        (username,)
    )
    row = fetchone_dict(cur)
    conn.close()

    if not row:
        return None

    stored = row["password"]
    # Password match (plain or hashed)
    if stored == password or stored == _hash(password):
        return _to_dict(row)

    # PIN match (for Frappe-synced users who may not have a local password)
    stored_pin = (row.get("pin") or "").strip()
    if stored_pin and password.strip() == stored_pin:
        return _to_dict(row)

    return None


def authenticate_by_pin(pin: str) -> dict | None:
    """Quick PIN login — finds the first active user with this PIN."""
    if not pin or not pin.strip():
        return None
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT TOP 1 * FROM users WHERE pin = ? AND active = 1",
        (pin.strip(),)
    )
    row = fetchone_dict(cur)
    conn.close()
    return _to_dict(row) if row else None


# =============================================================================
# CRUD
# =============================================================================

def create_user(username: str, password: str, role: str = "cashier",
                email: str = "", full_name: str = "", first_name: str = "",
                last_name: str = "", pin: str = "",
                cost_center: str = "", warehouse: str = "",
                frappe_user: str = "", synced_from_frappe: bool = False) -> dict | None:
    if role not in ("admin", "cashier"):
        raise ValueError(f"Invalid role: {role}. Must be 'admin' or 'cashier'.")

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO users
                (username, password, role, email, full_name, first_name, last_name,
                 pin, cost_center, warehouse, frappe_user, synced_from_frappe)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            username.strip(), _hash(password) if password else _hash("changeme"),
            role,
            (email      or "").strip(),
            (full_name  or "").strip(),
            (first_name or "").strip(),
            (last_name  or "").strip(),
            (pin        or "").strip(),
            (cost_center or "").strip(),
            (warehouse   or "").strip(),
            (frappe_user or "").strip(),
            int(synced_from_frappe),
        ))
        conn.commit()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = fetchone_dict(cur)
        return _to_dict(row) if row else None
    except Exception as e:
        print(f"[create_user] Error: {e}")
        return None
    finally:
        conn.close()


def upsert_frappe_user(u: dict) -> dict | None:
    """
    Insert or update a user coming from Frappe sync.
    Uses frappe_user (email) as the unique key.
    Maps Frappe role_select → local role.
    """
    frappe_name  = (u.get("name")        or "").strip()
    email        = (u.get("email")       or frappe_name).strip()
    full_name    = (u.get("full_name")   or "").strip()
    first_name   = (u.get("first_name")  or "").strip()
    last_name    = (u.get("last_name")   or "").strip()
    pin          = (u.get("pin")         or "").strip()
    cost_center  = (u.get("cost_center") or "").strip()
    warehouse    = (u.get("warehouse")   or "").strip()
    role_select  = (u.get("role_select") or "Cashier").strip().lower()
    role         = "admin" if role_select == "admin" else "cashier"

    # Use full_name or email as local username
    username = full_name if full_name else email

    conn = get_connection()
    cur  = conn.cursor()

    # Check if user already exists by frappe_user key
    cur.execute("SELECT id, username FROM users WHERE frappe_user = ?", (frappe_name,))
    existing = fetchone_dict(cur)

    if existing:
        cur.execute("""
            UPDATE users SET
                username     = ?,
                role         = ?,
                email        = ?,
                full_name    = ?,
                first_name   = ?,
                last_name    = ?,
                pin          = ?,
                cost_center  = ?,
                warehouse    = ?,
                synced_from_frappe = 1
            WHERE frappe_user = ?
        """, (username, role, email, full_name, first_name, last_name,
              pin, cost_center, warehouse, frappe_name))
        conn.commit()
        user_id = existing["id"]
    else:
        cur.execute("""
            INSERT INTO users
                (username, password, role, email, full_name, first_name, last_name,
                 pin, cost_center, warehouse, frappe_user, synced_from_frappe)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            username,
            _hash(pin) if pin else _hash("changeme"),
            role, email, full_name, first_name, last_name,
            pin, cost_center, warehouse, frappe_name,
        ))
        conn.commit()
        cur.execute("SELECT id FROM users WHERE frappe_user = ?", (frappe_name,))
        row = cur.fetchone()
        user_id = row[0] if row else None

    conn.close()
    return get_user_by_id(user_id) if user_id else None


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


def update_user(user_id: int, username: str = None, role: str = None,
                display_name: str = None, active: bool = None) -> dict | None:
    user = get_user_by_id(user_id)
    if not user:
        return None

    new_username     = username.strip()     if username     is not None else user["username"]
    new_role         = role                 if role         is not None else user["role"]
    new_display_name = display_name.strip() if display_name is not None else user.get("display_name", "")
    new_active       = int(active)          if active       is not None else int(user.get("active", True))

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            UPDATE users
            SET username=?, role=?, display_name=?, active=?
            WHERE id=?
        """, (new_username, new_role, new_display_name, new_active, user_id))
        conn.commit()
        return get_user_by_id(user_id)
    finally:
        conn.close()


def delete_user(user_id: int) -> bool:
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_all_users() -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, username, role,
               COALESCE(display_name,'') AS display_name,
               COALESCE(email,'')        AS email,
               COALESCE(full_name,'')    AS full_name,
               COALESCE(first_name,'')   AS first_name,
               COALESCE(last_name,'')    AS last_name,
               COALESCE(pin,'')          AS pin,
               COALESCE(cost_center,'')  AS cost_center,
               COALESCE(warehouse,'')    AS warehouse,
               COALESCE(frappe_user,'')  AS frappe_user,
               COALESCE(synced_from_frappe,0) AS synced_from_frappe,
               COALESCE(active,1)        AS active
        FROM users ORDER BY role, username
    """)
    rows = fetchall_dicts(cur)
    conn.close()
    return [_to_dict(r) for r in rows]


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = fetchone_dict(cur)
    conn.close()
    return _to_dict(row) if row else None


def is_admin(user: dict) -> bool:
    return bool(user and user.get("role") == "admin")


# =============================================================================
# MIGRATION
# =============================================================================

def migrate():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'users'
        )
        CREATE TABLE users (
            id           INT           IDENTITY(1,1) PRIMARY KEY,
            username     NVARCHAR(80)  NOT NULL UNIQUE,
            password     NVARCHAR(255) NOT NULL,
            role         NVARCHAR(20)  NOT NULL DEFAULT 'cashier',
            display_name NVARCHAR(120) NULL,
            email        NVARCHAR(120) NULL,
            full_name    NVARCHAR(120) NULL,
            first_name   NVARCHAR(80)  NULL,
            last_name    NVARCHAR(80)  NULL,
            pin          NVARCHAR(20)  NULL,
            cost_center  NVARCHAR(140) NULL,
            warehouse    NVARCHAR(140) NULL,
            frappe_user  NVARCHAR(120) NULL,
            synced_from_frappe BIT NOT NULL DEFAULT 0,
            active       BIT           NOT NULL DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()
    print("[user] Table ready.")


# =============================================================================
# PRIVATE
# =============================================================================

def _to_dict(row: dict) -> dict | None:
    if not row:
        return None
    return {
        "id":                   row["id"],
        "username":             row.get("username")     or "",
        "role":                 row.get("role")         or "cashier",
        "display_name":         row.get("display_name") or "",
        "email":                row.get("email")        or "",
        "full_name":            row.get("full_name")    or "",
        "first_name":           row.get("first_name")   or "",
        "last_name":            row.get("last_name")    or "",
        "pin":                  row.get("pin")          or "",
        "cost_center":          row.get("cost_center")  or "",
        "warehouse":            row.get("warehouse")    or "",
        "frappe_user":          row.get("frappe_user")  or "",
        "synced_from_frappe":   bool(row.get("synced_from_frappe", 0)),
        "active":               bool(row.get("active", 1)),
    }
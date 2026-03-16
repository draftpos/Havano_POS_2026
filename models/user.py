# =============================================================================
# models/user.py  —  SQL Server version
# =============================================================================

import hashlib
from database.db import get_connection, fetchall_dicts, fetchone_dict


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def authenticate(username: str, password: str) -> dict | None:
    """
    Returns user dict if credentials match, else None.
    Accepts both plain-text (legacy) and hashed passwords.
    """
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT id, username, role, password FROM users WHERE username = ?",
        (username,)
    )
    row = fetchone_dict(cur)
    conn.close()

    if not row:
        return None

    stored = row["password"]
    if stored == password or stored == _hash(password):
        return {"id": row["id"], "username": row["username"], "role": row["role"]}
    return None


def create_user(username: str, password: str, role: str = "cashier") -> dict | None:
    if role not in ("admin", "cashier"):
        raise ValueError(f"Invalid role: {role}. Must be 'admin' or 'cashier'.")

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username.strip(), _hash(password), role)
        )
        conn.commit()
        cur.execute(
            "SELECT id, username, role FROM users WHERE username = ?", (username,)
        )
        row = fetchone_dict(cur)
        return {"id": row["id"], "username": row["username"], "role": row["role"]} if row else None
    except Exception as e:
        print(f"[create_user] Error: {e}")
        return None
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


def update_user(user_id: int, username: str = None, role: str = None,
                display_name: str = None, active: bool = None) -> dict | None:
    """Update any combination of user fields."""
    user = get_user_by_id(user_id)
    if not user:
        return None

    new_username     = username.strip()     if username     is not None else user["username"]
    new_role         = role                 if role         is not None else user["role"]
    new_display_name = display_name.strip() if display_name is not None else user.get("display_name", "")
    new_active       = int(active)          if active       is not None else user.get("active", 1)

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
    cur.execute(
        "SELECT id, username, role, COALESCE(display_name,'') AS display_name, active "
        "FROM users ORDER BY role, username"
    )
    rows = fetchall_dicts(cur)
    conn.close()
    return [_to_dict(r) for r in rows]


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "SELECT id, username, role, COALESCE(display_name,'') AS display_name, active "
        "FROM users WHERE id = ?",
        (user_id,)
    )
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
            active       BIT           NOT NULL DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()
    print("[user] ✅  Table ready.")


# =============================================================================
# PRIVATE
# =============================================================================

def _to_dict(row: dict) -> dict | None:
    if not row:
        return None
    return {
        "id":           row["id"],
        "username":     row["username"]     or "",
        "role":         row["role"]         or "cashier",
        "display_name": row.get("display_name") or "",
        "active":       bool(row.get("active", 1)),
    }
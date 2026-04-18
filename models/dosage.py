# =============================================================================
# models/dosage.py  —  SQL Server version
# Dosage reference data mirrored from Frappe (Pharmacy module)
# =============================================================================

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from database.db import get_connection, fetchall_dicts, fetchone_dict


@dataclass
class Dosage:
    id: Optional[int] = None
    frappe_name: Optional[str] = None
    code: str = ""
    description: Optional[str] = None
    synced: bool = False
    sync_date: Optional[str] = None


# =============================================================================
# READ
# =============================================================================

def list_dosages() -> list[Dosage]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, frappe_name, code, description, synced, sync_date
        FROM dosages
        ORDER BY code
    """)
    rows = fetchall_dicts(cur)
    conn.close()
    return [_to_dosage(r) for r in rows]


def get_dosage_by_code(code: str) -> Optional[Dosage]:
    if not code:
        return None
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, frappe_name, code, description, synced, sync_date
        FROM dosages
        WHERE code = ?
    """, (code,))
    row = fetchone_dict(cur)
    conn.close()
    return _to_dosage(row) if row else None


# =============================================================================
# WRITE
# =============================================================================

def create_dosage_local(code: str, description: Optional[str] = None) -> int:
    """
    INSERT a new local Dosage record. Marked unsynced (synced=0, frappe_name=NULL)
    so the push service picks it up. Returns the new local id.
    """
    code = (code or "").strip()
    if not code:
        raise ValueError("Dosage code is required")

    def _n(v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    description = _n(description)

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO dosages (
                frappe_name, code, description, synced, sync_date
            )
            OUTPUT INSERTED.id
            VALUES (NULL, ?, ?, 0, NULL)
        """, (code, description))
        new_id = int(cur.fetchone()[0])
        conn.commit()
        return new_id
    finally:
        conn.close()


def update_dosage_local(dosage_id: int, **fields) -> bool:
    """
    UPDATE an existing local Dosage record. Any content-field change resets
    synced=0 so the push service re-pushes it. Returns True on success,
    False if the row was not found.

    Accepts kwargs: code, description.
    """
    allowed = ("code", "description")

    def _n(v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    updates: dict = {}
    for k in allowed:
        if k in fields:
            v = fields[k]
            if k == "code":
                s = (str(v) if v is not None else "").strip()
                if not s:
                    raise ValueError("Dosage code cannot be empty")
                updates[k] = s
            else:
                updates[k] = _n(v)

    if not updates:
        return True

    set_parts = [f"{col} = ?" for col in updates.keys()]
    set_parts.append("synced = 0")
    set_parts.append("sync_date = NULL")
    params = list(updates.values()) + [dosage_id]

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            f"UPDATE dosages SET {', '.join(set_parts)} WHERE id = ?",
            params,
        )
        ok = cur.rowcount > 0
        conn.commit()
        return ok
    finally:
        conn.close()


def mark_dosage_synced(dosage_id: int, frappe_name: str) -> None:
    """Flag a local Dosage row as synced (synced=1, sync_date=now, frappe_name=?)."""
    if not frappe_name:
        return
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            UPDATE dosages
               SET synced      = 1,
                   sync_date   = SYSDATETIME(),
                   frappe_name = ?
             WHERE id = ?
        """, (str(frappe_name), int(dosage_id)))
        conn.commit()
    finally:
        conn.close()


def get_unsynced_dosages() -> list[Dosage]:
    """Return dosages where synced=0 (both brand-new and locally edited)."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, frappe_name, code, description, synced, sync_date
          FROM dosages
         WHERE synced = 0
         ORDER BY id
    """)
    rows = fetchall_dicts(cur)
    conn.close()
    return [d for d in (_to_dosage(r) for r in rows) if d is not None]


def upsert_dosage_from_frappe(payload: dict) -> int:
    """
    Upsert a dosage record using the payload from Frappe's get_dosages endpoint.
    Returns the local id of the row.

    Expected payload keys:
        name        → Frappe doc name (unique)
        code        → short code (falls back to name)
        description → long-form description
    """
    frappe_name = str(payload.get("name") or "").strip() or None
    code        = str(
        payload.get("code")
        or payload.get("dosage_code")
        or payload.get("name")
        or ""
    ).strip()
    description = payload.get("description") or payload.get("dosage") or payload.get("label")

    def _n(v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    description = _n(description)

    if not code:
        # Cannot insert without a code (UNIQUE NOT NULL)
        raise ValueError("Dosage payload missing both 'code' and 'name'")

    conn = get_connection()
    cur  = conn.cursor()
    try:
        # Prefer lookup by frappe_name, fall back to code
        existing_id = None
        if frappe_name:
            cur.execute("SELECT id FROM dosages WHERE frappe_name = ?", (frappe_name,))
            row = cur.fetchone()
            if row:
                existing_id = int(row[0])
        if not existing_id:
            cur.execute("SELECT id FROM dosages WHERE code = ?", (code,))
            row = cur.fetchone()
            if row:
                existing_id = int(row[0])

        if existing_id:
            cur.execute("""
                UPDATE dosages SET
                    frappe_name = ISNULL(?, frappe_name),
                    code        = ?,
                    description = ?,
                    synced      = 1,
                    sync_date   = ?
                WHERE id = ?
            """, (frappe_name, code, description, datetime.now(), existing_id))
            conn.commit()
            return existing_id

        cur.execute("""
            INSERT INTO dosages (
                frappe_name, code, description, synced, sync_date
            )
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, 1, ?)
        """, (frappe_name, code, description, datetime.now()))
        new_id = int(cur.fetchone()[0])
        conn.commit()
        return new_id
    finally:
        conn.close()


# =============================================================================
# PRIVATE
# =============================================================================

def _to_dosage(row: dict) -> Optional[Dosage]:
    if not row:
        return None
    sd = row.get("sync_date")
    sd_str = sd.isoformat() if hasattr(sd, "isoformat") else (str(sd) if sd else None)
    return Dosage(
        id=row.get("id"),
        frappe_name=row.get("frappe_name"),
        code=row.get("code") or "",
        description=row.get("description"),
        synced=bool(row.get("synced", False)),
        sync_date=sd_str,
    )

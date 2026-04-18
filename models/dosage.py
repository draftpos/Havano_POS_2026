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

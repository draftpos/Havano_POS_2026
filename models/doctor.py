# =============================================================================
# models/doctor.py  —  SQL Server version
# Doctor records mirrored from Frappe (Pharmacy module)
# =============================================================================

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from database.db import get_connection, fetchall_dicts, fetchone_dict


@dataclass
class Doctor:
    id: Optional[int] = None
    frappe_name: Optional[str] = None
    full_name: str = ""
    practice_no: Optional[str] = None
    qualification: Optional[str] = None
    school: Optional[str] = None
    phone: Optional[str] = None
    synced: bool = False
    sync_date: Optional[str] = None


# =============================================================================
# READ
# =============================================================================

def list_doctors() -> list[Doctor]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, frappe_name, full_name, practice_no, qualification,
               school, phone, synced, sync_date
        FROM doctors
        ORDER BY full_name
    """)
    rows = fetchall_dicts(cur)
    conn.close()
    return [_to_doctor(r) for r in rows]


def get_doctor_by_id(doctor_id: int) -> Optional[Doctor]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, frappe_name, full_name, practice_no, qualification,
               school, phone, synced, sync_date
        FROM doctors
        WHERE id = ?
    """, (doctor_id,))
    row = fetchone_dict(cur)
    conn.close()
    return _to_doctor(row) if row else None


def get_doctor_by_frappe_name(name: str) -> Optional[Doctor]:
    if not name:
        return None
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, frappe_name, full_name, practice_no, qualification,
               school, phone, synced, sync_date
        FROM doctors
        WHERE frappe_name = ?
    """, (name,))
    row = fetchone_dict(cur)
    conn.close()
    return _to_doctor(row) if row else None


# =============================================================================
# WRITE
# =============================================================================

def create_doctor_local(
    full_name: str,
    practice_no: Optional[str] = None,
    qualification: Optional[str] = None,
    school: Optional[str] = None,
    phone: Optional[str] = None,
) -> int:
    """
    INSERT a new local Doctor record. Marked unsynced (synced=0, frappe_name=NULL)
    so the push service picks it up. Returns the new local id.
    """
    full_name = (full_name or "").strip()
    if not full_name:
        raise ValueError("Doctor full_name is required")

    def _n(v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    practice_no   = _n(practice_no)
    qualification = _n(qualification)
    school        = _n(school)
    phone         = _n(phone)

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO doctors (
                frappe_name, full_name, practice_no, qualification,
                school, phone, synced, sync_date
            )
            OUTPUT INSERTED.id
            VALUES (NULL, ?, ?, ?, ?, ?, 0, NULL)
        """, (full_name, practice_no, qualification, school, phone))
        new_id = int(cur.fetchone()[0])
        conn.commit()
        return new_id
    finally:
        conn.close()


def update_doctor_local(doctor_id: int, **fields) -> bool:
    """
    UPDATE an existing local Doctor record. Any content-field change resets
    synced=0 so the push service re-pushes it on next run. Returns True on
    success, False if the row was not found.

    Accepts kwargs: full_name, practice_no, qualification, school, phone.
    """
    allowed = ("full_name", "practice_no", "qualification", "school", "phone")

    def _n(v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    updates: dict = {}
    for k in allowed:
        if k in fields:
            v = fields[k]
            # full_name cannot be empty
            if k == "full_name":
                s = (str(v) if v is not None else "").strip()
                if not s:
                    raise ValueError("Doctor full_name cannot be empty")
                updates[k] = s
            else:
                updates[k] = _n(v)

    if not updates:
        return True  # nothing to do

    set_parts = [f"{col} = ?" for col in updates.keys()]
    # Any write to content fields resets synced so push picks it up
    set_parts.append("synced = 0")
    set_parts.append("sync_date = NULL")
    params = list(updates.values()) + [doctor_id]

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            f"UPDATE doctors SET {', '.join(set_parts)} WHERE id = ?",
            params,
        )
        ok = cur.rowcount > 0
        conn.commit()
        return ok
    finally:
        conn.close()


def mark_doctor_synced(doctor_id: int, frappe_name: str) -> None:
    """Flag a local Doctor row as synced (synced=1, sync_date=now, frappe_name=?)."""
    if not frappe_name:
        return
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            UPDATE doctors
               SET synced      = 1,
                   sync_date   = SYSDATETIME(),
                   frappe_name = ?
             WHERE id = ?
        """, (str(frappe_name), int(doctor_id)))
        conn.commit()
    finally:
        conn.close()


def get_unsynced_doctors() -> list[Doctor]:
    """Return doctors where synced=0 (both brand-new and locally edited)."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, frappe_name, full_name, practice_no, qualification,
               school, phone, synced, sync_date
          FROM doctors
         WHERE synced = 0
         ORDER BY id
    """)
    rows = fetchall_dicts(cur)
    conn.close()
    return [d for d in (_to_doctor(r) for r in rows) if d is not None]


def upsert_doctor_from_frappe(payload: dict) -> int:
    """
    Upsert a doctor record using the payload from Frappe's get_doctors endpoint.
    Returns the local id of the row.

    Expected payload keys (all optional except full_name / name):
        name            → Frappe doc name (unique)
        full_name       → display name
        practice_no     → registration / practice number
        qualification   → qualifications string
        school          → school / college of qualification
        phone / mobile_no → contact phone
    """
    frappe_name   = str(payload.get("name") or "").strip() or None
    full_name     = str(
        payload.get("full_name")
        or payload.get("doctor_name")
        or payload.get("name")
        or ""
    ).strip()
    practice_no   = payload.get("practice_no") or payload.get("practice_number")
    qualification = payload.get("qualification") or payload.get("qualifications")
    school        = payload.get("school") or payload.get("college")
    phone         = payload.get("phone") or payload.get("mobile_no") or payload.get("mobile")

    # Normalise to strings / None
    def _n(v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    practice_no   = _n(practice_no)
    qualification = _n(qualification)
    school        = _n(school)
    phone         = _n(phone)

    if not full_name:
        # Fall back to frappe_name so we don't violate NOT NULL constraint
        full_name = frappe_name or "Unknown Doctor"

    conn = get_connection()
    cur  = conn.cursor()
    try:
        existing_id = None
        if frappe_name:
            cur.execute("SELECT id FROM doctors WHERE frappe_name = ?", (frappe_name,))
            row = cur.fetchone()
            if row:
                existing_id = int(row[0])

        if existing_id:
            cur.execute("""
                UPDATE doctors SET
                    full_name     = ?,
                    practice_no   = ?,
                    qualification = ?,
                    school        = ?,
                    phone         = ?,
                    synced        = 1,
                    sync_date     = ?
                WHERE id = ?
            """, (
                full_name, practice_no, qualification, school, phone,
                datetime.now(), existing_id
            ))
            conn.commit()
            return existing_id

        cur.execute("""
            INSERT INTO doctors (
                frappe_name, full_name, practice_no, qualification,
                school, phone, synced, sync_date
            )
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            frappe_name, full_name, practice_no, qualification,
            school, phone, datetime.now()
        ))
        new_id = int(cur.fetchone()[0])
        conn.commit()
        return new_id
    finally:
        conn.close()


# =============================================================================
# PRIVATE
# =============================================================================

def _to_doctor(row: dict) -> Optional[Doctor]:
    if not row:
        return None
    sd = row.get("sync_date")
    sd_str = sd.isoformat() if hasattr(sd, "isoformat") else (str(sd) if sd else None)
    return Doctor(
        id=row.get("id"),
        frappe_name=row.get("frappe_name"),
        full_name=row.get("full_name") or "",
        practice_no=row.get("practice_no"),
        qualification=row.get("qualification"),
        school=row.get("school"),
        phone=row.get("phone"),
        synced=bool(row.get("synced", False)),
        sync_date=sd_str,
    )

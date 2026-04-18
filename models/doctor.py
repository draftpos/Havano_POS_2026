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

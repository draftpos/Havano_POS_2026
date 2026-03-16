# models/cost_center.py
from database.db import get_connection, fetchall_dicts, fetchone_dict

_SEL = """
    SELECT cc.id, cc.name, cc.company_id, c.name AS company_name
    FROM cost_centers cc LEFT JOIN companies c ON c.id = cc.company_id
"""

def get_all_cost_centers() -> list[dict]:
    conn = get_connection(); cur = conn.cursor()
    cur.execute(_SEL + " ORDER BY cc.name")
    rows = fetchall_dicts(cur); conn.close()
    return [_to_dict(r) for r in rows]


def get_cost_centers_by_company(company_id: int) -> list[dict]:
    conn = get_connection(); cur = conn.cursor()
    cur.execute(_SEL + " WHERE cc.company_id = ? ORDER BY cc.name", (company_id,))
    rows = fetchall_dicts(cur); conn.close()
    return [_to_dict(r) for r in rows]


def get_cost_center_by_id(cost_center_id: int) -> dict | None:
    conn = get_connection(); cur = conn.cursor()
    cur.execute(_SEL + " WHERE cc.id = ?", (cost_center_id,))
    row = fetchone_dict(cur); conn.close()
    return _to_dict(row) if row else None


def create_cost_center(name: str, company_id: int) -> dict:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("INSERT INTO cost_centers (name, company_id) OUTPUT INSERTED.id VALUES (?, ?)",
                (name.strip(), company_id))
    new_id = int(cur.fetchone()[0]); conn.commit(); conn.close()
    return get_cost_center_by_id(new_id)


def update_cost_center(cost_center_id: int, name: str = None, company_id: int = None) -> dict | None:
    cc = get_cost_center_by_id(cost_center_id)
    if not cc: return None
    conn = get_connection(); cur = conn.cursor()
    cur.execute("UPDATE cost_centers SET name=?, company_id=? WHERE id=?", (
        name.strip() if name is not None else cc["name"],
        company_id if company_id is not None else cc["company_id"],
        cost_center_id,
    )); conn.commit(); conn.close()
    return get_cost_center_by_id(cost_center_id)


def delete_cost_center(cost_center_id: int) -> bool:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM cost_centers WHERE id = ?", (cost_center_id,))
    affected = cur.rowcount; conn.commit(); conn.close()
    return affected > 0


def _to_dict(row: dict) -> dict | None:
    if not row: return None
    return {"id": row["id"], "name": row["name"] or "",
            "company_id": row["company_id"], "company_name": row.get("company_name") or ""}

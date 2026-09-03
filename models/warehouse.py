# models/warehouse.py
from database.db import get_connection, fetchall_dicts, fetchone_dict

_SEL = """
    SELECT w.id, w.name, w.company_id, c.name AS company_name
    FROM warehouses w LEFT JOIN companies c ON c.id = w.company_id
"""

def get_all_warehouses() -> list[dict]:
    conn = get_connection(); cur = conn.cursor()
    cur.execute(_SEL + " ORDER BY w.name")
    rows = fetchall_dicts(cur); conn.close()
    return [_to_dict(r) for r in rows]


def get_warehouses_by_company(company_id: int) -> list[dict]:
    conn = get_connection(); cur = conn.cursor()
    cur.execute(_SEL + " WHERE w.company_id = ? ORDER BY w.name", (company_id,))
    rows = fetchall_dicts(cur); conn.close()
    return [_to_dict(r) for r in rows]


def get_warehouse_by_id(warehouse_id: int) -> dict | None:
    conn = get_connection(); cur = conn.cursor()
    cur.execute(_SEL + " WHERE w.id = ?", (warehouse_id,))
    row = fetchone_dict(cur); conn.close()
    return _to_dict(row) if row else None


def create_warehouse(name: str, company_id: int) -> dict:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("INSERT INTO warehouses (name, company_id) OUTPUT INSERTED.id VALUES (?, ?)",
                (name.strip(), company_id))
    new_id = int(cur.fetchone()[0]); conn.commit(); conn.close()
    return get_warehouse_by_id(new_id)


def update_warehouse(warehouse_id: int, name: str = None, company_id: int = None) -> dict | None:
    w = get_warehouse_by_id(warehouse_id)
    if not w: return None
    conn = get_connection(); cur = conn.cursor()
    cur.execute("UPDATE warehouses SET name=?, company_id=? WHERE id=?", (
        name.strip() if name is not None else w["name"],
        company_id if company_id is not None else w["company_id"],
        warehouse_id,
    )); conn.commit(); conn.close()
    return get_warehouse_by_id(warehouse_id)


def delete_warehouse(warehouse_id: int) -> bool:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM warehouses WHERE id = ?", (warehouse_id,))
    affected = cur.rowcount; conn.commit(); conn.close()
    return affected > 0


def _to_dict(row: dict) -> dict | None:
    if not row: return None
    return {"id": row["id"], "name": row["name"] or "",
            "company_id": row["company_id"], "company_name": row.get("company_name") or ""}

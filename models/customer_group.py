# models/customer_group.py
from database.db import get_connection, fetchall_dicts, fetchone_dict


def get_all_customer_groups() -> list[dict]:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id, name, parent_group_id FROM customer_groups ORDER BY name")
    rows = fetchall_dicts(cur); conn.close()
    return [_to_dict(r) for r in rows]


def get_customer_group_by_id(group_id: int) -> dict | None:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id, name, parent_group_id FROM customer_groups WHERE id = ?", (group_id,))
    row = fetchone_dict(cur); conn.close()
    return _to_dict(row) if row else None


def create_customer_group(name: str, parent_group_id: int = None) -> dict:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("INSERT INTO customer_groups (name, parent_group_id) OUTPUT INSERTED.id VALUES (?, ?)",
                (name.strip(), parent_group_id))
    new_id = int(cur.fetchone()[0]); conn.commit(); conn.close()
    return get_customer_group_by_id(new_id)


def update_customer_group(group_id: int, name: str = None, parent_group_id: int = None) -> dict | None:
    g = get_customer_group_by_id(group_id)
    if not g: return None
    conn = get_connection(); cur = conn.cursor()
    cur.execute("UPDATE customer_groups SET name=?, parent_group_id=? WHERE id=?", (
        name.strip() if name is not None else g["name"],
        parent_group_id if parent_group_id is not None else g["parent_group_id"],
        group_id,
    )); conn.commit(); conn.close()
    return get_customer_group_by_id(group_id)


def delete_customer_group(group_id: int) -> bool:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM customer_groups WHERE id = ?", (group_id,))
    affected = cur.rowcount; conn.commit(); conn.close()
    return affected > 0


def _to_dict(row: dict) -> dict | None:
    if not row: return None
    return {"id": row["id"], "name": row["name"] or "", "parent_group_id": row.get("parent_group_id")}

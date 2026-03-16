# models/price_list.py
from database.db import get_connection, fetchall_dicts, fetchone_dict


def get_all_price_lists() -> list[dict]:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id, name, selling FROM price_lists ORDER BY name")
    rows = fetchall_dicts(cur); conn.close()
    return [_to_dict(r) for r in rows]


def get_selling_price_lists() -> list[dict]:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id, name, selling FROM price_lists WHERE selling = 1 ORDER BY name")
    rows = fetchall_dicts(cur); conn.close()
    return [_to_dict(r) for r in rows]


def get_price_list_by_id(price_list_id: int) -> dict | None:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id, name, selling FROM price_lists WHERE id = ?", (price_list_id,))
    row = fetchone_dict(cur); conn.close()
    return _to_dict(row) if row else None


def create_price_list(name: str, selling: bool = True) -> dict:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO price_lists (name, selling) OUTPUT INSERTED.id VALUES (?, ?)
    """, (name.strip(), int(selling)))
    new_id = int(cur.fetchone()[0]); conn.commit(); conn.close()
    return get_price_list_by_id(new_id)


def update_price_list(price_list_id: int, name: str = None, selling: bool = None) -> dict | None:
    pl = get_price_list_by_id(price_list_id)
    if not pl: return None
    conn = get_connection(); cur = conn.cursor()
    cur.execute("UPDATE price_lists SET name=?, selling=? WHERE id=?", (
        name.strip() if name is not None else pl["name"],
        int(selling) if selling is not None else int(pl["selling"]),
        price_list_id,
    )); conn.commit(); conn.close()
    return get_price_list_by_id(price_list_id)


def delete_price_list(price_list_id: int) -> bool:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM price_lists WHERE id = ?", (price_list_id,))
    affected = cur.rowcount; conn.commit(); conn.close()
    return affected > 0


def _to_dict(row: dict) -> dict | None:
    if not row: return None
    return {"id": row["id"], "name": row["name"] or "", "selling": bool(row["selling"])}

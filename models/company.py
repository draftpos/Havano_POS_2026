# models/company.py
from database.db import get_connection, fetchall_dicts, fetchone_dict


def get_all_companies() -> list[dict]:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id, name, abbreviation, default_currency, country FROM companies ORDER BY name")
    rows = fetchall_dicts(cur); conn.close()
    return [_to_dict(r) for r in rows]


def get_company_by_id(company_id: int) -> dict | None:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id, name, abbreviation, default_currency, country FROM companies WHERE id = ?", (company_id,))
    row = fetchone_dict(cur); conn.close()
    return _to_dict(row) if row else None


def create_company(name: str, abbreviation: str, default_currency: str, country: str) -> dict:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO companies (name, abbreviation, default_currency, country)
        OUTPUT INSERTED.id VALUES (?, ?, ?, ?)
    """, (name.strip(), abbreviation.strip().upper(), default_currency.strip(), country.strip()))
    new_id = int(cur.fetchone()[0]); conn.commit(); conn.close()
    return get_company_by_id(new_id)


def update_company(company_id: int, name: str = None, abbreviation: str = None,
                   default_currency: str = None, country: str = None) -> dict | None:
    c = get_company_by_id(company_id)
    if not c: return None
    conn = get_connection(); cur = conn.cursor()
    cur.execute("UPDATE companies SET name=?, abbreviation=?, default_currency=?, country=? WHERE id=?", (
        name.strip() if name is not None else c["name"],
        abbreviation.strip().upper() if abbreviation is not None else c["abbreviation"],
        default_currency.strip() if default_currency is not None else c["default_currency"],
        country.strip() if country is not None else c["country"],
        company_id,
    )); conn.commit(); conn.close()
    return get_company_by_id(company_id)


def delete_company(company_id: int) -> bool:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM companies WHERE id = ?", (company_id,))
    affected = cur.rowcount; conn.commit(); conn.close()
    return affected > 0


def _to_dict(row: dict) -> dict | None:
    if not row: return None
    return {
        "id": row["id"], "name": row["name"] or "",
        "abbreviation": row["abbreviation"] or "",
        "default_currency": row["default_currency"] or "",
        "country": row["country"] or "",
    }

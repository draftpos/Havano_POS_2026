# models/gl_account.py
from database.db import get_connection, fetchall_dicts, fetchone_dict


def get_all_accounts() -> list[dict]:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM gl_accounts ORDER BY company, account_name")
    rows = fetchall_dicts(cur); conn.close()
    return [_to_dict(r) for r in rows]


def get_accounts_by_currency(currency: str) -> list[dict]:
    conn = get_connection(); cur = conn.cursor()
    cur.execute(
        "SELECT * FROM gl_accounts WHERE account_currency = ? ORDER BY company, account_name",
        (currency.upper(),)
    )
    rows = fetchall_dicts(cur); conn.close()
    return [_to_dict(r) for r in rows]


def get_account_for_payment(currency: str, company: str) -> dict | None:
    """
    Returns the best GL account for a given currency + company.
    Used to populate paid_to in Payment Entry.
    Prefers Cash account type, then any match.
    """
    conn = get_connection(); cur = conn.cursor()

    # Try: exact currency + company + Cash type
    cur.execute("""
        SELECT TOP 1 * FROM gl_accounts
        WHERE account_currency = ?
          AND company = ?
          AND account_type = 'Cash'
        ORDER BY name
    """, (currency.upper(), company))
    row = fetchone_dict(cur)

    if not row:
        # Relax: any type, same currency + company
        cur.execute("""
            SELECT TOP 1 * FROM gl_accounts
            WHERE account_currency = ?
              AND company = ?
            ORDER BY name
        """, (currency.upper(), company))
        row = fetchone_dict(cur)

    if not row:
        # Last resort: any company, matching currency
        cur.execute("""
            SELECT TOP 1 * FROM gl_accounts
            WHERE account_currency = ?
            ORDER BY name
        """, (currency.upper(),))
        row = fetchone_dict(cur)

    conn.close()
    return _to_dict(row) if row else None


def upsert_account(a: dict) -> None:
    """Insert or update a GL account from Frappe sync."""
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        MERGE gl_accounts AS target
        USING (SELECT ? AS name) AS source ON target.name = source.name
        WHEN MATCHED THEN
            UPDATE SET
                account_name     = ?,
                account_number   = ?,
                company          = ?,
                parent_account   = ?,
                account_type     = ?,
                account_currency = ?,
                updated_at       = SYSDATETIME()
        WHEN NOT MATCHED THEN
            INSERT (name, account_name, account_number, company,
                    parent_account, account_type, account_currency)
            VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (
        a["name"],
        # UPDATE values
        a.get("account_name",     ""),
        a.get("account_number"),
        a.get("company",          ""),
        a.get("parent_account",   ""),
        a.get("account_type",     ""),
        a.get("account_currency", "USD"),
        # INSERT values
        a["name"],
        a.get("account_name",     ""),
        a.get("account_number"),
        a.get("company",          ""),
        a.get("parent_account",   ""),
        a.get("account_type",     ""),
        a.get("account_currency", "USD"),
    ))
    conn.commit(); conn.close()


def _to_dict(row: dict) -> dict | None:
    if not row: return None
    return {
        "id":               row["id"],
        "name":             row["name"]             or "",
        "account_name":     row["account_name"]     or "",
        "account_number":   row.get("account_number") or "",
        "company":          row["company"]          or "",
        "parent_account":   row["parent_account"]   or "",
        "account_type":     row["account_type"]     or "",
        "account_currency": row["account_currency"] or "USD",
    }
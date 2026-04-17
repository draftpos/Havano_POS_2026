# models/gl_account.py
from database.db import get_connection, fetchall_dicts, fetchone_dict
import logging

log = logging.getLogger("GLAccount")


# =============================================================================
# MIGRATION
# =============================================================================

def migrate():
    """
    Ensures gl_accounts and modes_of_payment tables exist with all required columns.
    Safe to call on every startup — uses IF NOT EXISTS guards throughout.
    """
    conn = get_connection(); cur = conn.cursor()

    # ── gl_accounts ──────────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'gl_accounts'
        )
        CREATE TABLE gl_accounts (
            id               INT IDENTITY(1,1) PRIMARY KEY,
            name             NVARCHAR(140) NOT NULL UNIQUE,
            account_name     NVARCHAR(140) NOT NULL DEFAULT '',
            account_number   NVARCHAR(40)  NULL,
            company          NVARCHAR(120) NOT NULL DEFAULT '',
            parent_account   NVARCHAR(140) NOT NULL DEFAULT '',
            account_type     NVARCHAR(50)  NOT NULL DEFAULT '',
            account_currency NVARCHAR(10)  NOT NULL DEFAULT 'USD',
            updated_at       DATETIME2     NOT NULL DEFAULT SYSDATETIME()
        )
    """)

    for col, definition in [
        ("account_currency", "NVARCHAR(10)  NOT NULL DEFAULT 'USD'"),
        ("is_group",         "BIT           NOT NULL DEFAULT 0"),
        ("updated_at",       "DATETIME2     NOT NULL DEFAULT SYSDATETIME()"),
    ]:
        cur.execute(f"""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'gl_accounts' AND COLUMN_NAME = '{col}'
            )
            ALTER TABLE gl_accounts ADD {col} {definition}
        """)

    # ── modes_of_payment ─────────────────────────────────────────────────────
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'modes_of_payment'
        )
        CREATE TABLE modes_of_payment (
            id               INT IDENTITY(1,1) PRIMARY KEY,
            name             NVARCHAR(100) NOT NULL UNIQUE,
            mop_type         NVARCHAR(30)  NOT NULL DEFAULT 'Cash',
            company          NVARCHAR(120) NOT NULL DEFAULT '',
            gl_account       NVARCHAR(140) NOT NULL DEFAULT '',
            account_currency NVARCHAR(10)  NOT NULL DEFAULT 'USD',
            updated_at       DATETIME2     NOT NULL DEFAULT SYSDATETIME()
        )
    """)

    for col, definition in [
        ("mop_type",         "NVARCHAR(30)  NOT NULL DEFAULT 'Cash'"),
        ("company",          "NVARCHAR(120) NOT NULL DEFAULT ''"),
        ("gl_account",       "NVARCHAR(140) NOT NULL DEFAULT ''"),
        ("account_currency", "NVARCHAR(10)  NOT NULL DEFAULT 'USD'"),
        ("updated_at",       "DATETIME2     NOT NULL DEFAULT SYSDATETIME()"),
    ]:
        cur.execute(f"""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'modes_of_payment' AND COLUMN_NAME = '{col}'
            )
            ALTER TABLE modes_of_payment ADD {col} {definition}
        """)

    conn.commit(); conn.close()
    log.info("gl_accounts and modes_of_payment tables verified.")
    print("[gl_account] ✅ gl_accounts and modes_of_payment tables verified.")


# =============================================================================
# GL ACCOUNTS — READ
# =============================================================================

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


def get_account_by_name(name: str) -> dict | None:
    """Returns a GL account by its unique name."""
    if not name: return None
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM gl_accounts WHERE name = ?", (name.strip(),))
    row = fetchone_dict(cur); conn.close()
    return _to_dict(row) if row else None


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


# =============================================================================
# GL ACCOUNTS — WRITE
# =============================================================================

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
                is_group         = ?,
                updated_at       = SYSDATETIME()
        WHEN NOT MATCHED THEN
            INSERT (name, account_name, account_number, company,
                    parent_account, account_type, account_currency, is_group)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        a["name"],
        # UPDATE values
        a.get("account_name",     ""),
        a.get("account_number"),
        a.get("company",          ""),
        a.get("parent_account",   ""),
        a.get("account_type",     ""),
        a.get("account_currency", "USD"),
        int(a.get("is_group") or 0),
        # INSERT values
        a["name"],
        a.get("account_name",     ""),
        a.get("account_number"),
        a.get("company",          ""),
        a.get("parent_account",   ""),
        a.get("account_type",     ""),
        a.get("account_currency", "USD"),
        int(a.get("is_group") or 0),
    ))
    conn.commit(); conn.close()


# =============================================================================
# MODES OF PAYMENT — READ
# =============================================================================

def get_all_mops() -> list[dict]:
    """Returns all locally cached Mode of Payment records."""
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM modes_of_payment ORDER BY name")
    rows = fetchall_dicts(cur); conn.close()
    return [_mop_to_dict(r) for r in rows]


def get_mop_by_name(name: str) -> dict | None:
    """
    Exact lookup by Frappe MOP name.
    Returns the MOP row including its gl_account and account_currency.
    """
    if not name: return None
    conn = get_connection(); cur = conn.cursor()
    cur.execute(
        "SELECT * FROM modes_of_payment WHERE name = ?",
        (name.strip(),)
    )
    row = fetchone_dict(cur); conn.close()
    return _mop_to_dict(row) if row else None


def get_mop_for_currency(currency: str, company: str) -> dict | None:
    """
    Best MOP for a given currency + company.
    Used as fallback when sale.method doesn't match any known MOP name.
    """
    conn = get_connection(); cur = conn.cursor()

    # Prefer exact currency + company match
    cur.execute("""
        SELECT TOP 1 * FROM modes_of_payment
        WHERE account_currency = ?
          AND company = ?
        ORDER BY name
    """, (currency.upper(), company))
    row = fetchone_dict(cur)

    if not row:
        # Relax: any company, matching currency
        cur.execute("""
            SELECT TOP 1 * FROM modes_of_payment
            WHERE account_currency = ?
            ORDER BY name
        """, (currency.upper(),))
        row = fetchone_dict(cur)

    conn.close()
    return _mop_to_dict(row) if row else None


# =============================================================================
# MODES OF PAYMENT — WRITE
# =============================================================================

def upsert_mop(m: dict) -> None:
    """Insert or update a Mode of Payment row (called during Frappe sync)."""
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        MERGE modes_of_payment AS target
        USING (SELECT ? AS name) AS source ON target.name = source.name
        WHEN MATCHED THEN
            UPDATE SET
                mop_type         = ?,
                company          = ?,
                gl_account       = ?,
                account_currency = ?,
                updated_at       = SYSDATETIME()
        WHEN NOT MATCHED THEN
            INSERT (name, mop_type, company, gl_account, account_currency)
            VALUES (?, ?, ?, ?, ?);
    """, (
        m["name"],
        # UPDATE
        m.get("mop_type",         "Cash"),
        m.get("company",          ""),
        m.get("gl_account",       ""),
        m.get("account_currency", "USD"),
        # INSERT
        m["name"],
        m.get("mop_type",         "Cash"),
        m.get("company",          ""),
        m.get("gl_account",       ""),
        m.get("account_currency", "USD"),
    ))
    conn.commit(); conn.close()


# =============================================================================
# MODES OF PAYMENT — FRAPPE SYNC
# =============================================================================

def sync_modes_of_payment(api_key: str, api_secret: str,
                           host: str, company: str) -> int:
    """
    Fetches all Mode of Payment records from Frappe and stores them locally.
    For each MOP, reads the accounts child table to get the GL account and
    currency that belongs to this company.

    Call this on startup and periodically (e.g. every hour).
    Returns count of MOP records successfully synced.
    """
    import json
    import urllib.request
    import urllib.parse

    url = (
        f"{host}/api/resource/Mode%20of%20Payment"
        f"?fields=[\"name\",\"type\"]&limit=100"
    )
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {api_key}:{api_secret}")

    with urllib.request.urlopen(req, timeout=30) as r:
        mop_list = json.loads(r.read().decode()).get("data", [])

    count = 0
    for mop in mop_list:
        mop_name = mop["name"]

        detail_url = (
            f"{host}/api/resource/Mode%20of%20Payment/"
            f"{urllib.parse.quote(mop_name)}"
        )
        req2 = urllib.request.Request(detail_url)
        req2.add_header("Authorization", f"token {api_key}:{api_secret}")

        try:
            with urllib.request.urlopen(req2, timeout=30) as r2:
                detail   = json.loads(r2.read().decode()).get("data", {})
                accounts = detail.get("accounts", [])

            # Prefer the account row that belongs to our company;
            # fall back to the first row if no company match found.
            acct_row = next(
                (a for a in accounts if a.get("company") == company),
                accounts[0] if accounts else {}
            )

            # Resolve account_currency from our local gl_accounts table
            # so we don't have to trust whatever Frappe returns in the child row
            gl_account_name = acct_row.get("default_account", "")
            currency = acct_row.get("account_currency", "")

            if not currency and gl_account_name:
                local_acct = get_account_by_name(gl_account_name)
                if local_acct:
                    currency = local_acct.get("account_currency", "USD")

            currency = (currency or "USD").upper()

            upsert_mop({
                "name":             mop_name,
                "mop_type":         mop.get("type", "Cash"),
                "company":          acct_row.get("company", company),
                "gl_account":       gl_account_name,
                "account_currency": currency,
            })
            log.debug("MOP synced: %s → %s (%s)", mop_name, gl_account_name, currency)
            count += 1

        except Exception as e:
            log.warning("Could not fetch MOP detail for '%s': %s", mop_name, e)

    log.info("Synced %d Mode of Payment record(s) from Frappe.", count)
    return count


# =============================================================================
# PRIVATE HELPERS
# =============================================================================

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
        "is_group":         int(row.get("is_group") or 0),
    }


def _mop_to_dict(row: dict) -> dict | None:
    if not row: return None
    return {
        "id":               row["id"],
        "name":             row["name"]             or "",
        "mop_type":         row.get("mop_type",     "Cash"),
        "company":          row.get("company",      ""),
        "gl_account":       row.get("gl_account",   ""),
        "account_currency": row.get("account_currency", "USD"),
    }
    
# In models/gl_account.py, add this function if not present:

def get_leaf_accounts(currency: str = None) -> list[dict]:
    """Get only leaf accounts (is_group = 0)"""
    from database.db import get_connection
    
    conn = get_connection()
    cur = conn.cursor()
    
    if currency:
        cur.execute("""
            SELECT * FROM gl_accounts 
            WHERE (is_group = 0 OR is_group IS NULL)
            AND account_currency = ?
            ORDER BY name
        """, (currency,))
    else:
        cur.execute("""
            SELECT * FROM gl_accounts 
            WHERE (is_group = 0 OR is_group IS NULL)
            ORDER BY name
        """)
    
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    
    return [dict(zip(cols, r)) for r in rows]
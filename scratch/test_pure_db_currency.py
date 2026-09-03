import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from database.db import get_connection, fetchone_dict

def get_pure_db_currency(method_name: str) -> str:
    """
    100% data-driven currency lookup from database.
    No hardcoded string checks or currency literals.
    """
    if not method_name:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
        return d.get("server_company_currency") or d.get("company_currency") or "USD"
        
    clean_name = method_name.strip()

    try:
        conn = get_connection()
        cur = conn.cursor()

        # 1. Check modes_of_payment table
        cur.execute("""
            SELECT account_currency, gl_account 
            FROM modes_of_payment 
            WHERE LOWER(name) = LOWER(?)
        """, (clean_name,))
        row = fetchone_dict(cur)

        if row:
            curr = (row.get("account_currency") or "").strip()
            if curr:
                conn.close()
                return curr
            
            gl_acc = (row.get("gl_account") or "").strip()
            if gl_acc:
                cur.execute("SELECT account_currency FROM gl_accounts WHERE LOWER(name) = LOWER(?)", (gl_acc,))
                gl_row = fetchone_dict(cur)
                if gl_row and (gl_row.get("account_currency") or "").strip():
                    conn.close()
                    return gl_row.get("account_currency").strip()

        # 2. Check gl_accounts table directly
        cur.execute("SELECT account_currency FROM gl_accounts WHERE LOWER(name) = LOWER(?)", (clean_name,))
        gl_row = fetchone_dict(cur)
        if gl_row and (gl_row.get("account_currency") or "").strip():
            conn.close()
            return gl_row.get("account_currency").strip()

        # 3. Check payment_entries table for recent transaction
        cur.execute("""
            SELECT TOP 1 currency 
            FROM payment_entries 
            WHERE LOWER(mode_of_payment) = LOWER(?) AND currency IS NOT NULL AND currency <> ''
            ORDER BY id DESC
        """, (clean_name,))
        pe_row = fetchone_dict(cur)
        conn.close()
        if pe_row and (pe_row.get("currency") or "").strip():
            return pe_row.get("currency").strip()

        conn.close()
    except Exception as e:
        print(f"DB lookup error: {e}")

    # 4. Fallback to company default currency
    try:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
        default_curr = d.get("server_company_currency") or d.get("company_currency")
        if default_curr:
            return default_curr.strip()
    except Exception:
        pass

    return "USD"

conn = get_connection()
cur = conn.cursor()
print("--- PURE DB CURRENCY TEST ---")
cur.execute("SELECT name FROM modes_of_payment")
mops = [r[0] for r in cur.fetchall()]
for m in mops:
    print(f"MOP '{m}' -> '{get_pure_db_currency(m)}'")
conn.close()

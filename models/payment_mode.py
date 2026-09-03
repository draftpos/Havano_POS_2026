# models/payment_mode.py
from database.db import get_connection, fetchall_dicts

def create_payment_mode(name: str, gl_account: str = None, currency: str = "USD") -> int:
    conn = get_connection(); cur = conn.cursor()
    # Get max display order
    cur.execute("SELECT ISNULL(MAX(display_order), 0) FROM modes_of_payment")
    max_order = int(cur.fetchone()[0])
    
    cur.execute("""
        INSERT INTO modes_of_payment (name, gl_account, account_currency, enabled, display_order)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, 1, ?)
    """, (name.strip(), gl_account, currency.upper(), max_order + 1))
    new_id = int(cur.fetchone()[0]); conn.commit(); conn.close()
    return new_id

def delete_payment_mode(mop_id: int) -> bool:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM modes_of_payment WHERE id = ?", (mop_id,))
    affected = cur.rowcount; conn.commit(); conn.close()
    return affected > 0

def update_payment_mode(mop_id: int, name: str, gl_account: str, currency: str, enabled: bool) -> bool:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        UPDATE modes_of_payment 
        SET name = ?, gl_account = ?, account_currency = ?, enabled = ? 
        WHERE id = ?
    """, (name, gl_account, currency, 1 if enabled else 0, mop_id))
    affected = cur.rowcount; conn.commit(); conn.close()
    return affected > 0

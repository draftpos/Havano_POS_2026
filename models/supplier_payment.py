from database.db import get_connection, fetchall_dicts

def ensure_supplier_payment_table():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='supplier_payments')
            CREATE TABLE supplier_payments (
                id               INT           IDENTITY(1,1) PRIMARY KEY,
                supplier_id      INT           NULL,
                supplier_name    NVARCHAR(200) NOT NULL DEFAULT '',
                amount           DECIMAL(12,2) NOT NULL DEFAULT 0,
                method           NVARCHAR(50)  NOT NULL DEFAULT '',
                reference        NVARCHAR(200) NULL,
                created_at       DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
                synced           BIT           NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
    except Exception as e:
        print(f"[ensure_supplier_payment_table] Error: {e}")
    finally:
        conn.close()

def create_supplier_payment(supplier_id: int, supplier_name: str, amount: float, method: str, reference: str):
    """
    Record an outward payment to a supplier.
    """
    ensure_supplier_payment_table()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO supplier_payments (supplier_id, supplier_name, amount, method, reference)
            VALUES (?, ?, ?, ?, ?)
        """, (supplier_id, supplier_name, amount, method, reference))
        
        # Decrement the owed balance for the supplier
        cur.execute("""
            UPDATE suppliers 
            SET balance = ISNULL(balance, 0) - ?
            WHERE id = ?
        """, (amount, supplier_id))
        
        conn.commit()
    except Exception as e:
        print(f"[create_supplier_payment] Error: {e}")
    finally:
        conn.close()

def get_supplier_payments():
    """
    Fetch all supplier payments.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM supplier_payments ORDER BY created_at DESC")
        return fetchall_dicts(cur)
    except Exception as e:
        print(f"[get_supplier_payments] Error: {e}")
        return []
    finally:
        conn.close()

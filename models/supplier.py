# models/supplier.py
from database.db import get_connection, fetchall_dicts, fetchone_dict

def ensure_supplier_table():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[suppliers]') AND type in (N'U'))
        BEGIN
            CREATE TABLE [dbo].[suppliers](
                [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
                [name] [nvarchar](200) NOT NULL,
                [email] [nvarchar](200) NULL,
                [phone] [nvarchar](50) NULL,
                [address] [nvarchar](max) NULL,
                [balance] [decimal](18,4) DEFAULT 0.0,
                [created_at] [datetime] DEFAULT GETDATE()
            )
        END
        ELSE
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='suppliers' AND COLUMN_NAME='balance')
            ALTER TABLE suppliers ADD balance DECIMAL(18,4) DEFAULT 0.0;
        END
    """)
    conn.commit(); conn.close()

def get_all_suppliers() -> list[dict]:
    ensure_supplier_table()
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id, name, email, phone, address, balance FROM suppliers ORDER BY name")
    rows = fetchall_dicts(cur); conn.close()
    return rows

def create_supplier(name: str, email: str = None, phone: str = None, address: str = None) -> int:
    ensure_supplier_table()
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO suppliers (name, email, phone, address) 
        OUTPUT INSERTED.id 
        VALUES (?, ?, ?, ?)
    """, (name.strip(), email, phone, address))
    new_id = int(cur.fetchone()[0]); conn.commit(); conn.close()
    return new_id

def delete_supplier(supplier_id: int) -> bool:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
    affected = cur.rowcount; conn.commit(); conn.close()
    return affected > 0

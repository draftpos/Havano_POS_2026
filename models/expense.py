# models/expense.py
from database.db import get_connection, fetchall_dicts, fetchone_dict

def ensure_expense_tables():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[expense_categories]') AND type in (N'U'))
        BEGIN
            CREATE TABLE [dbo].[expense_categories](
                [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
                [name] [nvarchar](200) NOT NULL UNIQUE,
                [created_at] [datetime] DEFAULT GETDATE()
            )
        END
    """)
    cur.execute("""
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[expenses]') AND type in (N'U'))
        BEGIN
            CREATE TABLE [dbo].[expenses](
                [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
                [expense_category_id] [int] NULL,
                [name] [nvarchar](200) NOT NULL,
                [amount] [decimal](18,4) NOT NULL DEFAULT 0.0,
                [supplier_id] [int] NULL,
                [paid] [bit] NOT NULL DEFAULT 1,
                [created_at] [datetime] DEFAULT GETDATE()
            )
        END
        ELSE
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='expense_number')
            ALTER TABLE expenses ADD expense_number NVARCHAR(50) NULL;
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='balance')
            BEGIN
                ALTER TABLE expenses ADD balance DECIMAL(18,4) NULL;
                EXEC('UPDATE expenses SET balance = amount WHERE balance IS NULL');
            END
        END
    """)
    conn.commit(); conn.close()

def get_expense_categories():
    ensure_expense_tables()
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id, name FROM expense_categories ORDER BY name")
    rows = fetchall_dicts(cur); conn.close()
    return rows

def create_expense_category(name: str):
    ensure_expense_tables()
    conn = get_connection(); cur = conn.cursor()
    cur.execute("INSERT INTO expense_categories (name) OUTPUT INSERTED.id VALUES (?)", (name.strip(),))
    new_id = int(cur.fetchone()[0]); conn.commit(); conn.close()
    return new_id

def create_expense(name: str, category_id: int, amount: float, supplier_id: int = None, paid: bool = True):
    ensure_expense_tables()
    conn = get_connection(); cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO expenses (name, expense_category_id, amount, supplier_id, paid, balance)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name.strip(), category_id, amount, supplier_id, 1 if paid else 0, 0 if paid else amount))
    new_id = int(cur.fetchone()[0])
    
    # Auto-generate expense number EXP-000001
    expense_number = f"EXP-{new_id:06d}"
    cur.execute("UPDATE expenses SET expense_number = ? WHERE id = ?", (expense_number, new_id))
    
    if supplier_id and not paid:
        cur.execute("UPDATE suppliers SET balance = balance + ? WHERE id = ?", (amount, supplier_id))
        
    conn.commit(); conn.close()
    return new_id

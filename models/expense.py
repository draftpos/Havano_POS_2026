# models/expense.py
from datetime import datetime
from database.db import get_connection, fetchall_dicts, fetchone_dict

_tables_ensured = False

def ensure_expense_tables():
    global _tables_ensured
    if _tables_ensured:
        return
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[expense_categories]') AND type in (N'U'))
        BEGIN
            CREATE TABLE [dbo].[expense_categories](
                [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
                [name] [nvarchar](200) NOT NULL UNIQUE,
                [default_account] [nvarchar](200) NULL,
                [description] [nvarchar](500) NULL,
                [created_at] [datetime] DEFAULT GETDATE()
            )
        END
        ELSE
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expense_categories' AND COLUMN_NAME='default_account')
            ALTER TABLE expense_categories ADD default_account NVARCHAR(200) NULL;
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expense_categories' AND COLUMN_NAME='description')
            ALTER TABLE expense_categories ADD description NVARCHAR(500) NULL;
        END
    """)
    cur.execute("""
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[expenses]') AND type in (N'U'))
        BEGIN
            CREATE TABLE [dbo].[expenses](
                [id] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
                [expense_category_id] [int] NULL,
                [expense_type] [nvarchar](200) NULL,
                [name] [nvarchar](200) NOT NULL,
                [description] [nvarchar](max) NULL,
                [amount] [decimal](18,4) NOT NULL DEFAULT 0.0,
                [payment_method] [nvarchar](100) NOT NULL DEFAULT 'Cash',
                [currency] [nvarchar](10) NULL,
                [supplier_id] [int] NULL,
                [paid] [bit] NOT NULL DEFAULT 1,
                [synced] [bit] NOT NULL DEFAULT 0,
                [cloud_name] [nvarchar](100) NULL,
                [cloud_status] [nvarchar](50) NULL,
                [sync_error] [nvarchar](max) NULL,
                [created_at] [datetime] DEFAULT GETDATE()
            )
        END
        ELSE
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='expense_number')
            ALTER TABLE expenses ADD expense_number NVARCHAR(50) NULL;
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='expense_type')
            ALTER TABLE expenses ADD expense_type NVARCHAR(200) NULL;
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='description')
            ALTER TABLE expenses ADD description NVARCHAR(MAX) NULL;
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='balance')
            BEGIN
                ALTER TABLE expenses ADD balance DECIMAL(18,4) NULL;
                EXEC('UPDATE expenses SET balance = amount WHERE balance IS NULL');
            END
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='payment_method')
            ALTER TABLE expenses ADD payment_method NVARCHAR(100) NOT NULL DEFAULT 'Cash';
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='currency')
            ALTER TABLE expenses ADD currency NVARCHAR(10) NULL;
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='shift_id')
            ALTER TABLE expenses ADD shift_id INT NULL;
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='cashier_id')
            ALTER TABLE expenses ADD cashier_id INT NULL;
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='cashier_name')
            ALTER TABLE expenses ADD cashier_name NVARCHAR(100) NULL;
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='synced')
            ALTER TABLE expenses ADD synced BIT NOT NULL DEFAULT 0;
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='cloud_name')
            ALTER TABLE expenses ADD cloud_name NVARCHAR(100) NULL;
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='cloud_status')
            ALTER TABLE expenses ADD cloud_status NVARCHAR(50) NULL;
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='sync_error')
            ALTER TABLE expenses ADD sync_error NVARCHAR(MAX) NULL;
        END
    """)
    conn.commit(); conn.close()
    _tables_ensured = True

def get_expense_payment_methods() -> list[str]:
    """Retrieve distinct enabled payment methods for expenses."""
    methods = []
    try:
        from models.gl_account import get_all_mops
        mops = get_all_mops()
        for m in mops:
            if m.get("enabled", 1):
                name = (m.get("name") or "").strip()
                if name and name not in methods:
                    methods.append(name)
    except Exception as e:
        print(f"Error fetching expense payment methods: {e}")

    if not methods:
        methods = ["Cash", "Ecocash", "Swipe", "Bank Transfer"]
    elif "Cash" not in methods:
        methods.insert(0, "Cash")
    else:
        # Ensure Cash is first in list
        methods.remove("Cash")
        methods.insert(0, "Cash")
    return methods

def get_expense_categories():
    ensure_expense_tables()
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id, name, default_account, description FROM expense_categories ORDER BY name")
    rows = fetchall_dicts(cur); conn.close()

    # If local table is empty and in SaaS mode, trigger background cloud fetch without blocking
    if not rows:
        try:
            from services.expense_sync_service import is_saas_mode, fetch_cloud_expense_categories
            if is_saas_mode():
                import threading
                threading.Thread(target=fetch_cloud_expense_categories, daemon=True, name="FetchExpenseCats").start()
        except Exception:
            pass

    return rows

def create_expense_category(name: str):
    ensure_expense_tables()
    conn = get_connection(); cur = conn.cursor()
    cur.execute("INSERT INTO expense_categories (name) OUTPUT INSERTED.id VALUES (?)", (name.strip(),))
    new_id = int(cur.fetchone()[0]); conn.commit(); conn.close()

    # In SaaS mode, also create category in cloud asynchronously in background
    try:
        from services.expense_sync_service import is_saas_mode, create_cloud_expense_category
        if is_saas_mode():
            import threading
            threading.Thread(target=create_cloud_expense_category, args=(name.strip(),), daemon=True, name="CreateExpenseCat").start()
    except Exception as e:
        print(f"[expense] SaaS category cloud push notice: {e}")

    return new_id

def create_expense(name: str, category_id: int, amount: float, supplier_id: int = None, paid: bool = True,
                   shift_id: int = None, cashier_id: int = None, cashier_name: str = None,
                   synced: bool = False, cloud_name: str = None, cloud_status: str = None,
                   payment_method: str = "Cash", currency: str = None):
    ensure_expense_tables()
    conn = get_connection(); cur = conn.cursor()
    
    clean_pm = (payment_method or "Cash").strip()
    if not clean_pm:
        clean_pm = "Cash"
    if not currency:
        try:
            from models.shift import get_payment_method_currency
            currency = get_payment_method_currency(clean_pm)
        except Exception:
            currency = "USD"

    exp_type = None
    if category_id:
        try:
            cur.execute("SELECT name FROM expense_categories WHERE id = ?", (category_id,))
            c_row = cur.fetchone()
            if c_row:
                exp_type = c_row[0]
        except Exception:
            pass

    cur.execute("""
        INSERT INTO expenses (name, description, expense_category_id, expense_type, amount, payment_method, currency, supplier_id, paid, balance, shift_id, cashier_id, cashier_name, synced, cloud_name, cloud_status)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name.strip(), name.strip(), category_id, exp_type, amount, clean_pm, currency, supplier_id, 1 if paid else 0, 0 if paid else amount, shift_id, cashier_id, cashier_name,
          1 if synced else 0, cloud_name, cloud_status))
    new_id = int(cur.fetchone()[0])
    
    # Auto-generate expense number EXP-000001
    expense_number = f"EXP-{new_id:06d}"
    cur.execute("UPDATE expenses SET expense_number = ? WHERE id = ?", (expense_number, new_id))
    
    if supplier_id and not paid:
        cur.execute("UPDATE suppliers SET balance = balance + ? WHERE id = ?", (amount, supplier_id))
        
    conn.commit(); conn.close()
    return new_id

def get_shift_expenses(shift_id: int) -> list[dict]:
    """Retrieve all paid till expenses recorded during a shift."""
    ensure_expense_tables()
    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("SELECT created_at, end_time FROM shifts WHERE id = ?", (shift_id,))
        s_times = cur.fetchone()
        if not s_times:
            conn.close()
            return []
        st = s_times[0]
        et = s_times[1] if s_times[1] else datetime.now()

        cur.execute("""
            SELECT e.id, e.expense_number, e.name, e.amount, e.paid, e.created_at,
                   COALESCE(c.name, 'Uncategorized') as category_name,
                   e.cashier_id, e.cashier_name,
                   COALESCE(NULLIF(LTRIM(RTRIM(e.payment_method)), ''), 'Cash') as payment_method,
                   COALESCE(e.currency, '') as currency
            FROM expenses e
            LEFT JOIN expense_categories c ON e.expense_category_id = c.id
            WHERE e.paid = 1
              AND (e.shift_id = ? OR (e.shift_id IS NULL AND e.created_at >= ? AND e.created_at <= ?))
            ORDER BY e.id ASC
        """, (shift_id, st, et))
        rows = fetchall_dicts(cur)
        conn.close()
        return rows
    except Exception as e:
        try: conn.close()
        except: pass
        return []

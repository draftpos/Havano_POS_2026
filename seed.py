import pyodbc
from database.db import get_connection

def setup_database():
    print("🚀 Starting Database Update...")
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # --- 1. SETUP CUSTOMERS TABLE ---
        print("Checking 'customers' table for balance fields...")
        # Add outstanding_amount if missing
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.columns 
                           WHERE object_id = OBJECT_ID('customers') AND name = 'outstanding_amount')
            ALTER TABLE customers ADD outstanding_amount DECIMAL(18,2) DEFAULT 0;
        """)
        # Add balance if missing
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.columns 
                           WHERE object_id = OBJECT_ID('customers') AND name = 'balance')
            ALTER TABLE customers ADD balance DECIMAL(18,2) DEFAULT 0;
        """)
        print("✅ Customers table is ready.")

        # --- 2. SETUP CUSTOMER_PAYMENTS TABLE ---
        print("Checking 'customer_payments' table...")
        
        # We drop and recreate or carefully add. To be safe and ensure EVERY field exists:
        table_schema = """
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'customer_payments')
        BEGIN
            CREATE TABLE customer_payments (
                id INT IDENTITY(1,1) PRIMARY KEY,
                customer_id INT NOT NULL,
                amount DECIMAL(18,2) NOT NULL,
                currency NVARCHAR(10) DEFAULT 'USD',
                method NVARCHAR(50) NOT NULL,       -- Cash, Swipe, EcoCash, etc.
                account_name NVARCHAR(100),        -- Bank account / Drawer name
                reference NVARCHAR(100),           -- Trans ID or Ref
                cashier_id INT,                    -- User ID
                payment_date DATE,                 -- Date picked in UI
                created_at DATETIME2 DEFAULT SYSDATETIME(),
                
                CONSTRAINT FK_Payment_Customer FOREIGN KEY (customer_id) 
                REFERENCES customers(id) ON DELETE CASCADE
            );
            PRINT 'Created customer_payments table.';
        END
        """
        cur.execute(table_schema)
        
        # --- 3. FIX EXISTING TABLE (In case it was created half-way before) ---
        extra_columns = [
            ("currency", "NVARCHAR(10) DEFAULT 'USD'"),
            ("account_name", "NVARCHAR(100)"),
            ("payment_date", "DATE"),
            ("cashier_id", "INT")
        ]
        
        for col, col_type in extra_columns:
            cur.execute(f"""
                IF NOT EXISTS (SELECT 1 FROM sys.columns 
                               WHERE object_id = OBJECT_ID('customer_payments') AND name = '{col}')
                ALTER TABLE customer_payments ADD {col} {col_type};
            """)

        conn.commit()
        print("✅ SUCCESS: All fields generated and tables synced.")

    except Exception as e:
        conn.rollback()
        print(f"❌ DATABASE ERROR: {e}")
    finally:
        conn.close()
        print("Done.")

if __name__ == "__main__":
    setup_database()
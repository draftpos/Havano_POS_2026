# models/payment.py
from database.db import get_connection

def create_customer_payment(customer_id, amount, method, reference, cashier_id):
    """Saves a non-sale payment (account payment) to the database."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO customer_payments (customer_id, amount, method, reference, cashier_id, created_at)
        VALUES (?, ?, ?, ?, ?, GETDATE())
    """, (customer_id, float(amount), method, reference, cashier_id))
    conn.commit()
    conn.close()

def migrate_payments():
    """Create the payments table if it doesn't exist."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'customer_payments')
        CREATE TABLE customer_payments (
            id INT IDENTITY(1,1) PRIMARY KEY,
            customer_id INT NOT NULL,
            amount DECIMAL(12,2) NOT NULL,
            method NVARCHAR(30) NOT NULL,
            reference NVARCHAR(100),
            cashier_id INT,
            created_at DATETIME2 DEFAULT SYSDATETIME()
        )
    """)
    conn.commit()
    conn.close()
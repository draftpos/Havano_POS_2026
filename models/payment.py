# models/payment.py
import logging
from database.db import get_connection, fetchone_dict
from models.receipt import ReceiptData, Item, MultiCurrencyDetail
from services.printing_service import PrintingService

log = logging.getLogger(__name__)

# Note: We initialize the service inside the print function to ensure 
# it picks up the latest printer settings from AdvanceSettings.

def create_customer_payment(customer_id, amount, method, reference, cashier_id, 
                            currency="USD", splits=None, payment_date=None, account_name=None):
    """
    Saves a customer payment to the database and reduces the customer's debt.
    """
    if not customer_id:
        raise ValueError("Cannot record payment: No customer ID provided.")
    
    try:
        amt_float = float(amount)
        if amt_float <= 0:
            raise ValueError("Payment amount must be greater than zero.")
    except ValueError:
        raise ValueError(f"Invalid amount provided: {amount}")

    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # 1. RECORD THE PAYMENT
        cur.execute("""
            INSERT INTO customer_payments (
                customer_id, amount, currency, method, account_name, 
                reference, cashier_id, payment_date, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, SYSDATETIME())
        """, (
            customer_id, 
            amt_float, 
            currency or "USD", 
            method, 
            account_name, 
            reference, 
            cashier_id, 
            payment_date
        ))
        
        # Get the new ID (SQL Server specific)
        cur.execute("SELECT @@IDENTITY AS id")
        row = cur.fetchone()
        payment_id = int(row[0]) if row else None

        # 2. REDUCE THE CUSTOMER'S OUTSTANDING AMOUNT ONLY.
        # NOTE: We do NOT touch the 'balance' column — that is an internal
        # accounting/ledger figure set when sales are posted, not by payments.
        cur.execute("""
            UPDATE customers 
            SET outstanding_amount = ISNULL(outstanding_amount, 0) - ?
            WHERE id = ?
        """, (amt_float, customer_id))

        conn.commit()

        return {
            "id": payment_id,
            "customer_id": customer_id,
            "amount": amt_float,
            "currency": currency,
            "method": method,
            "account_name": account_name,
            "reference": reference,
            "payment_date": payment_date,
            "splits": splits
        }

    except Exception as e:
        conn.rollback()
        log.error(f"Failed to create payment: {e}")
        raise e
    finally:
        conn.close()

def get_payment_by_id(payment_id: int) -> dict | None:
    """Fetches full payment details, customer name, and current balance for printing."""
    sql = """
        SELECT p.*, c.customer_name, c.outstanding_amount as customer_balance
        FROM customer_payments p
        JOIN customers c ON p.customer_id = c.id
        WHERE p.id = ?
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (payment_id,))
        row = cur.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in cur.description]
        return dict(zip(columns, row))
    finally:
        conn.close()

def print_customer_payment(payment_id: int, printer_name: str = None) -> bool:
    """
    Constructs a receipt for a customer payment and sends it to the printer.
    """
    payment = get_payment_by_id(payment_id)
    if not payment:
        log.error(f"Print failed: Payment {payment_id} not found.")
        return False

    try:
        # Load company details the same way every other receipt does it
        from models.company_defaults import get_defaults
        co = get_defaults() or {}

        ps = PrintingService()

        receipt = ReceiptData()
        receipt.receiptType = "PAYMENT RECEIPT"
        receipt.doc_type    = "payment"

        # ── COMPANY DETAILS (from company_defaults, same source as all receipts) ──
        receipt.companyName         = co.get("company_name", "")
        receipt.companyAddress      = co.get("address_1", "")
        receipt.companyAddressLine1 = co.get("address_2", "")
        receipt.companyEmail        = co.get("email", "")
        receipt.tel                 = co.get("phone", "")
        receipt.tin                 = co.get("tin_number", "")
        receipt.vatNo               = co.get("vat_number", "")

        # ── PAYMENT DETAILS ──────────────────────────────────────────────────
        receipt.customer = payment.get("customer_name") or "Walk-in"
        receipt.cashier  = str(payment.get("cashier_id") or "")
        receipt.orderNo  = f"PAY-{payment.get('id'):05d}"
        receipt.date     = str(payment.get("payment_date") or "")

        # ── AMOUNTS ──────────────────────────────────────────────────────────
        receipt.total          = float(payment.get("amount", 0))
        receipt.amountReceived = receipt.total

        # Real remaining customer balance fetched via JOIN in get_payment_by_id
        receipt.balanceDue = float(payment.get("customer_balance") or 0.0)

        # ── OTHER FIELDS ─────────────────────────────────────────────────────
        receipt.items = [
            Item(
                productName=f"Account Payment ({payment.get('method')})",
                qty=1,
                price=receipt.total,
                amount=receipt.total
            )
        ]
        receipt.multiCurrencyDetails = [
            MultiCurrencyDetail(key=str(payment.get("currency") or "USD"), value=receipt.total)
        ]
        receipt.footer = co.get("footer_text", "Thank you for your payment!")

        return ps.print_receipt(receipt, printer_name=printer_name)

    except Exception as e:
        log.error(f"Printing Service Error: {e}")
        return False

def migrate_payments():
    """Ensures the customer_payments table exists."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'customer_payments')
            BEGIN
                CREATE TABLE customer_payments (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    customer_id INT NOT NULL,
                    amount DECIMAL(18,2) NOT NULL,
                    currency NVARCHAR(10) DEFAULT 'USD',
                    method NVARCHAR(30) NOT NULL,
                    account_name NVARCHAR(100),
                    reference NVARCHAR(100),
                    cashier_id INT,
                    payment_date DATE,
                    created_at DATETIME2 DEFAULT SYSDATETIME(),
                    CONSTRAINT FK_Payment_Customer FOREIGN KEY (customer_id) 
                    REFERENCES customers(id) ON DELETE CASCADE
                )
            END
        """)
        conn.commit()
    finally:
        conn.close()
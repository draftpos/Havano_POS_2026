# models/payment.py - Auto-migrating version with split support

import json
import logging
from datetime import datetime
from database.db import get_connection, fetchone_dict
from models.receipt import ReceiptData, Item, MultiCurrencyDetail
from services.printing_service import printing_service

log = logging.getLogger(__name__)

# Flag to ensure migrations run only once per process
_MIGRATIONS_RUN = False


# =============================================================================
# AUTO DATABASE SCHEMA MIGRATION - Runs automatically on import
# =============================================================================

def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 1 FROM sys.columns 
            WHERE object_id = OBJECT_ID(?) 
            AND name = ?
        """, (table_name, column_name))
        result = cur.fetchone() is not None
        conn.close()
        return result
    except Exception:
        conn.close()
        return False


def _table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = ?
        """, (table_name,))
        result = cur.fetchone() is not None
        conn.close()
        return result
    except Exception:
        conn.close()
        return False


def _add_column(table_name: str, column_name: str, column_definition: str):
    """Add a column to a table if it doesn't exist."""
    if not _column_exists(table_name, column_name):
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(f"ALTER TABLE {table_name} ADD {column_name} {column_definition}")
            conn.commit()
            log.info(f"Added column '{column_name}' to '{table_name}'")
        except Exception as e:
            log.warning(f"Could not add column '{column_name}': {e}")
        finally:
            conn.close()
        return True
    return False


def _create_payment_splits_table():
    """Create payment_splits table if it doesn't exist."""
    if not _table_exists("payment_splits"):
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE payment_splits (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    payment_id INT NOT NULL,
                    method NVARCHAR(100) NOT NULL,
                    mop_name NVARCHAR(100) NOT NULL,
                    gl_account NVARCHAR(200) NULL,
                    currency NVARCHAR(10) NOT NULL DEFAULT 'USD',
                    amount DECIMAL(18,2) NOT NULL,
                    amount_usd DECIMAL(18,2) NOT NULL,
                    exchange_rate DECIMAL(18,6) NOT NULL DEFAULT 1.0,
                    created_at DATETIME2 DEFAULT SYSDATETIME()
                )
            """)
            conn.commit()
            log.info("Created 'payment_splits' table")
        except Exception as e:
            log.warning(f"Could not create payment_splits table: {e}")
        finally:
            conn.close()
        return True
    return False


def _add_foreign_key_if_needed():
    """Add foreign key constraint to payment_splits if it doesn't exist."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Check if constraint exists
        cur.execute("""
            SELECT 1 FROM sys.foreign_keys 
            WHERE name = 'FK_PaymentSplit_Payment'
        """)
        if not cur.fetchone():
            cur.execute("""
                ALTER TABLE payment_splits 
                ADD CONSTRAINT FK_PaymentSplit_Payment 
                FOREIGN KEY (payment_id) REFERENCES customer_payments(id) ON DELETE CASCADE
            """)
            conn.commit()
            log.info("Added foreign key constraint to payment_splits")
    except Exception as e:
        log.warning(f"Could not add foreign key: {e}")
    finally:
        conn.close()


def auto_migrate():
    """Run all auto-migrations - called once when module loads."""
    global _MIGRATIONS_RUN
    
    if _MIGRATIONS_RUN:
        return
    
    log.info("Running payment table auto-migrations...")
    
    # Ensure customer_payments table exists first
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Create customer_payments table if it doesn't exist
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
                    created_at DATETIME2 DEFAULT SYSDATETIME()
                )
            END
        """)
        conn.commit()
        log.info("Created customer_payments table or ensured it exists")
    except Exception as e:
        log.warning(f"Could not create customer_payments table: {e}")
    finally:
        conn.close()
    
    # Add all missing columns to customer_payments
    _add_column("customer_payments", "payment_type", "NVARCHAR(20) NOT NULL DEFAULT 'outstanding'")
    _add_column("customer_payments", "splits_json", "NVARCHAR(MAX) NULL")
    _add_column("customer_payments", "synced", "INT NOT NULL DEFAULT 0")
    _add_column("customer_payments", "frappe_ref", "NVARCHAR(255) NOT NULL DEFAULT ''")
    _add_column("customer_payments", "sync_attempts", "INT NOT NULL DEFAULT 0")
    _add_column("customer_payments", "last_sync_attempt", "DATETIME2 NULL")
    _add_column("customer_payments", "sync_error", "NVARCHAR(MAX) NULL")
    _add_column("customer_payments", "syncing", "INT NOT NULL DEFAULT 0")
    _add_column("customer_payments", "amount_usd", "DECIMAL(18,2) NOT NULL DEFAULT 0")
    _add_column("customer_payments", "exchange_rate", "DECIMAL(18,6) NOT NULL DEFAULT 1.0")
    
    # Create payment_splits table and its foreign key
    _create_payment_splits_table()
    _add_foreign_key_if_needed()
    
    _MIGRATIONS_RUN = True
    log.info("Payment table auto-migrations completed.")


# Run migrations immediately when module loads
auto_migrate()


# =============================================================================
# Sync Helper Functions
# =============================================================================

def get_unsynced_payments() -> list[dict]:
    """Return payments that have not yet been pushed to Frappe."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Fetch unsynced payments with customer details
    cur.execute("""
        SELECT p.*, c.customer_name
        FROM customer_payments p
        LEFT JOIN customers c ON p.customer_id = c.id
        WHERE (p.synced = 0 OR p.synced IS NULL)
          AND (p.sync_attempts < 3 
               OR p.last_sync_attempt < DATEADD(MINUTE, -5, GETDATE())
               OR p.last_sync_attempt IS NULL)
        ORDER BY p.id ASC
    """)
    
    rows = cur.fetchall()
    if not rows:
        conn.close()
        return []
    
    columns = [col[0] for col in cur.description]
    results = []
    for row in rows:
        result = dict(zip(columns, row))
        # Convert any datetime objects to ISO strings
        for key, value in result.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
        
        # Fetch splits for this payment
        result["splits"] = get_payment_splits(result["id"])
        
        results.append(result)
    
    conn.close()
    return results


def get_payment_splits(payment_id: int) -> list[dict]:
    """Get all splits for a payment."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, method, mop_name, gl_account, currency, amount, amount_usd, exchange_rate
        FROM payment_splits
        WHERE payment_id = ?
        ORDER BY id
    """, (payment_id,))
    
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        return []
    
    columns = [col[0] for col in cur.description]
    return [dict(zip(columns, row)) for row in rows]


def mark_payment_synced(payment_id: int, frappe_ref: str = ""):
    """Mark a payment as successfully pushed to Frappe."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE customer_payments 
        SET synced = 1, 
            frappe_ref = ?,
            sync_attempts = 0,
            last_sync_attempt = GETDATE(),
            sync_error = NULL
        WHERE id = ?
    """, (frappe_ref, payment_id))
    conn.commit()
    conn.close()
    
    log.info(f"Payment {payment_id} marked as synced with ref: {frappe_ref}")


def mark_payment_sync_failed(payment_id: int, error_message: str):
    """Mark a payment sync attempt as failed."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE customer_payments 
        SET sync_attempts = sync_attempts + 1,
            last_sync_attempt = GETDATE(),
            sync_error = ?
        WHERE id = ?
    """, (error_message, payment_id))
    conn.commit()
    conn.close()
    
    log.warning(f"Payment {payment_id} sync failed: {error_message}")


def get_payment_sync_status(payment_id: int) -> dict:
    """Get sync status for a payment."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT synced, frappe_ref, sync_attempts, last_sync_attempt, sync_error
        FROM customer_payments 
        WHERE id = ?
    """, (payment_id,))
    
    row = cur.fetchone()
    conn.close()
    
    if row:
        return {
            "synced": row[0] == 1,
            "frappe_ref": row[1] or "",
            "sync_attempts": row[2] or 0,
            "last_sync_attempt": row[3],
            "sync_error": row[4]
        }
    return {"synced": False, "frappe_ref": "", "sync_attempts": 0, 
            "last_sync_attempt": None, "sync_error": None}


def schedule_payment_sync_check(payment_id: int, delay_seconds: int = 30):
    """Schedule a sync check for a payment after a delay."""
    import threading
    import time
    
    def _check_and_retry():
        time.sleep(delay_seconds)
        try:
            status = get_payment_sync_status(payment_id)
            if not status["synced"] and status["sync_attempts"] < 3:
                from services.payment_upload_service import push_unsynced_payments
                push_unsynced_payments()
                log.info(f"Retry sync check completed for payment {payment_id}")
        except Exception as e:
            log.error(f"Failed to retry sync for payment {payment_id}: {e}")
    
    t = threading.Thread(target=_check_and_retry, daemon=True, 
                         name=f"PaymentSyncRetry-{payment_id}")
    t.start()
    log.debug(f"Scheduled sync retry for payment {payment_id} in {delay_seconds}s")


def _trigger_payment_sync(payment_id: int):
    """Trigger immediate sync of the payment in the background."""
    import threading
    
    def _sync_worker():
        try:
            from services.payment_upload_service import push_unsynced_payments
            result = push_unsynced_payments()
            log.info(f"Auto-sync triggered for payment {payment_id} - result: {result}")
        except Exception as e:
            log.error(f"Auto-sync failed for payment {payment_id}: {e}")
            schedule_payment_sync_check(payment_id, 30)
    
    t = threading.Thread(target=_sync_worker, daemon=True, 
                         name=f"PaymentAutoSync-{payment_id}")
    t.start()
    log.debug(f"Started auto-sync thread for payment {payment_id}")


# =============================================================================
# Main Payment Functions
# =============================================================================

def create_customer_payment(customer_id, amount, method, reference, cashier_id, 
                            currency="USD", splits=None, payment_date=None, 
                            account_name=None, payment_type="outstanding",
                            amount_usd=None, exchange_rate=1.0):
    """
    Saves a customer payment to the database and reduces the customer's debt.
    Automatically triggers background sync to Frappe.
    
    Args:
        payment_type: "outstanding" or "laybye" - which balance to reduce
        splits: List of dicts with keys: method, mop_name, gl_account, currency, amount, amount_usd, exchange_rate
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
        # 1. RECORD THE PAYMENT with splits_json and payment_type
        splits_json = json.dumps(splits) if splits else None
        
        amt_usd_float = float(amount_usd) if amount_usd is not None else amt_float
        
        cur.execute("""
            INSERT INTO customer_payments (
                customer_id, amount, currency, method, account_name, 
                reference, cashier_id, payment_date, created_at, payment_type, splits_json,
                synced, frappe_ref, sync_attempts, amount_usd, exchange_rate
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, SYSDATETIME(), ?, ?, 0, '', 0, ?, ?)
        """, (
            customer_id, 
            amt_float, 
            currency or "USD", 
            method, 
            account_name, 
            reference, 
            cashier_id, 
            payment_date,
            payment_type,
            splits_json,
            amt_usd_float,
            float(exchange_rate)
        ))
        
        # Get the new ID
        cur.execute("SELECT @@IDENTITY AS id")
        row = cur.fetchone()
        payment_id = int(row[0]) if row else None

        # 2. Save splits to payment_splits table if provided
        if splits and payment_id:
            for split in splits:
                cur.execute("""
                    INSERT INTO payment_splits (
                        payment_id, method, mop_name, gl_account, 
                        currency, amount, amount_usd, exchange_rate
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    payment_id,
                    split.get("method", ""),
                    split.get("mop_name", split.get("method", "")),
                    split.get("gl_account", ""),
                    split.get("currency", "USD"),
                    split.get("amount", 0),
                    split.get("amount_usd", split.get("amount", 0) * split.get("exchange_rate", 1)),
                    split.get("exchange_rate", 1.0)
                ))

        # 3. REDUCE THE CUSTOMER'S BALANCE based on payment_type using amount_usd
        if payment_type == "laybye":
            cur.execute("""
                UPDATE customers 
                SET laybye_balance = ISNULL(laybye_balance, 0) - ?
                WHERE id = ?
            """, (amt_usd_float, customer_id))
        else:
            cur.execute("""
                UPDATE customers 
                SET outstanding_amount = ISNULL(outstanding_amount, 0) - ?
                WHERE id = ?
            """, (amt_usd_float, customer_id))

        conn.commit()

        result = {
            "id": payment_id,
            "customer_id": customer_id,
            "amount": amt_float,
            "currency": currency,
            "method": method,
            "account_name": account_name,
            "reference": reference,
            "payment_date": payment_date,
            "payment_type": payment_type,
            "splits": splits
        }
        
        # Auto-sync to Frappe - wrap in try/except so threading errors don't kill the payment creation
        if payment_id:
            try:
                _trigger_payment_sync(payment_id)
            except Exception as se:
                log.error(f"Failed to trigger sync for payment {payment_id}: {se}")
        
        return result

    except Exception as e:
        conn.rollback()
        log.error(f"Failed to create payment: {e}")
        raise e
    finally:
        conn.close()


def get_payment_by_id(payment_id: int) -> dict | None:
    """Fetches full payment details, customer name, splits, and current balance."""
    sql = """
        SELECT p.*, c.customer_name, 
               c.outstanding_amount as customer_outstanding,
               c.laybye_balance as customer_laybye
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
        payment = dict(zip(columns, row))
        
        # Fetch splits
        payment["splits"] = get_payment_splits(payment_id)
        
        return payment
    finally:
        conn.close()


def print_customer_payment(payment_id: int, printer_name: str = None) -> bool:
    """Constructs a receipt for a customer payment and sends it to the printer."""
    payment = get_payment_by_id(payment_id)
    if not payment:
        log.error(f"Print failed: Payment {payment_id} not found.")
        return False

    try:
        from models.company_defaults import get_defaults
        co = get_defaults() or {}

        # Use the singleton instance instead of creating a new one
        ps = printing_service

        receipt = ReceiptData()
        receipt.receiptType = "PAYMENT RECEIPT"
        receipt.doc_type    = "payment"
        receipt.total = 0.0 # Initialize dynamic field

        # Company details
        receipt.companyName         = co.get("company_name", "")
        receipt.companyAddress      = co.get("address_1", "")
        receipt.companyAddressLine1 = co.get("address_2", "")
        receipt.companyEmail        = co.get("email", "")
        receipt.tel                 = co.get("phone", "")
        receipt.tin                 = co.get("tin_number", "")
        receipt.vatNo               = co.get("vat_number", "")

        # Payment details
        payment_native_amt = float(payment.get("amount", 0))
        payment_usd_amt    = float(payment.get("amount_usd") or payment_native_amt)
        payment_curr       = payment.get("currency", "USD")
        payment_rate       = float(payment.get("exchange_rate") or 1.0)
        
        receipt.customerName = payment.get("customer_name") or "Walk-in"
        receipt.cashier  = str(payment.get("cashier_id") or "")
        receipt.orderNo  = f"PAY-{payment.get('id'):05d}"
        receipt.date     = str(payment.get("payment_date") or "")
        receipt.grandTotal    = payment_usd_amt
        receipt.amountTendered = payment_usd_amt
        
        # Balance based on payment type
        payment_type = payment.get("payment_type", "outstanding")
        if payment_type == "laybye":
            receipt.balanceDue = float(payment.get("customer_laybye") or 0.0)
        else:
            receipt.balanceDue = float(payment.get("customer_outstanding") or 0.0)

        # Populate paymentItems so PrintingService can detect the currency and rate
        receipt.paymentItems = [
            Item(
                productName=payment.get("method", "Payment"),
                productid=payment_curr,
                price=payment_native_amt,
                amount=payment_usd_amt
            )
        ]

        # Items - show splits if multiple methods used
        splits = payment.get("splits", [])
        if splits and len(splits) > 1:
            receipt.items = []
            receipt.paymentItems = [] # Clear and rebuild if splits exist
            for split in splits:
                s_curr = split.get("currency", "USD")
                s_amt = float(split.get("amount", 0))
                s_usd = float(split.get("amount_usd") or s_amt)
                s_rate = float(split.get("exchange_rate") or 1.0)
                
                # Format without rate per user request
                name_str = f"Payment ({split.get('method')}) {s_amt:,.2f} {s_curr}"
                    
                it = Item(
                    productName=name_str,
                    qty=1,
                    price=s_usd,
                    amount=s_usd
                )
                receipt.items.append(it)
                receipt.paymentItems.append(Item(
                    productName=split.get("method", "Payment"),
                    productid=s_curr,
                    price=s_amt,
                    amount=s_usd
                ))
        else:
            if payment_curr.upper() != "USD":
                name_str = f"Account Payment ({payment.get('method')}) {payment_native_amt:,.2f} {payment_curr}"
            else:
                name_str = f"Account Payment ({payment.get('method')})"
                
            receipt.items = [
                Item(
                    productName=name_str,
                    qty=1,
                    price=receipt.grandTotal,
                    amount=receipt.grandTotal
                )
            ]
        
        # Add to multiCurrencyDetails for totals section display
        if payment_curr.upper() != "USD":
             receipt.multiCurrencyDetails = [
                MultiCurrencyDetail(key=payment_curr, value=payment_native_amt)
            ]
        else:
            receipt.multiCurrencyDetails = []

        receipt.footer = co.get("footer_text", "Thank you for your payment!")

        # Set doc_type second time to be safe
        receipt.doc_type = "payment"
        
        # Use total as well for backward compatibility
        receipt.total = receipt.grandTotal
        # Sync itemlist for any consumers that prefer it
        receipt.itemlist = receipt.items

        try:
             return ps.print_receipt(receipt, printer_name=printer_name)
        except Exception as pe:
             log.error(f"Error inside ps.print_receipt: {pe}")
             return False

    except Exception as e:
        log.error(f"Printing Service Error: {e}")
        return False


def migrate_payments():
    """Manually trigger migrations (auto-migration already runs on import)."""
    auto_migrate()


def get_failed_payments() -> list[dict]:
    """Get payments that have failed sync and need attention."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT p.*, c.customer_name
        FROM customer_payments p
        LEFT JOIN customers c ON p.customer_id = c.id
        WHERE (p.synced = 0 OR p.synced IS NULL)
          AND p.sync_attempts >= 3
        ORDER BY p.last_sync_attempt DESC
    """)
    
    rows = cur.fetchall()
    if not rows:
        conn.close()
        return []
    
    columns = [col[0] for col in cur.description]
    results = []
    for row in rows:
        result = dict(zip(columns, row))
        for key, value in result.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
        results.append(result)
    
    conn.close()
    return results


def reset_failed_payment(payment_id: int):
    """Reset a failed payment so it can be retried."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE customer_payments 
        SET sync_attempts = 0,
            last_sync_attempt = NULL,
            sync_error = NULL,
            syncing = 0
        WHERE id = ? AND (synced = 0 OR synced IS NULL)
    """, (payment_id,))
    
    conn.commit()
    conn.close()
    
    log.info(f"Payment {payment_id} reset for retry")
    _trigger_payment_sync(payment_id)


def try_lock_customer_payment(payment_id: int) -> bool:
    """Atomic lock attempt: set syncing=1 ONLY if 0 and not yet synced."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE customer_payments 
            SET syncing = 1 
            WHERE id = ? AND (syncing = 0 OR syncing IS NULL) AND (synced = 0 OR synced IS NULL)
        """, (payment_id,))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        log.error(f"try_lock_customer_payment error: {e}")
        return False
    finally:
        conn.close()

def unlock_customer_payment(payment_id: int):
    """Safely release syncing lock."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE customer_payments SET syncing = 0 WHERE id = ?", (payment_id,))
        conn.commit()
    except Exception as e:
        log.error(f"unlock_customer_payment error: {e}")
    finally:
        conn.close()


def get_sync_stats() -> dict:
    """Get statistics about payment sync status."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN synced = 1 THEN 1 ELSE 0 END) as synced,
            SUM(CASE WHEN synced = 0 OR synced IS NULL THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN sync_attempts >= 3 AND (synced = 0 OR synced IS NULL) 
                THEN 1 ELSE 0 END) as failed
        FROM customer_payments
    """)
    
    row = cur.fetchone()
    conn.close()
    
    if row:
        return {
            "total": row[0] or 0,
            "synced": row[1] or 0,
            "pending": row[2] or 0,
            "failed": row[3] or 0
        }
    return {"total": 0, "synced": 0, "pending": 0, "failed": 0}
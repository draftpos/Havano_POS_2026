# models/credit_note.py - Complete working version with auto-created exchange_rate column

from __future__ import annotations

from database.db import get_connection
from datetime import date, datetime
import logging
import random
import hashlib

log = logging.getLogger("CreditNote")


# =============================================================================
# AUTO-MIGRATION - Creates missing tables and columns automatically
# =============================================================================

def _ensure_tables_and_columns():
    """Automatically create missing tables and columns - runs on every import"""
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. Create credit_notes table if not exists
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'credit_notes'
        )
        CREATE TABLE credit_notes (
            id                  INT           IDENTITY(1,1) PRIMARY KEY,
            cn_number           NVARCHAR(40)  NOT NULL DEFAULT '',
            original_sale_id    INT           NOT NULL,
            original_invoice_no NVARCHAR(40)  NOT NULL DEFAULT '',
            frappe_ref          NVARCHAR(80)  NULL,
            frappe_cn_ref       NVARCHAR(80)  NULL,
            total               DECIMAL(12,2) NOT NULL DEFAULT 0,
            currency            NVARCHAR(10)  NOT NULL DEFAULT 'USD',
            exchange_rate       DECIMAL(18,8) NULL,
            cashier_name        NVARCHAR(120) NOT NULL DEFAULT '',
            customer_name       NVARCHAR(120) NOT NULL DEFAULT '',
            cn_status           NVARCHAR(20)  NOT NULL DEFAULT 'pending_sync',
            syncing             INT           NOT NULL DEFAULT 0,
            created_at          DATETIME2     NOT NULL DEFAULT SYSDATETIME()
        )
    """)
    
    # 2. Create credit_note_items table if not exists
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'credit_note_items'
        )
        CREATE TABLE credit_note_items (
            id             INT           IDENTITY(1,1) PRIMARY KEY,
            credit_note_id INT           NOT NULL
                               REFERENCES credit_notes(id) ON DELETE CASCADE,
            part_no        NVARCHAR(50)  NOT NULL DEFAULT '',
            product_name   NVARCHAR(120) NOT NULL DEFAULT '',
            qty            DECIMAL(12,4) NOT NULL DEFAULT 0,
            price          DECIMAL(12,2) NOT NULL DEFAULT 0,
            total          DECIMAL(12,2) NOT NULL DEFAULT 0,
            tax_amount     DECIMAL(12,2) NOT NULL DEFAULT 0,
            tax_rate       DECIMAL(8,4)  NOT NULL DEFAULT 0,
            tax_type       NVARCHAR(20)  NOT NULL DEFAULT '',
            reason         NVARCHAR(255) NOT NULL DEFAULT 'Customer Return'
        )
    """)
    
    # 3. Add missing columns to credit_note_items
    tax_columns = [
        ("tax_amount", "DECIMAL(12,2) NOT NULL DEFAULT 0"),
        ("tax_rate", "DECIMAL(8,4) NOT NULL DEFAULT 0"),
        ("tax_type", "NVARCHAR(20) NOT NULL DEFAULT ''"),
    ]
    
    for col_name, col_def in tax_columns:
        try:
            cur.execute(f"""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'credit_note_items' AND COLUMN_NAME = '{col_name}'
                )
                ALTER TABLE credit_note_items ADD {col_name} {col_def}
            """)
        except Exception as e:
            log.warning(f"Could not add column {col_name} to credit_note_items: {e}")
    
    # 4. Add fiscal columns to credit_notes
    fiscal_columns = [
        ("fiscal_status", "NVARCHAR(20) NOT NULL DEFAULT 'pending'"),
        ("fiscal_qr_code", "NVARCHAR(500) NULL"),
        ("fiscal_verification_code", "NVARCHAR(100) NULL"),
        ("fiscal_receipt_counter", "INT NULL"),
        ("fiscal_global_no", "NVARCHAR(50) NULL"),
        ("fiscal_sync_date", "DATETIME2 NULL"),
        ("fiscal_error", "NVARCHAR(MAX) NULL"),
        ("sync_error", "NVARCHAR(MAX) NULL"),
    ]
    
    for col_name, col_def in fiscal_columns:
        try:
            cur.execute(f"""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'credit_notes' AND COLUMN_NAME = '{col_name}'
                )
                ALTER TABLE credit_notes ADD {col_name} {col_def}
            """)
        except Exception as e:
            log.warning(f"Could not add column {col_name} to credit_notes: {e}")
    
    # 5. Add exchange_rate column to credit_notes if not exists (CRITICAL FOR FIX)
    try:
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'credit_notes' AND COLUMN_NAME = 'exchange_rate'
            )
            ALTER TABLE credit_notes ADD exchange_rate DECIMAL(18,8) NULL
        """)
        log.info("exchange_rate column verified/added to credit_notes table")
    except Exception as e:
        log.warning(f"Could not add exchange_rate column: {e}")
    
    # 6. Add conversion_rate column to sales table if not exists
    try:
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'sales' AND COLUMN_NAME = 'conversion_rate'
            )
            ALTER TABLE sales ADD conversion_rate DECIMAL(18,8) NULL
        """)
        log.info("conversion_rate column verified/added to sales table")
    except Exception as e:
        log.warning(f"Could not add conversion_rate column to sales: {e}")
    
    conn.commit()
    conn.close()
    log.info("Credit notes tables and columns verified/created")

    # Double check for syncing column separately (robust)
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'credit_notes' AND COLUMN_NAME = 'syncing'
            )
            ALTER TABLE credit_notes ADD syncing INT NOT NULL DEFAULT 0
        """)
        conn.commit(); conn.close()
    except Exception:
        pass


# Call auto-migration when module loads
_ensure_tables_and_columns()


# =============================================================================
# CN NUMBER GENERATION
# =============================================================================

def _next_cn_number() -> str:
    """Generate a unique credit note number"""
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now()
    
    # RMA format with timestamp
    date_part = now.strftime("%Y%m%d")
    time_part = now.strftime("%H%M%S")
    random_suffix = random.randint(1000, 9999)
    rma_number = f"RMA-{date_part}-{time_part}-{random_suffix}"
    
    cur.execute("SELECT COUNT(*) FROM credit_notes WHERE cn_number = ?", (rma_number,))
    if cur.fetchone()[0] == 0:
        conn.close()
        return rma_number
    
    # Fallback
    micro_cn = f"RTN-{now.strftime('%Y%m%d%H%M%S%f')}"
    conn.close()
    return micro_cn


# =============================================================================
# CREATE CREDIT NOTE - WITH EXCHANGE RATE FROM ORIGINAL SALE
# =============================================================================

def create_credit_note(
    original_sale_id: int,
    items_to_return: list[dict],
    currency: str = "USD",
    customer_name: str = "",
    cashier_name: str = "",
) -> dict:
    """
    Create a credit note by copying EXACT values from the original sale.
    Uses SAME currency and SAME exchange rate as original sale.
    """
    from models.product import adjust_stock

    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # 1. Get original sale details INCLUDING exchange_rate
        # Check if exchange_rate column exists in sales table
        has_exch_rate = False
        try:
            cur.execute("""
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'sales' AND COLUMN_NAME = 'exchange_rate'
            """)
            has_exch_rate = cur.fetchone() is not None
        except Exception:
            pass
        
        if has_exch_rate:
            cur.execute("""
                SELECT invoice_no, frappe_ref, currency, customer_name, total, exchange_rate
                FROM sales 
                WHERE id = ?
            """, (original_sale_id,))
        else:
            cur.execute("""
                SELECT invoice_no, frappe_ref, currency, customer_name, total
                FROM sales 
                WHERE id = ?
            """, (original_sale_id,))
            original_exchange_rate = None
        
        sale_row = cur.fetchone()
        if not sale_row:
            raise Exception(f"Original sale {original_sale_id} not found")
        
        original_invoice_no = sale_row[0]
        frappe_ref = sale_row[1]
        original_currency = sale_row[2] or "USD"
        original_customer = sale_row[3] or ""
        
        # Get exchange_rate if available
        original_exchange_rate = None
        if has_exch_rate and len(sale_row) > 5:
            original_exchange_rate = sale_row[5]
        
        # CRITICAL: Use original sale's currency and exchange rate - NO CONVERSION
        final_currency = original_currency
        final_customer_name = customer_name or original_customer or "Walk-in Customer"
        
        # Store the original exchange_rate (USD per local) for later use
        stored_rate = None
        if original_exchange_rate and float(original_exchange_rate) > 0:
            stored_rate = float(original_exchange_rate)
            log.info(f"Original sale exchange_rate: {stored_rate} (USD per {final_currency})")
        else:
            log.info(f"No exchange rate stored for original sale {original_sale_id}, will be resolved from Frappe if needed")
        
        # 2. Get original sale items with their EXACT values
        credit_items = []
        total_credit_amount = 0
        
        for return_item in items_to_return:
            part_no = return_item.get("part_no", "")
            return_qty = float(return_item.get("qty", 0))
            
            if not part_no:
                continue
            
            # Get the original sale item with ALL values
            cur.execute("""
                SELECT TOP 1 
                    part_no, product_name, price, tax_amount, tax_rate, tax_type, total, qty
                FROM sale_items 
                WHERE sale_id = ? AND part_no = ?
                ORDER BY id DESC
            """, (original_sale_id, part_no))
            
            orig_item = cur.fetchone()
            if not orig_item:
                continue
            
            orig_part_no = orig_item[0] or ""
            product_name = orig_item[1] or ""
            price = float(orig_item[2] or 0)
            tax_amount = float(orig_item[3] or 0)
            tax_rate = float(orig_item[4] or 0)
            tax_type = orig_item[5] or ""
            original_total = float(orig_item[6] or 0)
            original_qty = float(orig_item[7] or 1)
            
            # Calculate proportional values
            if original_qty > 0 and return_qty <= original_qty:
                item_total = price * return_qty
                item_tax = (tax_amount / original_qty) * return_qty if tax_amount > 0 else 0
            else:
                item_total = price * return_qty
                item_tax = tax_amount if tax_amount > 0 else 0
            
            credit_items.append({
                "part_no": orig_part_no,
                "product_name": product_name,
                "qty": return_qty,
                "price": price,
                "total": item_total,
                "tax_amount": item_tax,
                "tax_rate": tax_rate,
                "tax_type": tax_type,
                "reason": return_item.get("reason", "Customer Return"),
            })
            
            total_credit_amount += item_total
            
            # Adjust stock
            try:
                cur.execute("SELECT id FROM products WHERE part_no = ?", (orig_part_no,))
                prod_row = cur.fetchone()
                if prod_row:
                    adjust_stock(prod_row[0], return_qty)
            except Exception as e:
                print(f"Stock adjustment failed: {e}")
        
        if not credit_items:
            raise Exception("No valid items to return")
        
        # 3. Generate unique credit note number
        cn_number = f"RMA-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"
        cn_status = "ready" if frappe_ref else "pending_sync"
        
        # 4. Insert credit note header (use SAME currency and exchange rate as original sale)
        # Check if exchange_rate column exists in credit_notes
        has_exchange_rate = False
        try:
            cur.execute("""
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'credit_notes' AND COLUMN_NAME = 'exchange_rate'
            """)
            has_exchange_rate = cur.fetchone() is not None
        except Exception:
            pass
        
        if has_exchange_rate:
            cur.execute("""
                INSERT INTO credit_notes
                    (cn_number, original_sale_id, original_invoice_no,
                     frappe_ref, total, currency, exchange_rate, cashier_name, customer_name,
                     cn_status, fiscal_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                cn_number, original_sale_id, original_invoice_no,
                frappe_ref, total_credit_amount, final_currency, stored_rate, cashier_name, final_customer_name,
                cn_status
            ))
        else:
            cur.execute("""
                INSERT INTO credit_notes
                    (cn_number, original_sale_id, original_invoice_no,
                     frappe_ref, total, currency, cashier_name, customer_name,
                     cn_status, fiscal_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                cn_number, original_sale_id, original_invoice_no,
                frappe_ref, total_credit_amount, final_currency, cashier_name, final_customer_name,
                cn_status
            ))
        
        # 5. Get the inserted ID
        cur.execute("SELECT CAST(SCOPE_IDENTITY() AS INT)")
        row = cur.fetchone()
        if row and row[0] is not None:
            cn_id = int(row[0])
        else:
            cur.execute("SELECT id FROM credit_notes WHERE cn_number = ?", (cn_number,))
            row2 = cur.fetchone()
            if row2 and row2[0] is not None:
                cn_id = int(row2[0])
            else:
                raise Exception("Failed to get credit note ID")
        
        # 5b. Insert credit note items (CRITICAL FIX: Was missing entirely)
        for item in credit_items:
            cur.execute("""
                INSERT INTO credit_note_items (
                    credit_note_id, part_no, product_name, qty, price,
                    total, tax_amount, tax_rate, tax_type, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cn_id,
                item["part_no"],
                item["product_name"],
                item["qty"],
                item["price"],
                item["total"],
                item["tax_amount"],
                item["tax_rate"],
                item["tax_type"],
                item["reason"]
            ))
        
        conn.commit()
        
        # 6. Build result
        cn_result = {
            "id": cn_id,
            "cn_number": cn_number,
            "original_sale_id": original_sale_id,
            "original_invoice_no": original_invoice_no,
            "frappe_ref": frappe_ref or "",
            "total": total_credit_amount,
            "currency": final_currency,
            "exchange_rate": stored_rate,
            "cashier_name": cashier_name,
            "customer_name": final_customer_name,
            "cn_status": cn_status,
            "fiscal_status": "pending",
            "items_to_return": credit_items,
        }
        
        print(f"✅ Created credit note: {cn_number}")
        print(f"   Original sale currency: {original_currency}")
        print(f"   Credit note currency: {final_currency}")
        print(f"   Exchange rate (stored): {stored_rate}")
        print(f"   Total: {total_credit_amount:.2f}")
        
        # 7. Fire fiscalization in background
        try:
            from services.fiscalization_service import get_fiscalization_service
            get_fiscalization_service().trigger_credit_note_fiscalization_background(cn_id)
        except Exception as fe:
            print(f"Fiscalization trigger failed: {fe}")
        
        return cn_result
        
    except Exception as e:
        conn.rollback()
        print(f"Failed to create credit note: {e}")
        import traceback
        traceback.print_exc()
        raise e
    finally:
        conn.close()


# =============================================================================
# READ FUNCTIONS
# =============================================================================

def get_credit_note_by_id(cn_id: int) -> dict | None:
    """Fetch a single credit note by id."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Check if exchange_rate column exists before selecting
    has_exchange_rate = False
    try:
        cur.execute("""
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'credit_notes' AND COLUMN_NAME = 'exchange_rate'
        """)
        has_exchange_rate = cur.fetchone() is not None
    except Exception:
        pass
    
    if has_exchange_rate:
        cur.execute("""
            SELECT id, cn_number, original_sale_id, original_invoice_no,
                   frappe_ref, frappe_cn_ref, total, currency, exchange_rate, cashier_name,
                   customer_name, cn_status, created_at,
                   fiscal_status, fiscal_qr_code, fiscal_verification_code,
                   fiscal_receipt_counter, fiscal_global_no, fiscal_sync_date,
                   fiscal_error
            FROM credit_notes
            WHERE id = ?
        """, (cn_id,))
    else:
        cur.execute("""
            SELECT id, cn_number, original_sale_id, original_invoice_no,
                   frappe_ref, frappe_cn_ref, total, currency, cashier_name,
                   customer_name, cn_status, created_at,
                   fiscal_status, fiscal_qr_code, fiscal_verification_code,
                   fiscal_receipt_counter, fiscal_global_no, fiscal_sync_date,
                   fiscal_error
            FROM credit_notes
            WHERE id = ?
        """, (cn_id,))
    
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    
    cols = [d[0] for d in cur.description]
    cn = dict(zip(cols, row))
    
    # Add exchange_rate if missing
    if "exchange_rate" not in cn:
        cn["exchange_rate"] = None
    
    # Get items
    cur.execute("""
        SELECT part_no, product_name, qty, price, total, 
               tax_amount, tax_rate, tax_type, reason
        FROM credit_note_items 
        WHERE credit_note_id = ?
    """, (cn_id,))
    
    item_cols = [d[0] for d in cur.description]
    cn["items_to_return"] = [dict(zip(item_cols, r)) for r in cur.fetchall()]
    
    conn.close()
    return cn


def get_credit_notes_by_sale(sale_id: int) -> list[dict]:
    """Fetch all credit notes for a specific sale."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Check if exchange_rate column exists
    has_exchange_rate = False
    try:
        cur.execute("""
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'credit_notes' AND COLUMN_NAME = 'exchange_rate'
        """)
        has_exchange_rate = cur.fetchone() is not None
    except Exception:
        pass
    
    if has_exchange_rate:
        cur.execute("""
            SELECT id, cn_number, total, currency, exchange_rate, cn_status, created_at,
                   fiscal_status, fiscal_global_no
            FROM credit_notes
            WHERE original_sale_id = ?
            ORDER BY created_at DESC
        """, (sale_id,))
    else:
        cur.execute("""
            SELECT id, cn_number, total, currency, cn_status, created_at,
                   fiscal_status, fiscal_global_no
            FROM credit_notes
            WHERE original_sale_id = ?
            ORDER BY created_at DESC
        """, (sale_id,))
    
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    
    # Add exchange_rate if missing
    for row in rows:
        if "exchange_rate" not in row:
            row["exchange_rate"] = None
    
    conn.close()
    return rows


def get_pending_credit_notes() -> list[dict]:
    """Return all CNs that are ready to sync."""
    conn = get_connection()
    cur = conn.cursor()

    # Update pending credit notes with frappe_ref from sales
    cur.execute("""
        UPDATE cn
        SET cn.cn_status = 'ready',
            cn.frappe_ref = s.frappe_ref
        FROM credit_notes cn
        INNER JOIN sales s ON s.id = cn.original_sale_id
        WHERE cn.cn_status = 'pending_sync'
          AND s.frappe_ref IS NOT NULL
          AND s.frappe_ref != ''
    """)
    
    if cur.rowcount > 0:
        conn.commit()

    # Check if exchange_rate column exists
    has_exchange_rate = False
    try:
        cur.execute("""
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'credit_notes' AND COLUMN_NAME = 'exchange_rate'
        """)
        has_exchange_rate = cur.fetchone() is not None
    except Exception:
        pass
    
    if has_exchange_rate:
        cur.execute("""
            SELECT id, cn_number, original_sale_id, original_invoice_no,
                   frappe_ref, total, currency, exchange_rate, customer_name, cn_status
            FROM credit_notes
            WHERE cn_status = 'ready'
            ORDER BY created_at
        """)
    else:
        cur.execute("""
            SELECT id, cn_number, original_sale_id, original_invoice_no,
                   frappe_ref, total, currency, customer_name, cn_status
            FROM credit_notes
            WHERE cn_status = 'ready'
            ORDER BY created_at
        """)
    
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    
    # Add exchange_rate if missing
    for row in rows:
        if "exchange_rate" not in row:
            row["exchange_rate"] = None
    
    conn.close()
    return rows


def mark_cn_synced(cn_id: int, frappe_cn_ref: str = "") -> None:
    """Mark credit note as synced to Frappe."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE credit_notes SET cn_status = 'synced', frappe_cn_ref = ? WHERE id = ?",
        (frappe_cn_ref or None, cn_id)
    )
    conn.commit()
    conn.close()
    log.info(f"Credit note {cn_id} marked as synced")

# =============================================================================
# Locking helpers (Atomic protection)
# =============================================================================

def try_lock_cn(cn_id: int) -> bool:
    """Atomic lock attempt like sales/pos_upload"""
    try:
        from database.db import get_connection
        conn = get_connection(); cur = conn.cursor()
        cur.execute("""
            UPDATE credit_notes 
            SET syncing = 1 
            WHERE id = ? AND (syncing = 0 OR syncing IS NULL)
        """, (cn_id,))
        conn.commit()
        rc = cur.rowcount
        conn.close()
        return rc > 0
    except Exception as e:
        log.error(f"try_lock_cn failed for {cn_id}: {e}")
        return False

def unlock_cn(cn_id: int):
    """Release atomic lock"""
    try:
        from database.db import get_connection
        conn = get_connection(); cur = conn.cursor()
        cur.execute("UPDATE credit_notes SET syncing = 0 WHERE id = ?", (cn_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"unlock_cn failed for {cn_id}: {e}")

def clear_stale_cn_locks() -> int:
    """Reset all syncing flags on startup or recovery"""
    try:
        from database.db import get_connection
        conn = get_connection(); cur = conn.cursor()
        cur.execute("UPDATE credit_notes SET syncing = 0 WHERE syncing = 1")
        conn.commit()
        rc = cur.rowcount
        conn.close()
        return rc
    except Exception as e:
        log.error(f"clear_stale_cn_locks failed: {e}")
        return 0
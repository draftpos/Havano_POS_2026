# models/stock_entry.py
import logging
from database.db import get_connection

log = logging.getLogger("StockEntry")

def create_stock_entry(warehouse_id: int, price_list_id: int, items: list, supplier: str = None,
                       doc_no: str = None, date_time: str = None, balance: float = 0.0,
                       is_paid: bool = False, address: str = None, supplier_invoice_no: str = None,
                       reference: str = None, is_return: bool = False, source_doc_no: str = None) -> bool:
    """
    Creates a stock entry (Purchase Invoice or Return) locally.
    items: list of dicts with {"product_id", "qty", "cost", "selling", "batch_no", "expiry_date"}
    """
    conn = get_connection()
    cur  = conn.cursor()
    try:
        # 1. Create Stock Entry header
        cur.execute("""
            INSERT INTO stock_entries (warehouse_id, price_list_id, supplier, date, synced,
                                      doc_no, date_time, balance, is_paid, address,
                                      supplier_invoice_no, reference, source_doc_no)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, SYSDATETIME(), 0, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (warehouse_id, price_list_id, supplier, doc_no, date_time, balance, 1 if is_paid else 0, address, supplier_invoice_no, reference, source_doc_no))
        entry_id = int(cur.fetchone()[0])

        # 1b. Update supplier's balance in suppliers table
        if supplier:
            sup_bal_adj = -balance if is_return else balance
            cur.execute("""
                UPDATE suppliers 
                SET balance = ISNULL(balance, 0.0) + ? 
                WHERE UPPER(TRIM(name)) = UPPER(TRIM(?))
            """, (sup_bal_adj, supplier))

        for item in items:
            p_id = item.get("product_id")
            qty  = float(item.get("qty") or 0)
            cost = float(item.get("cost") or 0)
            selling = float(item.get("selling") or item.get("selling_price") or 0)

            if not p_id: continue

            batch_no = item.get("batch_no")
            expiry = item.get("expiry_date")

            # 2. Add to stock_entry_items
            cur.execute("""
                INSERT INTO stock_entry_items (parent_id, product_id, qty, cost_price, selling_price, batch_no, expiry_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (entry_id, p_id, qty, cost, selling, batch_no, expiry))

            # 2b. If it's a purchase (not a return) and we have a batch_no, update product_batches locally
            if not is_return and batch_no:
                cur.execute("""
                    IF EXISTS (SELECT 1 FROM product_batches WHERE product_id = ? AND batch_no = ?)
                    BEGIN
                        UPDATE product_batches 
                        SET qty = ISNULL(qty, 0) + ?, expiry_date = ISNULL(?, expiry_date), synced = 0 
                        WHERE product_id = ? AND batch_no = ?
                    END
                    ELSE
                    BEGIN
                        INSERT INTO product_batches (product_id, batch_no, expiry_date, qty, synced)
                        VALUES (?, ?, ?, ?, 0)
                    END
                """, (p_id, batch_no, qty, expiry, p_id, batch_no, p_id, batch_no, expiry, qty))

            # 3. Update product stock level and cost_price
            # If return, subtract qty and do NOT overwrite cost_price with return cost
            stock_adj = -qty if is_return else qty
            if is_return:
                cur.execute("""
                    UPDATE products SET stock = ISNULL(stock, 0) + ? WHERE id = ?
                """, (stock_adj, p_id))
            else:
                cur.execute("""
                    UPDATE products SET stock = ISNULL(stock, 0) + ?, cost_price = ? WHERE id = ?
                """, (stock_adj, cost, p_id))

            # 4. Update item_prices for the selected price list
            part_no = item.get("part_no")
            if part_no:
                # We need the price list NAME for the item_prices table
                cur.execute("SELECT name FROM price_lists WHERE id = ?", (price_list_id,))
                pl_row = cur.fetchone()
                pl_name = pl_row[0] if pl_row else None
                
                if pl_name:
                    part_no = part_no.strip().upper()
                    cur.execute("""
                        IF EXISTS (SELECT 1 FROM item_prices WHERE part_no = ? AND price_list = ?)
                        BEGIN
                            UPDATE item_prices SET price = ?, updated_at = SYSDATETIME() 
                            WHERE part_no = ? AND price_list = ?
                        END
                        ELSE
                        BEGIN
                            INSERT INTO item_prices (part_no, price_list, price, uom, price_type)
                            VALUES (?, ?, ?, 'nos', 'selling')
                        END
                    """, (part_no, pl_name, selling, part_no, pl_name,
                          part_no, pl_name, selling))

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def migrate():
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. stock_entries header
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='stock_entries')
        CREATE TABLE stock_entries (
            id INT IDENTITY(1,1) PRIMARY KEY,
            warehouse_id INT,
            price_list_id INT,
            supplier NVARCHAR(200),
            date DATETIME2 DEFAULT SYSDATETIME(),
            synced BIT DEFAULT 0
        )
        ELSE
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='stock_entries' AND COLUMN_NAME='supplier')
            ALTER TABLE stock_entries ADD supplier NVARCHAR(200);
        END
    """)
    
    # Add new fields if they don't exist
    cols = [
        ("doc_no", "NVARCHAR(100)"),
        ("date_time", "DATETIME2"),
        ("balance", "DECIMAL(18,4)"),
        ("is_paid", "BIT DEFAULT 0"),
        ("address", "NVARCHAR(500)"),
        ("supplier_invoice_no", "NVARCHAR(100)"),
        ("reference", "NVARCHAR(200)"),
        ("source_doc_no", "NVARCHAR(100)"),
        ("created_by", "NVARCHAR(100)")
    ]
    for col_name, col_type in cols:
        cur.execute(f"""
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='stock_entries' AND COLUMN_NAME='{col_name}')
            ALTER TABLE stock_entries ADD {col_name} {col_type};
        """)
    
    # 2. stock_entry_items details
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='stock_entry_items')
        CREATE TABLE stock_entry_items (
            id INT IDENTITY(1,1) PRIMARY KEY,
            parent_id INT REFERENCES stock_entries(id),
            product_id INT REFERENCES products(id),
            qty DECIMAL(18,4),
            cost_price DECIMAL(18,4),
            selling_price DECIMAL(18,4),
            batch_no NVARCHAR(100),
            expiry_date DATE
        )
        ELSE
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='stock_entry_items' AND COLUMN_NAME='batch_no')
            ALTER TABLE stock_entry_items ADD batch_no NVARCHAR(100);
            
            IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='stock_entry_items' AND COLUMN_NAME='expiry_date')
            ALTER TABLE stock_entry_items ADD expiry_date DATE;
        END
    """)
    conn.commit()
    conn.close()
    print("[StockEntry] Migration complete.")

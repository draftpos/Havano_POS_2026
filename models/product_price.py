# =============================================================================
# models/product_price.py - Auto-migrating price management
# =============================================================================

import logging
from datetime import datetime
from database.db import get_connection, fetchone_dict, fetchall_dict, execute_query

log = logging.getLogger("ProductPrice")

# =============================================================================
# AUTO MIGRATION FUNCTIONS
# =============================================================================

def ensure_price_tables_and_columns():
    """Auto-create price tables and migrate columns if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # 1. Create price_types table if not exists
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'price_types'
            )
            CREATE TABLE price_types (
                id INT IDENTITY(1,1) PRIMARY KEY,
                price_name NVARCHAR(100) NOT NULL UNIQUE,
                description NVARCHAR(255),
                is_active BIT DEFAULT 1,
                created_at DATETIME DEFAULT GETDATE()
            )
        """)
        
        # 2. Create product_prices table if not exists
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'product_prices'
            )
            CREATE TABLE product_prices (
                id INT IDENTITY(1,1) PRIMARY KEY,
                part_no NVARCHAR(50) NOT NULL,
                price_type_id INT NOT NULL,
                price DECIMAL(12,2) NOT NULL DEFAULT 0,
                uom NVARCHAR(40) NOT NULL DEFAULT 'Nos',
                is_active BIT DEFAULT 1,
                created_at DATETIME DEFAULT GETDATE(),
                updated_at DATETIME DEFAULT GETDATE()
            )
        """)
        
        # 3. Auto-migrate: Add columns to products table if they don't exist
        # This preserves existing data while adding new columns
        
        # Check and add standard_price column
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'standard_price'
            )
            ALTER TABLE products ADD standard_price DECIMAL(12,2) DEFAULT 0
        """)
        
        # Check and add airport_price column
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'airport_price'
            )
            ALTER TABLE products ADD airport_price DECIMAL(12,2) DEFAULT 0
        """)
        
        # Check and add standard_uom column
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'standard_uom'
            )
            ALTER TABLE products ADD standard_uom NVARCHAR(40) DEFAULT 'Nos'
        """)
        
        # Check and add airport_uom column
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'airport_uom'
            )
            ALTER TABLE products ADD airport_uom NVARCHAR(40) DEFAULT 'Nos'
        """)
        
        # Check and add has_airport_price column
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'has_airport_price'
            )
            ALTER TABLE products ADD has_airport_price BIT DEFAULT 0
        """)
        
        # 4. Add foreign key constraints if not exists
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
                WHERE CONSTRAINT_NAME = 'FK_product_prices_product'
            )
            ALTER TABLE product_prices ADD CONSTRAINT FK_product_prices_product 
            FOREIGN KEY (part_no) REFERENCES products(part_no) ON DELETE CASCADE
        """)
        
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
                WHERE CONSTRAINT_NAME = 'FK_product_prices_price_type'
            )
            ALTER TABLE product_prices ADD CONSTRAINT FK_product_prices_price_type 
            FOREIGN KEY (price_type_id) REFERENCES price_types(id)
        """)
        
        # 5. Add unique constraint if not exists
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
                WHERE CONSTRAINT_NAME = 'UQ_product_part_no_price_type'
            )
            ALTER TABLE product_prices ADD CONSTRAINT UQ_product_part_no_price_type 
            UNIQUE (part_no, price_type_id)
        """)
        
        # 6. Insert default price types if not exists
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM price_types WHERE price_name = 'Standard Selling')
            INSERT INTO price_types (price_name, description, is_active) VALUES 
            ('Standard Selling', 'Standard selling price for regular locations', 1)
        """)
        
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM price_types WHERE price_name = 'Airport')
            INSERT INTO price_types (price_name, description, is_active) VALUES 
            ('Airport', 'Airport location pricing', 1)
        """)
        
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM price_types WHERE price_name = 'Promotional')
            INSERT INTO price_types (price_name, description, is_active) VALUES 
            ('Promotional', 'Promotional/special pricing', 1)
        """)
        
        conn.commit()
        log.info("✅ Price tables and columns auto-migrated successfully")
        
    except Exception as e:
        log.error(f"Failed to auto-migrate price tables: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


# =============================================================================
# PRICE MANAGEMENT FUNCTIONS
# =============================================================================

def get_price_type_id(price_name: str) -> int:
    """Get price type ID by name, auto-create if not exists."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM price_types WHERE price_name = ?", (price_name,))
        result = fetchone_dict(cur)
        if result:
            return result['id']
        
        # Auto-create new price type if not exists
        cur.execute("""
            INSERT INTO price_types (price_name, description, is_active, created_at)
            VALUES (?, ?, 1, ?)
        """, (price_name, f'Auto-created: {price_name}', datetime.now()))
        conn.commit()
        
        cur.execute("SELECT SCOPE_IDENTITY() as id")
        new_id = fetchone_dict(cur)['id']
        log.info(f"Auto-created price type: {price_name} (ID: {new_id})")
        return new_id
    finally:
        conn.close()


def upsert_product_price(part_no: str, price_name: str, price: float, uom: str = 'Nos') -> bool:
    """Insert or update a product price. Returns True if successful."""
    if price <= 0:
        return False
    
    try:
        price_type_id = get_price_type_id(price_name)
        conn = get_connection()
        cur = conn.cursor()
        now = datetime.now()
        
        # Also update the denormalized columns in products table for quick access
        if price_name == 'Standard Selling':
            cur.execute("""
                UPDATE products 
                SET standard_price = ?, standard_uom = ?
                WHERE part_no = ?
            """, (price, uom, part_no))
        elif price_name == 'Airport':
            cur.execute("""
                UPDATE products 
                SET airport_price = ?, airport_uom = ?, has_airport_price = 1
                WHERE part_no = ?
            """, (price, uom, part_no))
        
        # Upsert into product_prices table
        cur.execute("""
            IF EXISTS (SELECT 1 FROM product_prices WHERE part_no = ? AND price_type_id = ?)
                UPDATE product_prices 
                SET price = ?, uom = ?, updated_at = ?, is_active = 1
                WHERE part_no = ? AND price_type_id = ?
            ELSE
                INSERT INTO product_prices (part_no, price_type_id, price, uom, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
        """, (part_no, price_type_id, price, uom, now, part_no, price_type_id,
              part_no, price_type_id, price, uom, now, now))
        
        conn.commit()
        return True
    except Exception as e:
        log.error(f"Failed to upsert price for {part_no} - {price_name}: {e}")
        return False
    finally:
        conn.close()


def sync_all_product_prices_from_api(part_no: str, prices_data: list) -> dict:
    """
    Sync all prices for a product from API data.
    Returns dict with sync statistics.
    """
    result = {
        'synced': 0,
        'failed': 0,
        'price_types': []
    }
    
    if not prices_data:
        return result
    
    for price_item in prices_data:
        # Only sync selling prices
        if str(price_item.get("type", "")).lower() != "selling":
            continue
        
        price_name = price_item.get("priceName", "").strip()
        price = float(price_item.get("price", 0))
        uom = price_item.get("uom", "Nos")
        
        if price_name and price > 0:
            if upsert_product_price(part_no, price_name, price, uom):
                result['synced'] += 1
                result['price_types'].append(price_name)
            else:
                result['failed'] += 1
    
    return result


def get_product_prices(part_no: str) -> list:
    """Get all prices for a product."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                pt.id as price_type_id,
                pt.price_name, 
                pp.price, 
                pp.uom, 
                pp.is_active,
                pp.updated_at
            FROM product_prices pp
            JOIN price_types pt ON pp.price_type_id = pt.id
            WHERE pp.part_no = ? AND pp.is_active = 1
            ORDER BY pt.price_name
        """, (part_no,))
        return fetchall_dict(cur)
    finally:
        conn.close()


def get_product_price_by_type(part_no: str, price_name: str) -> dict:
    """Get specific price type for a product."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                pt.price_name, 
                pp.price, 
                pp.uom,
                pp.updated_at
            FROM product_prices pp
            JOIN price_types pt ON pp.price_type_id = pt.id
            WHERE pp.part_no = ? AND pt.price_name = ? AND pp.is_active = 1
        """, (part_no, price_name))
        result = fetchone_dict(cur)
        return result or {}
    finally:
        conn.close()


def get_all_product_prices_with_details() -> list:
    """Get all product prices with product details."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                p.part_no,
                p.name as product_name,
                p.category,
                pt.price_name as price_type,
                pp.price,
                pp.uom,
                pp.is_active,
                pp.created_at,
                pp.updated_at
            FROM products p
            INNER JOIN product_prices pp ON p.part_no = pp.part_no
            INNER JOIN price_types pt ON pp.price_type_id = pt.id
            WHERE pp.is_active = 1
            ORDER BY p.part_no, pt.price_name
        """)
        return fetchall_dict(cur)
    finally:
        conn.close()


def get_products_by_price_type(price_name: str, min_price: float = 0, max_price: float = None) -> list:
    """Get all products that have a specific price type within price range."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        query = """
            SELECT 
                p.part_no,
                p.name as product_name,
                p.category,
                pp.price,
                pp.uom
            FROM products p
            INNER JOIN product_prices pp ON p.part_no = pp.part_no
            INNER JOIN price_types pt ON pp.price_type_id = pt.id
            WHERE pt.price_name = ? AND pp.is_active = 1 AND pp.price >= ?
        """
        params = [price_name, min_price]
        
        if max_price is not None:
            query += " AND pp.price <= ?"
            params.append(max_price)
        
        query += " ORDER BY pp.price"
        
        cur.execute(query, params)
        return fetchall_dict(cur)
    finally:
        conn.close()


def get_price_summary_by_product(part_no: str) -> dict:
    """Get comprehensive price summary for a product."""
    prices = get_product_prices(part_no)
    
    summary = {
        'part_no': part_no,
        'total_price_types': len(prices),
        'prices': {}
    }
    
    for price in prices:
        summary['prices'][price['price_name']] = {
            'amount': float(price['price']),
            'uom': price['uom'],
            'last_updated': str(price['updated_at']) if price['updated_at'] else None
        }
    
    return summary


def deactivate_product_price(part_no: str, price_name: str) -> bool:
    """Deactivate a specific price for a product."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE pp
            SET pp.is_active = 0, pp.updated_at = ?
            FROM product_prices pp
            JOIN price_types pt ON pp.price_type_id = pt.id
            WHERE pp.part_no = ? AND pt.price_name = ?
        """, (datetime.now(), part_no, price_name))
        conn.commit()
        
        # If deactivating airport price, update products table flag
        if price_name == 'Airport':
            has_other_airport = check_product_has_active_price(part_no, 'Airport')
            if not has_other_airport:
                cur.execute("""
                    UPDATE products 
                    SET has_airport_price = 0
                    WHERE part_no = ?
                """, (part_no,))
                conn.commit()
        
        return cur.rowcount > 0
    except Exception as e:
        log.error(f"Failed to deactivate price for {part_no} - {price_name}: {e}")
        return False
    finally:
        conn.close()


def check_product_has_active_price(part_no: str, price_name: str) -> bool:
    """Check if a product has an active price of a specific type."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 1
            FROM product_prices pp
            JOIN price_types pt ON pp.price_type_id = pt.id
            WHERE pp.part_no = ? AND pt.price_name = ? AND pp.is_active = 1
        """, (part_no, price_name))
        return fetchone_dict(cur) is not None
    finally:
        conn.close()


def migrate_existing_product_prices():
    """Migrate existing prices from products table to product_prices table."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Check if products table has price column and migrate it
        cur.execute("""
            SELECT part_no, price, uom 
            FROM products 
            WHERE price IS NOT NULL AND price > 0
        """)
        products = fetchall_dict(cur)
        
        migrated = 0
        for product in products:
            part_no = product['part_no']
            price = float(product['price'])
            uom = product.get('uom', 'Nos')
            
            if upsert_product_price(part_no, 'Standard Selling', price, uom):
                migrated += 1
        
        log.info(f"✅ Migrated {migrated} existing product prices to price tables")
        return migrated
    except Exception as e:
        log.error(f"Failed to migrate existing prices: {e}")
        return 0
    finally:
        conn.close()


# =============================================================================
# INITIALIZATION - Call this when app starts
# =============================================================================

def init_price_system():
    """Initialize the entire price system - call on app startup."""
    ensure_price_tables_and_columns()
    migrate_existing_product_prices()
    log.info("✅ Price system initialized successfully")
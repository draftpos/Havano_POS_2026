# =============================================================================
# models/uom.py - Unit of Measure management
# =============================================================================

from database.db import get_connection, fetchall_dicts, fetchone_dict


def get_all_uoms():
    """Get all units of measure"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, abbreviation, category, conversion FROM uom ORDER BY name")
    rows = fetchall_dicts(cur)
    conn.close()
    return rows


def create_uom(name, abbreviation, category, conversion):
    """Create a new unit of measure"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO uom (name, abbreviation, category, conversion)
            VALUES (?, ?, ?, ?)
        """, (name, abbreviation, category, conversion))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error creating UOM: {e}")
        return False
    finally:
        conn.close()


def update_uom(uom_id, name, abbreviation, category, conversion):
    """Update a unit of measure"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE uom
            SET name = ?, abbreviation = ?, category = ?, conversion = ?
            WHERE id = ?
        """, (name, abbreviation, category, conversion, uom_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        print(f"Error updating UOM: {e}")
        return False
    finally:
        conn.close()


def delete_uom(uom_id):
    """Delete a unit of measure"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM uom WHERE id = ?", (uom_id,))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        print(f"Error deleting UOM: {e}")
        return False
    finally:
        conn.close()


def migrate():
    """Create uom table"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'uom'
        )
        CREATE TABLE uom (
            id            INT           IDENTITY(1,1) PRIMARY KEY,
            name          NVARCHAR(50)  NOT NULL UNIQUE,
            abbreviation  NVARCHAR(10)  NOT NULL,
            category      NVARCHAR(30)  NOT NULL DEFAULT 'Count',
            conversion    DECIMAL(12,4) NOT NULL DEFAULT 1.0,
            created_at    DATETIME2     NOT NULL DEFAULT SYSDATETIME()
        )
    """)
    
    # Add uom columns to products if not exists
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'uom'
        )
        ALTER TABLE products ADD uom NVARCHAR(50) NOT NULL DEFAULT 'Unit'
    """)
    
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'conversion_factor'
        )
        ALTER TABLE products ADD conversion_factor DECIMAL(12,4) NOT NULL DEFAULT 1.0
    """)
    
    conn.commit()
    conn.close()
    print("[uom] ✅ Tables ready.")
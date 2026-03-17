from database.db import get_connection

def update_product_table():
    print("Connecting to database to update 'products' table...")
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Add UOM column if it doesn't exist
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'uom'
            )
            ALTER TABLE products ADD uom NVARCHAR(20) DEFAULT 'Unit';
        """)
        
        # Add conversion_factor column if it doesn't exist
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'conversion_factor'
            )
            ALTER TABLE products ADD conversion_factor DECIMAL(12,4) DEFAULT 1.0000;
        """)
        
        # Optional: Update existing NULL values to defaults
        cur.execute("UPDATE products SET uom = 'Unit' WHERE uom IS NULL")
        cur.execute("UPDATE products SET conversion_factor = 1.0 WHERE conversion_factor IS NULL")
        
        conn.commit()
        print("✅ Database update successful: 'uom' and 'conversion_factor' columns added.")
        
    except Exception as e:
        print(f"❌ Error updating database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_product_table()
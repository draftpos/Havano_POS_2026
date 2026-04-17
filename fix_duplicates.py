from database.db import get_connection

def clean_duplicates_and_add_constraint():
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. Delete duplicates keeping the highest ID (newest)
    print("Deleting duplicate products...")
    cur.execute("""
        WITH CTE AS (
            SELECT id, part_no,
                   ROW_NUMBER() OVER(
                       PARTITION BY part_no 
                       ORDER BY id DESC
                   ) as rn
            FROM products
        )
        DELETE FROM CTE WHERE rn > 1;
    """)
    print(f"Deleted {cur.rowcount} duplicate products.")
    
    # 2. Add UNIQUE constraint to part_no
    print("Adding UNIQUE constraint to products.part_no...")
    try:
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM sys.indexes 
                WHERE name = 'UQ_products_part_no' 
                AND object_id = OBJECT_ID('products')
            )
            BEGIN
                ALTER TABLE products 
                ADD CONSTRAINT UQ_products_part_no UNIQUE (part_no);
            END
        """)
        print("UNIQUE constraint added successfully.")
    except Exception as e:
        print(f"Constraint might already exist or error occurred: {e}")
        
    conn.commit()
    conn.close()

if __name__ == '__main__':
    clean_duplicates_and_add_constraint()

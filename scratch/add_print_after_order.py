import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db import get_connection

conn = get_connection()
cur = conn.cursor()

cur.execute("""
    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'print_after_order'
    )
    BEGIN
        ALTER TABLE [products] ADD [print_after_order] BIT NOT NULL DEFAULT 0;
        SELECT 'ADDED' AS result;
    END
    ELSE
    BEGIN
        SELECT 'ALREADY_EXISTS' AS result;
    END
""")

res = cur.fetchone()
conn.commit()
print("Migration Result:", res[0] if res else "NO RESULT")
cur.close()
conn.close()

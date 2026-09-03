import sqlite3
import os
import re

# 1. Alter database
db_path = r'c:\Users\DELL\New_POS\Havano_POS_2026\database\havano.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE products ADD COLUMN hs_code TEXT")
        conn.commit()
        print("Added hs_code to sqlite products table")
    except Exception as e:
        print("SQLite error:", e)
    conn.close()

# Wait, the app uses SQL Server or SQLite? setup_database.py had [dbo].[products] meaning SQL Server.
# Let's check models/database.py to see how to connect to SQL server, or we can just use the app's internal get_connection.

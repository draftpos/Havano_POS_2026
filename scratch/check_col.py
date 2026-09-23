import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT COLUMN_NAME, DATA_TYPE, COLUMN_DEFAULT FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='products' AND COLUMN_NAME='print_after_order'")
row = cur.fetchone()
print("Column verified in database:", row)
cur.close()
conn.close()

import sys
sys.path.insert(0, '.')
from database.db import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='products'")
print([r[0] for r in cur.fetchall()])
conn.close()

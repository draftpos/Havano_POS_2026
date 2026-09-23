from database.db import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%exp%'")
print("Tables with exp:", cur.fetchall())
cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES")
tables = [r[0] for r in cur.fetchall()]
print("All tables:", tables)

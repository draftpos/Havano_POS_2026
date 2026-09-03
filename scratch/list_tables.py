from database.db import get_connection
conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'")
print(sorted([r[0] for r in cur.fetchall()]))
conn.close()

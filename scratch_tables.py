from database.db import get_connection
try:
    c = get_connection().cursor()
    c.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'")
    print([row[0] for row in c.fetchall()])
except Exception as e:
    print("Error:", e)

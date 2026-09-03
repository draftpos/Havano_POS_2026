from database.db import get_connection
conn = get_connection()
cur = conn.cursor()
cur.execute("UPDATE users SET pin = '7878', role = 'admin' WHERE username = 'admin'")
conn.commit()
print('INJECTED 7878!')
conn.close()

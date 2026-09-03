import pyodbc

conn_str = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=Fortune\\SQLEXPRESS;DATABASE=odoo_1256;UID=sa;PWD=admin123!;TrustServerCertificate=yes;Encrypt=no;"
try:
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()
    cur.execute("SELECT id, username, role FROM users")
    users = cur.fetchall()
    print("Users:", [(u.id, u.username, u.role) for u in users])

    # Update admin pin
    cur.execute("UPDATE users SET pin='7878' WHERE username='admin' OR role='Admin' OR username='administrator' OR username='Admin'")
    conn.commit()
    print("Successfully updated PIN to 7878")
    conn.close()
except Exception as e:
    print("Error:", e)

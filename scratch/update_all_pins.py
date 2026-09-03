import pyodbc

conn_str = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=Fortune\\SQLEXPRESS;Trusted_Connection=yes;TrustServerCertificate=yes;Encrypt=no;"

try:
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sys.databases")
    dbs = [row[0] for row in cur.fetchall()]
    
    for db in dbs:
        if db in ('master', 'tempdb', 'model', 'msdb'): continue
        try:
            cur.execute(f"USE [{db}]")
            # check if users table exists
            cur.execute("SELECT count(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'users'")
            if cur.fetchone()[0] > 0:
                cur.execute("UPDATE users SET pin='7878' WHERE username='admin' OR role='Admin' OR username='administrator' OR username='Admin'")
                conn.commit()
                print(f"Updated PIN in {db}")
        except Exception as e:
            pass
            
    conn.close()
    print("Done checking all databases.")
except Exception as e:
    print("Error:", e)

import pyodbc

conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;Trusted_Connection=yes;Database=master;",
    autocommit=True
)
cur = conn.cursor()
cur.execute("SELECT name FROM sys.databases WHERE name NOT IN ('master','tempdb','model','msdb')")
dbs = [r[0] for r in cur.fetchall()]
print("Databases on server:", dbs)

for db in dbs:
    try:
        cur.execute(f"USE [{db}]")
        cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='sales'")
        if cur.fetchone()[0] > 0:
            cur.execute("SELECT id, invoice_no, customer_name, total, tendered, method, payment_splits, payments FROM sales")
            rows = cur.fetchall()
            if rows:
                print(f"\n--- Found {len(rows)} sales in DB [{db}]:")
                for r in rows:
                    print("  Sale:", r)
                cur.execute("SELECT id, sale_id, sale_invoice_no, party_name, paid_amount, mode_of_payment, synced FROM payment_entries")
                pes = cur.fetchall()
                print(f"--- Found {len(pes)} payment_entries in DB [{db}]:")
                for pe in pes:
                    print("  PE:", pe)
    except Exception as e:
        pass

conn.close()

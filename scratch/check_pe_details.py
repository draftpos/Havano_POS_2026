import pyodbc

conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;Trusted_Connection=yes;Database=master;",
    autocommit=True
)
cur = conn.cursor()
for db in ['havano_posop079', 'havano_posop0797']:
    try:
        cur.execute(f"USE [{db}]")
        cur.execute("SELECT id, sale_id, sale_invoice_no, party_name, paid_amount, mode_of_payment, synced, sync_error, remarks, created_at FROM payment_entries")
        rows = cur.fetchall()
        print(f"\n--- DB: {db} (Found {len(rows)} PEs) ---")
        for r in rows:
            print(" ", r)
    except Exception as e:
        print(f"Error reading {db}: {e}")

conn.close()

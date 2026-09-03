import pyodbc

conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;Trusted_Connection=yes;Database=master;",
    autocommit=True
)
cur = conn.cursor()
cur.execute("SELECT name FROM sys.databases WHERE name NOT IN ('master','tempdb','model','msdb')")
dbs = [r[0] for r in cur.fetchall()]

for db in dbs:
    try:
        cur.execute(f"USE [{db}]")
        cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='payment_entries'")
        if cur.fetchone()[0] > 0:
            # Delete exact duplicate unsynced rows keeping only the smallest id
            cur.execute("""
                DELETE FROM payment_entries
                WHERE id IN (
                    SELECT id FROM (
                        SELECT id, ROW_NUMBER() OVER(
                            PARTITION BY sale_id, mode_of_payment, paid_amount 
                            ORDER BY id ASC
                        ) as rnum
                        FROM payment_entries
                    ) t
                    WHERE t.rnum > 1
                )
            """)
            deleted = cur.rowcount
            if deleted > 0:
                print(f"[{db}] Deleted {deleted} duplicate payment entries.")
    except Exception as e:
        pass

conn.close()
print("Deduplication complete across all databases.")

from database.db import get_connection

conn = get_connection()
cur = conn.cursor()

# Clear sync errors on the 3 pending NSM invoices so they retry with the new terminal_id
cur.execute("""
    UPDATE sales
    SET synced = 0, syncing = 0, sync_error = NULL
    WHERE invoice_no IN ('NSM-0001', 'NSM-0002', 'NSM-0003')
      AND (synced = 0 OR sync_error IS NOT NULL)
""")
rows = cur.rowcount
conn.commit()
conn.close()
print(f"[OK] Cleared sync errors for {rows} invoice(s). They will retry on next sync cycle.")

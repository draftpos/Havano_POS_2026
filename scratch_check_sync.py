import pyodbc

def main():
    try:
        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=.\\SQLEXPRESS;"
            "DATABASE=havano_pos_db65000778;"
            "Trusted_Connection=yes;"
        )
        cur = conn.cursor()
        print("--- SYNC STATUS REPORT ---")
        try:
            cur.execute("SELECT COUNT(*) FROM sales")
            tot = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sales WHERE synced = 1")
            syn = cur.fetchone()[0]
            print(f"Sales Invoices: {syn} synced / {tot} total")
        except Exception as e: print("Sales:", e)
        try:
            cur.execute("SELECT COUNT(*) FROM payment_entries")
            tot = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM payment_entries WHERE synced = 1")
            syn = cur.fetchone()[0]
            print(f"Payment Entries: {syn} synced / {tot} total")
        except Exception as e: print("PE:", e)
    except Exception as e:
        pass
if __name__ == "__main__": main()

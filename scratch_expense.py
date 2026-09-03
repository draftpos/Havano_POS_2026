from database.db import get_connection
conn = get_connection()
cur = conn.cursor()
try:
    cur.execute("IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='expenses' AND COLUMN_NAME='balance') ALTER TABLE expenses ADD balance DECIMAL(18,4) NULL")
    cur.execute("UPDATE expenses SET balance = amount WHERE balance IS NULL")
    conn.commit()
    print("Expense balance column added.")
except Exception as e:
    print(e)
finally:
    conn.close()

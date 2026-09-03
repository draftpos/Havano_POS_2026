from database.db import get_connection
conn = get_connection()
cursor = conn.cursor()

# Check for all tables
tables = [row[0] for row in cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME").fetchall()]
print("All tables:", tables)

# Check sales-related tables
for t in tables:
    if 'sale' in t.lower() or 'invoice' in t.lower():
        cols = [col[0] for col in cursor.execute(f"SELECT name FROM sys.columns WHERE object_id = OBJECT_ID('{t}')").fetchall()]
        print(f"\n{t}: {cols}")

conn.close()

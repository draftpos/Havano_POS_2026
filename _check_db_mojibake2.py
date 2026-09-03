import sqlite3

db_path = r'c:\Users\DELL\New_POS\Havano_POS_2026\pos_database.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]

with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\_mojibake_dump.txt', 'w', encoding='utf-8') as f:
    for t in tables:
        try:
            cur.execute(f"SELECT * FROM {t}")
            rows = cur.fetchall()
            for row in rows:
                for col in row:
                    if isinstance(col, str) and ('\u2261' in col or '\u0393' in col or 'Grays' in col):
                        f.write(f"Table {t} contains mojibake/Grays: {repr(col)}\n")
        except Exception as e:
            pass

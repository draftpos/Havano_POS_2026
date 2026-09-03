import sqlite3
import codecs

db_path = r'c:\Users\DELL\New_POS\Havano_POS_2026\pos_database.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
for t in tables:
    try:
        cur.execute(f"SELECT * FROM {t}")
        rows = cur.fetchall()
        for row in rows:
            for col in row:
                if isinstance(col, str) and ('\u2261' in col or '\u0393' in col):
                    print(f"Table {t} contains mojibake: {repr(col)[:100]}")
    except Exception as e:
        pass

try:
    s = codecs.open(r'c:\Users\DELL\New_POS\Havano_POS_2026\restaurant_settings.json', 'r', 'utf-8').read()
    if '\u2261' in s or '\u0393' in s:
        print("Settings json contains mojibake!")
        lines = s.split('\n')
        for l in lines:
            if '\u2261' in l or '\u0393' in l:
                print(l.strip())
except Exception as e:
    pass

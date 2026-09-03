import sqlite3

db_path = r'c:\Users\DELL\New_POS\Havano_POS_2026\pos_database.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
try:
    cur.execute("SELECT * FROM restaurant_predefined_notes")
    rows = cur.fetchall()
    with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\_predef_notes.txt', 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(repr(r) + '\n')
except Exception as e:
    with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\_predef_notes.txt', 'w', encoding='utf-8') as f:
        f.write(str(e))

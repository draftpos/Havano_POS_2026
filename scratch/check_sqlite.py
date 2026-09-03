import sqlite3

def check_db(name):
    print(f"Checking {name}")
    try:
        conn = sqlite3.connect(name)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(tables)
        conn.close()
    except Exception as e:
        print(e)

check_db('havano.db')
check_db('pos.db')

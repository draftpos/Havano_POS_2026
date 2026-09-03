import sqlite3

def dump():
    db = sqlite3.connect('database/pos.db')
    for row in db.execute("SELECT name, sql FROM sqlite_master WHERE type='table'"):
        print("TABLE:", row[0])
        print(row[1])
        print("---")

if __name__ == '__main__':
    dump()

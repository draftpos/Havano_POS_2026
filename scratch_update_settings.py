import sqlite3

def fix_db():
    try:
        conn = sqlite3.connect('database/pos_db.sqlite')
        c = conn.cursor()
        # Check if table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pos_settings'")
        if c.fetchone():
            c.execute("UPDATE pos_settings SET setting_value = '1' WHERE setting_key = 'allow_negative_stock'")
            conn.commit()
            print("Updated pos_db.sqlite")
        conn.close()
    except Exception as e:
        print("pos_db error:", e)

    try:
        from database.db import get_connection
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE pos_settings SET setting_value = '1' WHERE setting_key = 'allow_negative_stock'")
        conn.commit()
        conn.close()
        print("Updated main db")
    except Exception as e:
        print("main db error:", e)

if __name__ == '__main__':
    fix_db()

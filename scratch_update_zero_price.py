import re
f = 'views/main_window.py'
with open(f, 'r', encoding='utf-8') as file:
    text = file.read()

text = text.replace('"block_zero_price", default=True', '"block_zero_price", default=False')

with open(f, 'w', encoding='utf-8') as file:
    file.write(text)

import sqlite3
def fix_db():
    try:
        from database.db import get_connection
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE pos_settings SET setting_value = '0' WHERE setting_key = 'block_zero_price'")
        conn.commit()
        conn.close()
    except:
        pass
fix_db()

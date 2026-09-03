import sqlite3
import json

db_path = r'c:\Users\DELL\New_POS\Havano_POS_2026\pos_database.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
try:
    cur.execute("SELECT setting_value FROM pos_settings WHERE setting_key='restaurant_settings'")
    res = cur.fetchone()
    if res: 
        print("Settings found:")
        print(res[0])
        # Try to fix it if it contains mojibake
        val = res[0]
        if '\u2261' in val or '\u0393' in val:
            print("Found mojibake in DB! Fixing...")
            val = val.replace('\u2261\u0192\u00FB\u00E8', '🍔')
            val = val.replace('\u2261\u0192\u00F4\u00EE', '📌')
            cur.execute("UPDATE pos_settings SET setting_value=? WHERE setting_key='restaurant_settings'", (val,))
            conn.commit()
            print("Fixed in DB!")
    else:
        print("No restaurant_settings found in pos_settings table.")
except Exception as e:
    print('error:', e)

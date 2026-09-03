from database.db import get_connection

conn = get_connection()
cur = conn.cursor()
try:
    cur.execute("SELECT setting_value FROM pos_settings WHERE setting_key = 'block_zero_stock'")
    row = cur.fetchone()
    if row:
        val = int(row[0])
        new_val = "0" if val == 1 else "1"
        cur.execute("DELETE FROM pos_settings WHERE setting_key = 'block_zero_stock'")
        cur.execute("INSERT INTO pos_settings (setting_key, setting_value) VALUES ('allow_negative_stock', ?)", (new_val,))
        conn.commit()
        print("Updated DB")
    else:
        print("Not found in DB")
except Exception as e:
    print(e)
finally:
    conn.close()

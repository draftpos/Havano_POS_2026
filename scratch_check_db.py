from database.db import get_connection

def check():
    c = get_connection().cursor()
    c.execute("SELECT setting_value FROM pos_settings WHERE setting_key='allow_negative_stock'")
    row = c.fetchone()
    print('row:', row)
    if row:
        print('bool:', bool(int(row[0])))

check()

import sys
sys.path.insert(0, '.')
from database.db import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("INSERT INTO price_lists (name, selling) SELECT DISTINCT price_list, 1 FROM item_prices WHERE price_list NOT IN (SELECT name FROM price_lists) AND price_list IS NOT NULL AND price_list != ''")
conn.commit()
print(f'Added {cur.rowcount} new pricelists')
cur.execute('SELECT name FROM price_lists')
print('All Pricelists now:', [r[0] for r in cur.fetchall()])
conn.close()

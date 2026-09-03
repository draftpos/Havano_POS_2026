import sys, json
sys.path.append('c:\\Users\\DELL\\New_POS\\Havano_POS_2026')
from services.odoo.dosage_sync_service import sync_dosages_odoo
from database.db import get_connection
import logging

logging.basicConfig(level=logging.DEBUG)

print('Syncing...')
sync_dosages_odoo()

conn = get_connection()
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM dosages')
count = cur.fetchone()[0]
print(f'Total dosages in DB: {count}')
cur.execute('SELECT code, description FROM dosages')
for row in cur.fetchall():
    print(f' - {row[0]}: {row[1]}')

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("UPDATE company_defaults SET server_company_currency = 'R' WHERE id = 1")
conn.commit()
conn.close()
print("UPDATED server_company_currency TO R SUCCESSFULLY")

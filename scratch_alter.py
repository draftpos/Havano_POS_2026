import sys
sys.path.insert(0, r'c:\Users\DELL\New_POS\Havano_POS_2026')
from database.db import get_connection
c = get_connection()
try:
    c.execute("ALTER TABLE company_defaults ADD kitchen_order_start_number NVARCHAR(50) DEFAULT '0'")
    c.commit()
    print("Done")
except Exception as e:
    print(e)
c.close()

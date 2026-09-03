import sys
sys.path.append(r"c:\Users\DELL\New_POS\Havano_POS_2026")
from database.db import get_connection
c=get_connection().cursor()
c.execute("SELECT * FROM item_price WHERE item_code='52323'")
print(c.fetchall())

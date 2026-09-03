import sys
import os
import logging

sys.path.append(os.getcwd())
logging.basicConfig(level=logging.INFO)

from database.db import get_connection
from services.odoo.sync_service import sync_products_odoo
from services.credentials import get_all_credentials

if __name__ == "__main__":
    print("Testing Odoo Product UOM Sync...")
    conn = get_connection()
    cur = conn.cursor()
    
    # Check count before sync
    cur.execute("SELECT COUNT(*) FROM product_uom_prices")
    before_count = cur.fetchone()[0]
    print(f"product_uom_prices count before sync: {before_count}")
    
    # Run sync
    res = sync_products_odoo()
    print(f"Sync result: {res}")
    
    # Check count after sync
    cur.execute("SELECT COUNT(*) FROM product_uom_prices")
    after_count = cur.fetchone()[0]
    print(f"product_uom_prices count after sync: {after_count}")
    
    # Show some records
    cur.execute("SELECT TOP 20 part_no, uom, price FROM product_uom_prices")
    rows = cur.fetchall()
    print("Sample UOM prices in DB:")
    for row in rows:
        print(f"  Part No: {row[0]}, UOM: {row[1]}, Price: {row[2]}")
        
    conn.close()

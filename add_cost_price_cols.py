import sys
import os
sys.path.append(os.getcwd())
from database.db import get_connection

def main():
    conn = get_connection()
    cur = conn.cursor()
    
    # Check products table
    cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'products' AND COLUMN_NAME = 'cost_price'")
    if not cur.fetchone():
        print("Adding cost_price to products")
        cur.execute("ALTER TABLE products ADD cost_price DECIMAL(18,2) DEFAULT 0.0")
    else:
        print("cost_price already exists in products")
        
    # Check sale_items table
    cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'sale_items' AND COLUMN_NAME = 'cost_price'")
    if not cur.fetchone():
        print("Adding cost_price to sale_items")
        cur.execute("ALTER TABLE sale_items ADD cost_price DECIMAL(18,2) DEFAULT 0.0")
    else:
        print("cost_price already exists in sale_items")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()

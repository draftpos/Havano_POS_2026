import sqlite3

for db_name in ["pos.db", "pos_offline.db"]:
    try:
        conn = sqlite3.connect(db_name)
        cur = conn.cursor()
        print(f"=== DB: {db_name} ===")
        cur.execute("SELECT customer_name, price_list_name, default_price_list_id FROM customers WHERE customer_name LIKE '%Cash%'")
        rows = cur.fetchall()
        for r in rows:
            print("  Customer:", r)
            
        cur.execute("SELECT id, name, selling, is_selling FROM price_lists")
        print("  Price Lists:", cur.fetchall())
        
        cur.execute("SELECT part_no, uom, price_list, price FROM item_prices WHERE part_no LIKE 'TRIATIX 2L%'")
        print("  TRIATIX 2L Item Prices:", cur.fetchall())
        
        cur.execute("SELECT part_no, price FROM products WHERE part_no LIKE 'TRIATIX 2L%'")
        print("  TRIATIX 2L Products Table Price:", cur.fetchall())
        conn.close()
    except Exception as e:
        print(f"Error {db_name}: {e}")

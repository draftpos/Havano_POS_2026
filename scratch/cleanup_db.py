import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.db import get_connection

def cleanup_price_lists():
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Find the IDs
        cur.execute("SELECT id FROM price_lists WHERE name = 'Standard Selling'")
        res = cur.fetchone()
        target_id = res[0] if res else None
        
        cur.execute("SELECT id FROM price_lists WHERE name = 'Standard'")
        res = cur.fetchone()
        source_id = res[0] if res else None
        
        if source_id and target_id:
            print(f"Merging 'Standard' (ID {source_id}) into 'Standard Selling' (ID {target_id})...")
            
            # Update customers
            cur.execute("UPDATE customers SET default_price_list_id = ? WHERE default_price_list_id = ?", (target_id, source_id))
            print(f"Updated {cur.rowcount} customers.")
            
            # Update item_prices
            cur.execute("UPDATE item_prices SET price_list_id = ? WHERE price_list_id = ?", (target_id, source_id))
            print(f"Updated {cur.rowcount} item prices.")
            
            # Update product_uom_prices
            cur.execute("UPDATE product_uom_prices SET price_list_id = ? WHERE price_list_id = ?", (target_id, source_id))
            print(f"Updated {cur.rowcount} UOM prices.")
            
            # Delete old price list
            cur.execute("DELETE FROM price_lists WHERE id = ?", (source_id,))
            print("Deleted redundant 'Standard' price list.")
            
        elif source_id and not target_id:
            print("Renaming 'Standard' to 'Standard Selling'...")
            cur.execute("UPDATE price_lists SET name = 'Standard Selling' WHERE id = ?", (source_id,))
            
        else:
            print("No cleanup needed.")
            
        conn.commit()
        print("Done.")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    cleanup_price_lists()

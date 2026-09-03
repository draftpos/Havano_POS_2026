import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test():
    from database.db import get_connection
    from models.product import get_product_by_part_no

    barcode = "df455"
    print(f"Testing real synced barcode '{barcode}'...")
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT part_no, uom FROM product_barcodes WHERE barcode = ?", (barcode,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        print("Barcode not found in database!")
        return
        
    part_no, uom = row
    print(f"Resolved barcode '{barcode}' to Product Part No: '{part_no}', UOM: '{uom}'")
    
    prod = get_product_by_part_no(part_no)
    if prod:
        print(f"Successfully retrieved product: {prod.get('name')} (Base UOM: {prod.get('uom')})")
    else:
        print("Product not found in the products table!")

if __name__ == "__main__":
    test()

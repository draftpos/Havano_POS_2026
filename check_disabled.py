import sys
sys.path.append('c:/Users/user/Desktop/Havano_POS_2026-main')
from database.db import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM products WHERE active = 0")
    inactive_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM products")
    total_count = cur.fetchone()[0]
    
    print(f'Inactive/Disabled Products: {inactive_count}')
    print(f'Total Products: {total_count}')
    
    if inactive_count > 0:
        cur.execute("SELECT TOP 5 name, part_no FROM products WHERE active = 0")
        print('Sample of disabled products:', cur.fetchall())
        
    conn.close()
except Exception as e:
    print('Error:', e)

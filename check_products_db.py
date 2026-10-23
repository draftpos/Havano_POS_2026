import sys
sys.path.append('c:/Users/user/Desktop/Havano_POS_2026-main')
from database.db import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'products'")
    cols = [r[0] for r in cur.fetchall()]
    print('Columns in products:', cols)
    
    print_col = next((c for c in cols if 'print' in c.lower()), None)
    if print_col:
        print('Found print-related column:', print_col)
        cur.execute(f"SELECT COUNT(*) FROM products WHERE {print_col} = 1 OR {print_col} = '1' OR {print_col} = 'True'")
        count = cur.fetchone()[0]
        print(f'Products with {print_col}=1:', count)
    else:
        print('No print_after_order column found.')
    conn.close()
except Exception as e:
    print('Error:', e)

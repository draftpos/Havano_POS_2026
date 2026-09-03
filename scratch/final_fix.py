
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from database.db import get_connection

def fix():
    conn = get_connection()
    cur = conn.cursor()
    sql = """
    IF EXISTS (SELECT 1 FROM price_lists WHERE name='Standard') AND NOT EXISTS (SELECT 1 FROM price_lists WHERE name='Standard Selling')
        UPDATE price_lists SET name='Standard Selling' WHERE name='Standard'
    ELSE IF EXISTS (SELECT 1 FROM price_lists WHERE name='Standard') AND EXISTS (SELECT 1 FROM price_lists WHERE name='Standard Selling')
    BEGIN
        DECLARE @old int, @new int;
        SELECT @old=id FROM price_lists WHERE name='Standard';
        SELECT @new=id FROM price_lists WHERE name='Standard Selling';
        UPDATE customers SET default_price_list_id=@new WHERE default_price_list_id=@old;
        UPDATE item_prices SET price_list='Standard Selling' WHERE price_list='Standard';
        DELETE FROM price_lists WHERE id=@old;
    END
    """
    cur.execute(sql)
    conn.commit()
    conn.close()
    print("Database cleaned up successfully.")

if __name__ == "__main__":
    fix()

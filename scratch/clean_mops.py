import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from database.db import get_connection

def clean():
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT id, name FROM modes_of_payment")
    print("Before cleanup MOPs:", cur.fetchall())
    
    # In SaaS mode, if user only has 'Cash', delete 'Ecocash' and 'Card' from modes_of_payment if unsynced
    cur.execute("DELETE FROM modes_of_payment WHERE LOWER(name) IN ('ecocash', 'card')")
    print(f"Deleted {cur.rowcount} unsynced pre-seeded fallback mode(s).")
    
    # Clean 0-float, 0-income, 0-counted shift_rows for deleted methods in open shifts
    cur.execute("DELETE FROM shift_rows WHERE LOWER(method) IN ('ecocash', 'card') AND start_float = 0 AND income = 0 AND counted = 0")
    print(f"Deleted {cur.rowcount} empty shift row(s) for deleted methods.")
    
    conn.commit()
    
    cur.execute("SELECT id, name FROM modes_of_payment")
    print("After cleanup MOPs:", cur.fetchall())
    conn.close()

if __name__ == "__main__":
    clean()

from database.db import get_connection, fetchall_dicts

def check():
    conn = get_connection()
    cur = conn.cursor()
    print("--- Cost Centers ---")
    cur.execute("SELECT id, name FROM cost_centers")
    for r in fetchall_dicts(cur):
        print(r)
    
    print("\n--- Warehouses ---")
    cur.execute("SELECT id, name FROM warehouses")
    for r in fetchall_dicts(cur):
        print(r)
    conn.close()

if __name__ == "__main__":
    check()

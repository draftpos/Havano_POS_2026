
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from database.db import get_connection

def seed_mops():
    data = [
        {
            "id": 1,
            "name": "Manual Payment",
            "display_name": "Manual Payment (Bank)",
            "payment_type": "inbound",
            "journal_name": "Bank",
            "journal_type": "bank",
            "journal_currency_name": "USD"
        },
        {
            "id": 3,
            "name": "Cash",
            "display_name": "Cash",
            "payment_type": "inbound",
            "journal_name": "Cash",
            "journal_type": "cash",
            "journal_currency_name": "USD"
        }
    ]
    
    conn = get_connection()
    cur = conn.cursor()
    
    for item in data:
        name = item["display_name"]
        j_type = item["journal_type"].capitalize()
        j_name = item["journal_name"]
        currency = item["journal_currency_name"] or "USD"
        
        cur.execute("SELECT id FROM modes_of_payment WHERE name = ?", (name,))
        if not cur.fetchone():
            print(f"Inserting {name}...")
            cur.execute("""
                INSERT INTO modes_of_payment (name, type, mop_type, gl_account, gl_account_name, account_currency, synced_from_api, enabled)
                VALUES (?, ?, ?, ?, ?, ?, 1, 1)
            """, (name, j_type, j_type, j_name, j_name, currency))
        else:
            print(f"Updating {name}...")
            cur.execute("""
                UPDATE modes_of_payment
                SET type = ?, mop_type = ?, gl_account = ?, gl_account_name = ?, account_currency = ?, synced_from_api = 1
                WHERE name = ?
            """, (j_type, j_type, j_name, j_name, currency, name))
            
    conn.commit()
    conn.close()
    print("Done seeding MOPs.")

if __name__ == "__main__":
    seed_mops()

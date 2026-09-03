import sys, os
sys.path.insert(0, os.path.abspath("."))
import requests
from database.db import get_connection, fetchall_dicts
from models.company_defaults import get_defaults

defaults = get_defaults()
api_host = defaults.get("server_api_host", "https://backoffice.havano.pro")
api_key = defaults.get("api_key")
api_secret = defaults.get("api_secret")

headers = {
    "Authorization": f"token {api_key}:{api_secret}",
    "Content-Type": "application/json"
}

url = f"{api_host}/api/method/saas_api.www.api.get_users"
resp = requests.get(url, headers=headers)
if resp.status_code == 200:
    data = resp.json()
    users_list = (data.get("message") or {}).get("data") or []
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Ensure cloud_user_id column exists
    try:
        cur.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME='users' AND COLUMN_NAME='cloud_user_id'
            )
            ALTER TABLE users ADD cloud_user_id INT NULL
        """)
        conn.commit()
    except Exception as e:
        print("Schema update notice:", e)

    updated = 0
    for u in users_list:
        cid = u.get("id")
        email = (u.get("email") or "").strip()
        name = (u.get("name") or u.get("username") or "").strip()
        full_name = (u.get("full_name") or "").strip()
        
        cur.execute("""
            UPDATE users SET cloud_user_id=?
            WHERE email=? OR username=? OR full_name=? OR frappe_user=?
        """, (cid, email, name, full_name, email))
        conn.commit()
        if cur.rowcount > 0:
            updated += 1
            print(f"Mapped {full_name} ({email}) -> Cloud User ID: {cid}")

    conn.close()
    print(f"Total users updated with cloud_user_id: {updated}")

# createsuperuser.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# tells Python to look in the project root for imports

from database.db import init_db
from models.user import create_user, get_all_users

init_db()   # make sure tables exist

print("=== Create POS User ===")
username = input("Username: ").strip()
password = input("Password: ").strip()
print("Role options: admin / cashier")
role     = input("Role: ").strip() or "cashier"

create_user(username, password, role)

print("\nAll users:")
for u in get_all_users():
    print(f"  ID:{u['id']}  {u['username']}  ({u['role']})")
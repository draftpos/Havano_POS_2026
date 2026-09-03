import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models.user import get_all_users

print("=== get_all_users() ===")
for u in get_all_users():
    print(u["username"], "->", u.get("allowed_payment_methods"))

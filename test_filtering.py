import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.user import get_all_users, update_user, get_user_by_id
from views.dialogs.payment_dialog import _load_payment_methods

# Get first cashier
cashier = None
for u in get_all_users():
    if u["role"] == "cashier" and u["username"] == "cashier.cashier":
        cashier = u
        break

if not cashier:
    print("No cashier.cashier user found, searching for any cashier...")
    for u in get_all_users():
        if u["role"] == "cashier":
            cashier = u
            break

if not cashier:
    print("No cashier found!")
    sys.exit(1)

print(f"Testing with cashier: {cashier['username']} (ID: {cashier['id']})")
print(f"Original allowed_payment_methods in dict: {cashier.get('allowed_payment_methods')}")

# Update allowed payment methods to only allow Cash
updated = update_user(cashier["id"], allowed_payment_methods="Cash")
print(f"Updated user in dict: {updated.get('allowed_payment_methods') if updated else 'None'}")

# Verify database query returns the correct filtered payment methods
co_name = ""
try:
    from views.dialogs.payment_dialog import _get_default_company
    co = _get_default_company()
    co_name = co.get("name", "") if co else ""
except Exception:
    pass

methods = _load_payment_methods(co_name, cashier_id=cashier["id"])
print("\nAllowed payment methods in Checkout Dialog for this user:")
for m in methods:
    print(f"  - {m['label']} (GL: {m['gl_account']})")

# Reset back to ALL
update_user(cashier["id"], allowed_payment_methods="ALL")
print("\nReset allowed_payment_methods back to ALL.")

import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from models.shift import get_shift_by_id, refresh_income, get_payment_method_currency

print("Testing get_payment_method_currency:")
mops = ["Cash", "Cash ZIG", "CBZ Rands", "Eco Cash", "Innbucks", "Omari", "Test"]
for m in mops:
    print(f"  {m} -> {get_payment_method_currency(m)}")

print("\nRefreshing shift income for shift #3:")
refresh_income(3)

shift = get_shift_by_id(3)
if shift:
    print(f"\nShift #{shift.get('shift_number')} (ID {shift.get('id')}) rows:")
    for r in shift.get("rows", []):
        print(f"  Method: '{r.get('method')}', Currency: '{r.get('currency')}', Income: {r.get('income')}, Total: {r.get('total')}")
else:
    print("Shift #3 not found.")

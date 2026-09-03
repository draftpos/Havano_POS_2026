import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from models.shift import get_shift_by_id, refresh_income

refresh_income(3)

shift = get_shift_by_id(3)
print(f"Shift #{shift['shift_number']} (ID {shift['id']}) rows:")
for r in shift.get("rows", []):
    print(f"  Method: '{r.get('method')}', Currency: '{r.get('currency')}', Income: {r.get('income')}, Total: {r.get('total')}")

import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from models.shift import get_shift_by_id, get_payment_method_currency, get_company_base_currency
from views.dialogs.payment_dialog import _get_local_rate

shift = get_shift_by_id(3)
base_ccy = get_company_base_currency() or "USD"

print(f"Shift #3 Reconciliation Base Equivalence Test (Base: {base_ccy}):\n")
print(f"{'Method':<15} {'Currency':<10} {'Expected':<12} {'Counted':<12} {'Var (Native)':<14} {'Var (' + base_ccy + ')':<14}")
print("-" * 80)

total_base_expected = 0.0
total_base_counted = 0.0

for r in shift.get("rows", []):
    method = r["method"]
    curr = r.get("currency") or get_payment_method_currency(method)
    exp = float(r["total"])
    cnt = float(r["counted"])
    var_nat = cnt - exp
    
    rate_to_base = _get_local_rate(curr, base_ccy)
    var_base = var_nat * rate_to_base

    total_base_expected += exp * rate_to_base
    total_base_counted += cnt * rate_to_base

    print(f"{method:<15} {curr:<10} {exp:<12.2f} {cnt:<12.2f} {var_nat:<14.2f} {var_base:<14.2f}")

total_base_variance = total_base_counted - total_base_expected
print("-" * 80)
print(f"OVERALL BASE ({base_ccy}) -> Expected: {total_base_expected:,.2f} | Counted: {total_base_counted:,.2f} | Variance: {total_base_variance:,.2f}")

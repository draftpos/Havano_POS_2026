import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from models.shift import get_shift_by_id, get_payment_method_currency, get_company_base_currency
from views.dialogs.payment_dialog import _get_local_rate

shift = get_shift_by_id(3)
base_ccy = get_company_base_currency() or "USD"

currency_totals = {}
base_expected_total = 0.0
base_counted_total = 0.0

for r in shift.get("rows", []):
    method = r["method"]
    curr = r.get("currency") or get_payment_method_currency(method)
    exp = float(r["total"])
    cnt = float(r["counted"])
    
    rate_to_base = _get_local_rate(curr, base_ccy)
    base_expected_total += exp * rate_to_base
    base_counted_total += cnt * rate_to_base

    if curr not in currency_totals:
        currency_totals[curr] = {"expected": 0.0, "counted": 0.0}
    currency_totals[curr]["expected"] += exp
    currency_totals[curr]["counted"] += cnt

summary_parts = []
for curr, totals_map in sorted(currency_totals.items()):
    exp_val = totals_map["expected"]
    cnt_val = totals_map["counted"]
    summary_parts.append(f"{curr}: Exp {exp_val:,.2f} | Cnt {cnt_val:,.2f}")

base_summary = f"OVERALL BASE ({base_ccy}): Exp {base_expected_total:,.2f} | Cnt {base_counted_total:,.2f}"
summary_text = "   •   ".join(summary_parts) + f"\n  ▶  {base_summary}"

print("=== NEW FOOTER SUMMARY FORMAT ===")
print(summary_text)

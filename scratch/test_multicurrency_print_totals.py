# Test multi-currency breakdown on shift printout
methods = [
    {'method': 'Cash', 'currency': 'USD', 'expected': 100.0, 'counted': 100.0},
    {'method': 'Cash ZiG', 'currency': 'ZIG', 'expected': 500.0, 'counted': 500.0},
    {'method': 'EcoCash', 'currency': 'USD', 'expected': 20.0, 'counted': 20.0},
    {'method': 'Swipe ZiG', 'currency': 'ZIG', 'expected': 1200.0, 'counted': 1200.0}
]

summary_curr_totals = {}
for pm in methods:
    currency = (pm.get('currency') or 'USD').strip().upper()
    expected = float(pm.get('expected', 0))
    counted = float(pm.get('counted', 0))
    
    if currency not in summary_curr_totals:
        summary_curr_totals[currency] = {'expected': 0.0, 'counted': 0.0}
    summary_curr_totals[currency]['expected'] += expected
    summary_curr_totals[currency]['counted'] += counted

print("Calculated per-currency totals:")
for ccy, g_tot in summary_curr_totals.items():
    print(f"  GRAND TOTAL ({ccy}): Expected={g_tot['expected']}, Counted={g_tot['counted']}")

assert summary_curr_totals['USD']['expected'] == 120.0
assert summary_curr_totals['ZIG']['expected'] == 1700.0
print("Multi-currency separation test passed successfully!")

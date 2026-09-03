import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from models.exchange_rate import get_rate, get_all_rates

print("--- ALL EXCHANGE RATES IN DATABASE ---")
try:
    rates = get_all_rates()
    for r in rates:
        print(" ", r)
except Exception as e:
    print(" Error fetching exchange rates:", e)

def _get_local_rate(from_currency: str, to_currency: str = "USD") -> float:
    if from_currency.upper() == to_currency.upper():
        return 1.0
    try:
        from models.exchange_rate import get_rate
        r = get_rate(from_currency, to_currency)
        if r and float(r) > 0:
            return float(r)
        inv = get_rate(to_currency, from_currency)
        if inv and float(inv) > 0:
            return 1.0 / float(inv)
    except Exception:
        pass
    return 1.0

print("\n--- TEST _get_local_rate ---")
currencies = ["ZIG", "ZWG", "ZAR", "BWP", "EUR", "AMD"]
for c in currencies:
    r1 = _get_local_rate("USD", c)
    r2 = _get_local_rate(c, "USD")
    print(f" USD -> {c}: {r1}  |  {c} -> USD: {r2}")

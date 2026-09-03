import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

def _get_normalized_rate(from_curr: str, to_curr: str, base_ccy: str = "USD") -> float:
    from_u = from_curr.upper().strip()
    to_u = to_curr.upper().strip()
    base_u = base_ccy.upper().strip()

    if from_u == to_u:
        return 1.0

    try:
        from models.exchange_rate import get_rate
        # Try direct rate
        r = get_rate(from_u, to_u)
        if not r or float(r) <= 0:
            inv = get_rate(to_u, from_u)
            if inv and float(inv) > 0:
                r = 1.0 / float(inv)

        if not r or float(r) <= 0:
            return 1.0

        r = float(r)

        # Normalize rate direction:
        # If requesting FOREIGN -> BASE (e.g. ZIG -> USD):
        # Result should be < 1.0 (USD per ZIG). If r > 1.0, invert it!
        if from_u != base_u and to_u == base_u:
            if r > 1.0 and from_u not in ("GBP", "EUR", "AUD", "NZD"):
                return 1.0 / r
            return r

        # If requesting BASE -> FOREIGN (e.g. USD -> ZIG):
        # Result should be > 1.0 (ZIG per USD). If r < 1.0, invert it!
        if from_u == base_u and to_u != base_u:
            if r < 1.0 and to_u not in ("GBP", "EUR", "AUD", "NZD"):
                return 1.0 / r
            return r

        return r
    except Exception as e:
        print("Rate resolution error:", e)
        return 1.0

print("--- TESTING NORMALIZED RATE RESOLUTION ---")
test_currencies = ["ZIG", "ZAR", "AMD", "BWP", "EUR"]

for c in test_currencies:
    rate_to_usd = _get_normalized_rate(c, "USD")
    rate_from_usd = _get_normalized_rate("USD", c)
    print(f" {c} -> USD: {rate_to_usd:.6f}  |  USD -> {c}: {rate_from_usd:.2f}")

    # Test payment conversion simulation:
    # Say we pay 100 units of currency c
    val = 100.0
    paid_usd = val * rate_to_usd
    rem_usd = paid_usd
    converted_back = rem_usd * rate_from_usd
    print(f"   Pay {val} {c} -> ${paid_usd:.2f} USD -> Convert back: {converted_back:.2f} {c}")

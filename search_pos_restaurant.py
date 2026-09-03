import os
for fn in ["views/pos_view.py", "views/restaurant_view.py"]:
    if os.path.exists(fn):
        with open(fn, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if "PaymentDialog" in line or "checkout" in line.lower() or "pay" in line.lower():
                    if "def " in line or "class " in line or "dlg" in line:
                        print(f"{fn} Line {i}: {line.strip()}")

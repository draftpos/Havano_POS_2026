import re
with open("views/dialogs/payment_dialog.py", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "_load_payment_methods" in line:
            print(f"Line {i}: {line.strip()}")

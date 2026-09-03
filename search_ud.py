with open("views/dialogs/users_dialog.py", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "allowed_payment_methods" in line or "payment_toggles" in line or "payment_toggle" in line:
            print(f"Line {i}: {line.strip()}")

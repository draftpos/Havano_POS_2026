with open("views/dialogs/laybye_payment_dialog.py", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "modes_of_payment" in line or "allowed_payment_methods" in line or "_methods" in line:
            print(f"Line {i}: {line.strip()}")

with open("views/dialogs/payment_dialog.py", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "class PaymentDialog" in line or "def __init__" in line:
            if i < 1800:
                print(f"Line {i}: {line.strip()}")

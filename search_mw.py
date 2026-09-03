with open("views/main_window.py", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "PaymentDialog" in line:
            print(f"Line {i}: {line.strip()}")

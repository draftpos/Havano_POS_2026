with open("models/user.py", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "_to_dict" in line or "get_user_by_id" in line or "allowed_payment_methods" in line:
            print(f"Line {i}: {line.strip()}")

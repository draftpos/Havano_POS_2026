with open("models/user.py", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if line.strip().startswith("def "):
            print(f"Line {i}: {line.strip()}")

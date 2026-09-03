with open("main.py", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            print(f"Line {i}: {line.strip()}")
            if i > 250:
                break

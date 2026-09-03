with open("views/main_window.py", "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        if "def " in line and ("total" in line.lower() or "cart" in line.lower() or "price" in line.lower()):
            print(f"Line {idx+1}: {line.strip()}")

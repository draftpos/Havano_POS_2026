with open("views/main_window.py", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if i >= 7900 and i <= 8000:
            safe_line = line.strip().encode("ascii", errors="replace").decode("ascii")
            if "def " in safe_line:
                print(f"Line {i}: {safe_line}")

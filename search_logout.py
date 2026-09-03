with open("views/main_window.py", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "logout" in line.lower() or "login" in line.lower() or "self.user =" in line:
            if "def " in line or "class " in line or "self." in line:
                print(f"Line {i}: {line.strip()}")

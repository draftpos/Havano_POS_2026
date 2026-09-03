with open("views/dialogs/users_dialog.py", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "def _save" in line:
            print(f"Line {i}: {line.strip()}")

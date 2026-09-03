with open("views/dialogs/users_dialog.py", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "Double" in line or "clicked" in line or "edit" in line or "open" in line:
            if "def " in line:
                print(f"Line {i}: {line.strip()}")

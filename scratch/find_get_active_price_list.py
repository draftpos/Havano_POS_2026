with open("views/main_window.py", "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        if "def _get_active_price_list" in line:
            print(f"Line {idx+1}: {line.strip()}")

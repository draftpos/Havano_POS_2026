with open(r"c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py", "r", encoding="utf-8", errors="ignore") as f:
    for idx, line in enumerate(f):
        if "POSView" in line:
            print(f"Line {idx+1}: {line.strip()}")

with open("views/main_window.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

current_class = ""
current_def = ""
for i, line in enumerate(lines):
    if line.startswith("class "):
        current_class = line.strip()
    elif line.strip().startswith("def "):
        current_def = line.strip()
    if 'Inventory ▾' in line or 'Maintenance ▾' in line:
        print(f"Line {i+1} in {current_class} -> {current_def}: {line.strip()}")

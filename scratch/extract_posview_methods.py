with open("views/main_window.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

out = []
current_class = ""
for i, line in enumerate(lines):
    if line.startswith("class "):
        current_class = line.strip()
    elif line.strip().startswith("def "):
        if "POSView" in current_class and 6457 <= i <= 13780:
            out.append(f"Line {i+1}: {line.strip()}")

with open("scratch/posview_methods.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))

import re

with open("views/main_window.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.startswith("class ") or (line.strip().startswith("def ") and "switch_to_" in line):
        print(f"Line {i+1}: {line.strip()}")

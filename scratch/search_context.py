import re

with open("views/main_window.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

def print_matches(pattern, context_lines=5):
    print(f"=== Matches for: {pattern} ===")
    for i, line in enumerate(lines):
        if re.search(pattern, line, re.IGNORECASE):
            start = max(0, i - context_lines)
            end = min(len(lines), i + context_lines + 1)
            print(f"\n--- Match at line {i+1} ---")
            for idx in range(start, end):
                prefix = "-> " if idx == i else "   "
                print(f"{idx+1:5d}{prefix}{lines[idx].rstrip()}")

print_matches(r"Maintenance", 2)
print_matches(r"switch_to_dashboard", 2)

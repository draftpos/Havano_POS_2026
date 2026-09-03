import os
import re

root_dir = r"c:\Users\DELL\New_POS\Havano_POS_2026"
event_filters = []

for dirpath, dirnames, filenames in os.walk(root_dir):
    for filename in filenames:
        if filename.endswith(".py"):
            filepath = os.path.join(dirpath, filename)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if "def eventFilter" in content:
                    lines = content.splitlines()
                    for idx, line in enumerate(lines):
                        if "def eventFilter" in line:
                            # Extract 25 lines of the function
                            func_lines = lines[idx:idx+35]
                            print(f"--- File: {filepath}:{idx+1} ---")
                            print("\n".join(func_lines))
                            print("="*60)
            except Exception as e:
                pass

import os

root_dir = r"c:\Users\DELL\New_POS\Havano_POS_2026"
output_file = r"c:\Users\DELL\New_POS\Havano_POS_2026\scratch\event_filters_output.txt"

with open(output_file, "w", encoding="utf-8") as out:
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if "venv" in dirpath or "my" in dirpath or ".git" in dirpath:
            continue
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
                                func_lines = lines[idx:idx+35]
                                out.write(f"--- File: {filepath}:{idx+1} ---\n")
                                out.write("\n".join(func_lines))
                                out.write("\n" + "="*60 + "\n")
                except Exception as e:
                    pass

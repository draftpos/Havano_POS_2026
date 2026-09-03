import os
import re

def refactor_themes(root_dir):
    # Regex to match the typical colour palette block
    # It might have varying numbers of colors, but usually starts with NAVY and ends near TAB_COLORS
    pattern = re.compile(
        r"(?:# =+\n)?(?:# COLOUR PALETTE\n)?(?:# =+\n)?"
        r"(?:^#?\s*NAVY\s*=\s*['\"].*?\n)"
        r"(?:.*?TAB_COLORS\s*=\s*\[.*?\]\n?)",
        re.MULTILINE | re.DOTALL
    )
    
    count = 0
    for root, dirs, files in os.walk(root_dir):
        if "_internal" in root or "venv" in root or "__pycache__" in root:
            continue
        for file in files:
            if not file.endswith(".py"): continue
            if file == "theme.py" or file == "refactor_theme.py": continue
            
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                
            if "NAVY" in content and "theme import" not in content:
                new_content = pattern.sub("from theme import *\n", content)
                
                # If there are residual color definitions (sometimes they are re-declared without TAB_COLORS)
                # We can also do a broader replace
                residual_pattern = re.compile(
                    r"(?:^#?\s*NAVY\s*=\s*['\"].*?\n)"
                    r"(?:^#?\s*[A-Z0-9_]+\s*=\s*['\"].*?\n)*",
                    re.MULTILINE
                )
                if "NAVY" in new_content:
                     new_content = residual_pattern.sub("from theme import *\n", new_content)
                
                if new_content != content:
                    # Clean up multiple imports if they happened
                    new_content = new_content.replace("from theme import *\nfrom theme import *\n", "from theme import *\n")
                    
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"Refactored {path}")
                    count += 1
    print(f"Total files refactored: {count}")

if __name__ == '__main__':
    refactor_themes(r"c:\Users\DELL\New_POS\Havano_POS_2026")

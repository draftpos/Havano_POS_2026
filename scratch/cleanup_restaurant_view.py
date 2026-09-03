
import sys

def cleanup_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find the transition. The active code starts with docstrings or imports.
    # We saw in the previous view that active code starts around where FlowLayout was defined.
    # But wait, there is a whole block of uncommented code.
    
    # Let's find the FIRST line that is NOT starting with "#" and is NOT empty,
    # and is NOT part of the first commented block.
    # Actually, the active code starts with:
    # """
    # views/restaurant_view.py
    # ========================
    
    start_index = -1
    for i, line in enumerate(lines):
        if line.strip() == '"""' and i + 1 < len(lines) and 'views/restaurant_view.py' in lines[i+1]:
            # This is likely the start of the active code docstring
            # Check if it's NOT commented out
            if not line.startswith('#'):
                start_index = i
                break
    
    if start_index == -1:
        print("Could not find start of active code block.")
        return

    print(f"Found active code starting at line {start_index + 1}")
    
    active_lines = lines[start_index:]
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(active_lines)
    
    print(f"File cleaned. New line count: {len(active_lines)}")

if __name__ == "__main__":
    cleanup_file(sys.argv[1])

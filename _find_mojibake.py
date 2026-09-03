import codecs

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py'
content = codecs.open(path, 'r', 'utf-8').read()
lines = content.split('\n')

# Find all lines with Greek gamma (mojibake indicator)
gamma = '\u0393'
for i, line in enumerate(lines):
    if gamma in line:
        print(f"{i+1}: {line.strip()[:140]}")

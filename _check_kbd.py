import codecs
content = codecs.open(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py', 'r', 'utf-8').read()
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'osk_btn = QPushButton' in line:
        print(f'{i+1}: {repr(line.strip())}')

import codecs
lines = codecs.open(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py', 'r', 'utf-8').readlines()
for i, l in enumerate(lines):
    if 'Notes' in l:
        print(f'{i}: {l.strip().encode("ascii", "ignore").decode("ascii")}')

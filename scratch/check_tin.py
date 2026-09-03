import codecs
import re

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\services\printing_service.py'
content = codecs.open(path, 'r', 'utf-8').read()

lines = content.split('\n')
for i, l in enumerate(lines):
    if 'TIN' in l:
        print(f'{i}: {l.strip().encode("ascii", "ignore").decode("ascii")}')

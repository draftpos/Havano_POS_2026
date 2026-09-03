import codecs
import re

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py'
content = codecs.open(path, 'r', 'utf-8').read()

# Replace any occurrence of "Notes <emoji>"] with "Notes"]
new_content = re.sub(r'"Notes[^"]*"\]', '"Notes"]', content)

codecs.open(path, 'w', 'utf-8').write(new_content)
print('Replaced Notes headers!')

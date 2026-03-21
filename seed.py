import re

with open('database/db.py', encoding='utf-8') as f:
    content = f.read()

# Remove git conflict markers - keep HEAD version, discard incoming
fixed = re.sub(r'<<<<<<< HEAD\n', '', content)
fixed = re.sub(r'\n=======\n.*?\n>>>>>>> [^\n]+', '', fixed, flags=re.DOTALL)

with open('database/db.py', 'w', encoding='utf-8') as f:
    f.write(fixed)

print("Fixed. db.py is clean.")
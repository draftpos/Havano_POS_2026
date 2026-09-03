import sys

with open('views/main_window.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('border:1px solid #c8d8ec', 'border:none')
c = c.replace('border:1px solid {BORDER}', 'border:none')

with open('views/main_window.py', 'w', encoding='utf-8') as f:
    f.write(c)
print("Successfully removed borders")

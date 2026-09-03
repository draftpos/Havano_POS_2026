import re
f = 'views/main_window.py'
with open(f, 'r', encoding='utf-8') as file:
    text = file.read()

text = text.replace('"allow_negative_stock", default=False', '"allow_negative_stock", default=True')
text = text.replace("'allow_negative_stock', default=False", "'allow_negative_stock', default=True")
text = text.replace('"Allow selling items even when they have no stock.", False)', '"Allow selling items even when they have no stock.", True)')

text = re.sub(r'if float\(picked\["price"\] or 0\) <= 0:', 'if float(picked["price"] or 0) < 0:', text)
text = text.replace('Zero-priced item', 'Negative-priced item')
text = text.replace('zero-priced items', 'negative-priced items')

with open(f, 'w', encoding='utf-8') as file:
    file.write(text)

print("Replaced successfully")

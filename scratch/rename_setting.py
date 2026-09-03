import os

def replace_in_file(path, replacements):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    for old, new in replacements:
        content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

replacements = [
    ('self._get_pos_rule("block_zero_stock", default=True)', 'not self._get_pos_rule("allow_negative_stock", default=False)'),
    ('getattr(self, "_get_pos_rule", lambda k, default: default)("block_zero_stock", default=True)', 'not getattr(self, "_get_pos_rule", lambda k, default: default)("allow_negative_stock", default=False)'),
    ('("block_zero_stock",  "Block Zero-Stock Sales",', '("allow_negative_stock",  "Allow Negative Stock",'),
    ("Show 'Insufficient Stock' popup when item has no stock.", "Allow selling items even when they have no stock."),
    ("Disable 'Block Zero-Stock Sales' in ", "Enable 'Allow Negative Stock' in "),
    ("Disable 'Block Zero/Negative Stock Sales' in ", "Enable 'Allow Negative Stock' in ")
]

replace_in_file(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py', replacements)

settings_replacements = [
    ('("block_zero_stock",    "BLOCK ZERO-STOCK SALES",         "Stop sales when stock is empty."),', '("allow_negative_stock",    "ALLOW NEGATIVE STOCK",         "Allow sales even when stock is empty."),')
]

replace_in_file(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\dialogs\settings_dialog.py', settings_replacements)
print("Done!")

import os

files = ['stock_adjust_dialog.py', 'stock_transfer_dialog.py', 'stock_reconciliation_dialog.py', 'inventory_list_dialog.py']

for f in files:
    path = os.path.join(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\dialogs', f)
    if not os.path.exists(path): continue
    with open(path, 'r', encoding='utf-8') as file:
        content = file.read()
        
    print(f'=== {f} ===')
    for i, line in enumerate(content.splitlines()):
        if 'add_btn' in line or 'btn_add' in line or 'Add' in line:
            print(f'{i+1}: {line.strip()}')

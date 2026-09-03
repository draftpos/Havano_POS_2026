import os

files = [
    'shift_reconciliation_screen.py',
    'stock_adjustments_screen.py',
    'stock_reconciliation_screen.py',
    'stock_transfer_screen.py'
]
dir_path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\inventory'

for filename in files:
    path = os.path.join(dir_path, filename)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Change show_date_filter=False to True
    content = content.replace('show_date_filter=False', 'show_date_filter=True')
    
    # Ensure btn_add is visible and connected to a dummy method if not present
    if 'def _open_add_dialog(self):' not in content:
        content += '\n    def _open_add_dialog(self):\n        from PySide6.QtWidgets import QMessageBox\n        QMessageBox.information(self, "Coming Soon", "Add functionality will be available here.")\n'

    # Remove the hide btn_add logic I added earlier
    old_code = '''if hasattr(self, '_open_add_dialog'):
            self.report.btn_add.clicked.connect(self._open_add_dialog)
        else:
            self.report.btn_add.setVisible(False)'''
    new_code = 'self.report.btn_add.clicked.connect(self._open_add_dialog)'
    content = content.replace(old_code, new_code)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Fixed {filename}')

import os

def replace_dummy(filepath, new_code):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    old_code = '''    def _open_add_dialog(self):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Coming Soon", "Add functionality will be available here.")'''
    
    content = content.replace(old_code, new_code)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

replace_dummy(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\inventory\stock_transfer_screen.py', '''    def _open_add_dialog(self):
        from views.dialogs.stock_transfer_dialog import StockTransferDialog
        dlg = StockTransferDialog(self.window())
        dlg.exec()
        if hasattr(self, "_load_data"): self._load_data()''')

replace_dummy(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\inventory\stock_reconciliation_screen.py', '''    def _open_add_dialog(self):
        from views.dialogs.stock_reconciliation_dialog import StockReconciliationDialog
        dlg = StockReconciliationDialog(self.window())
        dlg.exec()
        if hasattr(self, "_load_data"): self._load_data()''')

replace_dummy(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\inventory\shift_reconciliation_screen.py', '''    def _open_add_dialog(self):
        from views.dialogs.shift_reconciliation_dialog import ShiftReconciliationDialog
        dlg = ShiftReconciliationDialog(self.window())
        dlg.exec()
        if hasattr(self, "_load_data"): self._load_data()''')

print('Wired up add dialogs')

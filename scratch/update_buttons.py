import os
import re
import glob

# 1. Update purchase_invoices_list_dialog.py
path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\dialogs\purchase_invoices_list_dialog.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove _btn definition
content = re.sub(r'def _btn\(.*?\n    return b\n', '', content, flags=re.DOTALL)

replacement = '''        if not self.selection_mode:
            self.btn_add.clicked.connect(self._on_add_new)
            
            self._edit_btn = QPushButton(" Edit")
            import qtawesome as qta
            self._edit_btn.setIcon(qta.icon("fa5s.edit", color="white"))
            self._edit_btn.setStyleSheet(f"background:{ACCENT}; color:{WHITE}; padding:8px 15px; border-radius:4px; font-weight:bold;")
            self._edit_btn.setEnabled(False)
            self._edit_btn.clicked.connect(self._on_edit)
            self.filters_layout.addWidget(self._edit_btn)
            
            self._delete_btn = QPushButton(" Delete")
            self._delete_btn.setIcon(qta.icon("fa5s.trash", color="white"))
            self._delete_btn.setStyleSheet(f"background:{DANGER}; color:{WHITE}; padding:8px 15px; border-radius:4px; font-weight:bold;")
            self._delete_btn.setEnabled(False)
            self._delete_btn.clicked.connect(self._on_delete)
            self.filters_layout.addWidget(self._delete_btn)
        else:
            self.btn_add.hide()
        
        view_str = " Select for Return" if self.selection_mode else " View Details"
        self._view_btn = QPushButton(view_str)
        import qtawesome as qta
        self._view_btn.setIcon(qta.icon("fa5s.eye", color="white"))
        self._view_btn.setStyleSheet(f"background:{ACCENT}; color:{WHITE}; padding:8px 15px; border-radius:4px; font-weight:bold;")
        self._view_btn.setEnabled(False)
        self._view_btn.clicked.connect(self._on_view_details)
        self.filters_layout.addWidget(self._view_btn)'''

content = re.sub(r'        if not self\.selection_mode:\n            add_str = .*?self\.filters_layout\.addWidget\(self\._view_btn\)', replacement, content, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

# 2. Update inventory_list_dialog.py
path2 = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\dialogs\inventory_list_dialog.py'
with open(path2, 'r', encoding='utf-8') as f:
    c2 = f.read()

# Replace custom add_stock_btn with self.btn_add
if 'self.add_stock_btn = QPushButton("  Add Stock")' in c2:
    rep2 = '''        self.btn_add.clicked.connect(self._open_add_stock)'''
    c2 = re.sub(r'        self\.add_stock_btn = QPushButton.*?\n.*?\n.*?\n.*?\n.*?\n.*?\n.*?\n.*?\n.*?\n.*?\n.*?\n        self\.add_stock_btn\.clicked\.connect\(self\._open_add_stock\)', rep2, c2, flags=re.DOTALL)
    c2 = re.sub(r'        self\.report\.filters_layout\.addWidget\(self\.add_stock_btn\)\n', '', c2)
    with open(path2, 'w', encoding='utf-8') as f:
        f.write(c2)

print('Updated dialogs')

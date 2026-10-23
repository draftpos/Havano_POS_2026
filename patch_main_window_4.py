import re

file_path = r'c:\Users\user\Desktop\Havano_POS_2026-main\views\main_window.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

injection = """        dining_option = ""
        if hasattr(self, "_get_pos_rule") and self._get_pos_rule("takeaway_or_sitin", default=False):
            from views.dialogs.dining_option_dialog import is_dining_prompt_hidden, DiningOptionDialog
            from PySide6.QtWidgets import QDialog
            if is_dining_prompt_hidden():
                dining_option = "TAKE AWAY"
            else:
                try:
                    dlg_dining = DiningOptionDialog(self)
                    if dlg_dining.exec() != QDialog.Accepted or not dlg_dining.selected_option:
                        return
                    dining_option = dlg_dining.selected_option
                except Exception as e:
                    print(f"[POSView] DiningOptionDialog error: {e}")

        is_restaurant = getattr(self, "_restaurant_mode", False)"""

content = content.replace('        is_restaurant = getattr(self, "_restaurant_mode", False)', injection)
content = content.replace('prefill_amounts=_prefill,\n            )', 'prefill_amounts=_prefill,\n                dining_option=dining_option,\n            )')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched main_window.py with dining option!")

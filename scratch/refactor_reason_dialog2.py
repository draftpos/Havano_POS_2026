# -*- coding: utf-8 -*-
with open('views/main_window.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('action_text: str = f"{checkmark}  Cancel KOT"', 'action_text: str = "\u2713  Cancel KOT"')
code = code.replace('reason = self._show_cancel_reason_dialog(order_data["id"], predefined_reasons, title="Modify Reason", action_text=f"{checkmark}  Modify KOT", is_danger=False)', 'reason = self._show_cancel_reason_dialog(order_data["id"], predefined_reasons, title="Modify Reason", action_text="\u2713  Modify KOT", is_danger=False)')

with open('views/main_window.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Done fixing literals')

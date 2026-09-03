# -*- coding: utf-8 -*-
import re

with open('views/main_window.py', 'r', encoding='utf-8') as f:
    code = f.read()

checkmark = chr(0x2713)
ellipsis = chr(0x2026)

# 1. Update _on_kot_action to use _show_cancel_reason_dialog
code = re.sub(
    r'(if\s+rs\.get\("require_modify_reason"\):.*?from\s+PySide6\.QtWidgets\s+import\s+QInputDialog\s*reason,\s*ok\s*=\s*QInputDialog\.getText\([^)]+\)\s*)if\s+not\s+ok\s+or\s+not\s+reason\.strip\(\):',
    f'''if rs.get("require_modify_reason"):
                from models.restaurant_order import get_cancel_reasons
                predefined_reasons = get_cancel_reasons()
                reason = self._show_cancel_reason_dialog(order_data["id"], predefined_reasons, title="Modify Reason", action_text=f"{{checkmark}}  Modify KOT", is_danger=False)
                if reason is None or not reason.strip():''',
    code, flags=re.DOTALL
)

# 2. Add parameters to _show_cancel_reason_dialog
code = re.sub(
    r'def _show_cancel_reason_dialog\(self,\s*order_id:\s*int,\s*predefined:\s*list\):',
    f'def _show_cancel_reason_dialog(self, order_id: int, predefined: list, title: str = "Cancel Reason", action_text: str = f"{{checkmark}}  Cancel KOT", is_danger: bool = True):',
    code
)

# 3. Update the title in the dialog
code = re.sub(
    r'dlg\.setWindowTitle\("Cancel Reason"\)',
    r'dlg.setWindowTitle(title)',
    code
)

# 4. Update the placeholder text
code = re.sub(
    f'reason_input\\.setPlaceholderText\\("Enter cancellation reason{{ellipsis}}"\\)',
    r'reason_input.setPlaceholderText(f"Enter {title.lower()}{chr(0x2026)}")',
    code
)

# 5. Update the action button text and color
code = re.sub(
    f'ok_btn = QPushButton\\("{{checkmark}}  Cancel KOT"\\)',
    r'ok_btn = QPushButton(action_text)',
    code
)
code = re.sub(
    r'background:\s*\{DANGER\};\s*color:\s*\{WHITE\};\s*border:\s*none;',
    r'background: {DANGER if is_danger else ACCENT}; color: {WHITE}; border: none;',
    code
)
code = re.sub(
    r'QPushButton:hover\s*\{\s*background:\s*\{DANGER_H\};\s*\}',
    r'QPushButton:hover { background: {DANGER_H if is_danger else ACCENT_H}; }',
    code
)

with open('views/main_window.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Done patching main_window.py')

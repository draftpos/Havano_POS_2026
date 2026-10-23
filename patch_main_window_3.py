import sys
import re

file_path = r'c:\Users\user\Desktop\Havano_POS_2026-main\views\main_window.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

expenses_method = '''
    def _on_expenses_clicked(self):
        try:
            from views.dialogs.expense_dialog import ProcessExpenseDialog
            parent_window = getattr(self, "parent_window", None) or getattr(self, "parent", lambda: self)() 
            if not isinstance(parent_window, type(self)):
                parent_window = self
            dlg = ProcessExpenseDialog(parent=parent_window)
            dlg.exec()
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to open Expenses dialog: {e}")
'''

# 8 spaces of base indentation in this raw string to match the destination
monitors_and_expenses_ui = '''
        # ── Expenses button ───────────────────────────────────────────────────
        self.expenses_btn = _nb("Expenses", self._on_expenses_clicked, color=ORANGE, hov=AMBER)
        self.expenses_btn.setToolTip("Record Till Expenses")
        layout.addWidget(self.expenses_btn)
        layout.addSpacing(4)
        try:
            if not getattr(adv_settings, "enableExpenses", False):
                self.expenses_btn.setVisible(False)
        except Exception:
            self.expenses_btn.setVisible(False)

        # ── Monitors dropdown ────────────────────────────────────────────────────
        self.monitors_menu_btn = HoverMenuButton("Monitors", color=NAVY_2, hov=NAVY_3, height=NAV_H)
        
        def _launch_kds(m):
            from views.restaurant_kds import KitchenWindow, ReadyBoardWindow, UnifiedMonitorWindow
            if m == "k":
                if not hasattr(self, "_kw") or self._kw is None:
                    self._kw = KitchenWindow()
                self._kw.show()
                self._kw.raise_()
                self._kw.activateWindow()
            elif m == "d":
                if not hasattr(self, "_db") or self._db is None:
                    self._db = ReadyBoardWindow()
                self._db.show()
                self._db.raise_()
                self._db.activateWindow()
            elif m == "u":
                if not hasattr(self, "_um") or self._um is None:
                    self._um = UnifiedMonitorWindow()
                self._um.show()
                self._um.raise_()
                self._um.activateWindow()

        self.monitors_menu_btn.addItem("Kitchen Display (KDS)", lambda: _launch_kds("k"))
        self.monitors_menu_btn.addItem("Ready Board (Dispatch)", lambda: _launch_kds("d"))
        self.monitors_menu_btn.addItem("Unified Monitor", lambda: _launch_kds("u"))
        
        layout.addWidget(self.monitors_menu_btn)
        layout.addSpacing(4)
        
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT setting_value FROM pos_settings WHERE setting_key IN ('enable_kds_websocket', 'takeaway_monitors')")
            rows = cur.fetchall()
            conn.close()
            
            kds_enabled = False
            for row in rows:
                if str(row[0]) == "1":
                    kds_enabled = True
                    break
            if not kds_enabled:
                self.monitors_menu_btn.setVisible(False)
        except Exception:
            self.monitors_menu_btn.setVisible(False)
'''

# Insert the expenses method next to _on_quotation
content = re.sub(
    r'(    def _on_quotation\(self\):)',
    lambda m: expenses_method.strip('\n') + '\n\n' + m.group(1),
    content
)

# Replace Options button definitions
# Because monitors_and_expenses_ui already has 8 spaces indent matching options_menu_btn block,
# we just inject it directly without lstrip.
content = re.sub(
    r'([ \t]+)(options_menu_btn = HoverMenuButton\("Options)',
    lambda m: monitors_and_expenses_ui.strip('\n') + '\n' + m.group(1) + m.group(2),
    content
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Patched main_window.py successfully with correct indentation!')

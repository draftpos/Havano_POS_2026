import sys
import re

file_path = r'c:\Users\user\Desktop\Havano_POS_2026-main\views\main_window.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

expenses_code = '''
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
'''

monitors_code = '''
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
          
          # Hide Monitors button if KDS & Takeaway monitors are both disabled
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

# First instance block replacement:
content = re.sub(
    r'(# "\?"\? Options dropdown \(replaces right-panel Options button\) [^\n]*\n\s*options_menu_btn = HoverMenuButton)',
    lambda m: expenses_code + '\n' + monitors_code + '\n' + m.group(1),
    content,
    count=1
)

# Replace other instances (using simpler regex matching the hover button instantiation)
# We can just match the quote button visibility block to insert after it.
content = re.sub(
    r'(quote_btn\.setVisible\(False\)\s*\n\s*)# [^\n]*Options dropdown[^\n]*\n\s*options_menu_btn = HoverMenuButton',
    lambda m: m.group(1) + expenses_code + '\n' + monitors_code + '\n          # Options dropdown\n          options_menu_btn = HoverMenuButton',
    content
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Expenses and Monitors buttons added to main_window.py.')

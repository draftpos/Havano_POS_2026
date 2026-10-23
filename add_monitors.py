import sys
import re

file_path = r'c:\Users\user\Desktop\Havano_POS_2026-main\views\new_d.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

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

# Insert monitors code before the first options_menu_btn block
content = re.sub(
    r'(# ── Options dropdown \(replaces right-panel Options button\) ───────────────\n\s*options_menu_btn = HoverMenuButton\(\"Options\")',
    lambda m: monitors_code + '\n' + m.group(1),
    content,
    count=1
)

# Insert monitors code before the second options_menu_btn block
content = re.sub(
    r'(# ── Options dropdown ──────────────────────────────────────────────────────\n\s*options_menu_btn = HoverMenuButton\(\"Options\")',
    lambda m: monitors_code + '\n' + m.group(1),
    content,
    count=1
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Monitors button added.')

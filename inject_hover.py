import sys

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

btn_code = '''
class HoverMenuButton(QPushButton):
    def __init__(self, text: str, color=None, hov=None, height=26, parent=None):
        super().__init__(text, parent)
        self._bg  = color or NAVY_2
        self._hov = hov   or NAVY_3
        self._menu = QMenu(self)
        self._menu.setStyleSheet(f"""
            QMenu {{ background-color: {WHITE}; border: 1px solid {BORDER}; border-radius: 6px; padding: 4px 0; font-size: 12px; color: {DARK_TEXT}; }}
            QMenu::item {{ padding: 8px 22px; border-radius: 4px; margin: 1px 4px; }}
            QMenu::item:selected {{ background-color: {ACCENT}; color: {WHITE}; }}
            QMenu::separator {{ height: 1px; background: {BORDER}; margin: 3px 10px; }}
        """)
        self.setFixedHeight(height)
        self.setCursor(Qt.PointingHandCursor)
        self._apply_style(False)
        self.clicked.connect(self._show_menu)

    def addItem(self, label: str, callback):
        a = QAction(label, self)
        a.triggered.connect(callback)
        self._menu.addAction(a)

    def addSeparator(self):
        self._menu.addSeparator()

    def _apply_style(self, hovered: bool):
        bg = self._hov if hovered else self._bg
        self.setStyleSheet(f"""
            QPushButton {{ background-color: {bg}; color: {WHITE}; border: none; border-radius: 3px; font-size: 11px; font-weight: bold; padding: 0 9px; }}
        """)

    def _show_menu(self):
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._apply_style(True)
        self._menu.exec(pos)
        self._apply_style(False)

    def enterEvent(self, event):
        super().enterEvent(event)
        self._show_menu()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._apply_style(False)
'''

if 'class HoverMenuButton(' not in content:
    idx = content.find('def decode_weight_barcode')
    if idx != -1:
        new_content = content[:idx] + btn_code + '\n' + content[idx:]
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print('Injected HoverMenuButton.')
    else:
        print('Could not find anchor.')
else:
    print('HoverMenuButton already exists.')

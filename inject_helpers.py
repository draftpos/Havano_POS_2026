import sys

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

helpers_code = '''
def coming_soon(parent, feature="This feature"):
    msg = QMessageBox(parent)
    msg.setWindowTitle("Not Yet Implemented")
    msg.setText(feature)
    msg.setInformativeText("This feature is not yet wired to the database.")
    msg.setIcon(QMessageBox.Information)
    msg.setStyleSheet(f"""
        QMessageBox {{ background-color: {WHITE}; }}
        QLabel {{ color: {DARK_TEXT}; font-size: 13px; }}
        QPushButton {{
            background-color: {ACCENT}; color: {WHITE}; border: none;
            border-radius: 5px; padding: 8px 22px; font-size: 13px; min-width: 80px;
        }}
        QPushButton:hover {{ background-color: {ACCENT_H}; }}
    """)
    msg.exec()

def hr(horizontal=True):
    line = QFrame()
    line.setFrameShape(QFrame.HLine if horizontal else QFrame.VLine)
    line.setStyleSheet(f"background-color: {BORDER}; border: none;")
    if horizontal:
        line.setFixedHeight(1)
    else:
        line.setFixedWidth(1)
    return line

def nav_pill(text, active=False):
    btn = QPushButton(text)
    btn.setFixedHeight(34)
    btn.setCursor(Qt.PointingHandCursor)
    if active:
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WHITE}; color: {NAVY};
                border: none; border-radius: 4px;
                font-size: 12px; font-weight: bold; padding: 0 20px;
            }}
            QPushButton:hover {{ background-color: {LIGHT}; }}
        """)
    else:
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {WHITE};
                border: 1px solid rgba(255,255,255,0.3); border-radius: 4px;
                font-size: 12px; padding: 0 20px;
            }}
            QPushButton:hover {{ background-color: {NAVY_2}; border-color: {WHITE}; }}
        """)
    return btn

def navy_btn(text, height=36, font_size=12, width=None, color=None, hover=None):
    bg  = color or NAVY
    hov = hover or NAVY_2
    btn = QPushButton(text)
    btn.setFixedHeight(height)
    if width:
        btn.setFixedWidth(width)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: {WHITE}; border: none;
            border-radius: 5px; font-size: {font_size}px; font-weight: bold; padding: 0 14px;
        }}
        QPushButton:hover   {{ background-color: {hov}; }}
        QPushButton:pressed {{ background-color: {NAVY_3}; }}
    """)
    return btn

def numpad_btn(text, kind="digit"):
    btn = QPushButton(text)
    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    btn.setCursor(Qt.PointingHandCursor)
    styles = {
        "digit": (WHITE,   LIGHT,    DARK_TEXT),
        "op":    (NAVY_2,  NAVY_3,   WHITE),
        "clear": (DANGER,  DANGER_H, WHITE),
        "del":   (NAVY_2,  NAVY_3,   WHITE),
        "enter": (ACCENT,  ACCENT_H, WHITE),
        "cash":  (NAVY_3,  NAVY_2,   WHITE),
    }
    bg, hov, fg = styles.get(kind, styles["digit"])
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: {fg};
            border: 1px solid {BORDER}; border-radius: 6px;
            font-size: 16px; font-weight: bold;
        }}
        QPushButton:hover   {{ background-color: {hov}; }}
        QPushButton:pressed {{ background-color: {NAVY_3}; color: {WHITE}; }}
    """)
    return btn
'''

if 'def hr(' not in content:
    idx = content.find('def decode_weight_barcode')
    if idx != -1:
        new_content = content[:idx] + helpers_code + '\n' + content[idx:]
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print('Injected helpers.')
    else:
        print('Could not find anchor.')
else:
    print('helpers already exists.')

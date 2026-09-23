import qtawesome as qta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor

import json
from pathlib import Path

_SETTINGS_FILE = Path("app_data/sql_settings.json")
_HIDE_DINING_PROMPT = False

def set_dining_prompt_hidden(hidden: bool):
    global _HIDE_DINING_PROMPT
    _HIDE_DINING_PROMPT = hidden
    try:
        data = {}
        if _SETTINGS_FILE.exists():
            data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        data["hide_dining_prompt"] = bool(hidden)
        _SETTINGS_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
    except Exception as e:
        print(f"[DiningOptionDialog] Error writing to sql_settings.json: {e}")

def is_dining_prompt_hidden() -> bool:
    global _HIDE_DINING_PROMPT
    if _HIDE_DINING_PROMPT:
        return True
    try:
        if _SETTINGS_FILE.exists():
            data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
            val = data.get("hide_dining_prompt")
            if val is True or str(val).lower() in ("true", "1", "yes"):
                _HIDE_DINING_PROMPT = True
                return True
    except Exception:
        pass
    return False

class DiningOptionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Dining Option")
        self.setFixedSize(520, 360)
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.selected_option = ""
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)

        card = QWidget()
        card.setStyleSheet("background: #ffffff; border-radius: 20px;")
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 10)
        card.setGraphicsEffect(shadow)

        vl = QVBoxLayout(card)
        vl.setContentsMargins(30, 25, 30, 25)
        vl.setSpacing(20)

        # Header
        lbl_title = QLabel("Dining Option")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("color: #1a5fb4; font-size: 24px; font-weight: 900; letter-spacing: 1px;")
        vl.addWidget(lbl_title)

        # Buttons
        hl = QHBoxLayout()
        hl.setSpacing(20)

        # Take Away
        self.btn_takeaway = QPushButton(" TAKE AWAY (1)")
        self.btn_takeaway.setIcon(qta.icon("fa5s.shopping-bag", color="white"))
        self.btn_takeaway.setIconSize(QSize(36, 36))
        self.btn_takeaway.setCursor(Qt.PointingHandCursor)
        self.btn_takeaway.setFixedHeight(120)
        self.btn_takeaway.setToolTip("Select Take Away (Shortcut: 1 or T)")
        self.btn_takeaway.setStyleSheet("""
            QPushButton {
                background: #f59e0b; color: white; border: none; border-radius: 15px;
                font-size: 20px; font-weight: bold;
            }
            QPushButton:hover { background: #d97706; }
        """)
        self.btn_takeaway.clicked.connect(lambda: self._select("TAKE AWAY"))

        # Sit In
        self.btn_sitin = QPushButton(" SIT IN (2)")
        self.btn_sitin.setIcon(qta.icon("fa5s.utensils", color="white"))
        self.btn_sitin.setIconSize(QSize(36, 36))
        self.btn_sitin.setCursor(Qt.PointingHandCursor)
        self.btn_sitin.setFixedHeight(120)
        self.btn_sitin.setToolTip("Select Sit In (Shortcut: 2 or S)")
        self.btn_sitin.setStyleSheet("""
            QPushButton {
                background: #10b981; color: white; border: none; border-radius: 15px;
                font-size: 20px; font-weight: bold;
            }
            QPushButton:hover { background: #059669; }
        """)
        self.btn_sitin.clicked.connect(lambda: self._select("SIT IN"))

        hl.addWidget(self.btn_takeaway)
        hl.addWidget(self.btn_sitin)
        vl.addLayout(hl)

        # Bottom Actions Row (Cancel & Hide/Fast Checkout)
        bottom_hl = QHBoxLayout()
        bottom_hl.setSpacing(12)

        # Cancel Button
        btn_cancel = QPushButton("Cancel (Esc)")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(45)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #f1f5f9; color: #64748b; border: none; border-radius: 10px;
                font-size: 15px; font-weight: bold;
            }
            QPushButton:hover { background: #e2e8f0; color: #475569; }
        """)
        btn_cancel.clicked.connect(self.reject)

        # Hide (Fast Checkout) Button
        self.btn_hide = QPushButton("Hide (Fast Checkout)")
        self.btn_hide.setCursor(Qt.PointingHandCursor)
        self.btn_hide.setFixedHeight(45)
        self.btn_hide.setToolTip("Hide this prompt for future sales until POS rule is toggled off and on again")
        self.btn_hide.setStyleSheet("""
            QPushButton {
                background: #fef2f2; color: #dc2626; border: 1px solid #fca5a5; border-radius: 10px;
                font-size: 15px; font-weight: bold;
            }
            QPushButton:hover { background: #fee2e2; color: #b91c1c; }
        """)
        self.btn_hide.clicked.connect(self._on_hide_clicked)

        bottom_hl.addWidget(btn_cancel, 1)
        bottom_hl.addWidget(self.btn_hide, 1)
        vl.addLayout(bottom_hl)

        root.addWidget(card)

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            try:
                parent_geo = self.parent().frameGeometry()
                geo = self.frameGeometry()
                geo.moveCenter(parent_geo.center())
                self.move(geo.topLeft())
            except Exception:
                pass

    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key_Escape:
            self.reject()
        elif k in (Qt.Key_1, Qt.Key_T):
            self._select("TAKE AWAY")
        elif k in (Qt.Key_2, Qt.Key_S):
            self._select("SIT IN")
        elif k in (Qt.Key_H,):
            self._on_hide_clicked()
        else:
            super().keyPressEvent(event)

    def _select(self, option):
        self.selected_option = option
        self.accept()

    def _on_hide_clicked(self):
        set_dining_prompt_hidden(True)
        self.selected_option = "TAKE AWAY"
        self.accept()

import qtawesome as qta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor

class DiningOptionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Dining Option")
        self.setFixedSize(500, 350)
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
        vl.setContentsMargins(30, 30, 30, 30)
        vl.setSpacing(25)

        # Header
        lbl_title = QLabel("Dining Option")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("color: #1a5fb4; font-size: 24px; font-weight: 900; letter-spacing: 1px;")
        vl.addWidget(lbl_title)

        # Buttons
        hl = QHBoxLayout()
        hl.setSpacing(20)

        # Take Away
        self.btn_takeaway = QPushButton(" TAKE AWAY")
        self.btn_takeaway.setIcon(qta.icon("fa5s.shopping-bag", color="white"))
        self.btn_takeaway.setIconSize(QSize(36, 36))
        self.btn_takeaway.setCursor(Qt.PointingHandCursor)
        self.btn_takeaway.setFixedHeight(120)
        self.btn_takeaway.setStyleSheet("""
            QPushButton {
                background: #f59e0b; color: white; border: none; border-radius: 15px;
                font-size: 20px; font-weight: bold;
            }
            QPushButton:hover { background: #d97706; }
        """)
        self.btn_takeaway.clicked.connect(lambda: self._select("TAKE AWAY"))

        # Sit In
        self.btn_sitin = QPushButton(" SIT IN")
        self.btn_sitin.setIcon(qta.icon("fa5s.utensils", color="white"))
        self.btn_sitin.setIconSize(QSize(36, 36))
        self.btn_sitin.setCursor(Qt.PointingHandCursor)
        self.btn_sitin.setFixedHeight(120)
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

        # Cancel
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(45)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #f1f5f9; color: #64748b; border: none; border-radius: 10px;
                font-size: 16px; font-weight: bold;
            }
            QPushButton:hover { background: #e2e8f0; color: #475569; }
        """)
        btn_cancel.clicked.connect(self.reject)
        vl.addWidget(btn_cancel)

        root.addWidget(card)

    def _select(self, option):
        self.selected_option = option
        self.accept()

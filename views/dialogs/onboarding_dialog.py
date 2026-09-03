# views/dialogs/onboarding_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QStackedWidget, QWidget, QFrame,
    QLineEdit, QFormLayout, QMessageBox, QSizePolicy,
    QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor
import qtawesome as qta
import json
from database.db import get_connection

# Design constants (matching login_dialog.py)
from theme import *

class OnboardingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Havano POS Onboarding")
        self.setFixedSize(720, 580)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.mode = None # "standard" or "offline"
        self._build_ui()

    def _build_ui(self):
        # Shadow/Main container
        self.container = QFrame(self)
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet(f"""
            QFrame#MainContainer {{
                background-color: {WHITE};
                border-radius: 20px;
            }}
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60); shadow.setXOffset(0); shadow.setYOffset(16)
        shadow.setColor(QColor(13, 31, 60, 100))
        self.container.setGraphicsEffect(shadow)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.addWidget(self.container)
        
        content_layout = QVBoxLayout(self.container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Header
        header = QWidget()
        header.setFixedHeight(120)
        header.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {NAVY}, stop:0.6 {NAVY_2}, stop:1 {NAVY_3});
                border-top-left-radius:20px; border-top-right-radius:20px;
            }}
        """)
        hl = QVBoxLayout(header)
        hl.setContentsMargins(20, 16, 20, 16)
        hl.setSpacing(4)
        
        top_row = QHBoxLayout()
        
        dummy = QWidget()
        dummy.setFixedSize(32, 32)
        dummy.setStyleSheet("background: transparent;")
        top_row.addWidget(dummy)
        
        title_lbl = QLabel("Havano POS Setup")
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(f"color: {WHITE}; font-size: 22px; font-weight: 800; background: transparent; letter-spacing: 1px;")
        top_row.addWidget(title_lbl, 1)
        
        close_btn = QPushButton()
        close_btn.setIcon(qta.icon("fa5s.times", color=WHITE))
        close_btn.setIconSize(QSize(20, 20))
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("QPushButton { background: transparent; border: none; } QPushButton:hover { background: rgba(255, 255, 255, 0.2); border-radius: 16px; }")
        close_btn.clicked.connect(self.reject)
        top_row.addWidget(close_btn)
        
        hl.addLayout(top_row)
        
        sub_lbl = QLabel("Choose how you would like to operate your system")
        sub_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl.setStyleSheet(f"color: {MID}; font-size: 13px; background: transparent;")
        hl.addWidget(sub_lbl)
        
        content_layout.addWidget(header)
        
        # Accent line
        al = QFrame()
        al.setFixedHeight(3)
        al.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {NAVY_3}, stop:0.3 {ACCENT},
                stop:0.7 {ACCENT_H}, stop:1 {NAVY_3});
        """)
        content_layout.addWidget(al)
        
        # Stacked Widget
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)
        
        # Step 1: Mode Selection
        self.stack.addWidget(self._create_mode_selection_page())

    def _create_mode_selection_page(self):
        page = QWidget()
        page.setStyleSheet(f"background: {OFF_WHITE}; border-bottom-left-radius: 20px; border-bottom-right-radius: 20px;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(20)
        
        # Havano Card (internally uses Odoo logic)
        self.odoo_card = self._create_mode_card(
            "Havano", 
            "Connects to Havano ERP for real-time inventory and sales sync.",
            "fa5s.cloud",
            ACCENT
        )
        self.odoo_card.clicked.connect(self._select_odoo)
        cards_layout.addWidget(self.odoo_card)

        # Frappe Card
        self.frappe_card = self._create_mode_card(
            "Frappe", 
            "Connects to Frappe ERP for real-time inventory and sales sync.",
            "fa5s.server",
            "#F59E0B" # Orange
        )
        self.frappe_card.clicked.connect(self._select_frappe)
        cards_layout.addWidget(self.frappe_card)
        
        # SaaS Card
        self.saas_card = self._create_mode_card(
            "SaaS Mode", 
            "Connects to SaaS ERP for real-time inventory and sales sync.",
            "fa5s.cloud",
            "#8B5CF6" # Purple
hhhhhhhhhhhhg
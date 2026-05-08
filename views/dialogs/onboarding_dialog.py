# views/dialogs/onboarding_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QStackedWidget, QWidget, QFrame,
    QLineEdit, QFormLayout, QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt, QSize
import qtawesome as qta
import json
from database.db import get_connection

# Design constants
WHITE = "#FFFFFF"
OFF_WHITE = "#F8FAFC"
NAVY = "#0F172A"
NAVY_LIGHT = "#1E293B"
ACCENT = "#2563EB"
ACCENT_HOVER = "#1D4ED8"
BORDER = "#E2E8F0"
MUTED = "#64748B"
SUCCESS = "#10B981"
DANGER = "#EF4444"

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
                border-radius: 12px;
                border: 1px solid {BORDER};
            }}
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(self.container)
        
        content_layout = QVBoxLayout(self.container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Header
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet(f"background-color: {NAVY}; border-top-left-radius: 11px; border-top-right-radius: 11px;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)
        
        title_lbl = QLabel("Havano POS Setup")
        title_lbl.setStyleSheet(f"color: {WHITE}; font-size: 18px; font-weight: bold; background: transparent;")
        hl.addWidget(title_lbl)
        hl.addStretch()
        
        content_layout.addWidget(header)
        
        # Stacked Widget
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)
        
        # Step 1: Mode Selection
        self.stack.addWidget(self._create_mode_selection_page())
        
        # Step 2: Company Setup (Offline)
        self.stack.addWidget(self._create_company_setup_page())
        
        # Step 3: Success
        self.stack.addWidget(self._create_success_page())

    def _create_mode_selection_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        
        intro_lbl = QLabel("Welcome to Havano POS")
        intro_lbl.setAlignment(Qt.AlignCenter)
        intro_lbl.setStyleSheet(f"color: {NAVY}; font-size: 24px; font-weight: 800; background: transparent;")
        layout.addWidget(intro_lbl)
        
        sub_lbl = QLabel("Please choose how you would like to operate your system.")
        sub_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl.setStyleSheet(f"color: {MUTED}; font-size: 14px; background: transparent;")
        layout.addWidget(sub_lbl)
        
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(20)
        
        # Standard Card
        self.standard_card = self._create_mode_card(
            "Standard Mode", 
            "Cloud synchronization enabled.\nConnects to Havano ERP for real-time inventory and sales sync.",
            "fa5s.cloud",
            ACCENT
        )
        self.standard_card.clicked.connect(self._select_standard)
        cards_layout.addWidget(self.standard_card)
        
        # Offline Card
        self.offline_card = self._create_mode_card(
            "Offline-Only Mode", 
            "Standalone operation.\nNo cloud sync required. Ideal for remote areas or private shops.",
            "fa5s.plug",
            SUCCESS
        )
        self.offline_card.clicked.connect(self._select_offline)
        cards_layout.addWidget(self.offline_card)
        
        layout.addLayout(cards_layout)
        layout.addStretch()
        
        return page

    def _create_mode_card(self, title, description, icon_name, color):
        btn = QPushButton()
        btn.setFixedHeight(220)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WHITE};
                border: 2px solid {BORDER};
                border-radius: 12px;
                padding: 20px;
                text-align: center;
            }}
            QPushButton:hover {{
                border: 2px solid {color};
                background-color: {OFF_WHITE};
            }}
        """)
        
        l = QVBoxLayout(btn)
        l.setSpacing(12)
        
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon(icon_name, color=color).pixmap(QSize(48, 48)))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent;")
        l.addWidget(icon_lbl)
        
        t_lbl = QLabel(title)
        t_lbl.setAlignment(Qt.AlignCenter)
        t_lbl.setStyleSheet(f"color: {NAVY}; font-size: 16px; font-weight: bold; background: transparent;")
        l.addWidget(t_lbl)
        
        d_lbl = QLabel(description)
        d_lbl.setAlignment(Qt.AlignCenter)
        d_lbl.setWordWrap(True)
        d_lbl.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
        l.addWidget(d_lbl)
        
        return btn

    def _create_company_setup_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(50, 30, 50, 30)
        layout.setSpacing(15)
        
        title = QLabel("Company Information")
        title.setStyleSheet(f"color: {NAVY}; font-size: 20px; font-weight: bold; background: transparent;")
        layout.addWidget(title)
        
        desc = QLabel("Enter your business details for receipts and reports.")
        desc.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
        layout.addWidget(desc)
        
        form_frame = QFrame()
        form_frame.setStyleSheet(f"background-color: {OFF_WHITE}; border: 1px solid {BORDER}; border-radius: 8px;")
        form_layout = QFormLayout(form_frame)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(12)
        
        self.comp_name = QLineEdit()
        self.comp_name.setPlaceholderText("e.g. Havano General Store")
        self.comp_addr1 = QLineEdit()
        self.comp_addr2 = QLineEdit()
        self.comp_phone = QLineEdit()
        self.comp_email = QLineEdit()
        self.comp_vat = QLineEdit()
        self.comp_tin = QLineEdit()
        
        form_layout.addRow("Business Name:", self.comp_name)
        form_layout.addRow("Address Line 1:", self.comp_addr1)
        form_layout.addRow("Address Line 2:", self.comp_addr2)
        form_layout.addRow("Phone Number:", self.comp_phone)
        form_layout.addRow("Email Address:", self.comp_email)
        form_layout.addRow("VAT Number:", self.comp_vat)
        form_layout.addRow("TIN Number:", self.comp_tin)
        
        layout.addWidget(form_frame)
        
        btn_row = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.setFixedSize(100, 40)
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        
        next_btn = QPushButton("Finish Setup")
        next_btn.setFixedSize(140, 40)
        next_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT}; color: {WHITE}; font-weight: bold; border: none; border-radius: 6px; }}
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
        """)
        next_btn.clicked.connect(self._save_offline_settings)
        
        btn_row.addWidget(back_btn)
        btn_row.addStretch()
        btn_row.addWidget(next_btn)
        layout.addLayout(btn_row)
        
        return page

    def _create_success_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 60, 40, 40)
        layout.setSpacing(20)
        
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon("fa5s.check-circle", color=SUCCESS).pixmap(QSize(80, 80)))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent;")
        layout.addWidget(icon_lbl)
        
        title = QLabel("All Set!")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {NAVY}; font-size: 24px; font-weight: bold; background: transparent;")
        layout.addWidget(title)
        
        self.success_msg = QLabel("")
        self.success_msg.setAlignment(Qt.AlignCenter)
        self.success_msg.setWordWrap(True)
        self.success_msg.setStyleSheet(f"color: {MUTED}; font-size: 14px; background: transparent;")
        layout.addWidget(self.success_msg)
        
        layout.addStretch()
        
        start_btn = QPushButton("Start Using Havano POS")
        start_btn.setFixedHeight(50)
        start_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {NAVY}; color: {WHITE}; font-weight: bold; font-size: 16px; border-radius: 8px; }}
            QPushButton:hover {{ background-color: {NAVY_LIGHT}; }}
        """)
        start_btn.clicked.connect(self.accept)
        layout.addWidget(start_btn)
        
        return page

    def _select_standard(self):
        self.mode = "standard"
        self._save_mode_setting("0")
        self.success_msg.setText("You have chosen Standard Mode.\nYour system will stay in sync with Havano Cloud.")
        self.stack.setCurrentIndex(2)

    def _select_offline(self):
        self.mode = "offline"
        self.stack.setCurrentIndex(1)

    def _save_mode_setting(self, val):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                MERGE pos_settings AS t
                USING (SELECT 'offline_mode' AS k, ? AS v) AS s ON t.setting_key = s.k
                WHEN MATCHED THEN UPDATE SET setting_value = s.v
                WHEN NOT MATCHED THEN INSERT (setting_key, setting_value) VALUES (s.k, s.v);
            """, (val,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[onboarding] Error saving mode: {e}")

    def _save_offline_settings(self):
        name = self.comp_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Required Field", "Please enter your Business Name.")
            return
            
        try:
            self._save_mode_setting("1")
            
            conn = get_connection()
            cur = conn.cursor()
            
            # Update company_defaults
            cur.execute("""
                UPDATE company_defaults
                SET company_name = ?,
                    address_1 = ?,
                    address_2 = ?,
                    phone = ?,
                    email = ?,
                    vat_number = ?,
                    tin_number = ?
                WHERE id = (SELECT TOP 1 id FROM company_defaults ORDER BY id ASC)
            """, (
                name,
                self.comp_addr1.text().strip(),
                self.comp_addr2.text().strip(),
                self.comp_phone.text().strip(),
                self.comp_email.text().strip(),
                self.comp_vat.text().strip(),
                self.comp_tin.text().strip()
            ))
            
            conn.commit()
            conn.close()
            
            self.success_msg.setText(f"Offline Mode configured for {name}.\nYour system is ready for standalone operation.")
            self.stack.setCurrentIndex(2)
            
        except Exception as e:
            QMessageBox.critical(self, "Setup Error", f"Could not save company details:\n{e}")

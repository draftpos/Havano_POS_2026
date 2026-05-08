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
DARK_TEXT = "#0F172A"

class OnboardingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Havano POS Onboarding")
        self.setFixedSize(520, 600)
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
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
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
        btn.setFixedHeight(180)
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
            QPushButton:pressed {{
                background-color: {BORDER};
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
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(10)
        
        title = QLabel("Company Information")
        title.setStyleSheet(f"color: {NAVY}; font-size: 20px; font-weight: 800; background: transparent;")
        
        subtitle = QLabel("Please provide your business details for the receipt.")
        subtitle.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
        
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)

        # Company Group
        comp_group = QFrame()
        comp_group.setStyleSheet(f"background: {OFF_WHITE}; border-radius: 8px; border: 1px solid {BORDER};")
        comp_l = QVBoxLayout(comp_group)
        comp_l.setContentsMargins(15, 10, 15, 10)
        
        comp_title = QLabel("BUSINESS DETAILS")
        comp_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748B; border: none;")
        comp_l.addWidget(comp_title)

        form = QFormLayout()
        form.setSpacing(15)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setVerticalSpacing(12)
        
        self.comp_name = QLineEdit()
        self.comp_name.setPlaceholderText("e.g. Havano Coffee")
        
        self.comp_addr = QLineEdit()
        self.comp_addr.setPlaceholderText("e.g. 123 Main St, Harare")
        
        self.comp_phone = QLineEdit()
        self.comp_phone.setPlaceholderText("e.g. +263 77 000 0000")
        
        self.comp_email = QLineEdit()
        self.comp_email.setPlaceholderText("e.g. hello@havano.cloud")

        form.addRow("Company Name", self.comp_name)
        form.addRow("Address", self.comp_addr)
        form.addRow("Phone", self.comp_phone)
        form.addRow("Email", self.comp_email)
        
        comp_l.addLayout(form)
        layout.addWidget(comp_group)
        layout.addSpacing(10)

        # User Group
        user_group = QFrame()
        user_group.setStyleSheet(f"background: {OFF_WHITE}; border-radius: 8px; border: 1px solid {BORDER};")
        user_l = QVBoxLayout(user_group)
        user_l.setContentsMargins(15, 10, 15, 10)
        
        user_title = QLabel("ADMIN ACCOUNT")
        user_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748B; border: none;")
        user_l.addWidget(user_title)

        uform = QFormLayout()
        uform.setSpacing(12)
        uform.setVerticalSpacing(8)
        
        self.admin_user = QLineEdit()
        self.admin_user.setPlaceholderText("Admin username")
        self.admin_user.setText("Administrator")
        
        self.admin_pass = QLineEdit()
        self.admin_pass.setPlaceholderText("Password")
        self.admin_pass.setEchoMode(QLineEdit.Password)
        
        self.admin_pin = QLineEdit()
        self.admin_pin.setPlaceholderText("4-digit PIN")
        self.admin_pin.setMaxLength(4)

        uform.addRow("Username", self.admin_user)
        uform.addRow("Password", self.admin_pass)
        uform.addRow("Login PIN", self.admin_pin)
        
        user_l.addLayout(uform)
        layout.addWidget(user_group)
        layout.addStretch()
        
        btn_row = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.setFixedSize(100, 40)
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        
        next_btn = QPushButton("Finish Setup")
        next_btn.setFixedSize(140, 40)
        self.setStyleSheet(f"""
            QDialog {{ background: white; border-radius: 12px; }}
            #MainFrame {{ background: white; border: 1px solid {BORDER}; border-radius: 12px; }}
            QLabel {{ color: {DARK_TEXT}; background: transparent; }}
            QLineEdit {{
                background-color: {WHITE};
                color: {DARK_TEXT};
                border: 1.5px solid {BORDER};
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
            }}
            QLineEdit:focus {{ border: 2px solid {ACCENT}; background-color: #f0f7ff; }}
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
        layout.setContentsMargins(30, 40, 30, 30)
        layout.setSpacing(15)
        
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
        self.success_msg.setText(
            "You have chosen Standard Mode.\n"
            "Your system will stay in sync with Havano Cloud.\n\n"
            "Tip: You can switch to Offline-Only mode at any time from the Login screen."
        )
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
        user = self.admin_user.text().strip()
        pwd  = self.admin_pass.text().strip()
        pin  = self.admin_pin.text().strip()

        if not name:
            QMessageBox.warning(self, "Required Field", "Please enter your Business Name.")
            return
        if not user or not pwd:
            QMessageBox.warning(self, "Required Field", "Please provide Admin credentials.")
            return
            
        try:
            self._save_mode_setting("1")
            
            conn = get_connection()
            cur = conn.cursor()
            
            # Update company_defaults (use first available row)
            cur.execute("""
                UPDATE company_defaults
                SET company_name = ?,
                    address_1 = ?,
                    phone = ?,
                    email = ?
                WHERE id = (SELECT TOP 1 id FROM company_defaults ORDER BY id ASC)
            """, (
                name,
                self.comp_addr.text().strip(),
                self.comp_phone.text().strip(),
                self.comp_email.text().strip()
            ))
            
            conn.commit()
            
            # Create the Admin User
            from models.user import create_user
            create_user(
                username=user,
                password=pwd,
                role="admin",
                pin=pin,
                full_name="System Administrator"
            )
            
            conn.close()
            
            self.success_msg.setText(
                f"Offline Mode configured for {name}.\n"
                "Your system is ready for standalone operation.\n\n"
                "Tip: You can switch back to Standard Mode at any time from the Login screen."
            )
            self.stack.setCurrentIndex(2)
            
        except Exception as e:
            QMessageBox.critical(self, "Setup Error", f"Could not save company details:\n{e}")

import qtawesome as qta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QWidget, QGraphicsDropShadowEffect,
    QApplication, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QClipboard

from utils.hardware import get_machine_id
from utils.license_manager import verify_license, save_license_key

# Colors from Havano Palette
from theme import *

class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Software Activation")
        self.setFixedSize(480, 680)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.machine_id = get_machine_id().replace("-", "").upper()

        from utils.license_manager import get_license_info, get_trial_info
        info = get_license_info()
        status = info.get("status", "Unlicensed")
        key = info.get("key", "")
        expiry = info.get("expiry_date", "")
        
        trial_info = get_trial_info()
        self._show_trial_button = (status != "Active")
        self._trial_status = trial_info["status"]

        self._build_ui()

        if key:
            self.inp_key.setText(key.replace("-", "").upper())
            
        if status == "Active":
            self.title_lbl.setText("License Active")
            self.icon_lbl.setPixmap(qta.icon("fa5s.unlock", color=WHITE).pixmap(40, 40))
            self.inp_key.setReadOnly(True)
            self.btn_activate.setText("System is Fully Licensed")
            self.btn_activate.setEnabled(False)
            self.btn_activate.setStyleSheet(f"""
                QPushButton {{
                    background:{SUCCESS}; color:{WHITE}; font-size:15px; font-weight:bold;
                    border-radius:12px; border:none; letter-spacing: 1px;
                }}
            """)
            self.lbl_status.setText(f"Status: {status}")
            self.lbl_status.setStyleSheet(f"color:{SUCCESS}; font-size:14px; font-weight:bold;")
            self.lbl_expiry.setText(f"Valid Until: {expiry}")
        elif status == "Expired":
            self.title_lbl.setText("License Expired")
            self.icon_lbl.setPixmap(qta.icon("fa5s.exclamation-triangle", color=WHITE).pixmap(40, 40))
            self.lbl_status.setText(f"Status: {status}")
            self.lbl_status.setStyleSheet(f"color:{DANGER}; font-size:14px; font-weight:bold;")
            self.lbl_expiry.setText(f"Expired On: {expiry}")
        elif status != "Unlicensed":
            self.title_lbl.setText("Invalid License")
            self.icon_lbl.setPixmap(qta.icon("fa5s.times-circle", color=WHITE).pixmap(40, 40))
            self.lbl_status.setText(f"Status: {status}")
            self.lbl_status.setStyleSheet(f"color:{DANGER}; font-size:14px; font-weight:bold;")
            if expiry:
                self.lbl_expiry.setText(f"Expiry: {expiry}")
        else:
            if self._trial_status == "Active":
                rem = trial_info.get("days_remaining", 30)
                self.title_lbl.setText("Free Trial Active")
                self.icon_lbl.setPixmap(qta.icon("fa5s.unlock", color=WHITE).pixmap(40, 40))
                self.lbl_status.setText(f"Status: Free Trial Active")
                self.lbl_status.setStyleSheet(f"color:{SUCCESS}; font-size:14px; font-weight:bold;")
                self.lbl_expiry.setText(f"Trial Remaining: {rem} day{'s' if rem != 1 else ''}")
                if hasattr(self, "btn_trial"):
                    self.btn_trial.setText(f"✓ Trial Active ({rem} Days Remaining)")
                    self.btn_trial.setStyleSheet(f"""
                        QPushButton {{
                            background:{SUCCESS}; color:{WHITE}; font-size:15px; font-weight:bold;
                            border-radius:12px; border:none; letter-spacing: 1px;
                        }}
                    """)
            elif self._trial_status == "Expired":
                self.title_lbl.setText("Trial Expired")
                self.lbl_status.setText("Free Trial Expired")
                self.lbl_status.setStyleSheet(f"color:{DANGER}; font-size:14px; font-weight:bold;")
            elif self._trial_status == "Time Travel":
                self.lbl_status.setText("System Clock Error")
                self.lbl_status.setStyleSheet(f"color:{DANGER}; font-size:14px; font-weight:bold;")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)

        # Main Card
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("QFrame#card { background:#ffffff; border-radius:20px; }")

        # Soft Shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60); shadow.setXOffset(0); shadow.setYOffset(16)
        shadow.setColor(QColor(13, 31, 60, 100))
        card.setGraphicsEffect(shadow)

        vl = QVBoxLayout(card)
        vl.setSpacing(0); vl.setContentsMargins(0, 0, 0, 0)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(140)
        hdr.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {NAVY}, stop:0.6 {NAVY_2}, stop:1 {NAVY_3});
                border-top-left-radius:20px; border-top-right-radius:20px;
            }}
        """)
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(0, 12, 12, 10); hl.setSpacing(0)

        # Top row with Minimize and Close buttons
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addStretch()
        

        
        self.close_btn = QPushButton()
        self.close_btn.setIcon(qta.icon("fa5s.times", color=WHITE))
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background:rgba(255,255,255,0.15); border:none;
                border-radius:16px;
            }}
            QPushButton:hover {{ background:{DANGER}; }}
        """)
        self.close_btn.clicked.connect(self.reject)
        top_row.addWidget(self.close_btn)
        hl.addLayout(top_row)

        # Title
        title_box = QVBoxLayout()
        title_box.setAlignment(Qt.AlignCenter)
        title_box.setSpacing(5)
        
        self.icon_lbl = QLabel()
        self.icon_lbl.setPixmap(qta.icon("fa5s.lock", color=WHITE).pixmap(40, 40))
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_lbl.setStyleSheet("background: transparent;")
        title_box.addWidget(self.icon_lbl)
        
        self.title_lbl = QLabel("System Locked")
        self.title_lbl.setAlignment(Qt.AlignCenter)
        self.title_lbl.setStyleSheet(f"color:{WHITE}; font-size:22px; font-weight:800; background:transparent; letter-spacing: 1px;")
        title_box.addWidget(self.title_lbl)
        
        hl.addLayout(title_box)
        vl.addWidget(hdr)

        # ── Body ────────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(30, 25, 30, 30)
        bl.setSpacing(20)
        
        info = QLabel("This software requires a valid license key to continue. Please provide your Machine ID to your administrator to receive a key.")
        info.setWordWrap(True)
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet(f"color:{MUTED}; font-size:13px; line-height: 1.4;")
        bl.addWidget(info)

        # Machine ID Section ─ Prominent panel for offline copying
        mac_lbl = QLabel("YOUR MACHINE ID")
        mac_lbl.setStyleSheet(f"color:{NAVY}; font-size:12px; font-weight:700; letter-spacing:1.5px;")
        bl.addWidget(mac_lbl)

        mac_panel = QFrame()
        mac_panel.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border-radius: 8px;
                border: 1px solid #e2e8f0;
            }
        """)
        mac_panel_layout = QVBoxLayout(mac_panel)
        mac_panel_layout.setContentsMargins(16, 14, 16, 14)
        mac_panel_layout.setSpacing(10)

        self.inp_mac = QLineEdit(self.machine_id)
        self.inp_mac.setReadOnly(True)
        self.inp_mac.setFixedHeight(52)
        self.inp_mac.setAlignment(Qt.AlignCenter)
        self.inp_mac.setStyleSheet("""
            QLineEdit {
                background: transparent; color: #0f172a;
                border: none;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 20px; font-weight: bold; letter-spacing: 2px;
                selection-background-color: #cbd5e1;
            }
        """)
        mac_panel_layout.addWidget(self.inp_mac)

        mac_hint = QLabel("Select the text above or click the button below to copy")
        mac_hint.setAlignment(Qt.AlignCenter)
        mac_hint.setStyleSheet("color: #64748b; font-size: 11px; background: transparent;")
        mac_panel_layout.addWidget(mac_hint)

        self.btn_copy = QPushButton("  Copy Machine ID")
        self.btn_copy.setIcon(qta.icon("fa5s.copy", color="#334155"))
        self.btn_copy.setFixedHeight(38)
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background: #ffffff; color: #334155;
                border-radius: 6px; border: 1px solid #cbd5e1;
                font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background: #f1f5f9; }
        """)
        self.btn_copy.clicked.connect(self._copy_machine_id)
        mac_panel_layout.addWidget(self.btn_copy)

        bl.addWidget(mac_panel)

        # License Key Section
        key_lbl = QLabel("LICENSE KEY")
        key_lbl.setStyleSheet(f"color:{NAVY}; font-size:11px; font-weight:700; letter-spacing:1px;")
        bl.addWidget(key_lbl)
        
        self.inp_key = QLineEdit()
        self.inp_key.setPlaceholderText("XXXXXXXXXXXXXXXXXXXX")
        self.inp_key.setFixedHeight(48)
        self.inp_key.setAlignment(Qt.AlignCenter)
        self.inp_key.setStyleSheet(f"""
            QLineEdit {{
                background:#ffffff; color:{NAVY}; border:2px solid {BORDER};
                border-radius:8px; font-size:16px; font-weight:bold; letter-spacing: 2px;
            }}
            QLineEdit:focus {{ border: 2px solid {ACCENT}; }}
        """)
        bl.addWidget(self.inp_key)

        # Status and Expiry Info
        self.status_box = QWidget()
        sbl = QVBoxLayout(self.status_box)
        sbl.setContentsMargins(0, 5, 0, 0)
        sbl.setSpacing(5)
        
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet(f"color:{MUTED}; font-size:14px; font-weight:bold;")
        sbl.addWidget(self.lbl_status)
        
        self.lbl_expiry = QLabel("")
        self.lbl_expiry.setAlignment(Qt.AlignCenter)
        self.lbl_expiry.setStyleSheet(f"color:{MUTED}; font-size:13px;")
        sbl.addWidget(self.lbl_expiry)
        
        bl.addWidget(self.status_box)

        bl.addStretch()

        # Activate Button
        self.btn_activate = QPushButton("Activate Software")
        self.btn_activate.setFixedHeight(48)
        self.btn_activate.setCursor(Qt.PointingHandCursor)
        self.btn_activate.setStyleSheet(f"""
            QPushButton {{
                background:{SUCCESS}; color:{WHITE}; font-size:15px; font-weight:bold;
                border-radius:12px; border:none; letter-spacing: 1px;
            }}
            QPushButton:hover {{ background:{SUCCESS_H}; }}
        """)
        self.btn_activate.clicked.connect(self._activate)
        bl.addWidget(self.btn_activate)

        if getattr(self, "_show_trial_button", False):
            bl.addSpacing(10)
            self.btn_trial = QPushButton("Activate 30-Day Free Trial")
            self.btn_trial.setFixedHeight(48)
            self.btn_trial.setCursor(Qt.PointingHandCursor)
            self.btn_trial.setStyleSheet(f"""
                QPushButton {{
                    background:{NAVY}; color:{WHITE}; font-size:15px; font-weight:bold;
                    border-radius:12px; border:none; letter-spacing: 1px;
                }}
                QPushButton:hover {{ background:{NAVY_3}; }}
            """)
            self.btn_trial.clicked.connect(self._activate_trial)
            bl.addWidget(self.btn_trial)

        vl.addWidget(body)
        root.addWidget(card)

    def _copy_machine_id(self):
        QApplication.clipboard().setText(self.machine_id)
        self.btn_copy.setIcon(qta.icon("fa5s.check", color="#15803d"))
        self.btn_copy.setText("  Copied!")
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background: #f0fdf4; color: #15803d;
                border-radius: 6px; border: 1px solid #bbf7d0;
                font-size: 13px; font-weight: bold;
            }
        """)
        
        # Reset after 2 seconds
        def reset():
            self.btn_copy.setIcon(qta.icon("fa5s.copy", color="#334155"))
            self.btn_copy.setText("  Copy Machine ID")
            self.btn_copy.setStyleSheet("""
                QPushButton {
                    background: #ffffff; color: #334155;
                    border-radius: 6px; border: 1px solid #cbd5e1;
                    font-size: 13px; font-weight: bold;
                }
                QPushButton:hover { background: #f1f5f9; }
            """)
        QTimer.singleShot(2000, reset)

    def _activate(self):
        raw_key = self.inp_key.text().strip()
        key_clean = raw_key.replace("-", "").replace(" ", "").strip().upper()
        if not key_clean:
            QMessageBox.warning(self, "Missing Key", "Please enter a valid license key.")
            return
            
        if verify_license(key_clean):
            ok = save_license_key(key_clean)   # saves to Registry + DB
            if ok:
                QMessageBox.information(self, "Activated",
                    "✓  License activated successfully!\n\nHavano POS is now fully licensed on this device.")
                self.accept()
            else:
                QMessageBox.warning(self, "Storage Error",
                    "License verified but could not be saved.\nPlease contact support.")
        else:
            self.inp_key.setStyleSheet(f"""
                QLineEdit {{
                    background:#ffffff; color:{DANGER}; border:2px solid {DANGER};
                    border-radius:8px; font-size:16px; font-weight:bold; letter-spacing: 2px;
                }}
            """)
            QMessageBox.critical(self, "Activation Failed", "Invalid or expired license key.\nPlease check the key and try again.")
            
    def _activate_trial(self):
        from utils.license_manager import activate_free_trial
        if activate_free_trial():
            QMessageBox.information(self, "Trial Activated", "✓ Free Trial Activated!\n\nYou have 30 days remaining.")
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to activate trial. Please contact support.")
            
    def closeEvent(self, event):
        self.reject()

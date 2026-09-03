import sys
import uuid
import hashlib
import platform
import subprocess
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QMessageBox, QFrame,
    QGridLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon, QClipboard

# ==============================================================================
# SECURE CONFIGURATION
# ==============================================================================
SECRET_KEY = "HavanoPOS_Super_Secret_Key_2026_!@#"
BASE_DATE = datetime(2024, 1, 1)

# ==============================================================================
# HARDWARE & CRYPTO LOGIC
# ==============================================================================
def get_machine_id() -> str:
    mac = uuid.getnode()
    mac_str = ':'.join(['{:02x}'.format((mac >> e) & 0xff) for e in range(0,12,2)][::-1]).upper()
    
    board = "UNKNOWN"
    if platform.system() == "Windows":
        try:
            out = subprocess.check_output("wmic baseboard get serialnumber", shell=True, text=True)
            lines = out.strip().split('\n')
            if len(lines) > 1 and lines[1].strip() not in ["", "None", "To be filled by O.E.M."]:
                board = lines[1].strip()
        except Exception:
            pass
            
    raw = f"{mac_str}-{board}"
    hashed = hashlib.sha256(raw.encode('utf-8')).hexdigest().upper()
    ch = hashed[:16]
    return f"{ch[:4]}-{ch[4:8]}-{ch[8:12]}-{ch[12:16]}"

def generate_short_license(machine_id: str, days: int) -> str:
    """
    Generates a 20-character license key: XXXXX-XXXXX-XXXXX-XXXXX
    The first 4 characters encode the expiration date.
    The remaining 16 characters are a cryptographic signature tied to the Machine ID.
    """
    machine_id = machine_id.replace("-", "").strip()
    
    # 1. Calculate expiration days since BASE_DATE
    if days >= 9999:
        exp_date = BASE_DATE + timedelta(days=36500) # 100 years
    else:
        exp_date = datetime.now() + timedelta(days=days)
        
    days_since = (exp_date - BASE_DATE).days
    
    # 2. Encode days as 4-character Hex string (supports up to 65535 days = 179 years)
    days_hex = f"{days_since:04X}"
    
    # 3. Cryptographic hash linking Machine ID, Expiration, and Secret
    raw_payload = f"{machine_id}:{days_hex}:{SECRET_KEY}"
    full_hash = hashlib.sha256(raw_payload.encode('utf-8')).hexdigest().upper()
    
    # 4. Combine encoded date (4 chars) + signature (16 chars) = 20 chars total
    sig_hex = full_hash[:16]
    raw_key = days_hex + sig_hex
    
    # 5. Format to XXXXX-XXXXX-XXXXX-XXXXX
    return f"{raw_key[:5]}-{raw_key[5:10]}-{raw_key[10:15]}-{raw_key[15:20]}"

# ==============================================================================
# UI APPLICATION
# ==============================================================================
class LicenseGeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Havano POS - License Generator")
        self.setFixedSize(500, 380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMinimizeButtonHint & ~Qt.WindowMaximizeButtonHint)
        self.setStyleSheet("background-color: #1a5fb4; color: white; font-family: 'Segoe UI', sans-serif;")
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Title
        title = QLabel("Havano POS License Generator")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #ffffff;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Card Layout
        card = QFrame()
        card.setStyleSheet("background-color: #162d52; border-radius: 10px; padding: 15px;")
        form = QGridLayout(card)
        form.setSpacing(15)
        
        # Machine ID Input
        lbl_mac = QLabel("Customer Machine ID:")
        lbl_mac.setStyleSheet("font-size: 13px; font-weight: bold;")
        self.inp_mac = QLineEdit()
        self.inp_mac.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.inp_mac.setStyleSheet("background-color: #ffffff; color: #1a5fb4; padding: 8px; border-radius: 5px; font-size: 14px; font-weight: bold;")
        
        # Auto-detect local machine ID
        local_id = get_machine_id()
        self.inp_mac.setText(local_id)
        
        form.addWidget(lbl_mac, 0, 0)
        form.addWidget(self.inp_mac, 0, 1)
        
        # Duration Input
        lbl_dur = QLabel("License Duration:")
        lbl_dur.setStyleSheet("font-size: 13px; font-weight: bold;")
        self.combo_dur = QComboBox()
        self.combo_dur.addItems(["30 Days (Trial)", "180 Days (6 Months)", "365 Days (1 Year)", "Lifetime (No Expiry)"])
        self.combo_dur.setStyleSheet("""
            QComboBox { background-color: #ffffff; color: #1a5fb4; padding: 8px; border-radius: 5px; font-size: 13px; font-weight: bold; }
            QComboBox::drop-down { border: none; }
        """)
        form.addWidget(lbl_dur, 1, 0)
        form.addWidget(self.combo_dur, 1, 1)
        
        layout.addWidget(card)
        
        # Generate Button
        self.btn_gen = QPushButton("Generate License Key")
        self.btn_gen.setCursor(Qt.PointingHandCursor)
        self.btn_gen.setStyleSheet("""
            QPushButton { background-color: #1a7a3c; color: white; padding: 12px; border-radius: 6px; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background-color: #1f9447; }
        """)
        self.btn_gen.clicked.connect(self.generate_key)
        layout.addWidget(self.btn_gen)
        
        # Result Area
        self.lbl_result = QLabel("")
        self.lbl_result.setAlignment(Qt.AlignCenter)
        self.lbl_result.setStyleSheet("font-size: 22px; font-weight: bold; color: #f9a825; letter-spacing: 2px;")
        self.lbl_result.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.lbl_result)
        
    def generate_key(self):
        machine_id = self.inp_mac.text().strip()
        if not machine_id:
            QMessageBox.warning(self, "Error", "Machine ID cannot be empty.")
            return
            
        dur_text = self.combo_dur.currentText()
        if "30" in dur_text: days = 30
        elif "180" in dur_text: days = 180
        elif "365" in dur_text: days = 365
        else: days = 9999
        
        key = generate_short_license(machine_id, days)
        self.lbl_result.setText(key)
        
        # Auto-copy to clipboard
        QApplication.clipboard().setText(key)
        self.btn_gen.setText("License Generated & Copied to Clipboard!")
        self.btn_gen.setStyleSheet("background-color: #1a5fb4; color: white; padding: 12px; border-radius: 6px; font-size: 14px; font-weight: bold;")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LicenseGeneratorApp()
    window.show()
    sys.exit(app.exec())

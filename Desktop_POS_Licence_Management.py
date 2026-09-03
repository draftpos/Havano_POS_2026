import sys
import uuid
import hashlib
import platform
import subprocess
import sqlite3
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QMessageBox, QFrame,
    QGridLayout, QTableWidget, QTableWidgetItem, QTabWidget, QHeaderView
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon, QClipboard, QColor

# ==============================================================================
# SECURE CONFIGURATION
# ==============================================================================
SECRET_KEY = "HavanoPOS_Super_Secret_Key_2026_!@#"
BASE_DATE = datetime(2024, 1, 1)

# ==============================================================================
# DATABASE LOGIC
# ==============================================================================
DB_PATH = "pos_licenses.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            machine_id TEXT,
            license_key TEXT,
            duration_days INTEGER,
            creation_date TEXT,
            expiry_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_license(customer_name, machine_id, license_key, duration_days, creation_date, expiry_date):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO licenses (customer_name, machine_id, license_key, duration_days, creation_date, expiry_date)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (customer_name, machine_id, license_key, duration_days, creation_date.isoformat(), expiry_date.isoformat()))
    conn.commit()
    conn.close()

def get_all_licenses():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM licenses ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows

# ==============================================================================
# HARDWARE & CRYPTO LOGIC (from licence.py)
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
    machine_id = machine_id.replace("-", "").strip()
    
    if days >= 9999:
        exp_date = BASE_DATE + timedelta(days=36500)
    else:
        exp_date = datetime.now() + timedelta(days=days)
        
    days_since = (exp_date - BASE_DATE).days
    days_hex = f"{days_since:04X}"
    
    raw_payload = f"{machine_id}:{days_hex}:{SECRET_KEY}"
    full_hash = hashlib.sha256(raw_payload.encode('utf-8')).hexdigest().upper()
    
    sig_hex = full_hash[:16]
    raw_key = days_hex + sig_hex
    
    return f"{raw_key[:5]}-{raw_key[5:10]}-{raw_key[10:15]}-{raw_key[15:20]}"

# ==============================================================================
# UI APPLICATION
# ==============================================================================
class LicenseManagementApp(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()
        self.setWindowTitle("Desktop POS Licence Management")
        self.setMinimumSize(900, 600)
        self.setStyleSheet("background-color: #1a5fb4; color: white; font-family: 'Segoe UI', sans-serif;")
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #162d52; background: #1a5fb4; }
            QTabBar::tab { background: #162d52; color: white; padding: 12px 25px; font-size: 14px; font-weight: bold; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
            QTabBar::tab:selected { background: #1a7a3c; }
        """)
        self.setCentralWidget(self.tabs)
        
        self.init_generate_tab()
        self.init_monitor_tab()
        
    def init_generate_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(20)
        
        title = QLabel("Generate New POS License")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        card = QFrame()
        card.setStyleSheet("background-color: #162d52; border-radius: 10px; padding: 20px;")
        form = QGridLayout(card)
        form.setSpacing(15)
        
        # Customer Name
        lbl_name = QLabel("Customer Name:")
        lbl_name.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Enter customer or business name")
        self.inp_name.setStyleSheet("background-color: #ffffff; color: #1a5fb4; padding: 10px; border-radius: 5px; font-size: 14px;")
        
        # Machine ID
        lbl_mac = QLabel("Customer Machine ID:")
        lbl_mac.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.inp_mac = QLineEdit()
        self.inp_mac.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.inp_mac.setStyleSheet("background-color: #ffffff; color: #1a5fb4; padding: 10px; border-radius: 5px; font-size: 14px; font-weight: bold;")
        self.inp_mac.setText(get_machine_id())
        
        # Duration
        lbl_dur = QLabel("License Duration:")
        lbl_dur.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.combo_dur = QComboBox()
        self.combo_dur.addItems(["30 Days (Trial)", "180 Days (6 Months)", "365 Days (1 Year)", "Lifetime (No Expiry)"])
        self.combo_dur.setStyleSheet("""
            QComboBox { background-color: #ffffff; color: #1a5fb4; padding: 10px; border-radius: 5px; font-size: 14px; font-weight: bold; }
            QComboBox::drop-down { border: none; }
        """)
        
        form.addWidget(lbl_name, 0, 0)
        form.addWidget(self.inp_name, 0, 1)
        form.addWidget(lbl_mac, 1, 0)
        form.addWidget(self.inp_mac, 1, 1)
        form.addWidget(lbl_dur, 2, 0)
        form.addWidget(self.combo_dur, 2, 1)
        
        layout.addWidget(card)
        
        self.btn_gen = QPushButton("Generate & Save License")
        self.btn_gen.setCursor(Qt.PointingHandCursor)
        self.btn_gen.setStyleSheet("""
            QPushButton { background-color: #1a7a3c; color: white; padding: 15px; border-radius: 6px; font-size: 16px; font-weight: bold; }
            QPushButton:hover { background-color: #1f9447; }
        """)
        self.btn_gen.clicked.connect(self.generate_key)
        layout.addWidget(self.btn_gen)
        
        self.lbl_result = QLabel("")
        self.lbl_result.setAlignment(Qt.AlignCenter)
        self.lbl_result.setStyleSheet("font-size: 26px; font-weight: bold; color: #f9a825; letter-spacing: 2px;")
        self.lbl_result.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.lbl_result)
        layout.addStretch()
        
        self.tabs.addTab(tab, "Generate License")
        
    def init_monitor_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("License Monitor")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["ID", "Customer", "Machine ID", "License Key", "Duration", "Created", "Expiry", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #162d52; color: white; gridline-color: #2a4365; border: 1px solid #2a4365; border-radius: 5px; font-size: 13px; }
            QHeaderView::section { background-color: #0a172e; color: white; font-weight: bold; padding: 8px; border: 1px solid #2a4365; }
            QTableWidget::item { padding: 8px; }
        """)
        layout.addWidget(self.table)
        
        btn_refresh = QPushButton("Refresh Status")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet("""
            QPushButton { background-color: #1a5fb4; color: white; padding: 10px 20px; border-radius: 5px; font-weight: bold; font-size: 14px;}
            QPushButton:hover { background-color: #2570ce; }
        """)
        btn_refresh.clicked.connect(self.load_licenses)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_refresh)
        layout.addLayout(bottom_layout)
        
        self.tabs.addTab(tab, "Monitor Licenses")
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        self.load_licenses()
        
    def generate_key(self):
        customer_name = self.inp_name.text().strip()
        machine_id = self.inp_mac.text().strip()
        
        if not customer_name:
            QMessageBox.warning(self, "Error", "Customer Name cannot be empty.")
            return
        if not machine_id:
            QMessageBox.warning(self, "Error", "Machine ID cannot be empty.")
            return
            
        dur_text = self.combo_dur.currentText()
        if "30" in dur_text: days = 30
        elif "180" in dur_text: days = 180
        elif "365" in dur_text: days = 365
        else: days = 9999
        
        creation_date = datetime.now()
        if days >= 9999:
            expiry_date = BASE_DATE + timedelta(days=36500)
        else:
            expiry_date = creation_date + timedelta(days=days)
            
        key = generate_short_license(machine_id, days)
        self.lbl_result.setText(key)
        
        # Save to DB
        save_license(customer_name, machine_id, key, days, creation_date, expiry_date)
        
        # Auto-copy to clipboard
        QApplication.clipboard().setText(key)
        self.btn_gen.setText("License Generated & Copied!")
        self.btn_gen.setStyleSheet("background-color: #1a5fb4; color: white; padding: 15px; border-radius: 6px; font-size: 16px; font-weight: bold;")
        
        # Reset button text after 3 seconds
        QTimer.singleShot(3000, lambda: self.btn_gen.setText("Generate & Save License"))
        QTimer.singleShot(3000, lambda: self.btn_gen.setStyleSheet("QPushButton { background-color: #1a7a3c; color: white; padding: 15px; border-radius: 6px; font-size: 16px; font-weight: bold; } QPushButton:hover { background-color: #1f9447; }"))
        
        self.load_licenses()
        
    def on_tab_changed(self, index):
        if index == 1:
            self.load_licenses()
            
    def load_licenses(self):
        rows = get_all_licenses()
        self.table.setRowCount(len(rows))
        
        for row_idx, row_data in enumerate(rows):
            for col_idx, item in enumerate(row_data):
                if col_idx in (5, 6): # Dates
                    try:
                        dt = datetime.fromisoformat(item)
                        display_text = dt.strftime("%Y-%m-%d %H:%M")
                        if dt.year > 2100:
                            display_text = "Lifetime"
                    except:
                        display_text = str(item)
                    table_item = QTableWidgetItem(display_text)
                else:
                    if col_idx == 4 and item >= 9999:
                        table_item = QTableWidgetItem("Lifetime")
                    elif col_idx == 4:
                        table_item = QTableWidgetItem(f"{item} Days")
                    else:
                        table_item = QTableWidgetItem(str(item))
                
                table_item.setFlags(table_item.flags() & ~Qt.ItemIsEditable)
                table_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, col_idx, table_item)
                
            # Status Calculation
            expiry_str = row_data[6]
            status_item = QTableWidgetItem()
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            status_item.setTextAlignment(Qt.AlignCenter)
            try:
                expiry_dt = datetime.fromisoformat(expiry_str)
                now = datetime.now()
                if expiry_dt.year > 2100:
                    status_item.setText("Active (Lifetime)")
                    status_item.setForeground(QColor("#4caf50")) # Green
                elif expiry_dt < now:
                    status_item.setText("Expired")
                    status_item.setForeground(QColor("#f44336")) # Red
                else:
                    days_left = (expiry_dt - now).days
                    if days_left <= 7:
                        status_item.setText(f"Expiring ({days_left}d)")
                        status_item.setForeground(QColor("#ffeb3b")) # Yellow
                    else:
                        status_item.setText(f"Active ({days_left}d left)")
                        status_item.setForeground(QColor("#4caf50")) # Green
            except:
                status_item.setText("Unknown")
                
            self.table.setItem(row_idx, 7, status_item)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LicenseManagementApp()
    window.show()
    sys.exit(app.exec())

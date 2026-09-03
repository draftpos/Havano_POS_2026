import json
import os
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

WHITE = "#ffffff"
OFF_WHITE = "#f8f9fa"
from theme import *

class CostingMethodPage(QWidget):
    """
    Modern full-page configuration for Costing Methods.
    """
    
    SETTING_KEY = "costing_method"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Costing Method")
        self.setMinimumSize(600, 500)
        self.setStyleSheet(f"CostingMethodPage {{ background-color: {OFF_WHITE}; }}")
        self._toggles = {}
        self._build_ui()
        self._load_setting()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(25)

        # Header
        header_lay = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title = QLabel("Costing Method Configuration")
        title.setStyleSheet(f"font-size: 26px; font-weight: bold; color: {NAVY};")
        subtitle = QLabel("Select how item cost is calculated system-wide at the time of purchase or stock entry.")
        subtitle.setStyleSheet(f"font-size: 14px; color: {MUTED};")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_lay.addLayout(title_box)
        header_lay.addStretch()

        self._save_btn = QPushButton("Save")
        self._save_btn.setFixedSize(160, 42)
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT}; color: white; border: none;
                border-radius: 6px; font-weight: bold; font-size: 14px;
            }}
            QPushButton:hover {{ background-color: #1d4ed8; }}
        """)
        self._save_btn.clicked.connect(self._save_setting)
        header_lay.addWidget(self._save_btn)
        
        root.addLayout(header_lay)

        # Options Container
        options_container = QFrame()
        options_container.setStyleSheet(f"""
            QFrame {{
                background-color: {WHITE};
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }}
        """)
        opt_lay = QVBoxLayout(options_container)
        opt_lay.setContentsMargins(30, 30, 30, 30)
        opt_lay.setSpacing(20)

        methods = [
            ("FIFO",               "First In, First Out - oldest stock is costed and sold first."),
            ("LIFO",               "Last In, First Out - most recently received stock is costed first."),
            ("Weighted Average",   "Weighted average cost across all stock receipts dynamically calculated."),
            ("Standard Cost",      "Uses a fixed standard cost manually set for the product."),
        ]

        for i, (key, desc) in enumerate(methods):
            row_w = QFrame()
            row_w.setCursor(Qt.PointingHandCursor)
            row_w.setStyleSheet(f"""
                QFrame {{
                    background: {OFF_WHITE};
                    border: 2px solid transparent;
                    border-radius: 10px;
                }}
                QFrame:hover {{
                    border: 2px solid #bfdbfe;
                }}
            """)
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(20, 16, 20, 16)
            rl.setSpacing(16)
            
            # Custom Radio Button visualization
            indicator = QLabel()
            indicator.setFixedSize(24, 24)
            indicator.setStyleSheet(f"""
                QLabel {{
                    border: 2px solid #cbd5e1;
                    border-radius: 12px;
                    background-color: white;
                }}
            """)
            
            txt_lay = QVBoxLayout()
            txt_lay.setSpacing(4)
            lbl = QLabel(key)
            lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {NAVY}; border: none; background: transparent;")
            dlbl = QLabel(desc)
            dlbl.setStyleSheet(f"font-size: 13px; color: {MUTED}; border: none; background: transparent;")
            dlbl.setWordWrap(True)
            txt_lay.addWidget(lbl)
            txt_lay.addWidget(dlbl)
            
            rl.addWidget(indicator)
            rl.addLayout(txt_lay, 1)
            
            # Store references
            self._toggles[key] = (row_w, indicator)
            
            # Click event
            row_w.mousePressEvent = lambda _ev, k=key: self._activate(k)
            
            opt_lay.addWidget(row_w)

        root.addWidget(options_container)
        root.addStretch()

    def _activate(self, active_key: str):
        self._current_selection = active_key
        for key, (frame, indicator) in self._toggles.items():
            if key == active_key:
                frame.setStyleSheet(f"""
                    QFrame {{
                        background: #eff6ff;
                        border: 2px solid {ACCENT};
                        border-radius: 10px;
                    }}
                """)
                indicator.setStyleSheet(f"""
                    QLabel {{
                        border: 7px solid {ACCENT};
                        border-radius: 12px;
                        background-color: white;
                    }}
                """)
            else:
                frame.setStyleSheet(f"""
                    QFrame {{
                        background: {OFF_WHITE};
                        border: 2px solid transparent;
                        border-radius: 10px;
                    }}
                    QFrame:hover {{
                        border: 2px solid #bfdbfe;
                    }}
                """)
                indicator.setStyleSheet(f"""
                    QLabel {{
                        border: 2px solid #cbd5e1;
                        border-radius: 12px;
                        background-color: white;
                    }}
                """)

    def _load_setting(self):
        try:
            val = None
            try:
                from database.db import get_connection
                conn = get_connection()
                if conn:
                    cur = conn.cursor()
                    # First try to get it from pos_settings
                    cur.execute("SELECT setting_value FROM pos_settings WHERE setting_key=?", (self.SETTING_KEY,))
                    row = cur.fetchone()
                    if row:
                        val = row[0]
                    conn.close()
            except Exception as e:
                print(f"[CostingMethodPage] Could not load from DB: {e}")
                
            # Fallback to local settings file
            if not val:
                path = os.path.abspath(os.path.join("app_data", "hardware_settings.json"))
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        val = data.get(self.SETTING_KEY)
                        
            # Map legacy values
            if val == "Average":
                val = "Weighted Average"
            elif val == "Last Purchase Cost":
                val = "FIFO" # Standardize
                
            if not val or val not in self._toggles:
                val = "Weighted Average" # Default
                
            self._activate(val)
        except Exception as e:
            print(f"[CostingMethodPage] Load error: {e}")
            self._activate("Weighted Average")

    def _save_setting(self):
        val = self._current_selection
        try:
            from database.db import get_connection
            conn = get_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='pos_settings'")
                if cur.fetchone():
                    cur.execute("IF EXISTS (SELECT 1 FROM pos_settings WHERE setting_key=?) "
                                "UPDATE pos_settings SET setting_value=? WHERE setting_key=? "
                                "ELSE INSERT INTO pos_settings (setting_key, setting_value) VALUES (?, ?)",
                                (self.SETTING_KEY, val, self.SETTING_KEY, self.SETTING_KEY, val))
                    conn.commit()
                conn.close()
        except Exception as e:
            print(f"[CostingMethodPage] DB Save error: {e}")
            
        try:
            path = os.path.abspath(os.path.join("app_data", "hardware_settings.json"))
            if not os.path.exists("app_data"):
                os.makedirs("app_data")
            data = {}
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data[self.SETTING_KEY] = val
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
                
            QMessageBox.information(self, "Success", f"System Costing Method updated to '{val}'.\\n\\nThis will affect new inventory valuations and COGS calculations.")
            from utils.toast import show_toast; show_toast(self.window(), "Costing Method saved successfully!", kind="success")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Save failed:\\n{e}")

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QComboBox, QWidget, QFrame
)
from PySide6.QtCore import Qt
from models.advance_settings import AdvanceSettings
from theme import *

class MainMenuDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Main Menu & Mode Settings")
        self.setFixedSize(400, 450)
        self.setStyleSheet(f"QDialog {{ background: {WHITE}; }}")
        self._settings = AdvanceSettings.load_from_file()
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        title = QLabel("System Mode & Menu Toggles")
        title.setStyleSheet(f"color: {NAVY}; font-size: 16px; font-weight: bold;")
        lay.addWidget(title)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background-color: {BORDER}; border: none;")
        line.setFixedHeight(1)
        lay.addWidget(line)

        # Mode
        lay.addWidget(QLabel("System Mode Override (Requires Restart):", styleSheet="font-weight:bold;"))
        self._mode_combo = QComboBox()
        self._mode_combo.setFixedHeight(34)
        self._mode_combo.addItems(["(Auto / From DB)", "Frappe", "Odoo", "Offline"])
        self._mode_combo.setStyleSheet(f"""
            QComboBox {{
                border: 1px solid {BORDER}; border-radius: 4px; padding: 4px 10px; background: {WHITE};
            }}
        """)
        
        current_mode = self._settings.systemModeOverride.lower()
        if current_mode == "frappe":
            self._mode_combo.setCurrentIndex(1)
        elif current_mode == "odoo":
            self._mode_combo.setCurrentIndex(2)
        elif current_mode == "offline":
            self._mode_combo.setCurrentIndex(3)
        else:
            self._mode_combo.setCurrentIndex(0)
            
        lay.addWidget(self._mode_combo)
        lay.addSpacing(10)

        # Menus
        lay.addWidget(QLabel("Main Menus:", styleSheet="font-weight:bold;"))
        self._cb_pos = QCheckBox("Show 'POS' Menu")
        self._cb_pos.setChecked(self._settings.showMenuPOS)
        self._cb_sales = QCheckBox("Show 'Sales' Menu")
        self._cb_sales.setChecked(self._settings.showMenuSales)
        self._cb_rest = QCheckBox("Show 'Restaurant' Menu")
        self._cb_rest.setChecked(self._settings.showMenuRestaurant)
        lay.addWidget(self._cb_pos)
        lay.addWidget(self._cb_sales)
        lay.addWidget(self._cb_rest)
        lay.addSpacing(10)

        # Badges
        lay.addWidget(QLabel("Badges:", styleSheet="font-weight:bold;"))
        self._cb_q = QCheckBox("Show Q: (Sync) Badge")
        self._cb_q.setChecked(self._settings.showBadgeQ)
        lay.addWidget(self._cb_q)

        lay.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        
        cancel = QPushButton("Cancel")
        cancel.setFixedHeight(34)
        cancel.setFixedWidth(80)
        cancel.clicked.connect(self.reject)
        
        save = QPushButton("Save")
        save.setFixedHeight(34)
        save.setFixedWidth(80)
        save.setStyleSheet(f"""
            QPushButton {{
                background-color: {SUCCESS}; color: {WHITE}; font-weight: bold; border-radius: 4px;
            }}
            QPushButton:hover {{ background-color: {SUCCESS_H}; }}
        """)
        save.clicked.connect(self._save)
        
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        lay.addLayout(btn_row)

    def _save(self):
        idx = self._mode_combo.currentIndex()
        target_mode = ""
        if idx == 1:
            target_mode = "frappe"
        elif idx == 2:
            target_mode = "odoo"
        elif idx == 3:
            target_mode = "offline"

        mode_changed = False
        if target_mode:
            try:
                from services.credentials import set_system_mode, get_system_mode
                if target_mode.lower() != get_system_mode().lower():
                    mode_ok = set_system_mode(target_mode, parent=self)
                    if not mode_ok:
                        return
                    mode_changed = True
            except Exception as _ex_m:
                print(f"[main_menu_dialog] mode change error: {_ex_m}")

        self._settings.systemModeOverride = target_mode

        self._settings.showMenuPOS = self._cb_pos.isChecked()
        self._settings.showMenuSales = self._cb_sales.isChecked()
        self._settings.showMenuRestaurant = self._cb_rest.isChecked()
        self._settings.showBadgeQ = self._cb_q.isChecked()
        
        self._settings.save_to_file()
        self.accept()

        if mode_changed:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "Mode Changed",
                f"System mode changed to '{target_mode.upper()}'.\nDatabase was wiped and re-migrated.\n\nReturning to Login Screen..."
            )
            p = getattr(self, "parent_window", None) or self.parent()
            if p and hasattr(p, "_logout"):
                p._logout()
            elif p and hasattr(p, "_do_logout"):
                p._do_logout()

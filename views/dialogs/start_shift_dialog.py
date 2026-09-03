# views/dialogs/start_shift_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox
)
from PySide6.QtCore import Qt, QLocale
from PySide6.QtGui import QDoubleValidator
from theme import *


class StartShiftDialog(QDialog):
    """
    Small, clean modal dialog for manually starting a shift with opening float in base currency.
    """
    def __init__(self, parent=None, user=None):
        super().__init__(parent)
        self.parent_win = parent
        self.user = user or (parent.user if parent and hasattr(parent, "user") else {})
        
        self.setWindowTitle("Start Shift")
        self.setFixedSize(340, 150)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._base_ccy = "USD"
        try:
            from models.shift import get_company_base_currency
            self._base_ccy = get_company_base_currency() or "USD"
        except Exception:
            pass

        self._build_ui()

    def exec(self):
        try:
            from models.shift import get_active_shift
            if get_active_shift():
                return QDialog.Rejected
        except Exception:
            pass
        return super().exec()

    def _build_ui(self):
        self.setStyleSheet(f"""
            QDialog {{ background: {WHITE}; border-radius: 8px; }}
            QLabel {{ color: {DARK_TEXT}; font-family: 'Segoe UI', sans-serif; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        # Input field layout
        lbl_float = QLabel(f"Opening Float Balance ({self._base_ccy}):")
        lbl_float.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {NAVY};")
        layout.addWidget(lbl_float)

        self.float_edit = QLineEdit()
        self.float_edit.setPlaceholderText("0.00")
        self.float_edit.setFixedHeight(36)
        self.float_edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        val = QDoubleValidator(0.0, 999999.99, 2)
        val.setLocale(QLocale(QLocale.English))
        self.float_edit.setValidator(val)
        
        self.float_edit.setStyleSheet(f"""
            QLineEdit {{
                border: 1.5px solid {BORDER};
                border-radius: 6px;
                padding: 0 10px;
                font-size: 15px;
                font-weight: bold;
                font-family: 'Courier New', monospace;
                background: {WHITE};
            }}
            QLineEdit:focus {{
                border-color: {ACCENT};
            }}
        """)
        layout.addWidget(self.float_edit)

        layout.addSpacing(6)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(34)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: #e0e0e0; color: #424242;
                border: none; border-radius: 5px;
                font-weight: bold; font-size: 12px;
            }}
            QPushButton:hover {{ background: #d6d6d6; }}
        """)
        cancel_btn.clicked.connect(self.reject)

        self.start_btn = QPushButton("Start Shift")
        self.start_btn.setFixedHeight(34)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background: {SUCCESS}; color: white;
                border: none; border-radius: 5px;
                font-weight: bold; font-size: 13px;
            }}
            QPushButton:hover {{ background: {SUCCESS_H}; }}
        """)
        self.start_btn.clicked.connect(self._on_start_shift)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.start_btn)
        layout.addLayout(btn_layout)

        # Focus float edit
        self.float_edit.setFocus()

    def _on_start_shift(self):
        try:
            val_text = self.float_edit.text().strip() or "0"
            start_amount = float(val_text)
            if start_amount < 0:
                QMessageBox.warning(self, "Invalid Input", "Starting amount cannot be negative.")
                return
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid numeric starting amount.")
            return

        cashier_id = None
        if self.user and isinstance(self.user, dict):
            cashier_id = self.user.get("id")

        try:
            from models.shift import start_shift, get_next_shift_number, get_default_payment_methods, get_payment_method_currency
            from database.db import get_connection, fetchall_dicts
            from datetime import date as _date

            pm_list = get_default_payment_methods(cashier_id) or ["Cash"]

            base_mop_name = None
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("SELECT name, account_currency FROM modes_of_payment WHERE enabled = 1")
                mops = fetchall_dicts(cur)
                conn.close()
                for r in mops:
                    name = r.get("name", "")
                    curr = r.get("account_currency") or get_payment_method_currency(name)
                    if curr and curr.upper() == self._base_ccy.upper():
                        base_mop_name = name
                        break
            except Exception:
                pass

            if not base_mop_name:
                base_mop_name = "Cash"

            opening_floats = {}
            for pm in pm_list:
                opening_floats[pm.upper()] = 0.0

            opening_floats[base_mop_name.upper()] = start_amount

            shift_num = get_next_shift_number()
            shift_data = start_shift(
                station=1,
                shift_number=shift_num,
                cashier_id=cashier_id,
                date=_date.today().strftime("%Y-%m-%d"),
                opening_floats=opening_floats
            )

            if shift_data:
                for target in (self.parent_win, getattr(self.parent_win, "parent_window", None), getattr(self.parent_win, "parent_win", None)):
                    if target:
                        if hasattr(target, "_refresh_shift_pill"):
                            try: target._refresh_shift_pill()
                            except Exception: pass
                        if hasattr(target, "_refresh_shift_button"):
                            try: target._refresh_shift_button()
                            except Exception: pass

                # Trigger fiscal day open prompt if fiscal integration is enabled
                try:
                    from models.fiscal_settings import FiscalSettingsRepository
                    f_repo = FiscalSettingsRepository().get_settings()
                    if f_repo and f_repo.enabled:
                        if f_repo.provider == "axis":
                            from views.dialogs.axis_fiscal_dialog import AxisFiscalDialog
                            from PySide6.QtCore import QTimer
                            QTimer.singleShot(300, lambda: AxisFiscalDialog(self.parent_win, initial_action="open").exec())
                        elif f_repo.provider == "revmax":
                            from views.dialogs.revmax_fiscal_dialog import RevmaxFiscalDialog
                            from PySide6.QtCore import QTimer
                            QTimer.singleShot(300, lambda: RevmaxFiscalDialog(self.parent_win, initial_action="open").exec())
                except Exception as fe:
                    print(f"[StartShiftDialog] Fiscal trigger error: {fe}")

                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Failed to start shift.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not start shift: {e}")

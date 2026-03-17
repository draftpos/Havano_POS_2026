# =============================================================================
# views/dialogs/payment_entry_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
    QDateEdit, QTextEdit, QGroupBox
)
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtGui import QColor, QDoubleValidator

# Import colors (same as before)
NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
NAVY_3    = "#1e3d6e"
ACCENT    = "#1a5fb4"
ACCENT_H  = "#1c6dd0"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
LIGHT     = "#e4eaf4"
MID       = "#8fa8c8"
DARK_TEXT = "#0d1f3c"
MUTED     = "#5a7a9a"
BORDER    = "#c8d8ec"
ROW_ALT   = "#edf3fb"
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"
ORANGE    = "#c05a00"
AMBER     = "#b06000"


def navy_btn(text, height=36, font_size=12, width=None, color=None, hover=None):
    bg  = color or NAVY
    hov = hover or NAVY_2
    btn = QPushButton(text)
    btn.setFixedHeight(height)
    if width:
        btn.setFixedWidth(width)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: {WHITE}; border: none;
            border-radius: 5px; font-size: {font_size}px; font-weight: bold; padding: 0 14px;
        }}
        QPushButton:hover   {{ background-color: {hov}; }}
        QPushButton:pressed {{ background-color: {NAVY_3}; }}
    """)
    return btn


def hr():
    from PySide6.QtWidgets import QFrame
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"background-color: {BORDER}; border: none;")
    line.setFixedHeight(1)
    return line


class PaymentEntryDialog(QDialog):
    def __init__(self, parent=None, customer=None):
        super().__init__(parent)
        self.customer = customer
        self.setWindowTitle("Payment Entry")
        self.setMinimumSize(700, 550)
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
        self.amount = 0.0
        self._build()
        self._load_customers()
        if customer:
            self._select_customer(customer)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(44)
        hdr.setStyleSheet(f"background-color: {NAVY}; border-radius: 5px;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        title = QLabel("Payment Entry")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {WHITE}; background: transparent;")
        hl.addWidget(title)
        layout.addWidget(hdr)

        # Customer selection
        cust_row = QHBoxLayout()
        cust_row.setSpacing(8)

        cust_lbl = QLabel("Customer:")
        cust_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")

        self._cust_combo = QComboBox()
        self._cust_combo.setFixedHeight(34)
        self._cust_combo.setMinimumWidth(250)
        self._cust_combo.currentIndexChanged.connect(self._on_customer_changed)

        cust_row.addWidget(cust_lbl)
        cust_row.addWidget(self._cust_combo)
        cust_row.addStretch()
        layout.addLayout(cust_row)

        # Payment details
        details_group = QGroupBox("Payment Details")
        details_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold; border: 1px solid {BORDER}; border-radius: 5px;
                margin-top: 10px; padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px;
                color: {NAVY}; background: transparent;
            }}
        """)
        details_layout = QGridLayout(details_group)
        details_layout.setSpacing(10)
        details_layout.setContentsMargins(16, 16, 16, 16)

        # Date
        date_lbl = QLabel("Date:")
        date_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
        self._date_edit = QDateEdit()
        self._date_edit.setDate(QDate.currentDate())
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setFixedHeight(34)
        details_layout.addWidget(date_lbl, 0, 0)
        details_layout.addWidget(self._date_edit, 0, 1)

        # Reference
        ref_lbl = QLabel("Reference No:")
        ref_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
        self._ref_edit = QLineEdit()
        self._ref_edit.setPlaceholderText("Receipt/Transaction ID")
        self._ref_edit.setFixedHeight(34)
        details_layout.addWidget(ref_lbl, 0, 2)
        details_layout.addWidget(self._ref_edit, 0, 3)

        # Payment Method
        method_lbl = QLabel("Payment Method:")
        method_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
        self._method_combo = QComboBox()
        self._method_combo.addItems(["Cash", "Card", "Bank Transfer", "Cheque", "Mobile Money"])
        self._method_combo.setFixedHeight(34)
        details_layout.addWidget(method_lbl, 1, 0)
        details_layout.addWidget(self._method_combo, 1, 1)

        # Amount
        amount_lbl = QLabel("Amount:")
        amount_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
        self._amount_edit = QLineEdit()
        self._amount_edit.setPlaceholderText("0.00")
        self._amount_edit.setFixedHeight(34)
        self._amount_edit.setValidator(QDoubleValidator(0.0, 999999.99, 2))
        self._amount_edit.textChanged.connect(self._update_balance)
        details_layout.addWidget(amount_lbl, 1, 2)
        details_layout.addWidget(self._amount_edit, 1, 3)

        layout.addWidget(details_group)

        # Customer Balance Information
        balance_group = QGroupBox("Customer Balance")
        balance_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold; border: 1px solid {BORDER}; border-radius: 5px;
                margin-top: 10px; padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px;
                color: {NAVY}; background: transparent;
            }}
        """)
        balance_layout = QGridLayout(balance_group)
        balance_layout.setSpacing(10)
        balance_layout.setContentsMargins(16, 16, 16, 16)

        # Current Balance
        current_balance_lbl = QLabel("Current Balance:")
        current_balance_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
        self._current_balance = QLabel("$0.00")
        self._current_balance.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DARK_TEXT}; background: transparent;")
        balance_layout.addWidget(current_balance_lbl, 0, 0)
        balance_layout.addWidget(self._current_balance, 0, 1)

        # Payment Applied
        payment_applied_lbl = QLabel("Payment Applied:")
        payment_applied_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
        self._payment_applied = QLabel("$0.00")
        self._payment_applied.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {SUCCESS}; background: transparent;")
        balance_layout.addWidget(payment_applied_lbl, 1, 0)
        balance_layout.addWidget(self._payment_applied, 1, 1)

        # New Balance
        new_balance_lbl = QLabel("New Balance:")
        new_balance_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
        self._new_balance = QLabel("$0.00")
        self._new_balance.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DANGER}; background: transparent;")
        balance_layout.addWidget(new_balance_lbl, 2, 0)
        balance_layout.addWidget(self._new_balance, 2, 1)

        # Quick payment buttons
        quick_row = QHBoxLayout()
        quick_row.setSpacing(8)
        for amt in [10, 20, 50, 100, 200, 500]:
            btn = navy_btn(f"${amt}", height=30, font_size=11)
            btn.clicked.connect(lambda _, a=amt: self._amount_edit.setText(str(a)))
            quick_row.addWidget(btn)

        full_btn = navy_btn("Full Balance", height=30, font_size=11, color=ACCENT, hover=ACCENT_H)
        full_btn.clicked.connect(self._set_full_balance)

        quick_row.addWidget(full_btn)
        quick_row.addStretch()

        balance_layout.addLayout(quick_row, 3, 0, 1, 2)

        layout.addWidget(balance_group)

        # Notes
        notes_lbl = QLabel("Notes:")
        notes_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
        layout.addWidget(notes_lbl)

        self._notes_edit = QTextEdit()
        self._notes_edit.setPlaceholderText("Additional notes about this payment...")
        self._notes_edit.setFixedHeight(80)
        self._notes_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {WHITE}; color: {DARK_TEXT};
                border: 1px solid {BORDER}; border-radius: 5px;
                padding: 8px; font-size: 13px;
            }}
            QTextEdit:focus {{ border: 2px solid {ACCENT}; }}
        """)
        layout.addWidget(self._notes_edit)

        layout.addWidget(hr())

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._status = QLabel("")
        self._status.setStyleSheet(f"font-size: 12px; color: {SUCCESS}; background: transparent;")

        save_btn = navy_btn("Process Payment", height=38, color=SUCCESS, hover=SUCCESS_H)
        save_btn.clicked.connect(self._save)

        cancel_btn = navy_btn("Cancel", height=38, color=NAVY_2, hover=NAVY_3)
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(self._status, 1)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _load_customers(self):
        self._cust_combo.clear()
        self._cust_combo.addItem("Select Customer", None)

        try:
            from models.customer import get_all_customers_with_balance
            customers = get_all_customers_with_balance()
            for c in customers:
                name = c["customer_name"]
                balance = float(c.get("balance", 0))
                if balance != 0:
                    name += f" (${balance:.2f})"
                self._cust_combo.addItem(name, c)
        except Exception as e:
            print(f"Error loading customers: {e}")

    def _select_customer(self, customer):
        for i in range(self._cust_combo.count()):
            data = self._cust_combo.itemData(i)
            if data and data.get("id") == customer.get("id"):
                self._cust_combo.setCurrentIndex(i)
                break

    def _on_customer_changed(self, index):
        if index <= 0:
            self._current_balance.setText("$0.00")
            self._payment_applied.setText("$0.00")
            self._new_balance.setText("$0.00")
            return

        customer = self._cust_combo.currentData()
        if customer:
            balance = float(customer.get("balance", 0))
            self._current_balance.setText(f"${balance:.2f}")
            self._current_balance.setStyleSheet(
                f"font-size: 18px; font-weight: bold; color: {DANGER if balance > 0 else SUCCESS}; background: transparent;"
            )
            self._update_balance()

    def _update_balance(self):
        if self._cust_combo.currentIndex() <= 0:
            return

        try:
            amount = float(self._amount_edit.text() or "0")
        except ValueError:
            amount = 0.0

        self.amount = amount
        self._payment_applied.setText(f"${amount:.2f}")

        customer = self._cust_combo.currentData()
        if customer:
            current_balance = float(customer.get("balance", 0))
            new_balance = current_balance - amount  # Payment reduces balance
            self._new_balance.setText(f"${new_balance:.2f}")
            self._new_balance.setStyleSheet(
                f"font-size: 18px; font-weight: bold; color: {DANGER if new_balance > 0 else SUCCESS}; background: transparent;"
            )

    def _set_full_balance(self):
        if self._cust_combo.currentIndex() <= 0:
            return

        customer = self._cust_combo.currentData()
        if customer:
            balance = float(customer.get("balance", 0))
            if balance > 0:
                self._amount_edit.setText(f"{balance:.2f}")

    def _save(self):
        if self._cust_combo.currentIndex() <= 0:
            self._show_status("Please select a customer.", error=True)
            return

        try:
            amount = float(self._amount_edit.text() or "0")
        except ValueError:
            amount = 0.0

        if amount <= 0:
            self._show_status("Please enter a valid amount.", error=True)
            return

        customer = self._cust_combo.currentData()
        method = self._method_combo.currentText()
        notes = self._notes_edit.toPlainText().strip()
        ref_no = self._ref_edit.text().strip() or f"PAY-{QDate.currentDate().toString('yyyyMMdd')}-{id(self)}"

        try:
            from models.customer import create_payment_entry
            payment = create_payment_entry(
                customer_id=customer["id"],
                amount=amount,
                method=method,
                reference=ref_no,
                notes=notes,
                date=self._date_edit.date().toString("yyyy-MM-dd")
            )

            if payment:
                self._show_status(f"Payment processed. New balance: ${payment.get('new_balance', 0):.2f}")
                QTimer.singleShot(1500, self.accept)
            else:
                self._show_status("Error processing payment.", error=True)

        except Exception as e:
            self._show_status(str(e), error=True)
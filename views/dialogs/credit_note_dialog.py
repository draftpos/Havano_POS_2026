# =============================================================================
# views/dialogs/credit_note_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
    QDateEdit, QTextEdit
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


class CreditNoteDialog(QDialog):
    def __init__(self, parent=None, customer=None):
        super().__init__(parent)
        self.customer = customer
        self.setWindowTitle("Credit Note")
        self.setMinimumSize(700, 500)
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
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
        title = QLabel("Credit Note")
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

        # Credit note details
        details_group = QWidget()
        details_group.setStyleSheet(f"QWidget {{ background-color: {OFF_WHITE}; border: 1px solid {BORDER}; border-radius: 5px; }}")
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
        self._ref_edit.setPlaceholderText("Auto-generated if blank")
        self._ref_edit.setFixedHeight(34)
        details_layout.addWidget(ref_lbl, 0, 2)
        details_layout.addWidget(self._ref_edit, 0, 3)

        # Amount
        amount_lbl = QLabel("Amount:")
        amount_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
        self._amount_edit = QLineEdit()
        self._amount_edit.setPlaceholderText("0.00")
        self._amount_edit.setFixedHeight(34)
        self._amount_edit.setValidator(QDoubleValidator(0.0, 999999.99, 2))
        self._amount_edit.textChanged.connect(self._update_balance)
        details_layout.addWidget(amount_lbl, 1, 0)
        details_layout.addWidget(self._amount_edit, 1, 1)

        # Current Balance
        balance_lbl = QLabel("Current Balance:")
        balance_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
        self._balance_display = QLabel("$0.00")
        self._balance_display.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {DARK_TEXT}; background: transparent;")
        details_layout.addWidget(balance_lbl, 1, 2)
        details_layout.addWidget(self._balance_display, 1, 3)

        # New Balance after credit
        new_balance_lbl = QLabel("New Balance:")
        new_balance_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
        self._new_balance_display = QLabel("$0.00")
        self._new_balance_display.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {SUCCESS}; background: transparent;")
        details_layout.addWidget(new_balance_lbl, 2, 2)
        details_layout.addWidget(self._new_balance_display, 2, 3)

        layout.addWidget(details_group)

        # Reason/Notes
        notes_lbl = QLabel("Reason / Notes:")
        notes_lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
        layout.addWidget(notes_lbl)

        self._notes_edit = QTextEdit()
        self._notes_edit.setPlaceholderText("Enter reason for credit note...")
        self._notes_edit.setFixedHeight(100)
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

        save_btn = navy_btn("Save Credit Note", height=38, color=SUCCESS, hover=SUCCESS_H)
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
                if balance > 0:
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
            self._balance_display.setText("$0.00")
            self._new_balance_display.setText("$0.00")
            return

        customer = self._cust_combo.currentData()
        if customer:
            balance = float(customer.get("balance", 0))
            self._balance_display.setText(f"${balance:.2f}")
            self._balance_display.setStyleSheet(
                f"font-size: 16px; font-weight: bold; color: {DANGER if balance > 0 else SUCCESS}; background: transparent;"
            )
            self._update_balance()

    def _update_balance(self):
        if self._cust_combo.currentIndex() <= 0:
            return

        try:
            amount = float(self._amount_edit.text() or "0")
        except ValueError:
            amount = 0.0

        customer = self._cust_combo.currentData()
        if customer:
            current_balance = float(customer.get("balance", 0))
            new_balance = current_balance - amount  # Credit note reduces balance
            self._new_balance_display.setText(f"${new_balance:.2f}")
            self._new_balance_display.setStyleSheet(
                f"font-size: 16px; font-weight: bold; color: {DANGER if new_balance > 0 else SUCCESS}; background: transparent;"
            )

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
        notes = self._notes_edit.toPlainText().strip()
        ref_no = self._ref_edit.text().strip() or f"CN-{QDate.currentDate().toString('yyyyMMdd')}-{id(self)}"

        try:
            from models.customer import create_credit_note
            credit_note = create_credit_note(
                customer_id=customer["id"],
                amount=amount,
                reference=ref_no,
                notes=notes,
                date=self._date_edit.date().toString("yyyy-MM-dd")
            )

            if credit_note:
                self._show_status(f"Credit note saved. New balance: ${credit_note.get('new_balance', 0):.2f}")
                QTimer.singleShot(1500, self.accept)
            else:
                self._show_status("Error saving credit note.", error=True)

        except Exception as e:
            self._show_status(str(e), error=True)

    def _show_status(self, msg, error=False):
        color = DANGER if error else SUCCESS
        self._status.setStyleSheet(f"font-size: 12px; color: {color}; background: transparent;")
        self._status.setText(msg)
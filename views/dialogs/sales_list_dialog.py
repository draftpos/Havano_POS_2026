# =============================================================================
# views/dialogs/sales_list_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QAbstractItemView, QMessageBox
)
from PySide6.QtCore import Qt

from models.sale import get_all_sales, delete_sale, get_sale_items

# ── colours ───────────────────────────────────────────────────────────────────
NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
NAVY_3    = "#1e3d6e"
ACCENT    = "#1a5fb4"
ACCENT_H  = "#1c6dd0"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
LIGHT     = "#e4eaf4"
BORDER    = "#c8d8ec"
DARK_TEXT = "#0d1f3c"
MUTED     = "#5a7a9a"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"
ROW_ALT   = "#edf3fb"


def _hr():
    ln = QFrame()
    ln.setFrameShape(QFrame.HLine)
    ln.setStyleSheet(f"background: {BORDER}; border: none;")
    ln.setFixedHeight(1)
    return ln


def _btn(text, bg, hov, size=(110, 64)):
    b = QPushButton(text)
    b.setFixedSize(*size)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: {WHITE}; border: none;
            border-radius: 8px; font-size: 11px; font-weight: bold; text-align: center;
        }}
        QPushButton:hover   {{ background-color: {hov}; }}
        QPushButton:pressed {{ background-color: {NAVY_3}; }}
        QPushButton:disabled {{ background-color: {LIGHT}; color: {MUTED}; }}
    """)
    return b


# =============================================================================
class SalesListDialog(QDialog):
    """
    Sales List — F7 popup.

    Columns : Number | Date | Time | User | Amount $ | Tendered $
    Buttons : Receipt | Print (F3) | Delete (F4) | Close (Esc)

    After exec():
      self.selected_sale  — full sale dict if user recalled, else None
      self.selected_items — line items list for recalled sale (populates invoice)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sales List")
        self.setFixedSize(640, 560)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {OFF_WHITE}; }}
            QWidget {{ background-color: {OFF_WHITE}; color: {DARK_TEXT}; font-size: 13px; }}
        """)
        self.selected_sale  = None
        self.selected_items = []
        self._all_sales     = []

        self._build_ui()
        self._load_data()

    # =========================================================================
    # BUILD UI
    # =========================================================================
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # title
        title = QLabel("Sales List")
        title.setFixedHeight(40)
        title.setStyleSheet(f"""
            font-size: 15px; font-weight: bold; color: {WHITE};
            background-color: {NAVY}; border-radius: 6px; padding: 0 16px;
        """)
        root.addWidget(title)

        # table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Number", "Date", "Time", "User", "Amount $", "Tendered $"]
        )
        hh = self.table.horizontalHeader()
        for col, (mode, w) in enumerate([
            (QHeaderView.Fixed,   70),
            (QHeaderView.Fixed,   100),
            (QHeaderView.Fixed,   70),
            (QHeaderView.Fixed,   70),
            (QHeaderView.Stretch, 0),
            (QHeaderView.Stretch, 0),
        ]):
            hh.setSectionResizeMode(col, mode)
            if mode == QHeaderView.Fixed:
                self.table.setColumnWidth(col, w)

        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {WHITE}; color: {DARK_TEXT};
                border: 1px solid {BORDER}; gridline-color: {LIGHT};
                font-size: 13px; outline: none;
            }}
            QTableWidget::item           {{ padding: 5px 8px; }}
            QTableWidget::item:selected  {{ background-color: {ACCENT}; color: {WHITE}; }}
            QTableWidget::item:alternate {{ background-color: {ROW_ALT}; }}
            QHeaderView::section {{
                background-color: {WHITE}; color: {DARK_TEXT};
                padding: 8px; border: none;
                border-bottom: 2px solid {BORDER};
                border-right: 1px solid {BORDER};
                font-size: 12px; font-weight: bold;
            }}
        """)
        self.table.doubleClicked.connect(self._on_recall)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        root.addWidget(self.table, 1)

        # summary bar
        summary = QWidget()
        summary.setFixedHeight(34)
        summary.setStyleSheet(f"""
            background-color: {WHITE};
            border-top: 2px solid {BORDER};
            border-bottom: 1px solid {BORDER};
        """)
        sl = QHBoxLayout(summary)
        sl.setContentsMargins(10, 0, 10, 0)
        self.count_lbl = QLabel("No. of Sales    0")
        self.count_lbl.setStyleSheet(
            f"font-weight: bold; color: {DARK_TEXT}; background: transparent;"
        )
        self.total_lbl = QLabel("0.00")
        self.total_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.total_lbl.setStyleSheet(
            f"font-weight: bold; color: {DARK_TEXT}; background: transparent; min-width: 80px;"
        )
        sl.addWidget(self.count_lbl)
        sl.addStretch()
        sl.addWidget(self.total_lbl)
        root.addWidget(summary)
        root.addWidget(_hr())

        # buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.receipt_btn = _btn("🧾\nReceipt",     ACCENT,  ACCENT_H)
        self.print_btn   = _btn("🖨\nPrint (F3)",  NAVY,    NAVY_2)
        self.delete_btn  = _btn("🗑\nDelete (F4)", NAVY_2,  DANGER)
        self.close_btn   = _btn("✕\nClose (Esc)",  DANGER,  DANGER_H)

        self.receipt_btn.setEnabled(False)
        self.print_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)

        self.receipt_btn.clicked.connect(self._on_receipt)
        self.print_btn.clicked.connect(self._on_print)
        self.delete_btn.clicked.connect(self._on_delete)
        self.close_btn.clicked.connect(self.reject)

        btn_row.addWidget(self.receipt_btn)
        btn_row.addWidget(self.print_btn)
        btn_row.addWidget(self.delete_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.close_btn)
        root.addLayout(btn_row)

    # =========================================================================
    # DATA — models/sale.py only, no hardcoding
    # =========================================================================
    def _load_data(self):
        self._all_sales = get_all_sales()
        self._render_table(self._all_sales)

    def _render_table(self, sales: list[dict]):
        BLANK_ROWS = 12
        self.table.setRowCount(len(sales) + BLANK_ROWS)

        total = 0.0
        for r, sale in enumerate(sales):
            self.table.setRowHeight(r, 30)
            self._fill_row(r, sale)
            total += sale["amount"]

        for r in range(len(sales), self.table.rowCount()):
            self.table.setRowHeight(r, 30)
            for c in range(6):
                item = QTableWidgetItem("")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, c, item)

        self.count_lbl.setText(f"No. of Sales    {len(sales)}")
        self.total_lbl.setText(f"{total:.2f}")

    def _fill_row(self, row: int, sale: dict):
        """
        sale dict keys (from models/sale._sale_row_to_dict):
          id, number, date, time, user, amount, tendered, method
        """
        values = [
            str(sale["number"]),
            sale["date"],
            sale["time"],
            str(sale["user"]),
            f"{sale['amount']:.2f}",
            f"{sale['tendered']:.2f}",
        ]
        for c, val in enumerate(values):
            item = QTableWidgetItem(val)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(
                Qt.AlignRight | Qt.AlignVCenter if c in (0, 4, 5)
                else Qt.AlignCenter
            )
            if c == 0:
                item.setData(Qt.UserRole, sale["id"])   # DB id for lookup
            self.table.setItem(row, c, item)

    # =========================================================================
    # SELECTION
    # =========================================================================
    def _get_selected_sale(self) -> dict | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        if not item or not item.text().strip():
            return None
        sale_id = item.data(Qt.UserRole)
        return next((s for s in self._all_sales if s["id"] == sale_id), None)

    def _on_selection(self):
        has = self._get_selected_sale() is not None
        self.receipt_btn.setEnabled(has)
        self.print_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    # =========================================================================
    # BUTTON HANDLERS
    # =========================================================================
    def _on_recall(self):
        """
        Double-click or Enter — pull line items from DB and return to caller.

        Caller usage in main_window._open_sales_list():
            dlg = SalesListDialog(self)
            if dlg.exec() == QDialog.Accepted and dlg.selected_sale:
                self._new_sale(confirm=False)          # clear current invoice
                for item in dlg.selected_items:
                    self._add_product_to_invoice(
                        name    = item["product_name"],
                        price   = item["price"],
                        part_no = item["part_no"],
                    )
        """
        sale = self._get_selected_sale()
        if not sale:
            return
        self.selected_sale  = sale
        self.selected_items = get_sale_items(sale["id"])
        self.accept()

    def _on_receipt(self):
        """
        TODO: generate PDF receipt for selected sale.
              from utils.pdf_receipt import generate_receipt
              generate_receipt(sale_id=sale["id"])
        """
        sale = self._get_selected_sale()
        if not sale:
            return
        self._info(
            "Receipt",
            f"Sale #{sale['number']}  —  ${sale['amount']:.2f}\n"
            f"Date: {sale['date']}  {sale['time']}  |  Method: {sale['method']}\n\n"
            f"TODO: utils/pdf_receipt.py → generate_receipt(sale_id={sale['id']})"
        )

    def _on_print(self):
        """
        TODO: send to system printer.
              from utils.printer import print_receipt
              print_receipt(sale_id=sale["id"])
        """
        sale = self._get_selected_sale()
        if not sale:
            return
        self._info(
            "Print",
            f"Print Sale #{sale['number']}\n\n"
            f"TODO: utils/printer.py → print_receipt(sale_id={sale['id']})"
        )

    def _on_delete(self):
        """Delete from DB then reload table."""
        sale = self._get_selected_sale()
        if not sale:
            return

        confirm = QMessageBox(self)
        confirm.setWindowTitle("Confirm Delete")
        confirm.setText(f"Delete Sale #{sale['number']}?")
        confirm.setInformativeText("This cannot be undone.")
        confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        confirm.setDefaultButton(QMessageBox.No)
        confirm.setStyleSheet(f"""
            QMessageBox {{ background-color: {WHITE}; }}
            QLabel {{ color: {DARK_TEXT}; }}
            QPushButton {{
                background-color: {ACCENT}; color: {WHITE}; border: none;
                border-radius: 6px; padding: 8px 20px; min-width: 70px;
            }}
            QPushButton:hover {{ background-color: {ACCENT_H}; }}
        """)
        if confirm.exec() == QMessageBox.Yes:
            delete_sale(sale["id"])
            self._load_data()   # reload from DB — no manual list manipulation

    # =========================================================================
    # HELPERS
    # =========================================================================
    def _info(self, title: str, text: str):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStyleSheet(f"""
            QMessageBox {{ background-color: {WHITE}; }}
            QLabel {{ color: {DARK_TEXT}; font-size: 13px; }}
            QPushButton {{
                background-color: {ACCENT}; color: {WHITE}; border: none;
                border-radius: 6px; padding: 8px 20px; min-width: 70px;
            }}
            QPushButton:hover {{ background-color: {ACCENT_H}; }}
        """)
        msg.exec()

    # =========================================================================
    # KEYBOARD SHORTCUTS
    # =========================================================================
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F3:
            self._on_print()
        elif event.key() == Qt.Key_F4:
            self._on_delete()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._on_recall()
        else:
            super().keyPressEvent(event)
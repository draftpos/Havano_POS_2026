# =============================================================================
# views/dialogs/sales_list_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QAbstractItemView, QMessageBox,
    QMainWindow, QScrollArea, QStackedWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

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

# ── table column definitions ──────────────────────────────────────────────────
# (header, sale_dict_key, width, alignment, stretch)
_COLUMNS = [
    ("Invoice No.",  "number",        100, Qt.AlignCenter,                  False),
    ("Date",         "date",          100, Qt.AlignCenter,                  False),
    ("Time",         "time",           75, Qt.AlignCenter,                  False),
    ("Cashier",      "user",           90, Qt.AlignCenter,                  False),
    ("Customer",     "customer_name",  0,  Qt.AlignLeft | Qt.AlignVCenter,  True),
    ("Company",      "company_name",   0,  Qt.AlignLeft | Qt.AlignVCenter,  True),
    ("Method",       "method",         85, Qt.AlignCenter,                  False),
    ("Currency",     "currency",       75, Qt.AlignCenter,                  False),
    ("Items",        "total_items",    60, Qt.AlignCenter,                  False),
    ("Amount $",     "amount",        105, Qt.AlignRight | Qt.AlignVCenter, False),
    ("Tendered $",   "tendered",      105, Qt.AlignRight | Qt.AlignVCenter, False),
    ("Change $",     "change_amount", 105, Qt.AlignRight | Qt.AlignVCenter, False),
]


def _hr():
    ln = QFrame()
    ln.setFrameShape(QFrame.HLine)
    ln.setStyleSheet(f"background: {BORDER}; border: none;")
    ln.setFixedHeight(1)
    return ln


def _vr():
    ln = QFrame()
    ln.setFrameShape(QFrame.VLine)
    ln.setStyleSheet(f"background: {BORDER}; border: none;")
    ln.setFixedWidth(1)
    return ln


def _toolbar_btn(text, bg, hov, size=(130, 36)):
    b = QPushButton(text)
    b.setFixedSize(*size)
    b.setCursor(Qt.PointingHandCursor)
    b.setFocusPolicy(Qt.NoFocus)
    b.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: {WHITE}; border: none;
            border-radius: 6px; font-size: 12px; font-weight: bold;
        }}
        QPushButton:hover    {{ background-color: {hov}; }}
        QPushButton:pressed  {{ background-color: {NAVY_3}; }}
        QPushButton:disabled {{ background-color: {LIGHT}; color: {MUTED}; }}
    """)
    return b


def _build_toolbar(title: str, left_widget=None, right_widgets=None) -> QWidget:
    toolbar = QWidget()
    toolbar.setFixedHeight(56)
    toolbar.setStyleSheet(f"background-color: {NAVY};")
    tl = QHBoxLayout(toolbar)
    tl.setContentsMargins(20, 0, 20, 0)
    tl.setSpacing(10)
    if left_widget:
        tl.addWidget(left_widget)
    if title:
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color: {WHITE}; font-size: 17px; font-weight: bold; background: transparent;"
        )
        tl.addWidget(lbl)
    tl.addStretch()
    for w in (right_widgets or []):
        tl.addWidget(w)
    return toolbar


def _info_field(label: str, value: str, label_color=None, value_size=15) -> QVBoxLayout:
    """Reusable label+value column for header strips."""
    col = QVBoxLayout()
    col.setSpacing(4)
    lbl = QLabel(label)
    lbl.setStyleSheet(
        f"color: {label_color or MUTED}; font-size: 10px; font-weight: bold; "
        f"letter-spacing: 1px; background: transparent;"
    )
    val = QLabel(value)
    val.setStyleSheet(
        f"color: {DARK_TEXT}; font-size: {value_size}px; "
        f"font-weight: bold; background: transparent;"
    )
    val.setWordWrap(True)
    col.addWidget(lbl)
    col.addWidget(val)
    return col


# =============================================================================
# PAGE 1 — SALES LIST
# =============================================================================
class SalesListPage(QWidget):

    def __init__(self, on_view_invoice, on_close, parent=None):
        super().__init__(parent)
        self.on_view_invoice = on_view_invoice
        self.on_close        = on_close
        self._all_sales      = []
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── toolbar ───────────────────────────────────────────────────────────
        self.print_btn  = _toolbar_btn("🖨  Print (F3)",  NAVY_2, NAVY_3)
        self.delete_btn = _toolbar_btn("🗑  Delete (F4)", DANGER, DANGER_H)
        close_btn       = _toolbar_btn("✕  Close (Esc)",  DANGER, DANGER_H)

        self.print_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.print_btn.clicked.connect(self._on_print)
        self.delete_btn.clicked.connect(self._on_delete)
        close_btn.clicked.connect(self.on_close)

        root.addWidget(_build_toolbar(
            "🧾  Sales List",
            right_widgets=[self.print_btn, self.delete_btn, close_btn],
        ))

        # ── body ──────────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet(f"background-color: {OFF_WHITE};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(32, 20, 32, 20)
        bl.setSpacing(12)

        hint = QLabel("Double-click or press Enter on a row to view the full invoice")
        hint.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
        bl.addWidget(hint)

        # ── table ─────────────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(len(_COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in _COLUMNS])

        hh = self.table.horizontalHeader()
        for i, (_, _, w, _, stretch) in enumerate(_COLUMNS):
            if stretch:
                hh.setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                hh.setSectionResizeMode(i, QHeaderView.Fixed)
                self.table.setColumnWidth(i, w)

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
            QTableWidget::item           {{ padding: 8px 10px; }}
            QTableWidget::item:selected  {{ background-color: {ACCENT}; color: {WHITE}; }}
            QTableWidget::item:alternate {{ background-color: {ROW_ALT}; }}
            QHeaderView::section {{
                background-color: {NAVY}; color: {WHITE};
                padding: 10px; border: none;
                border-right: 1px solid {NAVY_2};
                font-size: 12px; font-weight: bold;
            }}
        """)
        self.table.doubleClicked.connect(self._on_open_invoice)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        bl.addWidget(self.table, 1)

        # ── summary bar ───────────────────────────────────────────────────────
        summary = QWidget()
        summary.setFixedHeight(44)
        summary.setStyleSheet(f"""
            background-color: {WHITE};
            border: 1px solid {BORDER};
            border-radius: 8px;
        """)
        sl = QHBoxLayout(summary)
        sl.setContentsMargins(20, 0, 20, 0)
        sl.setSpacing(32)

        self.count_lbl    = QLabel("Sales: 0")
        self.total_lbl    = QLabel("Total: $0.00")
        self.tendered_lbl = QLabel("Tendered: $0.00")
        self.change_lbl   = QLabel("Change: $0.00")

        for lbl, color in [
            (self.count_lbl,    DARK_TEXT),
            (self.total_lbl,    ACCENT),
            (self.tendered_lbl, DARK_TEXT),
            (self.change_lbl,   DARK_TEXT),
        ]:
            lbl.setStyleSheet(
                f"font-weight: bold; font-size: 13px; color: {color}; background: transparent;"
            )
            sl.addWidget(lbl)

        sl.addStretch()
        bl.addWidget(summary)
        root.addWidget(body)

    # ── data ──────────────────────────────────────────────────────────────────
    def _load_data(self):
        self._all_sales = get_all_sales()
        self._render_table(self._all_sales)

    def _render_table(self, sales: list[dict]):
        BLANK_ROWS = 6
        self.table.setRowCount(len(sales) + BLANK_ROWS)

        total    = 0.0
        tendered = 0.0
        change   = 0.0

        for r, sale in enumerate(sales):
            self.table.setRowHeight(r, 38)
            self._fill_row(r, sale)
            total    += sale.get("amount",        0.0)
            tendered += sale.get("tendered",      0.0)
            change   += sale.get("change_amount", 0.0)

        for r in range(len(sales), self.table.rowCount()):
            self.table.setRowHeight(r, 38)
            for c in range(len(_COLUMNS)):
                item = QTableWidgetItem("")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, c, item)

        self.count_lbl.setText(f"Sales: {len(sales)}")
        self.total_lbl.setText(f"Total: ${total:.2f}")
        self.tendered_lbl.setText(f"Tendered: ${tendered:.2f}")
        self.change_lbl.setText(f"Change: ${change:.2f}")

    def _fill_row(self, row: int, sale: dict):
        for c, (_, key, _, align, _) in enumerate(_COLUMNS):
            raw = sale.get(key, "")
            if key in ("amount", "tendered", "change_amount"):
                text = f"{float(raw):.2f}" if raw != "" else "0.00"
            elif key == "total_items":
                val  = float(raw) if raw != "" else 0
                text = str(int(val)) if val == int(val) else f"{val:.2f}"
            else:
                text = str(raw) if raw is not None else ""

            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align)
            if c == 0:
                item.setData(Qt.UserRole, sale["id"])
            self.table.setItem(row, c, item)

    # ── selection ─────────────────────────────────────────────────────────────
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
        self.delete_btn.setEnabled(has)
        self.print_btn.setEnabled(has)

    def _on_open_invoice(self):
        sale = self._get_selected_sale()
        if not sale:
            return
        items = get_sale_items(sale["id"])
        self.on_view_invoice(sale, items)

    # ── actions ───────────────────────────────────────────────────────────────
    def _on_print(self):
        sale = self._get_selected_sale()
        if not sale:
            return
        self._msg("Print",
                  f"Print Sale #{sale['number']}\n\n"
                  f"TODO: utils/printer.py → print_receipt(sale_id={sale['id']})")

    def _on_delete(self):
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
            self._load_data()

    def _msg(self, title, text):
        m = QMessageBox(self)
        m.setWindowTitle(title)
        m.setText(text)
        m.setStyleSheet(f"""
            QMessageBox {{ background-color: {WHITE}; }}
            QLabel {{ color: {DARK_TEXT}; font-size: 13px; }}
            QPushButton {{
                background-color: {ACCENT}; color: {WHITE}; border: none;
                border-radius: 6px; padding: 8px 20px; min-width: 70px;
            }}
            QPushButton:hover {{ background-color: {ACCENT_H}; }}
        """)
        m.exec()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F3:
            self._on_print()
        elif event.key() == Qt.Key_F4:
            self._on_delete()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._on_open_invoice()
        else:
            super().keyPressEvent(event)


# =============================================================================
# PAGE 2 — INVOICE DETAIL
# =============================================================================
class SalesInvoicePage(QWidget):

    def __init__(self, on_back, parent=None):
        super().__init__(parent)
        self.on_back = on_back
        self.sale    = None
        self.items   = []
        self.company = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        back_btn = QPushButton("←  Back to List")
        back_btn.setFixedSize(150, 36)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY_2}; color: {WHITE}; border: none;
                border-radius: 6px; font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {NAVY_3}; }}
        """)
        back_btn.clicked.connect(self.on_back)

        self.print_btn = _toolbar_btn("🖨  Print (F3)", NAVY_2, NAVY_3)
        self.print_btn.clicked.connect(self._on_print)

        self._toolbar_title = QLabel("Invoice")
        self._toolbar_title.setStyleSheet(
            f"color: {WHITE}; font-size: 17px; font-weight: bold; background: transparent;"
        )

        toolbar = _build_toolbar("", left_widget=back_btn, right_widgets=[self.print_btn])
        toolbar.layout().insertWidget(1, self._toolbar_title)
        root.addWidget(toolbar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none; background: transparent;")

        self.body = QWidget()
        self.body.setStyleSheet(f"background-color: {OFF_WHITE};")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(60, 32, 60, 48)
        self.body_layout.setSpacing(20)

        self.scroll.setWidget(self.body)
        root.addWidget(self.scroll)

    # ── load ──────────────────────────────────────────────────────────────────
    def load(self, sale: dict, items: list[dict], company: dict | None = None):
        self.sale  = sale
        self.items = items
        if company:
            self.company = company
        elif sale.get("company_name"):
            self.company = {
                "name":        sale["company_name"],
                "currency":    sale.get("currency", "USD"),
                "abbreviation": "",
                "country":     "",
            }
        else:
            self.company = self._load_default_company()
        self._refresh()

    @staticmethod
    def _load_default_company() -> dict | None:
        try:
            from models.company import get_all_companies
            companies = get_all_companies()
            return companies[0] if companies else None
        except Exception:
            return None

    # ── refresh ───────────────────────────────────────────────────────────────
    def _refresh(self):
        while self.body_layout.count():
            child = self.body_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                # clean nested layouts
                while child.layout().count():
                    sub = child.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        sale    = self.sale
        items   = self.items
        company = self.company

        currency = sale.get("currency") or (
            company.get("currency") or company.get("default_currency") or "USD"
            if company else "USD"
        )
        co_name  = (
            sale.get("company_name")
            or (company.get("name") if company else None)
            or "Havano POS"
        )
        co_abbr    = company.get("abbreviation", "") if company else ""
        co_country = company.get("country", "")      if company else ""

        self._toolbar_title.setText(f"Invoice  —  #{sale['number']}")

        # ── COMPANY HEADER ────────────────────────────────────────────────────
        company_card = QWidget()
        company_card.setStyleSheet(
            f"background-color: {NAVY}; border-radius: 10px;"
        )
        cc_layout = QHBoxLayout(company_card)
        cc_layout.setContentsMargins(32, 24, 32, 24)
        cc_layout.setSpacing(0)

        # left — name + subtitle
        name_col = QVBoxLayout()
        name_col.setSpacing(4)

        name_lbl = QLabel(co_name)
        name_lbl.setStyleSheet(
            f"color: {WHITE}; font-size: 24px; font-weight: bold; background: transparent;"
        )
        sub_lbl = QLabel("S A L E S   I N V O I C E")
        sub_lbl.setStyleSheet(
            f"color: {LIGHT}; font-size: 12px; letter-spacing: 3px; background: transparent;"
        )
        name_col.addWidget(name_lbl)
        name_col.addWidget(sub_lbl)
        cc_layout.addLayout(name_col, 1)

        # right — company details grid
        details_grid = QWidget()
        details_grid.setStyleSheet("background: transparent;")
        dg = QHBoxLayout(details_grid)
        dg.setSpacing(24)
        dg.setContentsMargins(0, 0, 0, 0)

        for lbl_txt, val_txt in [
            ("ABBREVIATION", co_abbr   or "—"),
            ("COUNTRY",      co_country or "—"),
            ("CURRENCY",     currency),
        ]:
            col = QVBoxLayout()
            col.setSpacing(3)
            l = QLabel(lbl_txt)
            l.setStyleSheet(
                f"color: {MID if False else '#8fa8c8'}; font-size: 9px; "
                f"font-weight: bold; letter-spacing: 1px; background: transparent;"
            )
            v = QLabel(val_txt)
            v.setStyleSheet(
                f"color: {WHITE}; font-size: 13px; font-weight: bold; background: transparent;"
            )
            col.addWidget(l)
            col.addWidget(v)
            dg.addLayout(col)

        cc_layout.addWidget(details_grid)
        self.body_layout.addWidget(company_card)

        # ── SALE HEADER STRIP — two rows of fields ────────────────────────────
        header_card = QWidget()
        header_card.setStyleSheet(
            f"background-color: {WHITE}; border: 1px solid {BORDER}; border-radius: 10px;"
        )
        hc_layout = QVBoxLayout(header_card)
        hc_layout.setContentsMargins(28, 16, 28, 16)
        hc_layout.setSpacing(12)

        # row 1 — invoice/date/time/cashier/method/payment
        row1 = QHBoxLayout()
        row1.setSpacing(0)

        row1_fields = [
            ("INVOICE NO.",  str(sale["number"])),
            ("DATE",         sale["date"]),
            ("TIME",         sale["time"]),
            ("CASHIER",      str(sale["user"])),
            ("METHOD",       str(sale.get("method", "—"))),
            ("CURRENCY",     currency),
        ]
        for i, (label, value) in enumerate(row1_fields):
            row1.addLayout(_info_field(label, value))
            if i < len(row1_fields) - 1:
                row1.addSpacing(20)
                row1.addWidget(_vr())
                row1.addSpacing(20)

        hc_layout.addLayout(row1)
        hc_layout.addWidget(_hr())

        # row 2 — customer + contact + invoice_no string + kot + receipt_type
        row2 = QHBoxLayout()
        row2.setSpacing(0)

        cust_name    = sale.get("customer_name")    or "Walk-in"
        cust_contact = sale.get("customer_contact") or "—"
        invoice_no   = sale.get("invoice_no")       or "—"
        kot          = sale.get("kot")              or "—"
        receipt_type = sale.get("receipt_type")     or "—"

        row2_fields = [
            ("CUSTOMER",      cust_name),
            ("CONTACT",       cust_contact),
            ("INVOICE REF.",  invoice_no),
            ("KOT",           kot),
            ("RECEIPT TYPE",  receipt_type),
        ]
        for i, (label, value) in enumerate(row2_fields):
            row2.addLayout(_info_field(label, value, value_size=13))
            if i < len(row2_fields) - 1:
                row2.addSpacing(20)
                row2.addWidget(_vr())
                row2.addSpacing(20)

        hc_layout.addLayout(row2)
        self.body_layout.addWidget(header_card)

        # ── ITEMS TABLE ───────────────────────────────────────────────────────
        items_lbl = QLabel("Items")
        items_lbl.setStyleSheet(
            f"color: {DARK_TEXT}; font-size: 14px; font-weight: bold; background: transparent;"
        )
        self.body_layout.addWidget(items_lbl)

        tbl = QTableWidget()
        tbl.setColumnCount(5)
        tbl.setHorizontalHeaderLabels([
            "#", "Product",
            f"Unit Price ({currency})",
            "Qty",
            f"Total ({currency})",
        ])
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setSelectionMode(QAbstractItemView.NoSelection)
        tbl.setAlternatingRowColors(True)
        tbl.setShowGrid(True)

        hh = tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed);  tbl.setColumnWidth(0, 50)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed);  tbl.setColumnWidth(2, 160)
        hh.setSectionResizeMode(3, QHeaderView.Fixed);  tbl.setColumnWidth(3, 80)
        hh.setSectionResizeMode(4, QHeaderView.Fixed);  tbl.setColumnWidth(4, 160)

        tbl.setStyleSheet(f"""
            QTableWidget {{
                background-color: {WHITE}; color: {DARK_TEXT};
                border: 1px solid {BORDER}; gridline-color: {LIGHT};
                font-size: 13px; outline: none; border-radius: 8px;
            }}
            QTableWidget::item           {{ padding: 10px; }}
            QTableWidget::item:alternate {{ background-color: {ROW_ALT}; }}
            QHeaderView::section {{
                background-color: {NAVY}; color: {WHITE};
                padding: 12px; border: none;
                border-right: 1px solid {NAVY_2};
                font-size: 12px; font-weight: bold;
            }}
        """)

        tbl.setRowCount(len(items))
        for r, item in enumerate(items):
            tbl.setRowHeight(r, 40)
            line_total = item["price"] * item["qty"]
            qty_str    = str(int(item["qty"])) if item["qty"] == int(item["qty"]) else str(item["qty"])
            cells = [
                (str(r + 1),               Qt.AlignCenter),
                (str(item["product_name"]), Qt.AlignLeft  | Qt.AlignVCenter),
                (f"{item['price']:.2f}",   Qt.AlignRight | Qt.AlignVCenter),
                (qty_str,                  Qt.AlignCenter),
                (f"{line_total:.2f}",      Qt.AlignRight | Qt.AlignVCenter),
            ]
            for c, (text, align) in enumerate(cells):
                cell = QTableWidgetItem(text)
                cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                cell.setTextAlignment(align)
                tbl.setItem(r, c, cell)

        tbl.setFixedHeight(min(44 + len(items) * 40 + 4, 420))
        self.body_layout.addWidget(tbl)

        # ── TOTALS + SALE SUMMARY side by side ────────────────────────────────
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(16)

        # left — sale metadata card
        meta_card = QWidget()
        meta_card.setStyleSheet(
            f"background-color: {WHITE}; border: 1px solid {BORDER}; border-radius: 10px;"
        )
        mc = QVBoxLayout(meta_card)
        mc.setContentsMargins(24, 16, 24, 16)
        mc.setSpacing(10)

        meta_title = QLabel("Sale Info")
        meta_title.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; font-weight: bold; "
            f"letter-spacing: 1px; background: transparent;"
        )
        mc.addWidget(meta_title)
        mc.addWidget(_hr())

        cashier_name = sale.get("cashier_name") or str(sale.get("user", "—"))
        synced       = "✓ Synced" if sale.get("synced") else "⏳ Not synced"
        total_items  = sale.get("total_items", 0)
        items_str    = str(int(total_items)) if float(total_items) == int(float(total_items)) else str(total_items)

        for lbl_txt, val_txt in [
            ("Cashier",       cashier_name),
            ("Total Items",   items_str),
            ("Receipt Type",  sale.get("receipt_type") or "—"),
            ("KOT",           sale.get("kot") or "—"),
            ("Sync Status",   synced),
        ]:
            row_w = QWidget(); row_w.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row_w); rl.setContentsMargins(0, 0, 0, 0)
            l = QLabel(lbl_txt)
            l.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
            v = QLabel(val_txt)
            v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            v.setStyleSheet(f"color: {DARK_TEXT}; font-size: 12px; font-weight: bold; background: transparent;")
            rl.addWidget(l); rl.addStretch(); rl.addWidget(v)
            mc.addWidget(row_w)

        mc.addStretch()
        bottom_row.addWidget(meta_card, 1)

        # right — totals card
        totals_card = QWidget()
        totals_card.setStyleSheet(
            f"background-color: {WHITE}; border: 1px solid {BORDER}; border-radius: 10px;"
        )
        totals_card.setFixedWidth(380)

        tc = QVBoxLayout(totals_card)
        tc.setContentsMargins(28, 20, 28, 20)
        tc.setSpacing(10)

        totals_title = QLabel("Totals")
        totals_title.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; font-weight: bold; "
            f"letter-spacing: 1px; background: transparent;"
        )
        tc.addWidget(totals_title)
        tc.addWidget(_hr())

        subtotal = sum(i["price"] * i["qty"] for i in items)
        discount = max(subtotal - sale["amount"], 0.0)
        tax      = float(sale.get("total_vat")     or 0.0)
        tendered = sale["tendered"]
        change   = float(sale.get("change_amount") or max(tendered - sale["amount"], 0.0))

        total_rows = [
            ("Subtotal",  f"{currency}  {subtotal:.2f}",        False),
            ("Discount",  f"- {currency}  {discount:.2f}",      False),
            ("Tax",       f"{currency}  {tax:.2f}",             False),
            ("divider",   "",                                    False),
            ("Total",     f"{currency}  {sale['amount']:.2f}",  True),
            ("Tendered",  f"{currency}  {tendered:.2f}",        False),
            ("Change",    f"{currency}  {change:.2f}",          False),
        ]

        for label, value, bold in total_rows:
            if label == "divider":
                tc.addWidget(_hr())
                continue
            rw = QWidget(); rw.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(rw); rl.setContentsMargins(0, 0, 0, 0)
            fs  = "15px" if bold else "13px"
            fw  = "bold" if bold else "normal"
            col = DARK_TEXT if bold else MUTED
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color: {col}; font-size: {fs}; font-weight: {fw}; background: transparent;"
            )
            val = QLabel(value)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setStyleSheet(
                f"color: {col}; font-size: {fs}; font-weight: {fw}; background: transparent;"
            )
            rl.addWidget(lbl); rl.addStretch(); rl.addWidget(val)
            tc.addWidget(rw)

        bottom_row.addWidget(totals_card)
        self.body_layout.addLayout(bottom_row)
        self.body_layout.addStretch()

    # ── print ─────────────────────────────────────────────────────────────────
    def _on_print(self):
        if not self.sale:
            return
        m = QMessageBox(self)
        m.setWindowTitle("Print")
        m.setText(
            f"Print Sale #{self.sale['number']}\n\n"
            f"TODO: utils/printer.py → print_receipt(sale_id={self.sale['id']})"
        )
        m.setStyleSheet(f"""
            QMessageBox {{ background-color: {WHITE}; }}
            QLabel {{ color: {DARK_TEXT}; font-size: 13px; }}
            QPushButton {{
                background-color: {ACCENT}; color: {WHITE}; border: none;
                border-radius: 6px; padding: 8px 20px; min-width: 70px;
            }}
            QPushButton:hover {{ background-color: {ACCENT_H}; }}
        """)
        m.exec()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F3:
            self._on_print()
        elif event.key() == Qt.Key_Escape:
            self.on_back()
        else:
            super().keyPressEvent(event)


# =============================================================================
# MAIN WINDOW — stacked router
# =============================================================================
class SalesListDialog(QMainWindow):
    """
    Full-screen sales window.
    Usage:
        dlg = SalesListDialog(self)
        dlg.show()
        # optionally pass company:
        dlg = SalesListDialog(self, company=accepted_company)
    """

    def __init__(self, parent=None, company: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Sales")
        self.showMaximized()
        self._company = company

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.list_page    = SalesListPage(
            on_view_invoice=self._go_to_invoice,
            on_close=self.close,
        )
        self.invoice_page = SalesInvoicePage(on_back=self._go_to_list)

        self.stack.addWidget(self.list_page)     # index 0
        self.stack.addWidget(self.invoice_page)  # index 1
        self.stack.setCurrentIndex(0)

    def _go_to_invoice(self, sale: dict, items: list[dict]):
        self.invoice_page.load(sale, items, company=self._company)
        self.stack.setCurrentIndex(1)

    def _go_to_list(self):
        self.stack.setCurrentIndex(0)

    def keyPressEvent(self, event):
        current = self.stack.currentWidget()
        if current:
            current.keyPressEvent(event)
        else:
            super().keyPressEvent(event)
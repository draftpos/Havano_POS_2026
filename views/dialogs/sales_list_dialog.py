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
_COLUMNS = [
    ("Invoice No.",  "number",        100, Qt.AlignCenter,                  False),
    ("Date",         "date",          100, Qt.AlignCenter,                  False),
    ("Time",         "time",           75, Qt.AlignCenter,                  False),
    ("Cashier",      "user",           90, Qt.AlignCenter,                  False),
    ("Customer",     "customer_name",   0, Qt.AlignLeft | Qt.AlignVCenter,  True),
    ("Company",      "company_name",    0, Qt.AlignLeft | Qt.AlignVCenter,  True),
    ("Method",       "method",          85, Qt.AlignCenter,                 False),
    ("Currency",     "currency",        75, Qt.AlignCenter,                 False),
    ("Items",        "total_items",     60, Qt.AlignCenter,                 False),
    ("Amount $",     "amount",         105, Qt.AlignRight | Qt.AlignVCenter, False),
    ("Tendered $",   "tendered",       105, Qt.AlignRight | Qt.AlignVCenter, False),
    ("Change $",     "change_amount",  105, Qt.AlignRight | Qt.AlignVCenter, False),
]


# ── helpers ───────────────────────────────────────────────────────────────────

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


def _field_col(label: str, value: str, value_size: int = 14) -> QVBoxLayout:
    """A stacked label+value column used in the header strip."""
    col = QVBoxLayout()
    col.setSpacing(3)
    lbl = QLabel(label)
    lbl.setStyleSheet(
        f"color: {MUTED}; font-size: 10px; font-weight: bold; "
        f"letter-spacing: 0.8px; background: transparent;"
    )
    val = QLabel(value or "—")
    val.setStyleSheet(
        f"color: {DARK_TEXT}; font-size: {value_size}px; "
        f"font-weight: bold; background: transparent;"
    )
    val.setWordWrap(False)
    col.addWidget(lbl)
    col.addWidget(val)
    return col


def _card(radius: int = 10) -> QWidget:
    w = QWidget()
    w.setStyleSheet(
        f"background-color: {WHITE}; border: 1px solid {BORDER}; border-radius: {radius}px;"
    )
    return w


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

        # toolbar
        self.print_btn  = _toolbar_btn("🖨  Print (F3)",  NAVY_2, NAVY_3)
        self.delete_btn = _toolbar_btn("🗑  Delete (F4)", DANGER, DANGER_H)
        close_btn       = _toolbar_btn("✕  Close (Esc)",  DANGER, DANGER_H)
        self.print_btn.setEnabled(False)
        # self.delete_btn.setEnabled(False)
        self.delete_btn.setVisible(False)
        self.print_btn.clicked.connect(self._on_print)
        self.delete_btn.clicked.connect(self._on_delete)
        close_btn.clicked.connect(self.on_close)
        root.addWidget(_build_toolbar(
            "🧾  Sales List",
            right_widgets=[self.print_btn, self.delete_btn, close_btn],
        ))

        body = QWidget()
        body.setStyleSheet(f"background-color: {OFF_WHITE};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(32, 20, 32, 20)
        bl.setSpacing(12)

        hint = QLabel("Double-click or press Enter on a row to view the invoice")
        hint.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
        bl.addWidget(hint)

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

        # summary bar
        summary = QWidget()
        summary.setFixedHeight(44)
        summary.setStyleSheet(
            f"background-color: {WHITE}; border: 1px solid {BORDER}; border-radius: 8px;"
        )
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

    def _load_data(self):
        self._all_sales = get_all_sales()
        self._render_table(self._all_sales)

    def _render_table(self, sales: list[dict]):
        self.table.setRowCount(len(sales) + 6)
        total = tendered = change = 0.0
        for r, sale in enumerate(sales):
            self.table.setRowHeight(r, 38)
            self._fill_row(r, sale)
            total    += sale.get("amount",        0.0)
            tendered += sale.get("tendered",      0.0)
            change   += sale.get("change_amount", 0.0)
        for r in range(len(sales), self.table.rowCount()):
            self.table.setRowHeight(r, 38)
            for c in range(len(_COLUMNS)):
                it = QTableWidgetItem("")
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, c, it)
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
                v = float(raw) if raw != "" else 0
                text = str(int(v)) if v == int(v) else f"{v:.2f}"
            else:
                text = str(raw) if raw is not None else ""
            it = QTableWidgetItem(text)
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            it.setTextAlignment(align)
            if c == 0:
                it.setData(Qt.UserRole, sale["id"])
            self.table.setItem(row, c, it)

    def _get_selected_sale(self) -> dict | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        it = self.table.item(rows[0].row(), 0)
        if not it or not it.text().strip():
            return None
        sale_id = it.data(Qt.UserRole)
        return next((s for s in self._all_sales if s["id"] == sale_id), None)

    def _on_selection(self):
        has = self._get_selected_sale() is not None
        self.delete_btn.setEnabled(has)
        self.print_btn.setEnabled(has)

    def _on_open_invoice(self):
        sale = self._get_selected_sale()
        if not sale:
            return
        self.on_view_invoice(sale, get_sale_items(sale["id"]))

    def _on_print(self):
        sale = self._get_selected_sale()
        if sale:
            self._msg("Print", f"Print Sale #{sale['number']}\n\nTODO: utils/printer.py")

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
        k = event.key()
        if k == Qt.Key_F3:
            self._on_print()
        elif k == Qt.Key_F4:
            self._on_delete()
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            self._on_open_invoice()
        else:
            super().keyPressEvent(event)


# =============================================================================
# PAGE 2 — INVOICE DETAIL  (clean minimal)
# =============================================================================
class SalesInvoicePage(QWidget):

    def __init__(self, on_back, parent=None):
        super().__init__(parent)
        self.on_back = on_back
        self.sale    = None
        self.items   = []
        self.company = None
        self._build_ui()

    # ── static shell ──────────────────────────────────────────────────────────
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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        self.body = QWidget()
        self.body.setStyleSheet(f"background-color: {OFF_WHITE};")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(80, 36, 80, 56)
        self.body_layout.setSpacing(16)

        scroll.setWidget(self.body)
        root.addWidget(scroll)

    # ── load & refresh ────────────────────────────────────────────────────────
    def load(self, sale: dict, items: list[dict], company: dict | None = None):
        self.sale  = sale
        self.items = items
        if company:
            self.company = company
        elif sale.get("company_name"):
            self.company = {
                "name":     sale["company_name"],
                "currency": sale.get("currency", "USD"),
                "country":  "",
            }
        else:
            self.company = self._load_default_company()
        self._refresh()

    @staticmethod
    def _load_default_company() -> dict | None:
        try:
            from models.company import get_all_companies
            c = get_all_companies()
            return c[0] if c else None
        except Exception:
            return None

    def _refresh(self):
        # clear body
        while self.body_layout.count():
            child = self.body_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        sale     = self.sale
        items    = self.items
        company  = self.company
        currency = (
            sale.get("currency")
            or (company.get("currency") or company.get("default_currency") if company else None)
            or "USD"
        )
        co_name  = (
            sale.get("company_name")
            or (company.get("name") if company else None)
            or "Havano POS"
        )
        co_country = company.get("country", "") if company else ""

        self._toolbar_title.setText(f"Invoice  #{sale['number']}")

        # ── 1. INVOICE HEADER CARD ────────────────────────────────────────────
        # Navy left stripe + white right content
        header_card = QWidget()
        header_card.setStyleSheet(
            f"background-color: {WHITE}; border: 1px solid {BORDER}; "
            f"border-radius: 10px;"
        )
        hc = QHBoxLayout(header_card)
        hc.setContentsMargins(0, 0, 0, 0)
        hc.setSpacing(0)

        # navy accent strip
        stripe = QWidget()
        stripe.setFixedWidth(8)
        stripe.setStyleSheet(
            f"background-color: {NAVY}; border-top-left-radius: 10px; "
            f"border-bottom-left-radius: 10px;"
        )
        hc.addWidget(stripe)

        # content
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QHBoxLayout(content)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(0)

        # company block
        co_col = QVBoxLayout()
        co_col.setSpacing(3)
        co_name_lbl = QLabel(co_name)
        co_name_lbl.setStyleSheet(
            f"color: {NAVY}; font-size: 20px; font-weight: bold; background: transparent;"
        )
        co_sub_lbl = QLabel(
            "  ·  ".join(filter(None, [co_country, currency]))
        )
        co_sub_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 12px; background: transparent;"
        )
        inv_tag = QLabel("SALES INVOICE")
        inv_tag.setStyleSheet(f"""
            color: {WHITE}; background: {ACCENT};
            font-size: 10px; font-weight: bold; letter-spacing: 1px;
            border-radius: 4px; padding: 2px 8px;
        """)
        inv_tag.setFixedHeight(22)
        inv_tag.setAlignment(Qt.AlignCenter)

        co_col.addWidget(co_name_lbl)
        co_col.addWidget(co_sub_lbl)
        co_col.addSpacing(6)
        co_col.addWidget(inv_tag)
        co_col.addStretch()
        cl.addLayout(co_col, 1)

        cl.addSpacing(32)
        cl.addWidget(_vr())
        cl.addSpacing(32)

        # invoice meta block — 2 columns side by side
        meta_left  = QVBoxLayout(); meta_left.setSpacing(10)
        meta_right = QVBoxLayout(); meta_right.setSpacing(10)

        left_pairs = [
            ("Invoice No.",  str(sale["number"])),
            ("Date",         sale["date"]),
            ("Time",         sale["time"]),
        ]
        right_pairs = [
            ("Cashier",  str(sale["user"])),
            ("Method",   str(sale.get("method", "—"))),
            ("Currency", currency),
        ]

        def _kv(k, v, large=False):
            w = QWidget(); w.setStyleSheet("background: transparent;")
            l = QVBoxLayout(w); l.setContentsMargins(0,0,0,0); l.setSpacing(2)
            kl = QLabel(k)
            kl.setStyleSheet(
                f"color: {MUTED}; font-size: 10px; font-weight: bold; "
                f"letter-spacing: 0.5px; background: transparent;"
            )
            vl = QLabel(v or "—")
            vl.setStyleSheet(
                f"color: {DARK_TEXT}; font-size: {'14' if large else '13'}px; "
                f"font-weight: bold; background: transparent;"
            )
            l.addWidget(kl); l.addWidget(vl)
            return w

        for k, v in left_pairs:
            meta_left.addWidget(_kv(k, v, large=(k == "Invoice No.")))
        for k, v in right_pairs:
            meta_right.addWidget(_kv(k, v))

        meta_row = QHBoxLayout(); meta_row.setSpacing(32)
        meta_row.addLayout(meta_left)
        meta_row.addLayout(meta_right)
        cl.addLayout(meta_row)

        hc.addWidget(content, 1)
        self.body_layout.addWidget(header_card)

        # ── 2. CUSTOMER CARD ──────────────────────────────────────────────────
        cust_name    = sale.get("customer_name")    or ""
        cust_contact = sale.get("customer_contact") or ""

        if cust_name or cust_contact:
            cust_card = _card()
            cc = QHBoxLayout(cust_card)
            cc.setContentsMargins(24, 16, 24, 16)
            cc.setSpacing(0)

            cust_icon = QLabel("👤")
            cust_icon.setStyleSheet("font-size: 20px; background: transparent;")
            cust_icon.setFixedWidth(36)
            cc.addWidget(cust_icon)

            cust_info = QVBoxLayout(); cust_info.setSpacing(2)
            name_lbl = QLabel(cust_name or "Walk-in")
            name_lbl.setStyleSheet(
                f"color: {DARK_TEXT}; font-size: 15px; font-weight: bold; background: transparent;"
            )
            cust_info.addWidget(name_lbl)
            if cust_contact:
                contact_lbl = QLabel(cust_contact)
                contact_lbl.setStyleSheet(
                    f"color: {MUTED}; font-size: 12px; background: transparent;"
                )
                cust_info.addWidget(contact_lbl)
            cc.addLayout(cust_info)
            cc.addStretch()

            # customer tag
            tag = QLabel("CUSTOMER")
            tag.setStyleSheet(
                f"color: {MUTED}; font-size: 10px; font-weight: bold; "
                f"letter-spacing: 1px; background: transparent;"
            )
            tag.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            cc.addWidget(tag)

            self.body_layout.addWidget(cust_card)

        # ── 3. ITEMS TABLE ────────────────────────────────────────────────────
        items_lbl = QLabel("Line Items")
        items_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; font-weight: bold; "
            f"letter-spacing: 1px; background: transparent;"
        )
        self.body_layout.addWidget(items_lbl)

        tbl = QTableWidget()
        tbl.setColumnCount(5)
        tbl.setHorizontalHeaderLabels([
            "#", "Product", f"Unit Price", "Qty", f"Total"
        ])
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setSelectionMode(QAbstractItemView.NoSelection)
        tbl.setAlternatingRowColors(True)
        tbl.setShowGrid(False)

        hh = tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed);  tbl.setColumnWidth(0, 44)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed);  tbl.setColumnWidth(2, 130)
        hh.setSectionResizeMode(3, QHeaderView.Fixed);  tbl.setColumnWidth(3, 70)
        hh.setSectionResizeMode(4, QHeaderView.Fixed);  tbl.setColumnWidth(4, 130)

        tbl.setStyleSheet(f"""
            QTableWidget {{
                background-color: {WHITE}; color: {DARK_TEXT};
                border: 1px solid {BORDER};
                font-size: 13px; outline: none;
                border-radius: 8px;
            }}
            QTableWidget::item           {{ padding: 10px 12px; border-bottom: 1px solid {LIGHT}; }}
            QTableWidget::item:alternate {{ background-color: {ROW_ALT}; }}
            QHeaderView::section {{
                background-color: {OFF_WHITE}; color: {MUTED};
                padding: 10px 12px; border: none;
                border-bottom: 2px solid {BORDER};
                font-size: 11px; font-weight: bold; letter-spacing: 0.5px;
            }}
        """)

        tbl.setRowCount(len(items))
        for r, item in enumerate(items):
            tbl.setRowHeight(r, 42)
            line_total = item["price"] * item["qty"]
            qty_str    = str(int(item["qty"])) if item["qty"] == int(item["qty"]) else str(item["qty"])
            cells = [
                (str(r + 1),               Qt.AlignCenter),
                (str(item["product_name"]), Qt.AlignLeft  | Qt.AlignVCenter),
                (f"{currency} {item['price']:.2f}", Qt.AlignRight | Qt.AlignVCenter),
                (qty_str,                  Qt.AlignCenter),
                (f"{currency} {line_total:.2f}", Qt.AlignRight | Qt.AlignVCenter),
            ]
            for c, (text, align) in enumerate(cells):
                cell = QTableWidgetItem(text)
                cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                cell.setTextAlignment(align)
                tbl.setItem(r, c, cell)

        tbl.setFixedHeight(min(46 + len(items) * 42 + 2, 440))
        self.body_layout.addWidget(tbl)

        # ── 4. TOTALS ─────────────────────────────────────────────────────────
        subtotal = sum(i["price"] * i["qty"] for i in items)
        discount = max(subtotal - sale["amount"], 0.0)
        tax      = float(sale.get("total_vat")     or 0.0)
        tendered = sale["tendered"]
        change   = float(sale.get("change_amount") or max(tendered - sale["amount"], 0.0))

        totals_row = QHBoxLayout()
        totals_row.addStretch()

        totals_card = _card()
        totals_card.setFixedWidth(360)
        tc = QVBoxLayout(totals_card)
        tc.setContentsMargins(24, 20, 24, 20)
        tc.setSpacing(0)

        def _total_row(label, value, bold=False, top_border=False):
            rw = QWidget(); rw.setStyleSheet("background: transparent;")
            if top_border:
                rw.setStyleSheet(
                    f"background: transparent; border-top: 2px solid {BORDER};"
                )
            rl = QHBoxLayout(rw)
            rl.setContentsMargins(0, 10 if top_border else 6, 0, 6)
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
            return rw

        tc.addWidget(_total_row("Subtotal",  f"{currency} {subtotal:.2f}"))
        if discount > 0:
            tc.addWidget(_total_row("Discount",  f"− {currency} {discount:.2f}"))
        if tax > 0:
            tc.addWidget(_total_row("Tax",       f"{currency} {tax:.2f}"))
        tc.addWidget(_total_row(
            "Total", f"{currency} {sale['amount']:.2f}", bold=True, top_border=True
        ))
        tc.addWidget(_total_row("Tendered",  f"{currency} {tendered:.2f}"))
        tc.addWidget(_total_row("Change",    f"{currency} {change:.2f}"))

        totals_row.addWidget(totals_card)
        self.body_layout.addLayout(totals_row)
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

        self.stack.addWidget(self.list_page)
        self.stack.addWidget(self.invoice_page)
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
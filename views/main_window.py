# =============================================================================
# views/main_window.py  —  POS System  —  Navy & White
# =============================================================================
# Roles:
#   admin   → sees full Admin Dashboard (stats, stock, sales, user management)
#             plus a "Switch to POS" button to use the cashier view.
#   cashier → goes straight to the POS (invoice) view only.
#
# Admin can switch between Dashboard and POS mode at any time.
# =============================================================================

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QFrame, QTableWidget, QTableWidgetItem,
    QLineEdit, QGridLayout, QMessageBox, QStatusBar, QSizePolicy,
    QDialog, QHeaderView, QAbstractItemView, QApplication,
    QListWidget, QListWidgetItem, QFormLayout, QComboBox, QScrollArea, QCompleter
)
from PySide6.QtCore import Qt, QTimer, QDate
from PySide6.QtGui import QAction, QColor, QFont

try:
    from views.dialogs.day_shift_dialog import DayShiftDialog
    _HAS_DAY_SHIFT = True
except ImportError:
    _HAS_DAY_SHIFT = False

try:
    from views.dialogs.sales_list_dialog import SalesListDialog
    _HAS_SALES_LIST = True
except ImportError:
    _HAS_SALES_LIST = False

try:
    from views.dialogs.stock_file_dialog import StockFileDialog
    _HAS_STOCK = True
except ImportError:
    _HAS_STOCK = False

try:
    from views.dialogs.payment_dialog import PaymentDialog as _ExternalPaymentDialog
    _HAS_PAYMENT_DIALOG = True
except ImportError:
    _HAS_PAYMENT_DIALOG = False

try:
    from views.dialogs.settings_dialog import SettingsDialog
    _HAS_SETTINGS_DIALOG = True
except ImportError:
    _HAS_SETTINGS_DIALOG = False

# =============================================================================
# COLOUR PALETTE
# =============================================================================
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

TAB_COLORS = [
    "#f5f5f5", "#e8c4b8", "#c8c4d8", "#d8e8c4", "#f0e8d0",
    "#d0e4ec", "#e8e8d8", "#f0e8c4", "#e8d8f0", "#f8e8e8",
]

# =============================================================================
# GLOBAL STYLESHEET
# =============================================================================
GLOBAL_STYLE = f"""
* {{ font-family: 'Segoe UI', sans-serif; }}
QMainWindow  {{ background-color: {OFF_WHITE}; }}
QWidget      {{ background-color: {OFF_WHITE}; color: {DARK_TEXT}; font-size: 13px; }}
QMenuBar {{
    background-color: {NAVY}; color: {WHITE};
    border-bottom: 2px solid {NAVY_2}; padding: 2px 0; font-size: 13px;
}}
QMenuBar::item          {{ padding: 6px 18px; }}
QMenuBar::item:selected {{ background-color: {NAVY_2}; border-radius: 3px; }}
QMenu {{
    background-color: {WHITE}; color: {DARK_TEXT};
    border: 1px solid {BORDER}; border-radius: 6px; padding: 4px;
}}
QMenu::item            {{ padding: 9px 28px; border-radius: 4px; font-size: 13px; }}
QMenu::item:selected   {{ background-color: {ACCENT}; color: {WHITE}; }}
QMenu::separator       {{ height: 1px; background: {BORDER}; margin: 4px 10px; }}
QTableWidget {{
    background-color: {WHITE}; color: {DARK_TEXT};
    border: 1px solid {BORDER}; gridline-color: {LIGHT};
    font-size: 13px; outline: none;
}}
QTableWidget::item           {{ padding: 0 8px; }}
QTableWidget::item:selected  {{ background-color: {ACCENT}; color: {WHITE}; }}
QTableWidget::item:alternate {{ background-color: {ROW_ALT}; }}
QHeaderView::section {{
    background-color: {NAVY}; color: {WHITE};
    padding: 10px 8px; border: none;
    border-right: 1px solid {NAVY_2};
    font-size: 11px; font-weight: bold; letter-spacing: 0.5px;
}}
QLineEdit {{
    background-color: {WHITE}; color: {DARK_TEXT};
    border: 1px solid {BORDER}; border-radius: 5px;
    padding: 6px 10px; font-size: 13px;
}}
QLineEdit:focus {{ border: 2px solid {ACCENT}; }}
QScrollBar:vertical   {{ background: {LIGHT}; width: 6px; border-radius: 3px; }}
QScrollBar::handle:vertical {{ background: {MID}; border-radius: 3px; min-height: 24px; }}
QScrollBar:horizontal {{ background: {LIGHT}; height: 6px; border-radius: 3px; }}
QScrollBar::handle:horizontal {{ background: {MID}; border-radius: 3px; }}
QStatusBar {{
    background-color: {NAVY}; color: {MID};
    border-top: 1px solid {NAVY_2}; font-size: 12px; padding: 2px 12px;
}}
QDialog {{ background-color: {WHITE}; color: {DARK_TEXT}; }}
QComboBox {{
    background-color: {WHITE}; color: {DARK_TEXT};
    border: 1px solid {BORDER}; border-radius: 5px;
    padding: 5px 10px; font-size: 13px;
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {WHITE}; border: 1px solid {BORDER};
    selection-background-color: {ACCENT}; selection-color: {WHITE};
}}
"""


# =============================================================================
# WIDGET HELPERS
# =============================================================================
def _friendly_db_error(e: Exception) -> str:
    msg = str(e)
    if "REFERENCE constraint" in msg or "FK_" in msg or "foreign key" in msg.lower():
        return "Cannot delete — record is still linked to other data. Remove those links first."
    if "UNIQUE" in msg or "duplicate key" in msg.lower():
        return "A record with that name already exists."
    if "Cannot insert the value NULL" in msg:
        return "A required field is missing."
    return msg


def coming_soon(parent, feature="This feature"):
    msg = QMessageBox(parent)
    msg.setWindowTitle("Not Yet Implemented")
    msg.setText(feature)
    msg.setInformativeText("This feature is not yet wired to the database.")
    msg.setIcon(QMessageBox.Information)
    msg.setStyleSheet(f"""
        QMessageBox {{ background-color: {WHITE}; }}
        QLabel {{ color: {DARK_TEXT}; font-size: 13px; }}
        QPushButton {{
            background-color: {ACCENT}; color: {WHITE}; border: none;
            border-radius: 5px; padding: 8px 22px; font-size: 13px; min-width: 80px;
        }}
        QPushButton:hover {{ background-color: {ACCENT_H}; }}
    """)
    msg.exec()


def hr(horizontal=True):
    line = QFrame()
    line.setFrameShape(QFrame.HLine if horizontal else QFrame.VLine)
    line.setStyleSheet(f"background-color: {BORDER}; border: none;")
    if horizontal:
        line.setFixedHeight(1)
    else:
        line.setFixedWidth(1)
    return line


def nav_pill(text, active=False):
    btn = QPushButton(text)
    btn.setFixedHeight(34)
    btn.setCursor(Qt.PointingHandCursor)
    if active:
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WHITE}; color: {NAVY};
                border: none; border-radius: 4px;
                font-size: 12px; font-weight: bold; padding: 0 20px;
            }}
            QPushButton:hover {{ background-color: {LIGHT}; }}
        """)
    else:
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {WHITE};
                border: 1px solid rgba(255,255,255,0.3); border-radius: 4px;
                font-size: 12px; padding: 0 20px;
            }}
            QPushButton:hover {{ background-color: {NAVY_2}; border-color: {WHITE}; }}
        """)
    return btn


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


def numpad_btn(text, kind="digit"):
    btn = QPushButton(text)
    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    btn.setCursor(Qt.PointingHandCursor)
    styles = {
        "digit": (WHITE,   LIGHT,    DARK_TEXT),
        "op":    (NAVY_2,  NAVY_3,   WHITE),
        "clear": (DANGER,  DANGER_H, WHITE),
        "del":   (NAVY_2,  NAVY_3,   WHITE),
        "enter": (ACCENT,  ACCENT_H, WHITE),
        "cash":  (NAVY_3,  NAVY_2,   WHITE),
    }
    bg, hov, fg = styles.get(kind, styles["digit"])
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: {fg};
            border: 1px solid {BORDER}; border-radius: 6px;
            font-size: 16px; font-weight: bold;
        }}
        QPushButton:hover   {{ background-color: {hov}; }}
        QPushButton:pressed {{ background-color: {NAVY_3}; color: {WHITE}; }}
    """)
    return btn


# =============================================================================
# PRODUCT SEARCH DIALOG
# =============================================================================
class ProductSearchDialog(QDialog):
    def __init__(self, parent=None, initial_query=""):
        super().__init__(parent)
        self.setWindowTitle("Product Search")
        self.setMinimumSize(720, 500)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
        self.selected_product = None
        self._build()
        if initial_query:
            self.search_input.setText(initial_query)
        else:
            self._do_search("")

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 16, 20, 16)

        hdr = QWidget()
        hdr.setFixedHeight(44)
        hdr.setStyleSheet(f"background-color: {NAVY}; border-radius: 5px;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        title = QLabel("Product Search")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {WHITE}; background: transparent;")
        hint = QLabel("Double-click or Enter to add to invoice")
        hint.setStyleSheet(f"font-size: 11px; color: {MID}; background: transparent;")
        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(hint)
        layout.addWidget(hdr)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setFixedHeight(38)
        self.search_input.setPlaceholderText("Type part number, name or any keyword — results appear instantly...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {WHITE}; border: 2px solid {ACCENT};
                border-radius: 5px; font-size: 14px; padding: 4px 12px; color: {DARK_TEXT};
            }}
        """)
        self.search_input.textChanged.connect(self._do_search)
        self.search_input.returnPressed.connect(self._pick_selected)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedSize(60, 38)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: {LIGHT}; color: {DARK_TEXT}; border: 1px solid {BORDER};
                border-radius: 5px; font-size: 12px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {BORDER}; }}
        """)
        clear_btn.clicked.connect(lambda: self.search_input.clear())
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(clear_btn)
        layout.addLayout(search_row)

        self._count_lbl = QLabel("Loading products...")
        self._count_lbl.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent; padding: 0 2px;")
        layout.addWidget(self._count_lbl)

        self.results = QTableWidget(0, 5)
        self.results.setHorizontalHeaderLabels(["Part No.", "Name / Description", "Category", "Price", "Stock"])
        hh = self.results.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed);     self.results.setColumnWidth(0, 110)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed);     self.results.setColumnWidth(2, 110)
        hh.setSectionResizeMode(3, QHeaderView.Fixed);     self.results.setColumnWidth(3, 90)
        hh.setSectionResizeMode(4, QHeaderView.Fixed);     self.results.setColumnWidth(4, 70)
        self.results.verticalHeader().setVisible(False)
        self.results.setAlternatingRowColors(True)
        self.results.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.results.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results.setSelectionMode(QAbstractItemView.SingleSelection)
        self.results.setStyleSheet(f"""
            QTableWidget {{ background: {WHITE}; border: 1px solid {BORDER};
                gridline-color: {LIGHT}; font-size: 13px; outline: none; }}
            QTableWidget::item           {{ padding: 6px 8px; }}
            QTableWidget::item:selected  {{ background-color: {ACCENT}; color: {WHITE}; }}
            QTableWidget::item:alternate {{ background-color: {ROW_ALT}; }}
            QHeaderView::section {{
                background-color: {NAVY}; color: {WHITE};
                padding: 10px 8px; border: none;
                border-right: 1px solid {NAVY_2};
                font-size: 11px; font-weight: bold;
            }}
        """)
        self.results.doubleClicked.connect(self._pick_selected)
        self.results.selectionModel().selectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.results, 1)
        layout.addWidget(hr())

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._add_btn = navy_btn("Add to Invoice", height=38, color=SUCCESS, hover=SUCCESS_H)
        self._add_btn.setFixedWidth(140)
        self._add_btn.setEnabled(False)
        self._add_btn.clicked.connect(self._pick_selected)
        cancel_btn = navy_btn("Cancel", height=38, color=NAVY_2, hover=NAVY_3)
        cancel_btn.setFixedWidth(90)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _do_search(self, query: str):
        query = query.strip()
        try:
            from models.product import search_products, get_all_products
            products = search_products(query) if query else get_all_products()
        except Exception:
            products = [
                {"id": 1, "part_no": "S",    "name": "SERVICE CHARGE",   "category": "Services", "price": 50.00, "stock": 0},
                {"id": 2, "part_no": "1",     "name": "Swiss Army Knife", "category": "General",  "price": 10.00, "stock": 5},
                {"id": 3, "part_no": "GR001", "name": "Cooking Oil",      "category": "Grocery",  "price": 3.50,  "stock": 12},
                {"id": 4, "part_no": "DK001", "name": "Coke 500ml",       "category": "Drinks",   "price": 1.20,  "stock": 30},
            ]
            if query:
                ql = query.lower()
                products = [p for p in products if ql in p["part_no"].lower() or ql in p["name"].lower()]

        self.results.setRowCount(0)
        for p in products:
            r = self.results.rowCount()
            self.results.insertRow(r)
            for c, (key, align) in enumerate([
                ("part_no",  Qt.AlignCenter),
                ("name",     Qt.AlignLeft | Qt.AlignVCenter),
                ("category", Qt.AlignCenter),
                ("price",    Qt.AlignRight | Qt.AlignVCenter),
                ("stock",    Qt.AlignCenter),
            ]):
                val = p.get(key, "")
                text = f"${val:.2f}" if key == "price" else str(val)
                item = QTableWidgetItem(text)
                item.setTextAlignment(align)
                if key == "price":
                    item.setForeground(QColor(ACCENT))
                if key == "stock" and isinstance(val, int) and val <= 5:
                    item.setForeground(QColor(DANGER))
                item.setData(Qt.UserRole, p)
                self.results.setItem(r, c, item)
            self.results.setRowHeight(r, 34)

        n = self.results.rowCount()
        self._count_lbl.setText(f"{n} product{'s' if n != 1 else ''} found")
        self._add_btn.setEnabled(False)

    def _on_selection_changed(self, selected, _):
        self._add_btn.setEnabled(bool(selected.indexes()))

    def _pick_selected(self):
        row = self.results.currentRow()
        if row < 0:
            return
        item = self.results.item(row, 0)
        if item:
            self.selected_product = item.data(Qt.UserRole)
            self.accept()


# =============================================================================
# CUSTOMER SEARCH POPUP
# =============================================================================
class CustomerSearchPopup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_customer = None
        self.setWindowTitle("Select Customer")
        self.setMinimumSize(620, 440)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(20, 16, 20, 16)

        hdr = QWidget(); hdr.setFixedHeight(44)
        hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16, 0, 16, 0)
        hl.addWidget(QLabel("Select Customer",
            styleSheet=f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;"))
        hint = QLabel("Double-click or Enter to select")
        hint.setStyleSheet(f"font-size:11px;color:{MID};background:transparent;")
        hl.addStretch(); hl.addWidget(hint)
        lay.addWidget(hdr)

        sr = QHBoxLayout(); sr.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by name, trade name or phone…")
        self._search.setFixedHeight(36)
        self._search.setStyleSheet(f"""
            QLineEdit {{ background:{WHITE}; border:2px solid {ACCENT};
                border-radius:5px; font-size:13px; padding:0 10px; color:{DARK_TEXT}; }}
        """)
        self._search.textChanged.connect(self._do_search)
        self._search.returnPressed.connect(self._pick)
        walk_in = navy_btn("Walk-in (No Customer)", height=36, color=NAVY_2, hover=NAVY_3)
        walk_in.clicked.connect(self._walk_in)
        sr.addWidget(self._search, 1)
        sr.addWidget(walk_in)
        lay.addLayout(sr)

        self._tbl = QTableWidget(0, 4)
        self._tbl.setHorizontalHeaderLabels(["Name", "Type", "Phone", "City"])
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for ci in [1, 2, 3]:
            hh.setSectionResizeMode(ci, QHeaderView.Fixed)
            self._tbl.setColumnWidth(ci, 110)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tbl.setStyleSheet(_settings_table_style())
        self._tbl.doubleClicked.connect(self._pick)
        lay.addWidget(self._tbl, 1)
        lay.addWidget(hr())

        br = QHBoxLayout(); br.setSpacing(8)
        ok_btn  = navy_btn("Select",  height=36, color=SUCCESS, hover=SUCCESS_H)
        cxl_btn = navy_btn("Cancel",  height=36, color=DANGER,  hover=DANGER_H)
        ok_btn.clicked.connect(self._pick)
        cxl_btn.clicked.connect(self.reject)
        br.addStretch(); br.addWidget(ok_btn); br.addWidget(cxl_btn)
        lay.addLayout(br)

        self._load_all()

    def _load_all(self):
        try:
            from models.customer import get_all_customers
            self._populate(get_all_customers())
        except Exception:
            self._populate([])

    def _do_search(self, q):
        if not q.strip():
            self._load_all(); return
        try:
            from models.customer import search_customers
            self._populate(search_customers(q))
        except Exception:
            self._populate([])

    def _populate(self, custs):
        self._tbl.setRowCount(0)
        for c in custs:
            r = self._tbl.rowCount(); self._tbl.insertRow(r)
            for col, val in enumerate([
                c["customer_name"], c.get("customer_type",""),
                c.get("custom_telephone_number",""), c.get("custom_city",""),
            ]):
                it = QTableWidgetItem(str(val)); it.setData(Qt.UserRole, c)
                self._tbl.setItem(r, col, it)
            self._tbl.setRowHeight(r, 32)

    def _pick(self):
        row = self._tbl.currentRow()
        if row < 0:
            return
        self.selected_customer = self._tbl.item(row, 0).data(Qt.UserRole)
        self.accept()

    def _walk_in(self):
        self.selected_customer = None
        self.accept()

    def showEvent(self, e):
        super().showEvent(e)
        self._search.setFocus()


# =============================================================================
# _InlineSettingsDialog  —  fallback
# =============================================================================
class _InlineSettingsDialog(QDialog):
    def __init__(self, parent=None, user=None):
        super().__init__(parent)
        self.user = user or {}
        self.setWindowTitle("Settings")
        self.setMinimumSize(1100, 700)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background-color: {OFF_WHITE}; }}")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background-color:{NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 0, 20, 0)
        t = QLabel("Settings")
        t.setStyleSheet(
            f"font-size:17px; font-weight:bold; color:{WHITE}; background:transparent;"
        )
        close_btn = QPushButton("✕  Close")
        close_btn.setFixedSize(90, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color:{DANGER}; color:{WHITE}; border:none;
                border-radius:4px; font-size:12px; font-weight:bold;
            }}
            QPushButton:hover {{ background-color:{DANGER_H}; }}
        """)
        close_btn.clicked.connect(self.accept)
        hl.addWidget(t); hl.addStretch(); hl.addWidget(close_btn)
        root.addWidget(hdr)

        body = QWidget()
        body.setStyleSheet(f"background:{OFF_WHITE};")
        bl = QHBoxLayout(body)
        bl.setSpacing(0)
        bl.setContentsMargins(0, 0, 0, 0)

        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet(f"background-color:{NAVY_2};")
        sl = QVBoxLayout(sidebar)
        sl.setSpacing(2)
        sl.setContentsMargins(8, 16, 8, 16)

        from PySide6.QtWidgets import QStackedWidget
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{OFF_WHITE};")

        pages = [
            ("⚙  General",        self._page_general()),
            ("🏢  Companies",      CompanyDialog(self)),
            ("👥  Customer Groups",CustomerGroupDialog(self)),
            ("🏭  Warehouses",     WarehouseDialog(self)),
            ("💰  Cost Centers",   CostCenterDialog(self)),
            ("🏷  Price Lists",    PriceListDialog(self)),
            ("👤  Customers",      CustomerDialog(self)),
            ("🔑  Users",          ManageUsersDialog(self, current_user=self.user)),
        ]

        self._nav_btns = []
        for i, (label, page) in enumerate(pages):
            self._stack.addWidget(page)
            btn = QPushButton(label)
            btn.setFixedHeight(42)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setStyleSheet(self._nav_style(False))
            btn.clicked.connect(lambda _, idx=i: self._switch(idx))
            sl.addWidget(btn)
            self._nav_btns.append(btn)

        sl.addStretch()

        ver = QLabel("Havano POS  v1.0")
        ver.setStyleSheet(
            f"color:{MID}; font-size:10px; background:transparent; padding:4px 6px;"
        )
        sl.addWidget(ver)

        bl.addWidget(sidebar)

        vline = QFrame()
        vline.setFrameShape(QFrame.VLine)
        vline.setStyleSheet(f"background:{NAVY_3}; border:none;")
        vline.setFixedWidth(1)
        bl.addWidget(vline)

        bl.addWidget(self._stack, 1)
        root.addWidget(body, 1)

        self._switch(0)

    def _switch(self, idx: int):
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.setChecked(i == idx)
            btn.setStyleSheet(self._nav_style(i == idx))

    @staticmethod
    def _nav_style(active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background-color:{WHITE}; color:{NAVY};
                    border:none; border-radius:5px;
                    font-size:12px; font-weight:bold;
                    text-align:left; padding:0 12px;
                }}
            """
        return f"""
            QPushButton {{
                background-color:transparent; color:{MID};
                border:none; border-radius:5px;
                font-size:12px; text-align:left; padding:0 12px;
            }}
            QPushButton:hover {{
                background-color:{NAVY_3}; color:{WHITE};
            }}
        """

    def _page_general(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{WHITE};")
        lay = QVBoxLayout(w)
        lay.setSpacing(20)
        lay.setContentsMargins(36, 28, 36, 28)

        title = QLabel("General Settings")
        title.setStyleSheet(
            f"font-size:18px; font-weight:bold; color:{NAVY}; background:transparent;"
        )
        lay.addWidget(title)
        lay.addWidget(hr())

        info = [
            ("System Name",  "Havano POS"),
            ("Version",      "1.0.0"),
            ("Database",     "SQL Server"),
            ("Default Currency", "USD"),
        ]
        for lbl_txt, val_txt in info:
            row = QHBoxLayout(); row.setSpacing(0)
            lbl = QLabel(lbl_txt); lbl.setFixedWidth(200)
            lbl.setStyleSheet(
                f"color:{MUTED}; font-size:13px; font-weight:bold; background:transparent;"
            )
            val = QLabel(val_txt)
            val.setStyleSheet(f"color:{DARK_TEXT}; font-size:13px; background:transparent;")
            row.addWidget(lbl); row.addWidget(val); row.addStretch()
            lay.addLayout(row)

        lay.addSpacing(20)

        tip = QLabel(
            "💡  Use the sidebar to manage Companies, Customers, Warehouses, "
            "Cost Centers, Price Lists and Users.\n"
            "Changes take effect immediately."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet(
            f"color:{MUTED}; font-size:12px; background:{LIGHT};"
            f" border:1px solid {BORDER}; border-radius:6px; padding:14px 16px;"
        )
        lay.addWidget(tip)
        lay.addStretch()
        return w


class QuantityPopup(QDialog):
    def __init__(self, parent=None, product_name: str = "", current_qty: float = 1.0):
        super().__init__(parent)
        self.product_name = product_name
        self.entered_qty   = current_qty
        self.setWindowTitle("Set Quantity")
        self.setFixedSize(340, 220)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self._build()

    def _build(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {WHITE};
                border: 2px solid {ACCENT};
                border-radius: 8px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        hdr = QWidget()
        hdr.setFixedHeight(38)
        hdr.setStyleSheet(f"background-color: {NAVY}; border-radius: 5px;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 0, 12, 0)
        t = QLabel("Quantity")
        t.setStyleSheet(f"color:{WHITE}; font-size:14px; font-weight:bold; background:transparent;")
        pn = QLabel(self.product_name[:30] + ("…" if len(self.product_name) > 30 else ""))
        pn.setStyleSheet(f"color:{MID}; font-size:11px; background:transparent;")
        hl.addWidget(t)
        hl.addStretch()
        hl.addWidget(pn)
        layout.addWidget(hdr)

        self._edit = QLineEdit(str(int(self.entered_qty) if self.entered_qty == int(self.entered_qty) else self.entered_qty))
        self._edit.setAlignment(Qt.AlignRight)
        self._edit.setFixedHeight(48)
        self._edit.setStyleSheet(f"""
            QLineEdit {{
                font-size: 26px; font-weight: bold; color: {NAVY};
                background: {OFF_WHITE}; border: 2px solid {ACCENT};
                border-radius: 5px; padding: 0 12px;
            }}
        """)
        self._edit.selectAll()
        layout.addWidget(self._edit)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        ok_btn  = navy_btn("✓  Set Qty", height=40, color=SUCCESS, hover=SUCCESS_H)
        cxl_btn = navy_btn("Cancel",     height=40, color=NAVY_2,  hover=NAVY_3)
        ok_btn.clicked.connect(self._confirm)
        cxl_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cxl_btn)
        layout.addLayout(btn_row)

        self._edit.returnPressed.connect(self._confirm)

    def _confirm(self):
        try:
            self.entered_qty = float(self._edit.text().replace(",", ".") or "1")
        except ValueError:
            self.entered_qty = 1.0
        self.accept()

    def showEvent(self, event):
        super().showEvent(event)
        self._edit.setFocus()
        self._edit.selectAll()


# =============================================================================
# SETTINGS DIALOGS — shared helpers + Company / Customer Group / Warehouse /
#                    Cost Center / Price List / Customer
# =============================================================================

def _settings_table_style():
    return f"""
        QTableWidget {{ background:{WHITE}; border:1px solid {BORDER};
            gridline-color:{LIGHT}; outline:none; font-size:13px; }}
        QTableWidget::item           {{ padding:8px; }}
        QTableWidget::item:selected  {{ background-color:{ACCENT}; color:{WHITE}; }}
        QTableWidget::item:alternate {{ background-color:{ROW_ALT}; }}
        QHeaderView::section {{
            background-color:{NAVY}; color:{WHITE};
            padding:10px 8px; border:none; border-right:1px solid {NAVY_2};
            font-size:11px; font-weight:bold;
        }}
    """


def _settings_dialog_base(parent, title: str, width=700, height=520) -> tuple:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumSize(width, height)
    dlg.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
    layout = QVBoxLayout(dlg)
    layout.setSpacing(12)
    layout.setContentsMargins(20, 16, 20, 16)

    hdr = QWidget()
    hdr.setFixedHeight(44)
    hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
    hl = QHBoxLayout(hdr)
    hl.setContentsMargins(16, 0, 16, 0)
    t = QLabel(title)
    t.setStyleSheet(f"font-size:15px; font-weight:bold; color:{WHITE}; background:transparent;")
    hl.addWidget(t)
    layout.addWidget(hdr)
    return dlg, layout


class CompanyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Companies")
        self.setMinimumSize(700, 480)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        self._build()
        self._reload()

    def _build(self):
        lay = QVBoxLayout(self); lay.setSpacing(10); lay.setContentsMargins(20, 16, 20, 16)
        hdr = QWidget(); hdr.setFixedHeight(44)
        hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16, 0, 16, 0)
        hl.addWidget(QLabel("Companies", styleSheet=f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;"))
        lay.addWidget(hdr)

        self._tbl = QTableWidget(0, 4)
        self._tbl.setHorizontalHeaderLabels(["Name", "Abbreviation", "Currency", "Country"])
        self._tbl.horizontalHeader().setStretchLastSection(True)
        self._tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setStyleSheet(_settings_table_style())
        lay.addWidget(self._tbl, 1); lay.addWidget(hr())

        form = QGridLayout(); form.setSpacing(8)
        self._f_name  = QLineEdit(); self._f_name.setPlaceholderText("Company name *"); self._f_name.setFixedHeight(34)
        self._f_abbr  = QLineEdit(); self._f_abbr.setPlaceholderText("Abbreviation *"); self._f_abbr.setFixedHeight(34)
        self._f_curr  = QLineEdit("USD"); self._f_curr.setPlaceholderText("Currency *"); self._f_curr.setFixedHeight(34)
        self._f_cntry = QLineEdit(); self._f_cntry.setPlaceholderText("Country *"); self._f_cntry.setFixedHeight(34)
        form.addWidget(self._f_name, 0, 0); form.addWidget(self._f_abbr, 0, 1)
        form.addWidget(self._f_curr, 0, 2); form.addWidget(self._f_cntry, 0, 3)
        lay.addLayout(form)

        br = QHBoxLayout(); br.setSpacing(8)
        self._status = QLabel(""); self._status.setStyleSheet(f"font-size:12px;color:{SUCCESS};background:transparent;")
        add_btn = navy_btn("Add", height=34, color=SUCCESS, hover=SUCCESS_H)
        del_btn = navy_btn("Delete", height=34, color=DANGER, hover=DANGER_H)
        cls_btn = navy_btn("Close", height=34)
        add_btn.clicked.connect(self._add); del_btn.clicked.connect(self._delete); cls_btn.clicked.connect(self.accept)
        br.addWidget(self._status, 1); br.addWidget(add_btn); br.addWidget(del_btn); br.addWidget(cls_btn)
        lay.addLayout(br)

    def _reload(self):
        self._tbl.setRowCount(0)
        try:
            from models.company import get_all_companies
            rows = get_all_companies()
        except Exception: rows = []
        for c in rows:
            r = self._tbl.rowCount(); self._tbl.insertRow(r)
            for col, key in enumerate(["name","abbreviation","default_currency","country"]):
                it = QTableWidgetItem(str(c.get(key,""))); it.setData(Qt.UserRole, c)
                self._tbl.setItem(r, col, it)
            self._tbl.setRowHeight(r, 32)

    def _add(self):
        name = self._f_name.text().strip(); abbr = self._f_abbr.text().strip()
        curr = self._f_curr.text().strip(); cntry = self._f_cntry.text().strip()
        if not all([name, abbr, curr, cntry]):
            self._status.setText("All fields required."); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;"); return
        try:
            from models.company import create_company
            create_company(name, abbr, curr, cntry)
            for f in [self._f_name, self._f_abbr, self._f_cntry]: f.clear()
            self._f_curr.setText("USD"); self._reload()
            self._status.setText(f"Company '{name}' added."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")

    def _delete(self):
        row = self._tbl.currentRow()
        if row < 0: self._status.setText("Select a company first."); return
        c = self._tbl.item(row, 0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{c['name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.company import delete_company
            delete_company(c["id"]); self._reload()
            self._status.setText("Deleted."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")


class CustomerGroupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customer Groups"); self.setMinimumSize(560, 420)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        self._build(); self._reload()

    def _build(self):
        lay = QVBoxLayout(self); lay.setSpacing(10); lay.setContentsMargins(20,16,20,16)
        hdr = QWidget(); hdr.setFixedHeight(44); hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16,0,16,0)
        hl.addWidget(QLabel("Customer Groups",styleSheet=f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;"))
        lay.addWidget(hdr)
        self._tbl = QTableWidget(0,2); self._tbl.setHorizontalHeaderLabels(["Name","Parent Group"])
        self._tbl.horizontalHeader().setStretchLastSection(True); self._tbl.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self._tbl.verticalHeader().setVisible(False); self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers); self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setStyleSheet(_settings_table_style()); lay.addWidget(self._tbl,1); lay.addWidget(hr())
        fr = QHBoxLayout(); fr.setSpacing(8)
        self._f_name = QLineEdit(); self._f_name.setPlaceholderText("Group name *"); self._f_name.setFixedHeight(34)
        self._f_parent = QComboBox(); self._f_parent.setFixedHeight(34); self._f_parent.addItem("(No parent)", None)
        fr.addWidget(self._f_name,2); fr.addWidget(QLabel("Parent:",styleSheet="background:transparent;"),0); fr.addWidget(self._f_parent,1)
        lay.addLayout(fr)
        br = QHBoxLayout(); br.setSpacing(8)
        self._status = QLabel(""); self._status.setStyleSheet(f"font-size:12px;color:{SUCCESS};background:transparent;")
        add_btn=navy_btn("Add",height=34,color=SUCCESS,hover=SUCCESS_H); del_btn=navy_btn("Delete",height=34,color=DANGER,hover=DANGER_H); cls_btn=navy_btn("Close",height=34)
        add_btn.clicked.connect(self._add); del_btn.clicked.connect(self._delete); cls_btn.clicked.connect(self.accept)
        br.addWidget(self._status,1); br.addWidget(add_btn); br.addWidget(del_btn); br.addWidget(cls_btn)
        lay.addLayout(br)

    def _reload(self):
        self._tbl.setRowCount(0); self._f_parent.clear(); self._f_parent.addItem("(No parent)", None)
        try:
            from models.customer_group import get_all_customer_groups
            groups = get_all_customer_groups()
        except Exception: groups=[]
        for g in groups:
            r=self._tbl.rowCount(); self._tbl.insertRow(r)
            parent_name = next((x["name"] for x in groups if x["id"]==g.get("parent_group_id")),"—")
            for col,val in enumerate([g["name"],parent_name]):
                it=QTableWidgetItem(val); it.setData(Qt.UserRole,g); self._tbl.setItem(r,col,it)
            self._tbl.setRowHeight(r,32)
            self._f_parent.addItem(g["name"], g["id"])

    def _add(self):
        name=self._f_name.text().strip()
        if not name: self._status.setText("Name required."); return
        parent_id=self._f_parent.currentData()
        try:
            from models.customer_group import create_customer_group
            create_customer_group(name,parent_id); self._f_name.clear(); self._reload()
            self._status.setText(f"Group '{name}' added."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")

    def _delete(self):
        row=self._tbl.currentRow()
        if row<0: self._status.setText("Select a group first."); return
        g=self._tbl.item(row,0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{g['name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.customer_group import delete_customer_group
            delete_customer_group(g["id"]); self._reload()
            self._status.setText("Deleted."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")


class WarehouseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Warehouses"); self.setMinimumSize(560,420)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        self._build(); self._reload()

    def _build(self):
        lay=QVBoxLayout(self); lay.setSpacing(10); lay.setContentsMargins(20,16,20,16)
        hdr=QWidget(); hdr.setFixedHeight(44); hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(16,0,16,0)
        hl.addWidget(QLabel("Warehouses",styleSheet=f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;"))
        lay.addWidget(hdr)
        self._tbl=QTableWidget(0,2); self._tbl.setHorizontalHeaderLabels(["Name","Company"])
        self._tbl.horizontalHeader().setStretchLastSection(True); self._tbl.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self._tbl.verticalHeader().setVisible(False); self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers); self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setStyleSheet(_settings_table_style()); lay.addWidget(self._tbl,1); lay.addWidget(hr())
        fr=QHBoxLayout(); fr.setSpacing(8)
        self._f_name=QLineEdit(); self._f_name.setPlaceholderText("Warehouse name *"); self._f_name.setFixedHeight(34)
        self._f_company=QComboBox(); self._f_company.setFixedHeight(34)
        fr.addWidget(self._f_name,2); fr.addWidget(QLabel("Company:",styleSheet="background:transparent;"),0); fr.addWidget(self._f_company,1)
        lay.addLayout(fr)
        br=QHBoxLayout(); br.setSpacing(8)
        self._status=QLabel(""); self._status.setStyleSheet(f"font-size:12px;color:{SUCCESS};background:transparent;")
        add_btn=navy_btn("Add",height=34,color=SUCCESS,hover=SUCCESS_H); del_btn=navy_btn("Delete",height=34,color=DANGER,hover=DANGER_H); cls_btn=navy_btn("Close",height=34)
        add_btn.clicked.connect(self._add); del_btn.clicked.connect(self._delete); cls_btn.clicked.connect(self.accept)
        br.addWidget(self._status,1); br.addWidget(add_btn); br.addWidget(del_btn); br.addWidget(cls_btn)
        lay.addLayout(br)

    def _reload(self):
        self._tbl.setRowCount(0); self._f_company.clear()
        try:
            from models.warehouse import get_all_warehouses
            from models.company import get_all_companies
            rows=get_all_warehouses(); companies=get_all_companies()
        except Exception: rows=[]; companies=[]
        for w in rows:
            r=self._tbl.rowCount(); self._tbl.insertRow(r)
            for col,val in enumerate([w["name"],w.get("company_name","")]):
                it=QTableWidgetItem(val); it.setData(Qt.UserRole,w); self._tbl.setItem(r,col,it)
            self._tbl.setRowHeight(r,32)
        for c in companies: self._f_company.addItem(c["name"],c["id"])

    def _add(self):
        name=self._f_name.text().strip(); cid=self._f_company.currentData()
        if not name or not cid: self._status.setText("Name and company required."); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;"); return
        try:
            from models.warehouse import create_warehouse
            create_warehouse(name,cid); self._f_name.clear(); self._reload()
            self._status.setText(f"Warehouse '{name}' added."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")

    def _delete(self):
        row=self._tbl.currentRow()
        if row<0: self._status.setText("Select a warehouse first."); return
        w=self._tbl.item(row,0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{w['name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.warehouse import delete_warehouse
            delete_warehouse(w["id"]); self._reload()
            self._status.setText("Deleted."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")


class CostCenterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cost Centers"); self.setMinimumSize(560,420)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        self._build(); self._reload()

    def _build(self):
        lay=QVBoxLayout(self); lay.setSpacing(10); lay.setContentsMargins(20,16,20,16)
        hdr=QWidget(); hdr.setFixedHeight(44); hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(16,0,16,0)
        hl.addWidget(QLabel("Cost Centers",styleSheet=f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;"))
        lay.addWidget(hdr)
        self._tbl=QTableWidget(0,2); self._tbl.setHorizontalHeaderLabels(["Name","Company"])
        self._tbl.horizontalHeader().setStretchLastSection(True); self._tbl.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self._tbl.verticalHeader().setVisible(False); self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers); self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setStyleSheet(_settings_table_style()); lay.addWidget(self._tbl,1); lay.addWidget(hr())
        fr=QHBoxLayout(); fr.setSpacing(8)
        self._f_name=QLineEdit(); self._f_name.setPlaceholderText("Cost center name *"); self._f_name.setFixedHeight(34)
        self._f_company=QComboBox(); self._f_company.setFixedHeight(34)
        fr.addWidget(self._f_name,2); fr.addWidget(QLabel("Company:",styleSheet="background:transparent;"),0); fr.addWidget(self._f_company,1)
        lay.addLayout(fr)
        br=QHBoxLayout(); br.setSpacing(8)
        self._status=QLabel(""); self._status.setStyleSheet(f"font-size:12px;color:{SUCCESS};background:transparent;")
        add_btn=navy_btn("Add",height=34,color=SUCCESS,hover=SUCCESS_H); del_btn=navy_btn("Delete",height=34,color=DANGER,hover=DANGER_H); cls_btn=navy_btn("Close",height=34)
        add_btn.clicked.connect(self._add); del_btn.clicked.connect(self._delete); cls_btn.clicked.connect(self.accept)
        br.addWidget(self._status,1); br.addWidget(add_btn); br.addWidget(del_btn); br.addWidget(cls_btn)
        lay.addLayout(br)

    def _reload(self):
        self._tbl.setRowCount(0); self._f_company.clear()
        try:
            from models.cost_center import get_all_cost_centers
            from models.company import get_all_companies
            rows=get_all_cost_centers(); companies=get_all_companies()
        except Exception: rows=[]; companies=[]
        for cc in rows:
            r=self._tbl.rowCount(); self._tbl.insertRow(r)
            for col,val in enumerate([cc["name"],cc.get("company_name","")]):
                it=QTableWidgetItem(val); it.setData(Qt.UserRole,cc); self._tbl.setItem(r,col,it)
            self._tbl.setRowHeight(r,32)
        for c in companies: self._f_company.addItem(c["name"],c["id"])

    def _add(self):
        name=self._f_name.text().strip(); cid=self._f_company.currentData()
        if not name or not cid: self._status.setText("Name and company required."); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;"); return
        try:
            from models.cost_center import create_cost_center
            create_cost_center(name,cid); self._f_name.clear(); self._reload()
            self._status.setText(f"Cost center '{name}' added."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")

    def _delete(self):
        row=self._tbl.currentRow()
        if row<0: self._status.setText("Select a cost center first."); return
        cc=self._tbl.item(row,0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{cc['name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.cost_center import delete_cost_center
            delete_cost_center(cc["id"]); self._reload()
            self._status.setText("Deleted."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")


class PriceListDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Price Lists"); self.setMinimumSize(480,380)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        self._build(); self._reload()

    def _build(self):
        lay=QVBoxLayout(self); lay.setSpacing(10); lay.setContentsMargins(20,16,20,16)
        hdr=QWidget(); hdr.setFixedHeight(44); hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(16,0,16,0)
        hl.addWidget(QLabel("Price Lists",styleSheet=f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;"))
        lay.addWidget(hdr)
        self._tbl=QTableWidget(0,2); self._tbl.setHorizontalHeaderLabels(["Name","Selling"])
        self._tbl.horizontalHeader().setStretchLastSection(True); self._tbl.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self._tbl.verticalHeader().setVisible(False); self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers); self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setStyleSheet(_settings_table_style()); lay.addWidget(self._tbl,1); lay.addWidget(hr())
        fr=QHBoxLayout(); fr.setSpacing(8)
        self._f_name=QLineEdit(); self._f_name.setPlaceholderText("Price list name *"); self._f_name.setFixedHeight(34)
        self._f_selling=QComboBox(); self._f_selling.addItems(["Selling","Not Selling"]); self._f_selling.setFixedHeight(34)
        fr.addWidget(self._f_name,2); fr.addWidget(self._f_selling,1)
        lay.addLayout(fr)
        br=QHBoxLayout(); br.setSpacing(8)
        self._status=QLabel(""); self._status.setStyleSheet(f"font-size:12px;color:{SUCCESS};background:transparent;")
        add_btn=navy_btn("Add",height=34,color=SUCCESS,hover=SUCCESS_H); del_btn=navy_btn("Delete",height=34,color=DANGER,hover=DANGER_H); cls_btn=navy_btn("Close",height=34)
        add_btn.clicked.connect(self._add); del_btn.clicked.connect(self._delete); cls_btn.clicked.connect(self.accept)
        br.addWidget(self._status,1); br.addWidget(add_btn); br.addWidget(del_btn); br.addWidget(cls_btn)
        lay.addLayout(br)

    def _reload(self):
        self._tbl.setRowCount(0)
        try:
            from models.price_list import get_all_price_lists
            rows=get_all_price_lists()
        except Exception: rows=[]
        for pl in rows:
            r=self._tbl.rowCount(); self._tbl.insertRow(r)
            for col,val in enumerate([pl["name"],"Yes" if pl["selling"] else "No"]):
                it=QTableWidgetItem(val); it.setData(Qt.UserRole,pl); self._tbl.setItem(r,col,it)
            self._tbl.setRowHeight(r,32)

    def _add(self):
        name=self._f_name.text().strip(); selling=self._f_selling.currentIndex()==0
        if not name: self._status.setText("Name required."); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;"); return
        try:
            from models.price_list import create_price_list
            create_price_list(name,selling); self._f_name.clear(); self._reload()
            self._status.setText(f"Price list '{name}' added."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")

    def _delete(self):
        row=self._tbl.currentRow()
        if row<0: self._status.setText("Select a price list first."); return
        pl=self._tbl.item(row,0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{pl['name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.price_list import delete_price_list
            delete_price_list(pl["id"]); self._reload()
            self._status.setText("Deleted."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")


class CustomerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customers"); self.setMinimumSize(860,560)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        self._build(); self._reload()

    def _build(self):
        lay=QVBoxLayout(self); lay.setSpacing(10); lay.setContentsMargins(20,16,20,16)
        hdr=QWidget(); hdr.setFixedHeight(44); hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(16,0,16,0)
        hl.addWidget(QLabel("Customers",styleSheet=f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;"))
        lay.addWidget(hdr)

        sr=QHBoxLayout(); sr.setSpacing(8)
        self._search=QLineEdit(); self._search.setPlaceholderText("Search by name, trade name or phone…"); self._search.setFixedHeight(34)
        self._search.textChanged.connect(self._do_search)
        sr.addWidget(self._search)
        lay.addLayout(sr)

        self._tbl=QTableWidget(0,6)
        self._tbl.setHorizontalHeaderLabels(["Name","Type","Group","Phone","City","Price List"])
        hh=self._tbl.horizontalHeader(); hh.setSectionResizeMode(0,QHeaderView.Stretch)
        for ci in [1,2,3,4,5]: hh.setSectionResizeMode(ci,QHeaderView.Fixed); self._tbl.setColumnWidth(ci,110)
        self._tbl.verticalHeader().setVisible(False); self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers); self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setStyleSheet(_settings_table_style()); lay.addWidget(self._tbl,1); lay.addWidget(hr())

        form=QGridLayout(); form.setSpacing(8)
        self._f_name  =QLineEdit(); self._f_name.setPlaceholderText("Customer name *"); self._f_name.setFixedHeight(32)
        self._f_type  =QComboBox(); self._f_type.addItems(["","Individual","Company"]); self._f_type.setFixedHeight(32)
        self._f_trade =QLineEdit(); self._f_trade.setPlaceholderText("Trade name"); self._f_trade.setFixedHeight(32)
        self._f_phone =QLineEdit(); self._f_phone.setPlaceholderText("Phone"); self._f_phone.setFixedHeight(32)
        self._f_email =QLineEdit(); self._f_email.setPlaceholderText("Email"); self._f_email.setFixedHeight(32)
        self._f_city  =QLineEdit(); self._f_city.setPlaceholderText("City"); self._f_city.setFixedHeight(32)
        self._f_house =QLineEdit(); self._f_house.setPlaceholderText("House No."); self._f_house.setFixedHeight(32)
        self._f_group =QComboBox(); self._f_group.setFixedHeight(32)
        self._f_wh    =QComboBox(); self._f_wh.setFixedHeight(32)
        self._f_cc    =QComboBox(); self._f_cc.setFixedHeight(32)
        self._f_pl    =QComboBox(); self._f_pl.setFixedHeight(32)

        for lbl_txt, widget, r, c in [
            ("Name *",       self._f_name,  0,0), ("Type",         self._f_type,  0,2),
            ("Trade Name",   self._f_trade, 1,0), ("Phone",        self._f_phone, 1,2),
            ("Email",        self._f_email, 2,0), ("City",         self._f_city,  2,2),
            ("House No.",    self._f_house, 3,0), ("Group *",      self._f_group, 3,2),
            ("Warehouse *",  self._f_wh,    4,0), ("Cost Center *",self._f_cc,    4,2),
            ("Price List *", self._f_pl,    5,0),
        ]:
            form.addWidget(QLabel(lbl_txt,styleSheet="background:transparent;font-size:12px;"),r,c)
            form.addWidget(widget,r,c+1)
        lay.addLayout(form)

        br=QHBoxLayout(); br.setSpacing(8)
        self._status=QLabel(""); self._status.setStyleSheet(f"font-size:12px;color:{SUCCESS};background:transparent;")
        add_btn=navy_btn("Add Customer",height=34,color=SUCCESS,hover=SUCCESS_H)
        del_btn=navy_btn("Delete",height=34,color=DANGER,hover=DANGER_H)
        cls_btn=navy_btn("Close",height=34)
        add_btn.clicked.connect(self._add); del_btn.clicked.connect(self._delete); cls_btn.clicked.connect(self.accept)
        br.addWidget(self._status,1); br.addWidget(add_btn); br.addWidget(del_btn); br.addWidget(cls_btn)
        lay.addLayout(br)

    def _reload(self):
        self._tbl.setRowCount(0)
        try:
            from models.customer import get_all_customers
            custs=get_all_customers()
        except Exception: custs=[]
        self._populate_combos()
        self._populate_table(custs)

    def _do_search(self, query):
        if not query.strip(): self._reload(); return
        try:
            from models.customer import search_customers
            custs=search_customers(query)
        except Exception: custs=[]
        self._populate_table(custs)

    def _populate_table(self, custs):
        self._tbl.setRowCount(0)
        for c in custs:
            r=self._tbl.rowCount(); self._tbl.insertRow(r)
            for col,val in enumerate([
                c["customer_name"], c.get("customer_type",""),
                c.get("customer_group_name",""), c.get("custom_telephone_number",""),
                c.get("custom_city",""), c.get("price_list_name",""),
            ]):
                it=QTableWidgetItem(str(val)); it.setData(Qt.UserRole,c); self._tbl.setItem(r,col,it)
            self._tbl.setRowHeight(r,32)

    def _populate_combos(self):
        try:
            from models.customer_group import get_all_customer_groups
            from models.warehouse import get_all_warehouses
            from models.cost_center import get_all_cost_centers
            from models.price_list import get_all_price_lists
            groups=get_all_customer_groups(); whs=get_all_warehouses()
            ccs=get_all_cost_centers(); pls=get_all_price_lists()
        except Exception: groups=[];whs=[];ccs=[];pls=[]
        for cb in [self._f_group,self._f_wh,self._f_cc,self._f_pl]: cb.clear()
        for g in groups: self._f_group.addItem(g["name"],g["id"])
        for w in whs: self._f_wh.addItem(f"{w['name']} ({w.get('company_name','')})",w["id"])
        for cc in ccs: self._f_cc.addItem(f"{cc['name']} ({cc.get('company_name','')})",cc["id"])
        for pl in pls: self._f_pl.addItem(pl["name"],pl["id"])

    def _add(self):
        name=self._f_name.text().strip()
        if not name: self._status.setText("Customer name required."); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;"); return
        gid=self._f_group.currentData(); wid=self._f_wh.currentData(); ccid=self._f_cc.currentData(); plid=self._f_pl.currentData()
        if not all([gid,wid,ccid,plid]): self._status.setText("Group, Warehouse, Cost Center and Price List are required."); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;"); return
        try:
            from models.customer import create_customer
            create_customer(
                customer_name=name, customer_group_id=gid,
                custom_warehouse_id=wid, custom_cost_center_id=ccid,
                default_price_list_id=plid,
                customer_type=self._f_type.currentText() or None,
                custom_trade_name=self._f_trade.text().strip(),
                custom_telephone_number=self._f_phone.text().strip(),
                custom_email_address=self._f_email.text().strip(),
                custom_city=self._f_city.text().strip(),
                custom_house_no=self._f_house.text().strip(),
            )
            for f in [self._f_name,self._f_trade,self._f_phone,self._f_email,self._f_city,self._f_house]: f.clear()
            self._reload()
            self._status.setText(f"Customer '{name}' added."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")

    def _delete(self):
        row=self._tbl.currentRow()
        if row<0: self._status.setText("Select a customer first."); return
        c=self._tbl.item(row,0).data(Qt.UserRole)
        if QMessageBox.question(self,"Delete",f"Delete '{c['customer_name']}'?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes: return
        try:
            from models.customer import delete_customer
            delete_customer(c["id"]); self._reload()
            self._status.setText("Deleted."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")


class PaymentDialog(QDialog):
    def __init__(self, parent=None, total=0.0, customer=None):
        super().__init__(parent)
        self.total    = total
        self._method  = "Cash"
        self._method_btns = {}
        self.setWindowTitle("Payment")
        self.setFixedSize(400, 420)
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        hdr = QWidget(); hdr.setFixedHeight(44)
        hdr.setStyleSheet(f"background-color: {NAVY}; border-radius: 5px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16, 0, 16, 0)
        t = QLabel("Payment")
        t.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {WHITE}; background: transparent;")
        hl.addWidget(t); layout.addWidget(hdr)

        total_row = QHBoxLayout()
        lbl = QLabel("Total Due"); lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
        val = QLabel(f"$ {self.total:.2f}")
        val.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {NAVY}; background: transparent;")
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        total_row.addWidget(lbl); total_row.addWidget(val)
        layout.addLayout(total_row); layout.addWidget(hr())

        m_lbl = QLabel("Payment Method"); m_lbl.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
        layout.addWidget(m_lbl)

        method_row = QHBoxLayout(); method_row.setSpacing(6)
        for m in ["Cash", "Card", "Mobile", "Credit"]:
            b = navy_btn(m, height=34, color=ACCENT if m == "Cash" else NAVY, hover=ACCENT_H)
            b.clicked.connect(lambda _, x=m: self._set_method(x))
            method_row.addWidget(b); self._method_btns[m] = b
        layout.addLayout(method_row)

        amt_row = QHBoxLayout()
        lbl2 = QLabel("Amount Tendered"); lbl2.setFixedWidth(148)
        lbl2.setStyleSheet(f"color: {MUTED}; background: transparent;")
        self._amt = QLineEdit("0.00"); self._amt.setFixedHeight(36)
        self._amt.setAlignment(Qt.AlignRight)
        self._amt.setStyleSheet(f"""
            QLineEdit {{
                font-size: 20px; font-weight: bold; color: {NAVY};
                background: {WHITE}; border: 2px solid {BORDER};
                border-radius: 5px; padding: 2px 10px;
            }}
            QLineEdit:focus {{ border: 2px solid {ACCENT}; }}
        """)
        self._amt.textChanged.connect(self._calc_change)
        amt_row.addWidget(lbl2); amt_row.addWidget(self._amt)
        layout.addLayout(amt_row)

        quick_row = QHBoxLayout(); quick_row.setSpacing(6)
        for amt in [5, 10, 20, 50, 100]:
            b = navy_btn(f"${amt}", height=30, font_size=12)
            b.clicked.connect(lambda _, a=amt: self._amt.setText(f"{a:.2f}"))
            quick_row.addWidget(b)
        exact_btn = navy_btn("Exact", height=30, font_size=12, color=SUCCESS, hover=SUCCESS_H)
        exact_btn.clicked.connect(lambda: self._amt.setText(f"{self.total:.2f}"))
        quick_row.addWidget(exact_btn)
        layout.addLayout(quick_row)

        chg_row = QHBoxLayout()
        lbl3 = QLabel("Change"); lbl3.setFixedWidth(148)
        lbl3.setStyleSheet(f"color: {MUTED}; background: transparent;")
        self._chg = QLabel("$ 0.00")
        self._chg.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {ORANGE}; background: transparent;")
        self._chg.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        chg_row.addWidget(lbl3); chg_row.addWidget(self._chg)
        layout.addLayout(chg_row); layout.addStretch()

        self._confirm_btn = navy_btn("Confirm Payment", height=44, color=SUCCESS, hover=SUCCESS_H)
        self._confirm_btn.clicked.connect(self._confirm); layout.addWidget(self._confirm_btn)

    def _set_method(self, method):
        self._method = method
        for m, b in self._method_btns.items():
            c = ACCENT if m == method else NAVY
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c}; color: {WHITE}; border: none;
                    border-radius: 5px; font-size: 12px; font-weight: bold; padding: 0 14px;
                }}
                QPushButton:hover {{ background-color: {ACCENT_H}; }}
            """)

    def _calc_change(self):
        try:
            tendered = float(self._amt.text() or "0")
            change   = max(tendered - self.total, 0.0)
            self._chg.setText(f"$ {change:.2f}")
        except ValueError:
            self._chg.setText("$ 0.00")

    def _confirm(self):
        try:
            tendered = float(self._amt.text() or "0")
        except ValueError:
            tendered = 0.0
        if tendered < self.total:
            QMessageBox.warning(self, "Insufficient Amount",
                f"Tendered ${tendered:.2f} is less than total ${self.total:.2f}")
            return
        change = tendered - self.total
        # Expose for caller
        self.accepted_tendered = tendered
        self.accepted_method   = self._method
        self.accepted_change   = change
        self.accepted_customer = None
        QMessageBox.information(self, "Payment Confirmed", f"Payment received.\n\nChange: $ {change:.2f}")
        self.accept()


# =============================================================================
# HOLD / RECALL DIALOG
# =============================================================================
class HoldRecallDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hold / Recall Orders")
        self.setFixedSize(560, 360)
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        hdr = QWidget(); hdr.setFixedHeight(42)
        hdr.setStyleSheet(f"background-color: {NAVY}; border-radius: 5px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16, 0, 16, 0)
        t = QLabel("Held Orders")
        t.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {WHITE}; background: transparent;")
        hl.addWidget(t); layout.addWidget(hdr)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Ref #", "Customer", "Total", "Time"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setStyleSheet(f"""
            QTableWidget {{ background: {WHITE}; border: 1px solid {BORDER}; }}
            QHeaderView::section {{
                background-color: {NAVY}; color: {WHITE};
                padding: 8px; font-size: 11px; font-weight: bold;
                border: none; border-right: 1px solid {NAVY_2};
            }}
        """)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        recall_btn = navy_btn("Recall", height=36, color=SUCCESS, hover=SUCCESS_H)
        delete_btn = navy_btn("Delete", height=36, color=DANGER, hover=DANGER_H)
        close_btn  = navy_btn("Close",  height=36)
        recall_btn.clicked.connect(lambda: coming_soon(self, "Recall — connect to DB"))
        delete_btn.clicked.connect(lambda: coming_soon(self, "Delete held — connect to DB"))
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(recall_btn); btn_row.addWidget(delete_btn)
        btn_row.addStretch(); btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


# =============================================================================
# MANAGE USERS DIALOG
# =============================================================================
class ManageUsersDialog(QDialog):
    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.current_user = current_user or {}
        self.setWindowTitle("Manage Users")
        self.setMinimumSize(640, 460)
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
        self._build(); self._reload()

    def _build(self):
        layout = QVBoxLayout(self); layout.setSpacing(12); layout.setContentsMargins(20, 16, 20, 16)

        hdr = QWidget(); hdr.setFixedHeight(44)
        hdr.setStyleSheet(f"background-color: {NAVY}; border-radius: 5px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16, 0, 16, 0)
        t = QLabel("Manage Users")
        t.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {WHITE}; background: transparent;")
        sub = QLabel("Admin access required")
        sub.setStyleSheet(f"font-size: 11px; color: {MID}; background: transparent;")
        hl.addWidget(t); hl.addStretch(); hl.addWidget(sub)
        layout.addWidget(hdr)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Username", "Role"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed); self.table.setColumnWidth(0, 60)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed); self.table.setColumnWidth(2, 110)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setStyleSheet(f"""
            QTableWidget {{ background: {WHITE}; border: 1px solid {BORDER};
                gridline-color: {LIGHT}; outline: none; }}
            QTableWidget::item           {{ padding: 8px; }}
            QTableWidget::item:selected  {{ background-color: {ACCENT}; color: {WHITE}; }}
            QTableWidget::item:alternate {{ background-color: {ROW_ALT}; }}
            QHeaderView::section {{
                background-color: {NAVY}; color: {WHITE};
                padding: 10px 8px; border: none; border-right: 1px solid {NAVY_2};
                font-size: 11px; font-weight: bold;
            }}
        """)
        layout.addWidget(self.table, 1); layout.addWidget(hr())

        add_lbl = QLabel("Add New User")
        add_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {NAVY}; background: transparent;")
        layout.addWidget(add_lbl)

        form_row = QHBoxLayout(); form_row.setSpacing(10)
        self._new_username = QLineEdit(); self._new_username.setPlaceholderText("Username"); self._new_username.setFixedHeight(36)
        self._new_password = QLineEdit(); self._new_password.setPlaceholderText("Password")
        self._new_password.setEchoMode(QLineEdit.Password); self._new_password.setFixedHeight(36)
        self._new_role = QComboBox(); self._new_role.addItems(["cashier", "admin"])
        self._new_role.setFixedHeight(36); self._new_role.setFixedWidth(110)
        add_btn = navy_btn("Add User", height=36, color=SUCCESS, hover=SUCCESS_H)
        add_btn.clicked.connect(self._add_user)
        form_row.addWidget(self._new_username, 2); form_row.addWidget(self._new_password, 2)
        form_row.addWidget(self._new_role); form_row.addWidget(add_btn)
        layout.addLayout(form_row)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        del_btn   = navy_btn("Delete Selected", height=36, color=DANGER, hover=DANGER_H)
        close_btn = navy_btn("Close",           height=36)
        del_btn.clicked.connect(self._delete_user); close_btn.clicked.connect(self.accept)
        btn_row.addWidget(del_btn); btn_row.addStretch(); btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._status = QLabel("")
        self._status.setStyleSheet(f"font-size: 12px; background: transparent; color: {SUCCESS};")
        layout.addWidget(self._status)

    def _reload(self):
        self.table.setRowCount(0)
        try:
            from models.user import get_all_users
            users = get_all_users()
        except Exception:
            users = [{"id": 1, "username": "admin", "role": "admin"}, {"id": 2, "username": "cashier1", "role": "cashier"}]
        for u in users:
            r = self.table.rowCount(); self.table.insertRow(r)
            for c, key in enumerate(["id", "username", "role"]):
                item = QTableWidgetItem(str(u.get(key, "")))
                item.setTextAlignment(Qt.AlignCenter if c != 1 else Qt.AlignLeft | Qt.AlignVCenter)
                if key == "role":
                    item.setForeground(QColor(ACCENT if u["role"] == "admin" else MUTED))
                item.setData(Qt.UserRole, u)
                self.table.setItem(r, c, item)
            self.table.setRowHeight(r, 36)

    def _add_user(self):
        username = self._new_username.text().strip(); password = self._new_password.text().strip()
        role     = self._new_role.currentText()
        if not username or not password:
            self._show_status("Username and password are required.", error=True); return
        try:
            from models.user import create_user
            user = create_user(username, password, role)
            if user:
                self._new_username.clear(); self._new_password.clear()
                self._new_role.setCurrentIndex(0); self._reload()
                self._show_status(f"User '{username}' ({role}) created successfully.")
            else:
                self._show_status(f"Username '{username}' already exists.", error=True)
        except Exception as e:
            self._show_status(f"Error: {e}", error=True)

    def _delete_user(self):
        row = self.table.currentRow()
        if row < 0: self._show_status("Select a user to delete.", error=True); return
        item = self.table.item(row, 0)
        if not item: return
        u = item.data(Qt.UserRole)
        if u["id"] == self.current_user.get("id"):
            self._show_status("You cannot delete your own account.", error=True); return
        if QMessageBox.question(self, "Delete User",
            f"Delete user '{u['username']}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            from models.user import delete_user
            if delete_user(u["id"]):
                self._reload(); self._show_status(f"User '{u['username']}' deleted.")
            else:
                self._show_status("Could not delete user.", error=True)
        except Exception as e:
            self._show_status(f"Error: {e}", error=True)

    def _show_status(self, msg, error=False):
        color = DANGER if error else SUCCESS
        self._status.setStyleSheet(f"font-size: 12px; background: transparent; color: {color};")
        self._status.setText(msg)
        QTimer.singleShot(4000, lambda: self._status.setText(""))


# =============================================================================
# ADMIN DASHBOARD
# =============================================================================
class AdminDashboard(QWidget):
    def __init__(self, parent_window=None, user=None):
        super().__init__()
        self.parent_window = parent_window
        self.user = user or {}
        self._build()
        self._load_data()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        nav = QWidget(); nav.setFixedHeight(54)
        nav.setStyleSheet(f"background-color: {NAVY};")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(20, 8, 20, 8); nav_layout.setSpacing(12)

        logo = QLabel("POS System")
        logo.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {WHITE}; background: transparent; letter-spacing: 1px;")
        nav_layout.addWidget(logo)

        badge = QLabel("ADMIN")
        badge.setStyleSheet(f"""
            background-color: {ACCENT}; color: {WHITE};
            border-radius: 4px; font-size: 10px; font-weight: bold;
            padding: 2px 8px; letter-spacing: 1px;
        """)
        nav_layout.addWidget(badge); nav_layout.addStretch()

        date_lbl = QLabel(QDate.currentDate().toString("dd MMM yyyy"))
        date_lbl.setStyleSheet(f"font-size: 12px; color: {MID}; background: transparent;")
        nav_layout.addWidget(date_lbl); nav_layout.addSpacing(16)

        self._pos_btn = QPushButton("Switch to POS  →")
        self._pos_btn.setFixedHeight(34)
        self._pos_btn.setCursor(Qt.PointingHandCursor)
        self._pos_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WHITE}; color: {NAVY};
                border: none; border-radius: 4px;
                font-size: 12px; font-weight: bold; padding: 0 16px;
            }}
            QPushButton:hover {{ background-color: {LIGHT}; }}
        """)
        if self.parent_window:
            self._pos_btn.clicked.connect(self.parent_window.switch_to_pos)
        nav_layout.addWidget(self._pos_btn)

        user_lbl = QLabel(self.user.get("username", ""))
        user_lbl.setStyleSheet(f"font-size: 12px; color: {OFF_WHITE}; background: transparent;")
        nav_layout.addSpacing(8); nav_layout.addWidget(user_lbl); nav_layout.addSpacing(4)

        logout_btn = navy_btn("Logout", height=30, width=72, color=DANGER, hover=DANGER_H)
        if self.parent_window:
            logout_btn.clicked.connect(self.parent_window._logout)
        nav_layout.addWidget(logout_btn)

        root.addWidget(nav); root.addWidget(hr())

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {OFF_WHITE}; }}")

        body = QWidget(); body.setStyleSheet(f"background: {OFF_WHITE};")
        body_layout = QVBoxLayout(body)
        body_layout.setSpacing(20); body_layout.setContentsMargins(24, 20, 24, 24)

        body_layout.addWidget(self._section_label("Today at a Glance"))
        body_layout.addLayout(self._build_stats_row())

        content_row = QHBoxLayout(); content_row.setSpacing(20)

        left_col = QVBoxLayout(); left_col.setSpacing(12)
        left_col.addWidget(self._section_label("Recent Sales  (Today)"))
        left_col.addWidget(self._build_sales_table())
        content_row.addLayout(left_col, 3)

        right_col = QVBoxLayout(); right_col.setSpacing(12)
        right_col.addWidget(self._section_label("Quick Actions"))
        right_col.addWidget(self._build_quick_actions())
        right_col.addWidget(self._section_label("Stock Alerts"))
        right_col.addWidget(self._build_stock_alerts())
        right_col.addStretch()
        content_row.addLayout(right_col, 1)

        body_layout.addLayout(content_row)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            font-size: 13px; font-weight: bold; color: {NAVY};
            background: transparent;
            border-left: 3px solid {ACCENT}; padding-left: 8px;
        """)
        return lbl

    def _build_stats_row(self):
        layout = QHBoxLayout(); layout.setSpacing(14)
        self._stat_widgets = {}

        for key, label, initial, color in [
            ("revenue",     "Today's Revenue",  "$0.00",    NAVY),
            ("txn_count",   "Transactions",     "0",        ACCENT),
            ("items_sold",  "Items Sold",        "0",        SUCCESS),
            ("top_method",  "Top Payment",       "—",        AMBER),
        ]:
            card = QWidget()
            card.setStyleSheet(f"""
                QWidget {{
                    background-color: {WHITE};
                    border: 1px solid {BORDER};
                    border-radius: 8px;
                    border-top: 3px solid {color};
                }}
            """)
            card.setFixedHeight(90)
            cl = QVBoxLayout(card); cl.setContentsMargins(16, 12, 16, 12); cl.setSpacing(4)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent; font-weight: bold; letter-spacing: 0.5px;")
            val = QLabel(initial)
            val.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: bold; background: transparent;")
            cl.addWidget(lbl); cl.addWidget(val)
            layout.addWidget(card, 1)
            self._stat_widgets[key] = val
        return layout

    def _build_sales_table(self):
        self.sales_table = QTableWidget(0, 6)
        self.sales_table.setHorizontalHeaderLabels(["Invoice #", "Time", "Cashier", "Method", "Total", "Synced"])
        hh = self.sales_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed);  self.sales_table.setColumnWidth(0, 100)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Fixed);  self.sales_table.setColumnWidth(3, 90)
        hh.setSectionResizeMode(4, QHeaderView.Fixed);  self.sales_table.setColumnWidth(4, 100)
        hh.setSectionResizeMode(5, QHeaderView.Fixed);  self.sales_table.setColumnWidth(5, 70)
        self.sales_table.verticalHeader().setVisible(False)
        self.sales_table.setAlternatingRowColors(True)
        self.sales_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sales_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sales_table.setFixedHeight(260)
        self.sales_table.setStyleSheet(f"""
            QTableWidget {{ background: {WHITE}; border: 1px solid {BORDER};
                gridline-color: {LIGHT}; outline: none; }}
            QTableWidget::item           {{ padding: 6px 8px; }}
            QTableWidget::item:selected  {{ background-color: {ACCENT}; color: {WHITE}; }}
            QTableWidget::item:alternate {{ background-color: {ROW_ALT}; }}
            QHeaderView::section {{
                background-color: {NAVY}; color: {WHITE};
                padding: 8px; border: none; border-right: 1px solid {NAVY_2};
                font-size: 11px; font-weight: bold;
            }}
        """)
        return self.sales_table

    def _build_quick_actions(self):
        card = QWidget()
        card.setStyleSheet(f"QWidget {{ background-color: {WHITE}; border: 1px solid {BORDER}; border-radius: 8px; }}")
        cl = QVBoxLayout(card); cl.setContentsMargins(16, 14, 16, 14); cl.setSpacing(8)

        actions = [
            ("Manage Users",    self._open_manage_users,              ACCENT),
            ("Stock File",      self._open_stock,                     NAVY),
            ("Sales History",   self._open_sales_history,             NAVY_3),
            ("Day Shift",       self._open_day_shift,                 NAVY_2),
            ("Companies",       lambda: self._open_settings_at(1),    MUTED),
            ("Customer Groups", lambda: self._open_settings_at(2),    MUTED),
            ("Warehouses",      lambda: self._open_settings_at(3),    MUTED),
            ("Cost Centers",    lambda: self._open_settings_at(4),    MUTED),
            ("Price Lists",     lambda: self._open_settings_at(5),    MUTED),
            ("Customers",       lambda: self._open_settings_at(6),    MUTED),
            ("Refresh Data",    self._load_data,                      SUCCESS),
        ]
        for label, handler, color in actions:
            btn = QPushButton(label)
            btn.setFixedHeight(38)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color}14; color: {color};
                    border: 1px solid {color}44; border-radius: 5px;
                    font-size: 13px; font-weight: bold;
                    text-align: left; padding: 0 14px;
                }}
                QPushButton:hover {{ background-color: {color}; color: {WHITE}; border-color: {color}; }}
            """)
            btn.clicked.connect(handler)
            cl.addWidget(btn)
        return card

    def _build_stock_alerts(self):
        self._stock_alert_widget = QWidget()
        self._stock_alert_widget.setStyleSheet(f"QWidget {{ background-color: {WHITE}; border: 1px solid {BORDER}; border-radius: 8px; }}")
        self._stock_alert_layout = QVBoxLayout(self._stock_alert_widget)
        self._stock_alert_layout.setContentsMargins(14, 12, 14, 12); self._stock_alert_layout.setSpacing(6)
        lbl = QLabel("No low-stock alerts"); lbl.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
        self._stock_alert_layout.addWidget(lbl)
        return self._stock_alert_widget

    def _load_data(self):
        try:
            from models.sale import get_today_sales, get_today_total, get_today_total_by_method
            sales   = get_today_sales(); total = get_today_total()
            by_meth = get_today_total_by_method()
            top_m   = max(by_meth, key=by_meth.get) if by_meth else "—"
            items   = sum(1 for _ in sales)
        except Exception:
            sales, total, top_m, items = [], 0.0, "Cash", 0

        self._stat_widgets["revenue"].setText(f"${total:,.2f}")
        self._stat_widgets["txn_count"].setText(str(len(sales)))
        self._stat_widgets["items_sold"].setText(str(items))
        self._stat_widgets["top_method"].setText(top_m)

        self.sales_table.setRowCount(0)
        for s in sales[:50]:
            r = self.sales_table.rowCount(); self.sales_table.insertRow(r)
            for c, (key, fmt) in enumerate([
                ("number", lambda v: f"#{v}"),
                ("time",   lambda v: str(v)),
                ("user",   lambda v: str(v)),
                ("method", lambda v: str(v)),
                ("total",  lambda v: f"${v:.2f}"),
                ("synced", lambda v: "✓" if v else "—"),
            ]):
                raw = s.get(key, ""); text = fmt(raw)
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter if c != 2 else Qt.AlignLeft | Qt.AlignVCenter)
                if key == "total": item.setForeground(QColor(ACCENT))
                elif key == "synced": item.setForeground(QColor(SUCCESS if s.get("synced") else MUTED))
                self.sales_table.setItem(r, c, item)
            self.sales_table.setRowHeight(r, 34)

        while self._stock_alert_layout.count():
            item = self._stock_alert_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        try:
            from models.product import get_all_products
            low = [p for p in get_all_products() if p["stock"] <= 5]
        except Exception:
            low = []

        if not low:
            lbl = QLabel("✓  All stock levels OK"); lbl.setStyleSheet(f"color: {SUCCESS}; font-size: 12px; background: transparent;")
            self._stock_alert_layout.addWidget(lbl)
        else:
            for p in low[:8]:
                row_w = QWidget(); row_w.setStyleSheet("background: transparent;")
                rh = QHBoxLayout(row_w); rh.setContentsMargins(0, 0, 0, 0)
                nm = QLabel(p["name"]); nm.setStyleSheet(f"color: {DARK_TEXT}; font-size: 12px; background: transparent;")
                st = QLabel(f"Stock: {p['stock']}"); st.setStyleSheet(f"color: {DANGER}; font-size: 12px; font-weight: bold; background: transparent;")
                rh.addWidget(nm, 1); rh.addWidget(st)
                self._stock_alert_layout.addWidget(row_w)

    def _open_manage_users(self):
        ManageUsersDialog(self, current_user=self.user).exec()

    def _open_stock(self):
        if _HAS_STOCK: StockFileDialog(self).exec()
        else: coming_soon(self, "Stock File")

    def _open_sales_history(self):
        if _HAS_SALES_LIST: SalesListDialog(self).exec()
        else: coming_soon(self, "Sales History")

    def _open_day_shift(self):
        if _HAS_DAY_SHIFT: DayShiftDialog(self, user=self.user).exec()
        else: coming_soon(self, "Day Shift")

    def _open_settings_at(self, page_index: int = 0):
        if _HAS_SETTINGS_DIALOG:
            dlg = SettingsDialog(self, user=self.user)
            dlg._switch(page_index)
            dlg.exec()
        else:
            coming_soon(self, "Settings — add views/dialogs/settings_dialog.py")


# =============================================================================
# CASHIER POS VIEW
# =============================================================================
class POSView(QWidget):
    MAX_ROWS = 20

    def __init__(self, parent_window=None, user=None):
        super().__init__()
        self.parent_window  = parent_window
        self.user           = user or {"username": "cashier", "role": "cashier"}
        self._active_row    = -1
        self._active_col    = -1
        self._numpad_buffer = ""
        self._block_signals = False
        self._cat_page        = 0
        self._last_filled_row = -1
        self._selected_customer: dict | None = None

        # ── Previous transaction info ─────────────────────────────────────────
        # Shown in the footer bar so the cashier always sees the last sale
        self._prev_paid:   float = 0.0
        self._prev_change: float = 0.0

        # Inline search state
        self._inline_edit   = None
        self._inline_popup  = None
        self._inline_row    = -1
        self._inline_col    = -1
        self._build_ui()

    # =========================================================================
    # ROOT LAYOUT
    # =========================================================================
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self._build_nav())

        body = QHBoxLayout()
        body.setSpacing(0)
        body.setContentsMargins(0, 0, 0, 0)
        body.addWidget(self._build_left_panel(), 1)
        body.addWidget(hr(horizontal=False))
        body.addWidget(self._build_right_panel())
        layout.addLayout(body, 2)   # invoice area ~2/5 of page

        layout.addWidget(hr())
        layout.addWidget(self._build_bottom_grid(), 3)   # product grid gets remaining

    # =========================================================================
    # NAV BAR
    # =========================================================================
    def _build_nav(self):
        bar = QWidget(); bar.setFixedHeight(44)
        bar.setStyleSheet(f"background-color: {NAVY};")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(6)

        logo = QLabel("Havano POS")
        logo.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {WHITE}; background: transparent;")
        date_lbl = QLabel(QDate.currentDate().toString("dd/MM/yyyy"))
        date_lbl.setStyleSheet(f"font-size: 12px; color: {MID}; background: transparent;")
        layout.addWidget(logo); layout.addSpacing(4); layout.addWidget(date_lbl); layout.addSpacing(8)

        def _npb(text, handler, color=NAVY_2, hov=NAVY_3):
            b = QPushButton(text); b.setFixedHeight(26); b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color}; color: {WHITE}; border: none;
                    border-radius: 3px; font-size: 11px; font-weight: bold; padding: 0 9px;
                }}
                QPushButton:hover {{ background-color: {hov}; }}
            """)
            b.clicked.connect(handler)
            return b

        layout.addWidget(_npb("Day Shift", self._open_day_shift))
        layout.addWidget(_npb("Stock",     self._open_stock_file))
        layout.addWidget(_npb("Settings",  self._open_settings))
        layout.addSpacing(10)

        f7_btn = QPushButton("F7  Sales"); f7_btn.setFixedHeight(26); f7_btn.setCursor(Qt.PointingHandCursor)
        f7_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT}; color: {WHITE}; border: none;
                border-radius: 3px; font-size: 11px; font-weight: bold; padding: 0 8px;
            }}
            QPushButton:hover {{ background-color: {ACCENT_H}; }}
        """)
        f7_btn.clicked.connect(self._open_sales_list)
        layout.addWidget(f7_btn); layout.addSpacing(6)

        self._cust_btn = QPushButton("👤  Customer")
        self._cust_btn.setFixedHeight(26); self._cust_btn.setMaximumWidth(170)
        self._cust_btn.setCursor(Qt.PointingHandCursor)
        self._cust_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY_2}; color: {MID}; border: 1px solid {NAVY_3};
                border-radius: 3px; font-size: 11px; padding: 0 8px;
            }}
            QPushButton:hover {{ background-color: {NAVY_3}; color: {WHITE}; }}
        """)
        self._cust_btn.clicked.connect(self._select_customer)
        layout.addWidget(self._cust_btn); layout.addSpacing(4)

        # ── havano.local — truly centred in the available space ─────────────────
        layout.addStretch(1)
        from PySide6.QtWidgets import QLabel as _QL
        havano_lnk = _QL('<a href="https://havano.local" style="color:#ffffff;font-size:11px;text-decoration:none;font-weight:bold;">havano.local</a>')
        havano_lnk.setOpenExternalLinks(True)
        havano_lnk.setAlignment(Qt.AlignCenter)
        havano_lnk.setStyleSheet("background: transparent;")
        havano_lnk.setCursor(Qt.PointingHandCursor)
        layout.addWidget(havano_lnk)
        layout.addStretch(1)

        try:
            from models.user import is_admin
            if self.user and is_admin(self.user):
                dash_btn = QPushButton("Dashboard"); dash_btn.setFixedHeight(26); dash_btn.setCursor(Qt.PointingHandCursor)
                dash_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ACCENT}; color: {WHITE};
                        border: none; border-radius: 3px; font-size: 11px; padding: 0 10px;
                    }}
                    QPushButton:hover {{ background-color: {ACCENT_H}; }}
                """)
                if self.parent_window:
                    dash_btn.clicked.connect(self.parent_window.switch_to_dashboard)
                layout.addWidget(dash_btn); layout.addSpacing(4)
        except Exception:
            pass

        role_badge = QLabel(self.user.get("role", "").upper())
        role_c = ACCENT if self.user.get("role") == "admin" else NAVY_3
        role_badge.setStyleSheet(f"background-color: {role_c}; color: {WHITE}; border-radius: 3px; font-size: 10px; font-weight: bold; padding: 2px 6px;")
        layout.addWidget(role_badge); layout.addSpacing(4)

        user_lbl = QLabel(self.user.get("username", ""))
        user_lbl.setStyleSheet(f"font-size: 12px; color: {OFF_WHITE}; background: transparent;")
        layout.addWidget(user_lbl); layout.addSpacing(8)

        logout = QPushButton("Logout"); logout.setFixedHeight(28); logout.setFixedWidth(70)
        logout.setCursor(Qt.PointingHandCursor)
        logout.setStyleSheet(f"""
            QPushButton {{
                background-color: {DANGER}; color: {WHITE}; border: none;
                border-radius: 3px; font-size: 11px; font-weight: bold; padding: 0 4px;
            }}
            QPushButton:hover   {{ background-color: {DANGER_H}; }}
            QPushButton:pressed {{ background-color: {NAVY};     }}
        """)
        if self.parent_window:
            logout.clicked.connect(self.parent_window._logout)
        layout.addWidget(logout)
        return bar

    # =========================================================================
    # LEFT PANEL
    # =========================================================================
    def _build_left_panel(self):
        panel = QWidget(); panel.setStyleSheet(f"background-color: {OFF_WHITE};")
        # 12 rows × 32 px + 32 header + 42 footer = 458 px min before scrolling
        panel.setMinimumHeight(290)
        layout = QVBoxLayout(panel)
        layout.setSpacing(0); layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build_invoice_table(), 1)
        layout.addWidget(self._build_invoice_footer())
        return panel

    # ── Invoice table ─────────────────────────────────────────────────────────
    def _build_invoice_table(self):
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(7)
        self.invoice_table.setHorizontalHeaderLabels(
            ["Item No.", "Item Details", "Amount $", "Qty", "Disc. %", "TAX", "Total $"]
        )
        hh = self.invoice_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed);  self.invoice_table.setColumnWidth(0, 95)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed);  self.invoice_table.setColumnWidth(2, 90)
        hh.setSectionResizeMode(3, QHeaderView.Fixed);  self.invoice_table.setColumnWidth(3, 90)
        hh.setSectionResizeMode(4, QHeaderView.Fixed);  self.invoice_table.setColumnWidth(4, 65)
        hh.setSectionResizeMode(5, QHeaderView.Fixed);  self.invoice_table.setColumnWidth(5, 45)
        hh.setSectionResizeMode(6, QHeaderView.Fixed);  self.invoice_table.setColumnWidth(6, 90)

        self.invoice_table.verticalHeader().setVisible(False)
        self.invoice_table.setAlternatingRowColors(False)
        self.invoice_table.setShowGrid(True)
        self.invoice_table.setRowCount(self.MAX_ROWS)
        self.invoice_table.verticalHeader().setDefaultSectionSize(20)
        # ── No native cell editor — all input goes through numpad / inline search
        self.invoice_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.invoice_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {WHITE}; color: {DARK_TEXT};
                border: 1px solid {BORDER}; gridline-color: {LIGHT};
                font-size: 12px; outline: none;
                selection-background-color: transparent;
            }}
            QTableWidget::item {{
                padding: 0 4px; color: {DARK_TEXT}; border-bottom: 1px solid {LIGHT};
            }}
            QTableWidget::item:selected {{
                background-color: #fff8e1; color: {DARK_TEXT}; border: 1px solid #f9a825;
            }}
            QTableWidget::item:focus {{
                background-color: #fff8e1; color: {DARK_TEXT};
                border: 2px solid #f57f17; font-weight: bold;
            }}
            QHeaderView::section {{
                background-color: {NAVY}; color: {WHITE};
                padding: 4px 6px; border: none; border-right: 1px solid {NAVY_2};
                font-size: 10px; font-weight: bold; letter-spacing: 0.3px;
            }}
        """)
        for r in range(self.MAX_ROWS):
            self.invoice_table.setRowHeight(r, 20)
            self._init_row(r)

        self.invoice_table.cellClicked.connect(self._on_cell_clicked)
        self.invoice_table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.invoice_table.itemChanged.connect(self._on_item_changed)
        self.invoice_table.installEventFilter(self)
        return self.invoice_table

    def _init_row(self, r, part_no="", details="", qty="",
                  amount="", disc="", tax="", total=""):
        vals = [part_no, details, amount, qty, disc, tax, total]
        for c, val in enumerate(vals):
            item = QTableWidgetItem(str(val))
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter if c == 1 else Qt.AlignCenter)
            if c == 6:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setForeground(QColor(ACCENT))
            self.invoice_table.setItem(r, c, item)
        self.invoice_table.setRowHeight(r, 20)

    def _find_next_empty_row(self):
        last_filled = -1
        for r in range(self.MAX_ROWS):
            name = self.invoice_table.item(r, 1)
            if name and name.text().strip():
                last_filled = r
        next_row = last_filled + 1
        return min(next_row, self.MAX_ROWS - 1)

    def _highlight_active_row(self, row: int):
        ACTIVE_BG  = QColor("#e3f2fd")
        ACTIVE_FG  = QColor(DARK_TEXT)
        FILLED_BG  = QColor(WHITE)
        FILLED_FG  = QColor(DARK_TEXT)
        ALT_BG     = QColor("#f5f8fc")

        for r in range(self.MAX_ROWS):
            is_active = (r == row)
            for c in range(7):
                item = self.invoice_table.item(r, c)
                if not item:
                    continue
                if is_active:
                    item.setBackground(ACTIVE_BG)
                    item.setForeground(ACTIVE_FG if c != 6 else QColor(ACCENT))
                else:
                    bg = FILLED_BG if r % 2 == 0 else ALT_BG
                    item.setBackground(bg)
                    item.setForeground(FILLED_FG if c != 6 else QColor(ACCENT))

    # ── Calculation engine ────────────────────────────────────────────────────
    def _recalc_row(self, r):
        if self._block_signals:
            return
        try:
            amount = float(self.invoice_table.item(r, 2).text() or "0")
            qty    = float(self.invoice_table.item(r, 3).text() or "0")
            disc   = float(self.invoice_table.item(r, 4).text() or "0")
            total  = qty * amount * (1.0 - disc / 100.0)
        except (ValueError, AttributeError):
            total = 0.0
        self._block_signals = True
        item = self.invoice_table.item(r, 6)
        if item:
            # Only show a value when the row has an actual product entry
            details = self.invoice_table.item(r, 1)
            has_product = bool(details and details.text().strip())
            item.setText(f"{total:.2f}" if has_product else "")
            item.setForeground(QColor(ACCENT))
        self._block_signals = False
        self._recalc_totals()

    def _recalc_totals(self):
        grand_total = 0.0
        qty_total   = 0.0
        for r in range(self.MAX_ROWS):
            try:
                grand_total += float(self.invoice_table.item(r, 6).text() or "0")
                qty_total   += float(self.invoice_table.item(r, 3).text() or "0")
            except (ValueError, AttributeError):
                pass
        self._lbl_total.setText(f"{grand_total:.2f}" if grand_total else "")
        self._bin_qty.setText(f"Items: {int(qty_total)}")
        # Update prev-txn labels (always visible, values set after each sale)
        if self.parent_window:
            self.parent_window._set_status(
                f"  Items: {int(qty_total)}   |   Total: ${grand_total:.2f}"
            )

    def _on_item_changed(self, item):
        if self._block_signals:
            return
        if item.column() in (2, 3, 4):
            self._recalc_row(item.row())

    # =========================================================================
    # INLINE CELL SEARCH
    # =========================================================================
    def _open_inline_search(self, row, col):
        self._close_inline_search()

        self._inline_row = row
        self._inline_col = col

        existing = self.invoice_table.item(row, 0)
        seed = existing.text().strip() if existing else ""

        # ── What text is already in this row? show it as placeholder ─────────
        details_item = self.invoice_table.item(row, 1)
        existing_details = details_item.text().strip() if details_item else ""

        edit = QLineEdit()
        edit.setText(seed)
        edit.selectAll()
        # If there is already a product on this row, show its name as a ghost
        # so the cashier can see what they are editing / replacing.
        if existing_details:
            edit.setPlaceholderText(existing_details)
        edit.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255,255,255,160); color: {DARK_TEXT};
                border: 2px solid {ACCENT}; border-radius: 0px;
                font-size: 13px; font-weight: bold; padding: 0 6px;
            }}
        """)
        edit.setParent(self.invoice_table.viewport())

        vp_w     = self.invoice_table.viewport().width()
        row_rect = self.invoice_table.visualRect(
                       self.invoice_table.model().index(row, 0))
        edit.setFixedHeight(row_rect.height())
        edit.setGeometry(0, row_rect.y(), vp_w, row_rect.height())
        edit.show()
        edit.setFocus()
        self._inline_edit = edit

        popup = QListWidget(self.invoice_table.viewport())
        popup.setStyleSheet(f"""
            QListWidget {{
                background: {WHITE}; border: 2px solid {ACCENT};
                border-radius: 0px; font-size: 13px; color: {DARK_TEXT}; outline: none;
            }}
            QListWidget::item           {{ padding: 6px 10px; min-height: 28px; }}
            QListWidget::item:selected  {{ background-color: {ACCENT}; color: {WHITE}; }}
            QListWidget::item:hover     {{ background-color: {LIGHT}; }}
        """)
        popup.setFocusPolicy(Qt.NoFocus)
        popup.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        popup.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        popup.setMaximumHeight(16777215)
        popup.hide()
        self._inline_popup = popup

        edit.textChanged.connect(self._inline_on_text_changed)
        edit.returnPressed.connect(self._inline_on_enter)
        edit.installEventFilter(self)
        popup.itemClicked.connect(self._inline_on_item_clicked)

        if seed:
            self._inline_refresh_popup(seed)

    def _inline_refresh_popup(self, query: str):
        popup = self._inline_popup
        if popup is None:
            return
        popup.clear()
        if not query.strip():
            popup.hide(); return

        try:
            from models.product import search_products
            products = search_products(query)
        except Exception:
            demo = [
                {"id": 1, "part_no": "S",     "name": "SERVICE CHARGE",   "price": 50.00},
                {"id": 2, "part_no": "1",     "name": "Swiss Army Knife", "price": 10.00},
                {"id": 3, "part_no": "GR001", "name": "Cooking Oil",      "price": 3.50},
                {"id": 4, "part_no": "DK001", "name": "Coke 500ml",       "price": 1.20},
            ]
            ql = query.lower()
            products = [p for p in demo if ql in p["part_no"].lower() or ql in p["name"].lower()]

        if not products:
            popup.hide(); return

        for p in products[:12]:
            label = f"{p['part_no']}   {p['name']}   ${p['price']:.2f}"
            it    = QListWidgetItem(label)
            it.setData(Qt.UserRole, p)
            popup.addItem(it)

        popup.setCurrentRow(0)

        if not self._inline_edit:
            return

        geo    = self._inline_edit.geometry()
        vp_h   = self.invoice_table.viewport().height()
        vp_w   = self.invoice_table.viewport().width()
        item_h = 40
        popup_h = min(item_h * popup.count() + 4, 260)

        # ── ALWAYS place popup BELOW the current row ──────────────────────────
        # This ensures it never covers already-filled rows above.
        popup_top    = geo.y() + geo.height()
        space_below  = vp_h - popup_top
        if space_below >= item_h:
            # Enough room below — show as many items as fit
            actual_h = min(popup_h, space_below)
            popup.setGeometry(0, popup_top, vp_w, actual_h)
        else:
            # Not much room below — still go below but clip to whatever is left
            # (minimum 1 item visible).  Never go above the current row.
            actual_h = max(item_h + 4, space_below)
            popup.setGeometry(0, popup_top, vp_w, actual_h)

        popup.show()
        popup.raise_()

    def _inline_on_text_changed(self, text):
        self._inline_refresh_popup(text)

    def _inline_on_enter(self):
        popup = self._inline_popup
        if popup and popup.isVisible() and popup.currentItem():
            self._inline_on_item_clicked(popup.currentItem())
        else:
            query = self._inline_edit.text().strip() if self._inline_edit else ""
            self._inline_commit_query(query)

    def _inline_on_item_clicked(self, list_item):
        product = list_item.data(Qt.UserRole)
        self._inline_commit_product(product)

    def _inline_commit_query(self, query):
        row = self._inline_row
        self._close_inline_search()
        if not query or row < 0:
            return
        product = None
        try:
            from models.product import search_products
            results = search_products(query)
            if results: product = results[0]
        except Exception:
            demo = [
                {"id": 1, "part_no": "S",     "name": "SERVICE CHARGE",   "price": 50.00},
                {"id": 2, "part_no": "1",     "name": "Swiss Army Knife", "price": 10.00},
                {"id": 3, "part_no": "GR001", "name": "Cooking Oil",      "price": 3.50},
                {"id": 4, "part_no": "DK001", "name": "Coke 500ml",       "price": 1.20},
            ]
            ql = query.lower()
            matches = [p for p in demo if ql in p["part_no"].lower() or ql in p["name"].lower()]
            if matches: product = matches[0]

        if product:
            # Route through _add_product_to_invoice so existing rows are incremented
            self._add_product_to_invoice(
                name=product["name"],
                price=product["price"],
                part_no=product.get("part_no", ""),
                product_id=product.get("id"),
            )
        else:
            self._block_signals = True
            item0 = self.invoice_table.item(row, 0)
            if item0: item0.setText(query)
            self._block_signals = False
            self.invoice_table.setCurrentCell(row, 1)
            self._active_row = row; self._active_col = 1

    def _inline_commit_product(self, product):
        self._close_inline_search()
        if not product:
            return
        # Route through _add_product_to_invoice so duplicates are incremented
        self._add_product_to_invoice(
            name=product["name"],
            price=product["price"],
            part_no=product.get("part_no", ""),
            product_id=product.get("id"),
        )

    def _fill_row_from_product(self, row, product):
        """Write a product into a specific row — only used when the product is
        NOT already on the invoice (called from _add_product_to_invoice new-row path)."""
        self._block_signals = True
        self._init_row(row, part_no=product["part_no"], details=product["name"],
                       qty="1", amount=f"{product['price']:.2f}", disc="0.00", tax="")
        item0 = self.invoice_table.item(row, 0)
        if item0: item0.setData(Qt.UserRole, product.get("id"))
        self._block_signals = False
        self._recalc_row(row)
        self.invoice_table.setCurrentCell(row, 3)
        self._active_row      = row
        self._active_col      = 3
        self._last_filled_row = row
        self._numpad_buffer   = ""
        self._highlight_active_row(row)
        self.invoice_table.setFocus()
        if self.parent_window:
            self.parent_window._set_status(
                f"Added: {product['name']} @ ${product['price']:.2f}  — type qty or Enter"
            )

    def _close_inline_search(self):
        if self._inline_popup:
            self._inline_popup.hide()
            self._inline_popup.deleteLater()
            self._inline_popup = None
        if self._inline_edit:
            self._inline_edit.hide()
            self._inline_edit.deleteLater()
            self._inline_edit = None
        self._inline_row = -1
        self._inline_col = -1

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self._inline_edit and self._inline_popup:
            if event.type() == QEvent.KeyPress:
                key = event.key()
                popup = self._inline_popup
                if key == Qt.Key_Down:
                    if popup.isVisible():
                        cur = popup.currentRow()
                        popup.setCurrentRow(min(cur + 1, popup.count() - 1))
                    return True
                elif key == Qt.Key_Up:
                    if popup.isVisible():
                        cur = popup.currentRow()
                        popup.setCurrentRow(max(cur - 1, 0))
                    return True
                elif key == Qt.Key_Escape:
                    self._close_inline_search()
                    self.invoice_table.setFocus()
                    return True
                elif key == Qt.Key_Tab:
                    self._inline_on_enter()
                    return True
        if obj is self.invoice_table and event.type().__class__.__name__ != "type":
            from PySide6.QtCore import QEvent
            if event.type() == QEvent.KeyPress:
                key = event.key()
                if key in (Qt.Key_Return, Qt.Key_Enter):
                    self._numpad_enter(); return True
                if key == Qt.Key_Delete:
                    self._numpad_del_line(); return True
                if key == Qt.Key_Asterisk:
                    self._open_qty_popup(); return True
                if key == Qt.Key_F2:
                    self._save_sale(); return True
                if key == Qt.Key_F3:
                    self._print_receipt(); return True
                if key == Qt.Key_F5:
                    self._open_payment(); return True
                if key == Qt.Key_F7:
                    self._open_sales_list(); return True
        return super().eventFilter(obj, event)

    # =========================================================================
    # CELL CLICK / DOUBLE-CLICK
    # =========================================================================
    def _on_cell_clicked(self, row, col):
        self._active_row    = row
        self._active_col    = col
        self._numpad_buffer = ""
        if col == 5:
            item = self.invoice_table.item(row, col)
            if item: item.setText("" if item.text() == "T" else "T")
        elif col in (0, 1):
            self._open_inline_search(row, col)

    def _on_cell_double_clicked(self, row, col):
        if col not in (0, 1):
            return
        part_item = self.invoice_table.item(row, 0)
        query = part_item.text().strip() if part_item else ""
        dlg = ProductSearchDialog(self, initial_query=query)
        if dlg.exec() == QDialog.Accepted and dlg.selected_product:
            p = dlg.selected_product
            self._block_signals = True
            self._init_row(row, part_no=p["part_no"], details=p["name"],
                           qty="1", amount=f"{p['price']:.2f}", disc="0.00", tax="")
            item0 = self.invoice_table.item(row, 0)
            if item0: item0.setData(Qt.UserRole, p.get("id"))
            self._block_signals = False
            self._recalc_row(row)
            self.invoice_table.setCurrentCell(row, 3)
            self._active_row = row; self._active_col = 3; self._numpad_buffer = ""

    def _add_product_to_invoice(self, name, price, part_no="", product_id=None):
        # ── Always close any open inline search before we touch the table ─────
        self._close_inline_search()

        # ── Check if already on invoice — increment qty ───────────────────────
        for r in range(self.MAX_ROWS):
            try:
                row_name   = self.invoice_table.item(r, 1).text().strip()
                row_amount = self.invoice_table.item(r, 2).text().strip()
                row_qty    = self.invoice_table.item(r, 3).text().strip()
            except AttributeError:
                continue
            if not row_name:
                continue
            row_pid = self.invoice_table.item(r, 0).data(Qt.UserRole) if self.invoice_table.item(r, 0) else None
            match = (row_pid and row_pid == product_id) or \
                    (not product_id and row_name == name and row_amount == f"{price:.2f}")
            if match:
                try:
                    current_qty = float(row_qty or "0")
                except ValueError:
                    current_qty = 0.0
                new_qty = current_qty + 1
                self._block_signals = True
                qty_item = self.invoice_table.item(r, 3)
                if qty_item:
                    qty_item.setText(f"{new_qty:.4g}")
                    qty_item.setTextAlignment(Qt.AlignCenter)
                self._block_signals = False
                self._recalc_row(r)
                self._active_row      = r
                self._active_col      = 3
                self._last_filled_row = r
                self._numpad_buffer   = ""
                self.invoice_table.setCurrentCell(r, 3)
                self._highlight_active_row(r)
                self.invoice_table.setFocus()
                if self.parent_window:
                    self.parent_window._set_status(f"{name}  ×{new_qty:.4g}  @ ${price:.2f}")
                # Open inline search on the NEXT empty row so cursor moves down
                next_r = self._find_next_empty_row()
                if next_r != r:
                    self._active_row = next_r
                    self._active_col = 0
                    self.invoice_table.setCurrentCell(next_r, 0)
                    self._highlight_active_row(next_r)
                    self._open_inline_search(next_r, 0)
                return

        # ── New row ───────────────────────────────────────────────────────────
        r = self._find_next_empty_row()
        self._block_signals = True
        self._init_row(r, part_no=part_no, details=name, qty="1",
                       amount=f"{price:.2f}", disc="0.00", tax="")
        item = self.invoice_table.item(r, 0)
        if item: item.setData(Qt.UserRole, product_id)
        self._block_signals = False
        self._recalc_row(r)
        self._last_filled_row = r
        self._numpad_buffer   = ""
        self._highlight_active_row(r)
        self.invoice_table.setFocus()
        if self.parent_window:
            self.parent_window._set_status(f"Added: {name} @ ${price:.2f}")
        # Move cursor to the NEXT empty row and open inline search there
        next_r = self._find_next_empty_row()
        self._active_row = next_r
        self._active_col = 0
        self.invoice_table.setCurrentCell(next_r, 0)
        self._highlight_active_row(next_r)
        self._open_inline_search(next_r, 0)

    # ── Invoice footer — Items | Paid | Change | TOTAL ───────────────────────
    def _build_invoice_footer(self):
        bar = QWidget(); bar.setFixedHeight(42)
        bar.setStyleSheet(f"background-color: {NAVY}; border-top: 1px solid {NAVY_2};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(0)

        # ── Items count ───────────────────────────────────────────────────────
        self._bin_qty = QLabel("Items: 0")
        self._bin_qty.setStyleSheet(f"color: {MID}; font-size: 11px; background: transparent;")
        layout.addWidget(self._bin_qty)

        layout.addSpacing(20)

        # ── Previous transaction: Paid ────────────────────────────────────────
        prev_paid_lbl = QLabel("Paid")
        prev_paid_lbl.setStyleSheet(f"color: {MID}; font-size: 10px; background: transparent; letter-spacing: 0.5px;")
        layout.addWidget(prev_paid_lbl)
        layout.addSpacing(4)

        self._lbl_prev_paid = QLabel("—")
        self._lbl_prev_paid.setStyleSheet(f"color: {WHITE}; font-size: 13px; font-weight: bold; background: transparent; min-width: 70px;")
        self._lbl_prev_paid.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._lbl_prev_paid)

        layout.addSpacing(20)

        # ── Previous transaction: Change ──────────────────────────────────────
        prev_chg_lbl = QLabel("Change")
        prev_chg_lbl.setStyleSheet(f"color: {MID}; font-size: 10px; background: transparent; letter-spacing: 0.5px;")
        layout.addWidget(prev_chg_lbl)
        layout.addSpacing(4)

        self._lbl_prev_change = QLabel("—")
        self._lbl_prev_change.setStyleSheet(f"color: #ffd54f; font-size: 13px; font-weight: bold; background: transparent; min-width: 70px;")
        self._lbl_prev_change.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._lbl_prev_change)

        layout.addStretch(1)

        # ── TOTAL ─────────────────────────────────────────────────────────────
        total_container = QWidget(); total_container.setStyleSheet("background: transparent;")
        tc_lay = QHBoxLayout(total_container)
        tc_lay.setContentsMargins(10, 4, 10, 4); tc_lay.setSpacing(10)

        tot_lbl = QLabel("TOTAL")
        tot_lbl.setStyleSheet(f"color: {MID}; font-size: 11px; font-weight: bold; letter-spacing: 1.5px; background: transparent;")
        tot_lbl.setAlignment(Qt.AlignVCenter)

        self._lbl_total = QLabel("")
        self._lbl_total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._lbl_total.setStyleSheet(f"color: {WHITE}; font-size: 22px; font-weight: bold; background: transparent; min-width: 110px;")

        tc_lay.addWidget(tot_lbl); tc_lay.addWidget(self._lbl_total)
        layout.addWidget(total_container)

        return bar

    def _update_prev_txn_display(self, paid: float, change: float):
        """Call after every completed sale to refresh the footer labels."""
        self._prev_paid   = paid
        self._prev_change = change
        self._lbl_prev_paid.setText(f"${paid:.2f}")
        self._lbl_prev_change.setText(f"${change:.2f}")

    # =========================================================================
    # RIGHT PANEL
    # =========================================================================
    def _build_right_panel(self):
        panel = QWidget(); panel.setFixedWidth(500)
        panel.setStyleSheet(f"background-color: {OFF_WHITE};")
        layout = QVBoxLayout(panel)
        layout.setSpacing(4); layout.setContentsMargins(4, 4, 4, 4)

        top_row = QHBoxLayout(); top_row.setSpacing(4)

        def _top_btn(label, bg, hov, handler):
            b = QPushButton(label); b.setFixedHeight(52)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg}; color: {WHITE}; border: none;
                    border-radius: 6px; font-size: 11px; font-weight: bold;
                }}
                QPushButton:hover   {{ background-color: {hov}; }}
                QPushButton:pressed {{ background-color: {NAVY_3}; }}
            """)
            b.clicked.connect(handler)
            return b

        top_row.addWidget(_top_btn("Save\nF2",      NAVY,   NAVY_2, self._save_sale))
        top_row.addWidget(_top_btn("Print\nF3",     NAVY,   NAVY_2, self._print_receipt))
        top_row.addWidget(_top_btn("Hold/\nRecall", NAVY_2, NAVY_3, self._open_hold_recall))
        top_row.addWidget(_top_btn("Del\nRow",      DANGER, DANGER_H, self._numpad_del_line))
        layout.addLayout(top_row)

        layout.addWidget(self._build_numpad(), 1)

        bottom_row = QHBoxLayout(); bottom_row.setSpacing(4)
        cash_btn = QPushButton("Open\nCash"); cash_btn.setFixedHeight(52); cash_btn.setFixedWidth(110)
        cash_btn.setCursor(Qt.PointingHandCursor)
        cash_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY_3}; color: {WHITE}; border: none;
                border-radius: 6px; font-size: 12px; font-weight: bold;
            }}
            QPushButton:hover   {{ background-color: {NAVY_2}; }}
            QPushButton:pressed {{ background-color: {NAVY};   }}
        """)
        cash_btn.clicked.connect(lambda: coming_soon(self, "Open Cash Drawer"))
        bottom_row.addWidget(cash_btn)

        pay_btn = QPushButton("PAY  F5"); pay_btn.setFixedHeight(52)
        pay_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        pay_btn.setCursor(Qt.PointingHandCursor)
        pay_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SUCCESS}; color: {WHITE}; border: none;
                border-radius: 6px; font-size: 17px; font-weight: bold; letter-spacing: 1px;
            }}
            QPushButton:hover   {{ background-color: {SUCCESS_H}; }}
            QPushButton:pressed {{ background-color: {NAVY_3};    }}
        """)
        pay_btn.clicked.connect(self._open_payment)
        bottom_row.addWidget(pay_btn)
        layout.addLayout(bottom_row)
        return panel

    def _build_numpad(self):
        card = QWidget()
        card.setStyleSheet(f"QWidget {{ background-color: {WHITE}; border: 1px solid {BORDER}; border-radius: 8px; }}")
        grid = QGridLayout(card); grid.setSpacing(5); grid.setContentsMargins(6, 6, 6, 6)

        rows_def = [
            [("7","digit"),("8","digit"),("9","digit"),("−","op"),   ("X","clear")      ],
            [("4","digit"),("5","digit"),("6","digit"),("×","op"),   ("Del\nLine","del")],
            [("1","digit"),("2","digit"),("3","digit")                                  ],
            [("0","digit"),(".","digit")                                                ],
        ]
        enter_btn = numpad_btn("Enter", "enter"); enter_btn.clicked.connect(self._numpad_enter)

        for ri, row_def in enumerate(rows_def):
            for ci, (ch, kind) in enumerate(row_def):
                b = numpad_btn(ch, kind)
                if ch in "0123456789.":
                    b.clicked.connect(lambda _, c=ch: self._numpad_press(c))
                elif ch == "−":
                    b.clicked.connect(lambda: self._numpad_press("-"))
                elif ch == "×":
                    b.clicked.connect(self._open_qty_popup)
                elif ch == "X":
                    b.clicked.connect(self._numpad_clear)
                elif "Del" in ch:
                    b.clicked.connect(self._numpad_del_line)
                grid.addWidget(b, ri, ci)

        grid.addWidget(enter_btn, 2, 3, 2, 2)
        for i in range(4): grid.setRowStretch(i, 1)
        for i in range(5): grid.setColumnStretch(i, 1)
        return card

    # =========================================================================
    # NUMPAD LOGIC
    # =========================================================================
    def _numpad_press(self, char):
        if self._active_row < 0:
            r = self._find_next_empty_row()
            self._active_row = r; self._active_col = 3
            self.invoice_table.setCurrentCell(r, 3)
        if self._active_col in (5, 6):
            return
        if char in ("*", "×"):
            self._open_qty_popup(); return

        self._numpad_buffer += char
        self._block_signals = True
        item = self.invoice_table.item(self._active_row, self._active_col)
        if not item:
            item = QTableWidgetItem("")
            self.invoice_table.setItem(self._active_row, self._active_col, item)
        item.setText(self._numpad_buffer)
        item.setTextAlignment(Qt.AlignCenter)
        self._block_signals = False
        if self._active_col in (2, 3, 4):
            self._recalc_row(self._active_row)

    def _numpad_clear(self):
        self._numpad_buffer = ""
        if self._active_row >= 0 and self._active_col >= 0:
            self._block_signals = True
            item = self.invoice_table.item(self._active_row, self._active_col)
            if item: item.setText("")
            self._block_signals = False
            if self._active_col in (2, 3, 4):
                self._recalc_row(self._active_row)

    def _numpad_del_line(self):
        row = self._active_row
        if row < 0: row = self.invoice_table.currentRow()
        if row < 0: return
        self._block_signals = True
        self._init_row(row)
        self._block_signals = False
        self._recalc_totals()
        self._numpad_buffer = ""; self._active_row = -1; self._active_col = -1
        self.invoice_table.setCurrentCell(row, 0)

    def _numpad_enter(self):
        if self._active_row < 0:
            return
        self._numpad_buffer = ""
        if self._active_col == 2:
            self._active_col = 3
            self.invoice_table.setCurrentCell(self._active_row, 3)
        else:
            self._recalc_row(self._active_row)
            next_row = self._active_row + 1
            if next_row >= self.MAX_ROWS: next_row = self.MAX_ROWS - 1
            self._active_row = next_row; self._active_col = 0
            self.invoice_table.setCurrentCell(next_row, 0)
            self._highlight_active_row(next_row)
            self._open_inline_search(next_row, 0)

    def _open_qty_popup(self):
        row = self._last_filled_row
        if row < 0: row = self._active_row
        if row < 0: row = self.invoice_table.currentRow()
        if row < 0: return

        name_item = self.invoice_table.item(row, 1)
        product_name = name_item.text().strip() if name_item else ""
        if not product_name: return

        qty_item = self.invoice_table.item(row, 3)
        try:
            current_qty = float(qty_item.text() or "1") if qty_item else 1.0
        except ValueError:
            current_qty = 1.0

        self._close_inline_search()

        popup = QuantityPopup(self, product_name=product_name, current_qty=current_qty)
        if popup.exec() == QDialog.Accepted:
            new_qty = popup.entered_qty
            self._block_signals = True
            if not qty_item:
                qty_item = QTableWidgetItem("")
                self.invoice_table.setItem(row, 3, qty_item)
            qty_item.setText(f"{new_qty:.4g}")
            qty_item.setTextAlignment(Qt.AlignCenter)
            self._block_signals = False
            self._recalc_row(row)
            self._active_row = row; self._active_col = 3; self._last_filled_row = row
            self.invoice_table.setCurrentCell(row, 3)
            self._highlight_active_row(row)
            if self.parent_window:
                self.parent_window._set_status(f"Qty updated: {product_name}  ×{new_qty:.4g}")

    # =========================================================================
    # BOTTOM GRID — category tabs + product cards
    # =========================================================================
    def _build_bottom_grid(self):
        container = QWidget(); container.setStyleSheet(f"background-color: {WHITE};")
        outer = QVBoxLayout(container); outer.setSpacing(0); outer.setContentsMargins(0, 0, 0, 0)

        try:
            from models.product import get_categories
            self._category_names = get_categories()
        except Exception:
            self._category_names = []
        if not self._category_names:
            self._category_names = ["All"]

        self._cat_buttons = []
        self._cat_page = 0
        self._CATS_VISIBLE = 6

        tab_row_w = QWidget(); tab_row_w.setFixedHeight(55)
        tab_row_w.setStyleSheet(f"background-color: {WHITE}; border-bottom: 1px solid {BORDER};")
        tab_row_h = QHBoxLayout(tab_row_w)
        tab_row_h.setSpacing(0); tab_row_h.setContentsMargins(0, 0, 0, 0)

        self._cat_prev_btn = QPushButton("◀"); self._cat_prev_btn.setFixedSize(40, 55)
        self._cat_prev_btn.setCursor(Qt.PointingHandCursor)
        self._cat_prev_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {LIGHT}; color: {DARK_TEXT}; border: none; border-right: 1px solid {BORDER}; font-size: 18px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {ACCENT}; color: {WHITE}; }}
        """)
        self._cat_prev_btn.clicked.connect(lambda: self._cat_scroll(-1))
        tab_row_h.addWidget(self._cat_prev_btn)

        self._cat_tab_container = QWidget(); self._cat_tab_container.setStyleSheet(f"background-color: {WHITE};")
        self._cat_tab_layout = QHBoxLayout(self._cat_tab_container)
        self._cat_tab_layout.setSpacing(4); self._cat_tab_layout.setContentsMargins(4, 4, 4, 4)
        tab_row_h.addWidget(self._cat_tab_container, 1)

        self._cat_next_btn = QPushButton("▶"); self._cat_next_btn.setFixedSize(40, 55)
        self._cat_next_btn.setCursor(Qt.PointingHandCursor)
        self._cat_next_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {LIGHT}; color: {DARK_TEXT}; border: none; border-left: 1px solid {BORDER}; font-size: 18px; font-weight: bold; }}
            QPushButton:hover {{ background-color: {ACCENT}; color: {WHITE}; }}
        """)
        self._cat_next_btn.clicked.connect(lambda: self._cat_scroll(1))
        tab_row_h.addWidget(self._cat_next_btn)
        outer.addWidget(tab_row_w)

        self._product_grid_widget = QWidget(); self._product_grid_widget.setStyleSheet(f"background-color: {WHITE};")
        self._product_grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._product_grid = QGridLayout(self._product_grid_widget)
        self._product_grid.setSpacing(1); self._product_grid.setContentsMargins(1, 1, 1, 1)
        outer.addWidget(self._product_grid_widget, 1)

        self._refresh_cat_tabs()
        self._load_category_products(0, self._category_names[0])
        return container

    def _cat_scroll(self, direction):
        total_pages = max(1, (len(self._category_names) + self._CATS_VISIBLE - 1) // self._CATS_VISIBLE)
        self._cat_page = max(0, min(self._cat_page + direction, total_pages - 1))
        self._refresh_cat_tabs()

    def _refresh_cat_tabs(self):
        while self._cat_tab_layout.count():
            item = self._cat_tab_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._cat_buttons.clear()

        start = self._cat_page * self._CATS_VISIBLE
        visible = self._category_names[start: start + self._CATS_VISIBLE]
        global_start = start

        for local_i, name in enumerate(visible):
            global_idx = global_start + local_i
            active = (global_idx == getattr(self, "_active_cat_idx", 0))
            b = QPushButton(name); b.setFixedHeight(48)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(self._cat_tab_style(active, TAB_COLORS[global_idx % len(TAB_COLORS)]))
            b.clicked.connect(lambda _, idx=global_idx, n=name: self._on_category_tap(idx, n))
            self._cat_tab_layout.addWidget(b)
            self._cat_buttons.append(b)

        total_pages = max(1, (len(self._category_names) + self._CATS_VISIBLE - 1) // self._CATS_VISIBLE)
        self._cat_prev_btn.setVisible(self._cat_page > 0)
        self._cat_next_btn.setVisible(self._cat_page < total_pages - 1)

    def _cat_tab_style(self, active, bg_color):
        border_bottom = f"2px solid {ACCENT}" if active else f"1px solid {BORDER}"
        font_weight   = "bold" if active else "normal"
        return (
            f"QPushButton {{"
            f"  background-color: {bg_color}; color: {DARK_TEXT};"
            f"  border: 1px solid {BORDER}; border-bottom: {border_bottom};"
            f"  border-radius: 0px; font-size: 11px; font-weight: {font_weight}; padding: 0 4px;"
            f"}}"
            f"QPushButton:hover {{ background-color: {ACCENT}; color: {WHITE}; }}"
        )

    def _on_category_tap(self, idx, name):
        self._active_cat_idx = idx
        self._refresh_cat_tabs()
        self._load_category_products(idx, name)

    def _load_category_products(self, idx, name):
        while self._product_grid.count():
            item = self._product_grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        try:
            from models.product import get_products_by_category, get_all_products
            db_products = get_all_products() if name == "All" else get_products_by_category(name)
            products = [(p["name"], p["part_no"], p["price"], p["id"], p.get("image_path", ""))
                        for p in db_products]
        except Exception:
            products = []

        any_image = any(ip for _, _, _, _, ip in products)
        icon_size = 52 if any_image else 0
        ROWS, COLS = 4, 12

        self._product_grid.setSpacing(1); self._product_grid.setContentsMargins(1, 1, 1, 1)
        for r in range(ROWS): self._product_grid.setRowStretch(r, 1)
        for c in range(COLS): self._product_grid.setColumnStretch(c, 1)

        from PySide6.QtWidgets import QToolButton

        for r in range(ROWS):
            for c in range(COLS):
                flat = r * COLS + c
                if flat < len(products):
                    pname, part_no, price, product_id, image_path = products[flat]
                    btn = QToolButton()
                    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.setAutoRaise(False)
                    btn.setToolTip(f"{pname}  ${price:.2f}\nRight-click for image options")
                    self._apply_btn_image(btn, pname, price, image_path,
                                         icon_size=icon_size, has_any_image=any_image)
                    btn.setStyleSheet(f"""
                        QToolButton {{
                            background-color: {OFF_WHITE}; color: {DARK_TEXT};
                            border: 1px solid {BORDER}; border-radius: 0px;
                            font-size: 8pt; font-weight: bold; padding: 2px;
                        }}
                        QToolButton:hover   {{ background-color: {ACCENT}; color: {WHITE}; }}
                        QToolButton:pressed {{ background-color: {ACCENT_H}; color: {WHITE}; }}
                    """)
                    btn.clicked.connect(
                        lambda _, n=pname, pr=price, pno=part_no, pid=product_id:
                        self._add_product_to_invoice(n, pr, pno, pid)
                    )
                    btn.setContextMenuPolicy(Qt.CustomContextMenu)
                    btn.customContextMenuRequested.connect(
                        lambda pos, b=btn, pid=product_id, pn=pname, ip=image_path:
                        self._product_btn_context_menu(b, pid, pn, ip)
                    )
                else:
                    btn = QToolButton()
                    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                    btn.setEnabled(False)
                    btn.setStyleSheet(f"QToolButton {{ background-color: {OFF_WHITE}; border: 1px solid {BORDER}; border-radius: 0px; }}")
                self._product_grid.addWidget(btn, r, c)

    def _apply_btn_image(self, btn, pname, price, image_path, icon_size: int = 48, has_any_image: bool = True):
        from PySide6.QtGui import QIcon, QPixmap
        from PySide6.QtCore import QSize, Qt as _Qt

        label = f"{pname}\n${price:.2f}" if price else pname
        if image_path and has_any_image:
            try:
                pix = QPixmap(image_path)
                if not pix.isNull():
                    isize = 56
                    btn.setIcon(QIcon(pix.scaled(isize, isize, _Qt.KeepAspectRatio, _Qt.SmoothTransformation)))
                    btn.setIconSize(QSize(isize, isize))
                    btn.setText(label)
                    btn.setToolButtonStyle(_Qt.ToolButtonTextUnderIcon)
                    return
            except Exception:
                pass
        btn.setIcon(QIcon())
        btn.setText(label)
        try:
            btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        except Exception:
            pass

    def _product_btn_context_menu(self, btn, product_id, product_name, current_image):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background-color: {WHITE}; color: {DARK_TEXT}; border: 1px solid {BORDER}; border-radius: 6px; padding: 4px; }}
            QMenu::item            {{ padding: 9px 28px; border-radius: 4px; font-size: 13px; }}
            QMenu::item:selected   {{ background-color: {ACCENT}; color: {WHITE}; }}
            QMenu::separator       {{ height: 1px; background: {BORDER}; margin: 4px 10px; }}
        """)
        act_set    = menu.addAction("🖼  Set Image…")
        act_remove = menu.addAction("🗑  Remove Image")
        act_remove.setEnabled(bool(current_image))
        chosen = menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        if chosen == act_set:
            self._set_product_image(btn, product_id, product_name)
        elif chosen == act_remove:
            self._remove_product_image(btn, product_id, product_name)

    def _set_product_image(self, btn, product_id, product_name):
        from PySide6.QtWidgets import QFileDialog
        from PySide6.QtGui import QPixmap
        path, _ = QFileDialog.getOpenFileName(self, f"Select image for  {product_name}", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if not path: return
        pix = QPixmap(path)
        if pix.isNull():
            QMessageBox.warning(self, "Image Error", "Could not load the selected image."); return
        try:
            from models.product import set_product_image
            set_product_image(product_id, path)
        except Exception: pass
        if self.parent_window: self.parent_window._set_status(f"Image set for: {product_name}")
        self._reload_current_category()

    def _remove_product_image(self, btn, product_id, product_name):
        try:
            from models.product import remove_product_image
            remove_product_image(product_id)
        except Exception: pass
        if self.parent_window: self.parent_window._set_status(f"Image removed for: {product_name}")
        self._reload_current_category()

    def _reload_current_category(self):
        idx  = getattr(self, "_active_cat_idx", 0)
        name = self._category_names[idx] if self._category_names else "All"
        self._load_category_products(idx, name)

    # =========================================================================
    # DIALOG OPENERS
    # =========================================================================
    def _open_day_shift(self):
        if _HAS_DAY_SHIFT: DayShiftDialog(self, user=self.user).exec()
        else: coming_soon(self, "Day Shift — add views/dialogs/day_shift_dialog.py")

    def _open_stock_file(self):
        if _HAS_STOCK: StockFileDialog(self).exec()
        else: coming_soon(self, "Stock File — add views/dialogs/stock_file_dialog.py")

    def _open_settings(self):
        if _HAS_SETTINGS_DIALOG:
            dlg = SettingsDialog(self, user=self.user)
        else:
            dlg = _InlineSettingsDialog(self, user=self.user)
        dlg.exec()

    def _select_customer(self):
        dlg = CustomerSearchPopup(self)
        if dlg.exec() == QDialog.Accepted:
            self._selected_customer = dlg.selected_customer
            if self._selected_customer:
                name = self._selected_customer.get("customer_name", "")
                self._cust_btn.setText(f"👤  {name[:22]}")
                self._cust_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ACCENT}; color: {WHITE};
                        border: none; border-radius: 3px;
                        font-size: 11px; font-weight: bold; padding: 0 8px;
                    }}
                    QPushButton:hover {{ background-color: {ACCENT_H}; }}
                """)
                if self.parent_window:
                    self.parent_window._set_status(f"Customer: {name}")
            else:
                self._reset_customer_btn()

    def _open_sales_list(self):
        if _HAS_SALES_LIST:
            dlg = SalesListDialog(self)
            if dlg.exec() == QDialog.Accepted and dlg.selected_sale:
                self._new_sale(confirm=False)
                for item in dlg.selected_items:
                    self._add_product_to_invoice(
                        name=item["product_name"], price=item["price"], part_no=item["part_no"],
                    )
        else:
            coming_soon(self, "Sales List — add views/dialogs/sales_list_dialog.py")

    def _collect_invoice_items(self) -> list[dict]:
        items = []
        for r in range(self.MAX_ROWS):
            try:
                qty = float(self.invoice_table.item(r, 3).text() or "0")
            except (ValueError, AttributeError):
                qty = 0.0
            if qty <= 0:
                continue
            try:
                part_no      = self.invoice_table.item(r, 0).text()
                product_name = self.invoice_table.item(r, 1).text()
                price        = float(self.invoice_table.item(r, 2).text() or "0")
                disc         = float(self.invoice_table.item(r, 4).text() or "0")
                tax          = self.invoice_table.item(r, 5).text()
                total        = float(self.invoice_table.item(r, 6).text() or "0")
                product_id   = self.invoice_table.item(r, 0).data(Qt.UserRole)
            except (ValueError, AttributeError):
                continue
            items.append({
                "part_no": part_no, "product_name": product_name,
                "qty": qty, "price": price, "discount": disc,
                "tax": tax, "total": total, "product_id": product_id,
            })
        return items

    def _save_sale(self):
        items = self._collect_invoice_items()
        if not items:
            QMessageBox.warning(self, "Empty Invoice", "Add items before saving."); return
        try:
            total = float(self._lbl_total.text() or "0")
        except ValueError:
            total = 0.0
        try:
            from models.sale import create_sale
            cashier_id   = self.user.get("id")          if isinstance(self.user, dict) else None
            cashier_name = self.user.get("username", "") if isinstance(self.user, dict) else ""
            sale = create_sale(
                items=items, total=total, tendered=total,
                method="CASH", cashier_id=cashier_id, cashier_name=cashier_name,
                customer_name=self._selected_customer.get("customer_name","") if self._selected_customer else "",
                customer_contact=self._selected_customer.get("custom_telephone_number","") if self._selected_customer else "",
                change_amount=0.0,
            )
            self._update_prev_txn_display(paid=total, change=0.0)
            if self.parent_window:
                self.parent_window._set_status(f"Sale #{sale['number']} saved — ${total:.2f}")
            self._new_sale(confirm=False)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", _friendly_db_error(e))

    def _print_receipt(self):
        items = self._collect_invoice_items()
        if not items:
            QMessageBox.information(self, "Nothing to Print", "Invoice is empty."); return
        try:
            total = float(self._lbl_total.text() or "0")
        except ValueError:
            total = 0.0

        from PySide6.QtCore import QDateTime
        now        = QDateTime.currentDateTime().toString("dd/MM/yyyy  hh:mm")
        cust_name  = self._selected_customer.get("customer_name", "") if self._selected_customer else "Walk-in"
        cust_phone = self._selected_customer.get("custom_telephone_number", "") if self._selected_customer else ""

        W = 40
        lines = ["=" * W, "          HAVANO POS", f"  {now}", f"  Customer:  {cust_name}"]
        if cust_phone:
            lines.append(f"  Phone:     {cust_phone}")
        lines += ["-" * W]

        subtotal = 0.0; total_disc = 0.0
        for it in items:
            name_str = it["product_name"][:24]; qty = it["qty"]; price = it["price"]
            disc = it.get("discount", 0.0); line_tot = it["total"]
            subtotal += qty * price
            total_disc += qty * price * (disc / 100.0) if disc else 0.0
            qty_str = f"{int(qty)}" if qty == int(qty) else f"{qty:.2f}"
            lines.append(f"{name_str:<24} {qty_str:>3}x ${price:.2f}")
            if disc:
                lines.append(f"  Disc {disc:.0f}%               -${qty*price*(disc/100):.2f}")
            lines.append(f"  {'─'*20}  ${line_tot:.2f}")

        lines += ["-" * W]
        if total_disc > 0:
            lines.append(f"  Subtotal:          ${subtotal:.2f}")
            lines.append(f"  Discount:         -${total_disc:.2f}")
        lines += [f"  TOTAL:             ${total:.2f}", "=" * W, "      Thank you for your purchase!", "=" * W]

        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
        dlg = QDialog(self); dlg.setWindowTitle("Receipt Preview  —  F3"); dlg.setMinimumSize(400, 500)
        dlg.setStyleSheet(f"QDialog {{ background:{WHITE}; }}")
        lay = QVBoxLayout(dlg); lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(10)
        txt = QTextEdit(); txt.setReadOnly(True)
        txt.setFont(__import__("PySide6.QtGui", fromlist=["QFont"]).QFont("Courier New", 10))
        txt.setPlainText("\n".join(lines))
        txt.setStyleSheet(f"QTextEdit {{ background:{WHITE}; color:{DARK_TEXT}; border:1px solid {BORDER}; border-radius:4px; }}")
        lay.addWidget(txt, 1)
        br = QHBoxLayout(); br.setSpacing(8)
        close_btn = QPushButton("Close"); close_btn.setFixedHeight(36); close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"QPushButton {{ background:{NAVY}; color:{WHITE}; border:none; border-radius:5px; font-size:13px; font-weight:bold; padding:0 20px; }} QPushButton:hover {{ background:{NAVY_2}; }}")
        close_btn.clicked.connect(dlg.accept)
        br.addStretch(); br.addWidget(close_btn)
        lay.addLayout(br)
        dlg.exec()

    def _open_payment(self):
        try:
            total = float(self._lbl_total.text() or "0")
        except ValueError:
            total = 0.0
        if total <= 0:
            QMessageBox.warning(self, "Empty Invoice", "Add items before payment."); return

        if _HAS_PAYMENT_DIALOG:
            dlg = _ExternalPaymentDialog(self, total=total, customer=self._selected_customer)
        else:
            dlg = PaymentDialog(self, total=total, customer=self._selected_customer)

        if dlg.exec() == QDialog.Accepted:
            items = self._collect_invoice_items()
            if hasattr(dlg, "accepted_tendered"):
                tendered       = dlg.accepted_tendered
                method         = dlg.accepted_method
                change_out     = getattr(dlg, "accepted_change", max(tendered - total, 0.0))
                final_customer = getattr(dlg, "accepted_customer", self._selected_customer)
            else:
                try:
                    tendered = float(dlg._amt.text() or "0")
                except (ValueError, AttributeError):
                    tendered = total
                method         = getattr(dlg, "_method", "CASH")
                change_out     = max(tendered - total, 0.0)
                final_customer = self._selected_customer

            cust_name    = final_customer.get("customer_name","")             if final_customer else ""
            cust_contact = final_customer.get("custom_telephone_number","")   if final_customer else ""

            try:
                from models.sale import create_sale
                cashier_id   = self.user.get("id")          if isinstance(self.user, dict) else None
                cashier_name = self.user.get("username", "") if isinstance(self.user, dict) else ""
                sale = create_sale(
                    items=items, total=total, tendered=tendered,
                    method=method, cashier_id=cashier_id, cashier_name=cashier_name,
                    customer_name=cust_name, customer_contact=cust_contact,
                    change_amount=change_out,
                )
                # ── Update previous-transaction display in footer ─────────────
                self._update_prev_txn_display(paid=tendered, change=change_out)
                if self.parent_window:
                    status = f"Sale #{sale['number']} saved — ${total:.2f} ({method})"
                    if cust_name: status += f" — {cust_name}"
                    self.parent_window._set_status(status)
            except Exception as e:
                QMessageBox.warning(self, "Save Error", _friendly_db_error(e)); return
            self._new_sale(confirm=False)

    def _open_hold_recall(self):
        HoldRecallDialog(self).exec()

    def _reset_customer_btn(self):
        self._selected_customer = None
        self._cust_btn.setText("👤  Customer")
        self._cust_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY_2}; color: {MID}; border: 1px solid {NAVY_3};
                border-radius: 3px; font-size: 11px; padding: 0 8px;
            }}
            QPushButton:hover {{ background-color: {NAVY_3}; color: {WHITE}; }}
        """)

    def _new_sale(self, confirm=True):
        if confirm:
            reply = QMessageBox.question(self, "New Sale", "Clear the current invoice and start a new sale?", QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes: return
        self._block_signals = True
        for r in range(self.MAX_ROWS): self._init_row(r)
        self._block_signals = False
        self._numpad_buffer   = ""
        self._active_row      = 0
        self._active_col      = 0
        self._last_filled_row = -1
        self._reset_customer_btn()
        self._recalc_totals()
        self._highlight_active_row(0)
        self.invoice_table.setCurrentCell(0, 0)
        self.invoice_table.setFocus()
        self._open_inline_search(0, 0)
        if self.parent_window:
            self.parent_window._set_status("New sale started.")

    def keyPressEvent(self, event):
        key = event.key()
        if   key == Qt.Key_F2:     self._save_sale()
        elif key == Qt.Key_F3:     self._print_receipt()
        elif key == Qt.Key_F5:     self._open_payment()
        elif key == Qt.Key_F7:     self._open_sales_list()
        elif key == Qt.Key_Delete: self._numpad_del_line()
        elif key == Qt.Key_Escape: self._numpad_clear()
        else: super().keyPressEvent(event)

    def _quick_tender(self, _amount):
        pass  # no-op


# =============================================================================
# MAIN WINDOW
# =============================================================================
class MainWindow(QMainWindow):
    def __init__(self, user=None):
        super().__init__()
        self.user = user or {"username": "admin", "role": "admin"}
        self.setWindowTitle("Havano POS System")
        self.setMinimumSize(1280, 820)
        self.setStyleSheet(GLOBAL_STYLE)

        self._stack = QStackedWidget()
        self._pos_view = POSView(parent_window=self, user=self.user)
        self._stack.addWidget(self._pos_view)

        from models.user import is_admin
        if is_admin(self.user):
            self._dashboard = AdminDashboard(parent_window=self, user=self.user)
            self._stack.addWidget(self._dashboard)

        self.setCentralWidget(self._stack)

        if is_admin(self.user):
            self._build_menubar()

        self._status_bar = QStatusBar()
        self._status_bar.showMessage(
            f"  {self.user['username']} ({self.user['role']})  |  "
            f"{QDate.currentDate().toString('dd/MM/yyyy')}  |  Ready"
        )
        self.setStatusBar(self._status_bar)

        if is_admin(self.user):
            self._stack.setCurrentIndex(1)
        else:
            self._stack.setCurrentIndex(0)

    def switch_to_pos(self):
        self._stack.setCurrentIndex(0)
        self._set_status("POS mode  —  ready to sell.")

    def switch_to_dashboard(self):
        from models.user import is_admin
        if is_admin(self.user):
            self._dashboard._load_data()
            self._stack.setCurrentIndex(1)
            self._set_status("Admin Dashboard.")

    def _set_status(self, msg):
        self._status_bar.showMessage(f"  {msg}")

    def _build_menubar(self):
        mb = self.menuBar()

        pos_menu = mb.addMenu("POS")
        for label, fn in [
            ("New Sale",         lambda: (self.switch_to_pos(), self._pos_view._new_sale())),
            ("Day Shift",        self._pos_view._open_day_shift),
            (None, None),
            ("Open Cash Drawer", lambda: coming_soon(self, "Cash Drawer")),
        ]:
            if label is None: pos_menu.addSeparator()
            else:
                a = QAction(label, self); a.triggered.connect(fn); pos_menu.addAction(a)

        sales_menu = mb.addMenu("Sales")
        for label in ["Sales History", "Returns / Refunds", "Daily Report", "Export CSV"]:
            a = QAction(label, self); a.triggered.connect(lambda _, l=label: coming_soon(self, l))
            sales_menu.addAction(a)

        stock_menu = mb.addMenu("Stock")
        a = QAction("Stock File", self); a.triggered.connect(self._pos_view._open_stock_file)
        stock_menu.addAction(a)

        settings_menu = mb.addMenu("Settings")
        a_users = QAction("Manage Users", self); a_users.triggered.connect(self._open_manage_users)
        settings_menu.addAction(a_users)
        settings_menu.addSeparator()
        for label, fn in [
            ("Companies",      lambda: CompanyDialog(self).exec()),
            ("Customer Groups",lambda: CustomerGroupDialog(self).exec()),
            ("Warehouses",     lambda: WarehouseDialog(self).exec()),
            ("Cost Centers",   lambda: CostCenterDialog(self).exec()),
            ("Price Lists",    lambda: PriceListDialog(self).exec()),
            ("Customers",      lambda: CustomerDialog(self).exec()),
        ]:
            a = QAction(label, self); a.triggered.connect(fn); settings_menu.addAction(a)
        settings_menu.addSeparator()
        for label in ["Products", "Categories", "Tax Settings", "Printer Setup", "Backup"]:
            a = QAction(label, self); a.triggered.connect(lambda _, l=label: coming_soon(self, l))
            settings_menu.addAction(a)

    def _open_manage_users(self):
        ManageUsersDialog(self, current_user=self.user).exec()

    def _logout(self):
        reply = QMessageBox.question(self, "Logout", "Logout and return to login screen?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.hide()
            try:
                from views.login_dialog import LoginDialog
                dlg = LoginDialog()
                if dlg.exec() == QDialog.Accepted:
                    new_win = MainWindow(user=dlg.logged_in_user)
                    new_win.show(); self._next_window = new_win
                else:
                    QApplication.quit()
            except Exception:
                QApplication.quit()
            self.close()
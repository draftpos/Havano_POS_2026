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
import qtawesome as qta

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
# PAYMENT DIALOG
# =============================================================================
class PaymentDialog(QDialog):
    def __init__(self, parent=None, total=0.0):
        super().__init__(parent)
        self.total = total
        self._method = "Cash"
        self._method_btns = {}
        self.setWindowTitle("Payment")
        self.setFixedSize(400, 420)
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        hdr = QWidget()
        hdr.setFixedHeight(44)
        hdr.setStyleSheet(f"background-color: {NAVY}; border-radius: 5px;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        t = QLabel("Payment")
        t.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {WHITE}; background: transparent;")
        hl.addWidget(t)
        layout.addWidget(hdr)

        total_row = QHBoxLayout()
        lbl = QLabel("Total Due")
        lbl.setStyleSheet(f"color: {MUTED}; font-size: 13px; background: transparent;")
        val = QLabel(f"$ {self.total:.2f}")
        val.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {NAVY}; background: transparent;")
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        total_row.addWidget(lbl)
        total_row.addWidget(val)
        layout.addLayout(total_row)
        layout.addWidget(hr())

        m_lbl = QLabel("Payment Method")
        m_lbl.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
        layout.addWidget(m_lbl)

        method_row = QHBoxLayout()
        method_row.setSpacing(6)
        for m in ["Cash", "Card", "Mobile", "Credit"]:
            b = navy_btn(m, height=34, color=ACCENT if m == "Cash" else NAVY, hover=ACCENT_H)
            b.clicked.connect(lambda _, x=m: self._set_method(x))
            method_row.addWidget(b)
            self._method_btns[m] = b
        layout.addLayout(method_row)

        amt_row = QHBoxLayout()
        lbl2 = QLabel("Amount Tendered")
        lbl2.setFixedWidth(148)
        lbl2.setStyleSheet(f"color: {MUTED}; background: transparent;")
        self._amt = QLineEdit("0.00")
        self._amt.setFixedHeight(36)
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
        amt_row.addWidget(lbl2)
        amt_row.addWidget(self._amt)
        layout.addLayout(amt_row)

        quick_row = QHBoxLayout()
        quick_row.setSpacing(6)
        for amt in [5, 10, 20, 50, 100]:
            b = navy_btn(f"${amt}", height=30, font_size=12)
            b.clicked.connect(lambda _, a=amt: self._amt.setText(f"{a:.2f}"))
            quick_row.addWidget(b)
        exact_btn = navy_btn("Exact", height=30, font_size=12, color=SUCCESS, hover=SUCCESS_H)
        exact_btn.clicked.connect(lambda: self._amt.setText(f"{self.total:.2f}"))
        quick_row.addWidget(exact_btn)
        layout.addLayout(quick_row)

        chg_row = QHBoxLayout()
        lbl3 = QLabel("Change")
        lbl3.setFixedWidth(148)
        lbl3.setStyleSheet(f"color: {MUTED}; background: transparent;")
        self._chg = QLabel("$ 0.00")
        self._chg.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {ORANGE}; background: transparent;")
        self._chg.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        chg_row.addWidget(lbl3)
        chg_row.addWidget(self._chg)
        layout.addLayout(chg_row)
        layout.addStretch()

        self._confirm_btn = navy_btn("Confirm Payment", height=44, color=SUCCESS, hover=SUCCESS_H)
        self._confirm_btn.clicked.connect(self._confirm)
        layout.addWidget(self._confirm_btn)

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
        QMessageBox.information(self, "Payment Confirmed",
            f"Payment received.\n\nChange: $ {change:.2f}")
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

        hdr = QWidget()
        hdr.setFixedHeight(42)
        hdr.setStyleSheet(f"background-color: {NAVY}; border-radius: 5px;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        t = QLabel("Held Orders")
        t.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {WHITE}; background: transparent;")
        hl.addWidget(t)
        layout.addWidget(hdr)

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
        btn_row.addWidget(recall_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


# =============================================================================
# MANAGE USERS DIALOG  (Admin only)
# =============================================================================
class ManageUsersDialog(QDialog):
    """
    Admin can:
      • View all users (id, username, role)
      • Add a new cashier or admin
      • Delete a user (cannot delete self)
    """
    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.current_user = current_user or {}
        self.setWindowTitle("Manage Users")
        self.setMinimumSize(640, 460)
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
        self._build()
        self._reload()

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
        t = QLabel("Manage Users")
        t.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {WHITE}; background: transparent;")
        sub = QLabel("Admin access required")
        sub.setStyleSheet(f"font-size: 11px; color: {MID}; background: transparent;")
        hl.addWidget(t)
        hl.addStretch()
        hl.addWidget(sub)
        layout.addWidget(hdr)

        # User table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Username", "Role"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed);    self.table.setColumnWidth(0, 60)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed);    self.table.setColumnWidth(2, 110)
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
        layout.addWidget(self.table, 1)
        layout.addWidget(hr())

        # ── Add user form ────────────────────────────────────────────────────
        add_lbl = QLabel("Add New User")
        add_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {NAVY}; background: transparent;")
        layout.addWidget(add_lbl)

        form_row = QHBoxLayout()
        form_row.setSpacing(10)

        self._new_username = QLineEdit()
        self._new_username.setPlaceholderText("Username")
        self._new_username.setFixedHeight(36)

        self._new_password = QLineEdit()
        self._new_password.setPlaceholderText("Password")
        self._new_password.setEchoMode(QLineEdit.Password)
        self._new_password.setFixedHeight(36)

        self._new_role = QComboBox()
        self._new_role.addItems(["cashier", "admin"])
        self._new_role.setFixedHeight(36)
        self._new_role.setFixedWidth(110)

        add_btn = navy_btn("Add User", height=36, color=SUCCESS, hover=SUCCESS_H)
        add_btn.clicked.connect(self._add_user)

        form_row.addWidget(self._new_username, 2)
        form_row.addWidget(self._new_password, 2)
        form_row.addWidget(self._new_role)
        form_row.addWidget(add_btn)
        layout.addLayout(form_row)

        # ── Bottom buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        del_btn   = navy_btn("Delete Selected", height=36, color=DANGER, hover=DANGER_H)
        close_btn = navy_btn("Close",           height=36)
        del_btn.clicked.connect(self._delete_user)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        # Status message
        self._status = QLabel("")
        self._status.setStyleSheet(f"font-size: 12px; background: transparent; color: {SUCCESS};")
        layout.addWidget(self._status)

    def _reload(self):
        self.table.setRowCount(0)
        try:
            from models.user import get_all_users
            users = get_all_users()
        except Exception:
            users = [
                {"id": 1, "username": "admin",    "role": "admin"},
                {"id": 2, "username": "cashier1", "role": "cashier"},
            ]
        for u in users:
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, key in enumerate(["id", "username", "role"]):
                item = QTableWidgetItem(str(u.get(key, "")))
                item.setTextAlignment(Qt.AlignCenter if c != 1 else Qt.AlignLeft | Qt.AlignVCenter)
                if key == "role":
                    item.setForeground(QColor(ACCENT if u["role"] == "admin" else MUTED))
                item.setData(Qt.UserRole, u)
                self.table.setItem(r, c, item)
            self.table.setRowHeight(r, 36)

    def _add_user(self):
        username = self._new_username.text().strip()
        password = self._new_password.text().strip()
        role     = self._new_role.currentText()

        if not username or not password:
            self._show_status("Username and password are required.", error=True)
            return

        try:
            from models.user import create_user
            user = create_user(username, password, role)
            if user:
                self._new_username.clear()
                self._new_password.clear()
                self._new_role.setCurrentIndex(0)
                self._reload()
                self._show_status(f"User '{username}' ({role}) created successfully.")
            else:
                self._show_status(f"Username '{username}' already exists.", error=True)
        except Exception as e:
            self._show_status(f"Error: {e}", error=True)

    def _delete_user(self):
        row = self.table.currentRow()
        if row < 0:
            self._show_status("Select a user to delete.", error=True)
            return
        item = self.table.item(row, 0)
        if not item:
            return
        u = item.data(Qt.UserRole)
        if u["id"] == self.current_user.get("id"):
            self._show_status("You cannot delete your own account.", error=True)
            return

        reply = QMessageBox.question(
            self, "Delete User",
            f"Delete user '{u['username']}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            from models.user import delete_user
            if delete_user(u["id"]):
                self._reload()
                self._show_status(f"User '{u['username']}' deleted.")
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
# ADMIN DASHBOARD  (admin role only)
# =============================================================================
class AdminDashboard(QWidget):
    """
    Full-screen admin panel with:
      • Stats row (today's sales, items sold, top method)
      • Recent sales table
      • Quick stock overview
      • User management shortcut
    """

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

        # ── Top nav bar ───────────────────────────────────────────────────────
        nav = QWidget()
        nav.setFixedHeight(54)
        nav.setStyleSheet(f"background-color: {NAVY};")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(20, 8, 20, 8)
        nav_layout.setSpacing(12)

        logo = QLabel("POS System")
        logo.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {WHITE}; background: transparent; letter-spacing: 1px;")
        nav_layout.addWidget(logo)

        badge = QLabel("ADMIN")
        badge.setStyleSheet(f"""
            background-color: {ACCENT}; color: {WHITE};
            border-radius: 4px; font-size: 10px; font-weight: bold;
            padding: 2px 8px; letter-spacing: 1px;
        """)
        nav_layout.addWidget(badge)
        nav_layout.addStretch()

        date_lbl = QLabel(QDate.currentDate().toString("dd MMM yyyy"))
        date_lbl.setStyleSheet(f"font-size: 12px; color: {MID}; background: transparent;")
        nav_layout.addWidget(date_lbl)
        nav_layout.addSpacing(16)

        # Switch to POS button
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
        nav_layout.addSpacing(8)
        nav_layout.addWidget(user_lbl)
        nav_layout.addSpacing(4)

        logout_btn = navy_btn("Logout", height=30, width=72, color=DANGER, hover=DANGER_H)
        if self.parent_window:
            logout_btn.clicked.connect(self.parent_window._logout)
        nav_layout.addWidget(logout_btn)

        root.addWidget(nav)
        root.addWidget(hr())

        # ── Scrollable body ───────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {OFF_WHITE}; }}")

        body = QWidget()
        body.setStyleSheet(f"background: {OFF_WHITE};")
        body_layout = QVBoxLayout(body)
        body_layout.setSpacing(20)
        body_layout.setContentsMargins(24, 20, 24, 24)

        # Section: Stats cards
        body_layout.addWidget(self._section_label("Today at a Glance"))
        body_layout.addLayout(self._build_stats_row())

        # Section: Recent sales + quick actions side by side
        content_row = QHBoxLayout()
        content_row.setSpacing(20)

        left_col = QVBoxLayout()
        left_col.setSpacing(12)
        left_col.addWidget(self._section_label("Recent Sales  (Today)"))
        left_col.addWidget(self._build_sales_table())
        content_row.addLayout(left_col, 3)

        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        right_col.addWidget(self._section_label("Quick Actions"))
        right_col.addWidget(self._build_quick_actions())
        right_col.addWidget(self._section_label("Stock Alerts"))
        right_col.addWidget(self._build_stock_alerts())
        right_col.addStretch()
        content_row.addLayout(right_col, 1)

        body_layout.addLayout(content_row)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    # ── Section label ─────────────────────────────────────────────────────────
    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            font-size: 13px; font-weight: bold; color: {NAVY};
            background: transparent;
            border-left: 3px solid {ACCENT}; padding-left: 8px;
        """)
        return lbl

    # ── Stats cards ───────────────────────────────────────────────────────────
    def _build_stats_row(self):
        layout = QHBoxLayout()
        layout.setSpacing(14)
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
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 12, 16, 12)
            cl.setSpacing(4)

            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent; font-weight: bold; letter-spacing: 0.5px;")

            val = QLabel(initial)
            val.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: bold; background: transparent;")

            cl.addWidget(lbl)
            cl.addWidget(val)
            layout.addWidget(card, 1)
            self._stat_widgets[key] = val

        return layout

    # ── Recent sales table ────────────────────────────────────────────────────
    def _build_sales_table(self):
        self.sales_table = QTableWidget(0, 5)
        self.sales_table.setHorizontalHeaderLabels(
            ["Invoice #", "Time", "Cashier", "Method", "Total"]
        )
        hh = self.sales_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed);  self.sales_table.setColumnWidth(0, 100)
        hh.setSectionResizeMode(1, QHeaderView.Fixed);  self.sales_table.setColumnWidth(1, 80)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Fixed);  self.sales_table.setColumnWidth(3, 90)
        hh.setSectionResizeMode(4, QHeaderView.Fixed);  self.sales_table.setColumnWidth(4, 100)
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

    # ── Quick actions ─────────────────────────────────────────────────────────
    def _build_quick_actions(self):
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background-color: {WHITE};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(8)

        actions = [
            ("Manage Users",   self._open_manage_users,   ACCENT),
            ("Stock File",     self._open_stock,           NAVY),
            ("Sales History",  self._open_sales_history,   NAVY_3),
            ("Day Shift",      self._open_day_shift,       NAVY_2),
            ("Refresh Data",   self._load_data,            SUCCESS),
        ]
        for label, handler, color in actions:
            btn = QPushButton(label)
            btn.setFixedHeight(38)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color}14;
                    color: {color};
                    border: 1px solid {color}44;
                    border-radius: 5px;
                    font-size: 13px; font-weight: bold;
                    text-align: left; padding: 0 14px;
                }}
                QPushButton:hover {{
                    background-color: {color};
                    color: {WHITE};
                    border-color: {color};
                }}
            """)
            btn.clicked.connect(handler)
            cl.addWidget(btn)

        return card

    # ── Stock alerts ──────────────────────────────────────────────────────────
    def _build_stock_alerts(self):
        self._stock_alert_widget = QWidget()
        self._stock_alert_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {WHITE};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
        """)
        self._stock_alert_layout = QVBoxLayout(self._stock_alert_widget)
        self._stock_alert_layout.setContentsMargins(14, 12, 14, 12)
        self._stock_alert_layout.setSpacing(6)
        lbl = QLabel("No low-stock alerts")
        lbl.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
        self._stock_alert_layout.addWidget(lbl)
        return self._stock_alert_widget

    # ── Data loading ──────────────────────────────────────────────────────────
    def _load_data(self):
        """Load today's stats, recent sales, and stock alerts from DB."""
        # --- Sales stats ---
        try:
            from models.sale import get_today_sales, get_today_total, get_today_total_by_method
            sales   = get_today_sales()
            total   = get_today_total()
            by_meth = get_today_total_by_method()
            top_m   = max(by_meth, key=by_meth.get) if by_meth else "—"
            items   = sum(1 for _ in sales)  # count transactions; swap for item count if available
        except Exception:
            sales, total, top_m, items = [], 0.0, "Cash", 0

        self._stat_widgets["revenue"].setText(f"${total:,.2f}")
        self._stat_widgets["txn_count"].setText(str(len(sales)))
        self._stat_widgets["items_sold"].setText(str(items))
        self._stat_widgets["top_method"].setText(top_m)

        # --- Populate sales table ---
        self.sales_table.setRowCount(0)
        for s in sales[:50]:
            r = self.sales_table.rowCount()
            self.sales_table.insertRow(r)
            for c, (key, fmt) in enumerate([
                ("number", lambda v: f"#{v}"),
                ("time",   lambda v: str(v)),
                ("user",   lambda v: str(v)),
                ("method", lambda v: str(v)),
                ("total",  lambda v: f"${v:.2f}"),
            ]):
                raw = s.get(key, "")
                text = fmt(raw)
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter if c != 2 else Qt.AlignLeft | Qt.AlignVCenter)
                if key == "total":
                    item.setForeground(QColor(ACCENT))
                self.sales_table.setItem(r, c, item)
            self.sales_table.setRowHeight(r, 34)

        # --- Stock alerts (low stock <= 5) ---
        while self._stock_alert_layout.count():
            item = self._stock_alert_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            from models.product import get_all_products
            low = [p for p in get_all_products() if p["stock"] <= 5]
        except Exception:
            low = []

        if not low:
            row_w = QWidget(); row_w.setStyleSheet("background: transparent;")
            rh = QHBoxLayout(row_w); rh.setContentsMargins(0, 0, 0, 0); rh.setSpacing(6)
            ic = QLabel(); ic.setPixmap(qta.icon("fa5s.check", color=SUCCESS).pixmap(14, 14))
            ic.setStyleSheet("background:transparent;")
            lbl = QLabel("All stock levels OK")
            lbl.setStyleSheet(f"color: {SUCCESS}; font-size: 12px; background: transparent;")
            rh.addWidget(ic); rh.addWidget(lbl); rh.addStretch()
            self._stock_alert_layout.addWidget(row_w)
        else:
            for p in low[:8]:
                row_w = QWidget()
                row_w.setStyleSheet("background: transparent;")
                rh = QHBoxLayout(row_w)
                rh.setContentsMargins(0, 0, 0, 0)
                nm = QLabel(p["name"])
                nm.setStyleSheet(f"color: {DARK_TEXT}; font-size: 12px; background: transparent;")
                st = QLabel(f"Stock: {p['stock']}")
                st.setStyleSheet(f"color: {DANGER}; font-size: 12px; font-weight: bold; background: transparent;")
                rh.addWidget(nm, 1)
                rh.addWidget(st)
                self._stock_alert_layout.addWidget(row_w)

    # ── Action handlers ───────────────────────────────────────────────────────
    def _open_manage_users(self):
        dlg = ManageUsersDialog(self, current_user=self.user)
        dlg.exec()

    def _open_stock(self):
        if _HAS_STOCK:
            StockFileDialog(self).exec()
        else:
            coming_soon(self, "Stock File")

    def _open_sales_history(self):
        if _HAS_SALES_LIST:
            SalesListDialog(self).exec()
        else:
            coming_soon(self, "Sales History")

    def _open_day_shift(self):
        if _HAS_DAY_SHIFT:
            DayShiftDialog(self, user=self.user).exec()
        else:
            coming_soon(self, "Day Shift")


# =============================================================================
# CASHIER POS VIEW  (the invoice / till screen)
# =============================================================================
class POSView(QWidget):
    """
    Layout matches reference image exactly:
      ┌─ thin navy title bar (POS-1 | date | user | logout) ────────────────┐
      ├─ LEFT: invoice table (10 visible rows, compact) ─┬─ RIGHT: numpad ──┤
      ├─ bin bar ─────────────────────────────────────────┤  + action btns  ┤
      ├─ bottom info (Invoice# | Client | Totals) ────────┴─────────────────┤
      ├─ category tabs (up to 10 visible, arrow scroll if more) ────────────┤
      └─ product grid (4 rows × 10 cols) + cash column ────────────────────┘
    """

    MAX_ROWS = 20   # total rows in table; only ~10 visible at once (scroll)

    def __init__(self, parent_window=None, user=None):
        super().__init__()
        self.parent_window  = parent_window
        self.user           = user or {"username": "cashier", "role": "cashier"}
        self._active_row    = -1
        self._active_col    = -1
        self._numpad_buffer = ""
        self._block_signals = False
        self._cat_page      = 0   # for category arrow paging
        self._build_ui()

    # =========================================================================
    # ROOT LAYOUT
    # =========================================================================
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self._build_nav())     # thin title bar

        # Middle body: left invoice + right numpad
        body = QHBoxLayout()
        body.setSpacing(0)
        body.setContentsMargins(0, 0, 0, 0)
        _rp = self._build_right_panel()   # stubs created first
        body.addWidget(self._build_left_panel(), 1)
        body.addWidget(hr(horizontal=False))
        body.addWidget(_rp)
        layout.addLayout(body, 1)

        layout.addWidget(hr())
        layout.addWidget(self._build_bottom_grid(), 0)   # categories + products

    # =========================================================================
    # NAV BAR — compact, no pill menu buttons (removed as requested)
    # =========================================================================
    def _build_nav(self):
        bar = QWidget()
        bar.setFixedHeight(38)
        bar.setStyleSheet(f"background-color: {NAVY};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        logo = QLabel("POS-1")
        logo.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {WHITE}; background: transparent;"
        )
        date_lbl = QLabel(QDate.currentDate().toString("dd/MM/yyyy"))
        date_lbl.setStyleSheet(
            f"font-size: 12px; color: {MID}; background: transparent;"
        )
        layout.addWidget(logo)
        layout.addSpacing(6)
        layout.addWidget(date_lbl)
        layout.addSpacing(10)

        def _npb(text, handler, color=NAVY_2, hov=NAVY_3):
            b = QPushButton(text)
            b.setFixedHeight(24)
            b.setCursor(Qt.PointingHandCursor)
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
        layout.addWidget(_npb("Settings",  lambda: coming_soon(self, "Settings")))
        layout.addSpacing(14)

        inv_lbl = QLabel("Inv#")
        inv_lbl.setStyleSheet(f"font-size: 10px; color: {MID}; background: transparent;")
        layout.addWidget(inv_lbl)

        f7_btn = QPushButton("F7  Sales")
        f7_btn.setFixedHeight(24)
        f7_btn.setCursor(Qt.PointingHandCursor)
        f7_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT}; color: {WHITE}; border: none;
                border-radius: 3px; font-size: 11px; font-weight: bold; padding: 0 8px;
            }}
            QPushButton:hover {{ background-color: {ACCENT_H}; }}
        """)
        f7_btn.clicked.connect(self._open_sales_list)
        layout.addWidget(f7_btn)
        layout.addSpacing(14)

        chg_prefix = QLabel("Change:")
        chg_prefix.setStyleSheet(f"font-size: 11px; color: {MID}; background: transparent;")
        self._lbl_change = QLabel("0.00")
        self._lbl_change.setFixedWidth(80)
        self._lbl_change.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._lbl_change.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {ORANGE}; background: transparent;"
        )
        layout.addWidget(chg_prefix)
        layout.addWidget(self._lbl_change)
        layout.addSpacing(12)

        paid_prefix = QLabel("Paid:")
        paid_prefix.setStyleSheet(f"font-size: 11px; color: {MID}; background: transparent;")
        self._inp_paid = QLineEdit("0.00")
        self._inp_paid.setFixedSize(80, 26)
        self._inp_paid.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._inp_paid.setStyleSheet(f"""
            QLineEdit {{
                background-color: {NAVY_2}; border: 1px solid {NAVY_3};
                border-radius: 3px; font-size: 13px; font-weight: bold;
                color: {WHITE}; padding: 0 6px;
            }}
            QLineEdit:focus {{ border: 2px solid {ACCENT}; }}
        """)
        self._inp_paid.textChanged.connect(lambda _: self._recalc_totals())
        layout.addWidget(paid_prefix)
        layout.addWidget(self._inp_paid)

        layout.addStretch()

        # Admin-only: Dashboard button
        try:
            from models.user import is_admin
            if self.user and is_admin(self.user):
                dash_btn = QPushButton("Dashboard")
                dash_btn.setFixedHeight(26)
                dash_btn.setCursor(Qt.PointingHandCursor)
                dash_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ACCENT}; color: {WHITE};
                        border: none; border-radius: 3px;
                        font-size: 11px; padding: 0 10px;
                    }}
                    QPushButton:hover {{ background-color: {ACCENT_H}; }}
                """)
                if self.parent_window:
                    dash_btn.clicked.connect(self.parent_window.switch_to_dashboard)
                layout.addWidget(dash_btn)
        except Exception:
            pass

        role_badge = QLabel(self.user.get("role", "").upper())
        role_c = ACCENT if self.user.get("role") == "admin" else NAVY_3
        role_badge.setStyleSheet(
            f"background-color: {role_c}; color: {WHITE}; border-radius: 3px;"
            f"font-size: 10px; font-weight: bold; padding: 2px 5px;"
        )
        user_lbl = QLabel(self.user.get("username", ""))
        user_lbl.setStyleSheet(
            f"font-size: 12px; color: {OFF_WHITE}; background: transparent;"
        )
        layout.addWidget(role_badge)
        layout.addWidget(user_lbl)

        logout = QPushButton("Logout")
        logout.setFixedHeight(26)
        logout.setFixedWidth(60)
        logout.setCursor(Qt.PointingHandCursor)
        logout.setStyleSheet(f"""
            QPushButton {{
                background-color: {DANGER}; color: {WHITE};
                border: none; border-radius: 3px; font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {DANGER_H}; }}
        """)
        if self.parent_window:
            logout.clicked.connect(self.parent_window._logout)
        layout.addWidget(logout)
        return bar

    # =========================================================================
    # LEFT PANEL — invoice table + bin bar + bottom info
    # =========================================================================
    def _build_left_panel(self):
        panel = QWidget()
        panel.setStyleSheet(f"background-color: {OFF_WHITE};")
        layout = QVBoxLayout(panel)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build_invoice_table(), 1)
        return panel

    # ── Invoice table ─────────────────────────────────────────────────────────
    def _build_invoice_table(self):
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(7)
        # Renamed as requested: Part No. → Item No., Part Details → Item Details
        self.invoice_table.setHorizontalHeaderLabels(
            ["Item No.", "Item Details", "Qty", "Amount $", "Disc. %", "TAX", "Total $"]
        )
        hh = self.invoice_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed);  self.invoice_table.setColumnWidth(0, 90)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed);  self.invoice_table.setColumnWidth(2, 60)
        hh.setSectionResizeMode(3, QHeaderView.Fixed);  self.invoice_table.setColumnWidth(3, 90)
        hh.setSectionResizeMode(4, QHeaderView.Fixed);  self.invoice_table.setColumnWidth(4, 65)
        hh.setSectionResizeMode(5, QHeaderView.Fixed);  self.invoice_table.setColumnWidth(5, 45)
        hh.setSectionResizeMode(6, QHeaderView.Fixed);  self.invoice_table.setColumnWidth(6, 90)

        self.invoice_table.verticalHeader().setVisible(False)
        self.invoice_table.setAlternatingRowColors(True)
        self.invoice_table.setShowGrid(True)
        self.invoice_table.setRowCount(self.MAX_ROWS)
        # compact rows so ~10 fit without scrolling
        self.invoice_table.verticalHeader().setDefaultSectionSize(26)
        self.invoice_table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked
        )
        for r in range(self.MAX_ROWS):
            self.invoice_table.setRowHeight(r, 26)
            self._init_row(r)

        self.invoice_table.cellClicked.connect(self._on_cell_clicked)
        self.invoice_table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.invoice_table.itemChanged.connect(self._on_item_changed)
        return self.invoice_table

    def _init_row(self, r, part_no="", details="", qty="",
                  amount="", disc="0.00", tax="", total=""):
        vals = [part_no, details, qty, amount, disc, tax, total]
        for c, val in enumerate(vals):
            item = QTableWidgetItem(str(val))
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter if c == 1 else Qt.AlignCenter)
            if c == 6:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setForeground(QColor(ACCENT))
            self.invoice_table.setItem(r, c, item)

    def _find_next_empty_row(self):
        for r in range(self.MAX_ROWS):
            item = self.invoice_table.item(r, 2)
            if not item or not item.text().strip():
                return r
        return self.MAX_ROWS - 1

    # ── Calculation engine ────────────────────────────────────────────────────
    def _recalc_row(self, r):
        if self._block_signals:
            return
        try:
            qty    = float(self.invoice_table.item(r, 2).text() or "0")
            amount = float(self.invoice_table.item(r, 3).text() or "0")
            disc   = float(self.invoice_table.item(r, 4).text() or "0")
            total  = qty * amount * (1.0 - disc / 100.0)
        except (ValueError, AttributeError):
            total = 0.0
        self._block_signals = True
        item = self.invoice_table.item(r, 6)
        if item:
            item.setText(f"{total:.2f}")
            item.setForeground(QColor(ACCENT))
        self._block_signals = False
        self._recalc_totals()

    def _recalc_totals(self):
        grand_total = 0.0
        qty_total   = 0.0
        for r in range(self.MAX_ROWS):
            try:
                grand_total += float(self.invoice_table.item(r, 6).text() or "0")
                qty_total   += float(self.invoice_table.item(r, 2).text() or "0")
            except (ValueError, AttributeError):
                pass
        self._lbl_total.setText(f"{grand_total:.2f}")
        try:
            paid   = float(self._inp_paid.text() or "0")
            change = paid - grand_total
        except ValueError:
            change = 0.0
        self._lbl_change.setText(f"{max(change, 0.0):.2f}")
        self._lbl_change.setStyleSheet(
            f"font-size: 16px; font-weight: bold; background: transparent; color: {ORANGE};"
        )
        self._bin_qty.setText(f"{qty_total:.2f}")
        self._bin_total.setText(f"{grand_total:.2f}")
        if self.parent_window:
            self.parent_window._set_status(
                f"  Items: {int(qty_total)}   |   Total: ${grand_total:.2f}   |   "
                f"Change: ${max(change, 0.0):.2f}"
            )

    def _on_item_changed(self, item):
        if self._block_signals:
            return
        if item.column() in (2, 3, 4):
            self._recalc_row(item.row())

    def _on_cell_clicked(self, row, col):
        self._active_row    = row
        self._active_col    = col
        self._numpad_buffer = ""
        if col == 5:
            item = self.invoice_table.item(row, col)
            if item:
                item.setText("" if item.text() == "T" else "T")

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
            if item0:
                item0.setData(Qt.UserRole, p.get("id"))
            self._block_signals = False
            self._recalc_row(row)
            self.invoice_table.setCurrentCell(row, 2)
            self._active_row = row
            self._active_col = 2

    def _add_product_to_invoice(self, name, price, part_no="", product_id=None):
        r = self._find_next_empty_row()
        self._block_signals = True
        self._init_row(r, part_no=part_no, details=name, qty="1",
                       amount=f"{price:.2f}", disc="0.00", tax="")
        item = self.invoice_table.item(r, 0)
        if item:
            item.setData(Qt.UserRole, product_id)
        self._block_signals = False
        self._recalc_row(r)
        self.invoice_table.setCurrentCell(r, 2)
        self._active_row = r
        self._active_col = 2
        if self.parent_window:
            self.parent_window._set_status(f"Added: {name} @ ${price:.2f}")

    # ── Stubs (_lbl_change/_inp_paid now in nav; _lbl_total etc. in right panel) ──
    def _create_totals_stubs(self):
        self._bin_qty             = QLabel()
        self._bin_total           = QLabel()
        self.invoice_number_input = QLineEdit("1")

        # =========================================================================
    # RIGHT PANEL — Save/Print/Hold top | numpad | TOTAL+Pay bottom
    # =========================================================================
    def _build_right_panel(self):
        self._create_totals_stubs()

        panel = QWidget()
        panel.setFixedWidth(310)
        panel.setStyleSheet(f"background-color: {OFF_WHITE};")
        layout = QVBoxLayout(panel)
        layout.setSpacing(4)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── TOP: Save / Print / Hold ──────────────────────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(4)
        for label, bg, hov, handler in [
            ("Save  F2",    NAVY,   NAVY_2, lambda: coming_soon(self, "Save Sale (F2)")),
            ("Print  F3",   NAVY,   NAVY_2, lambda: coming_soon(self, "Print Receipt (F3)")),
            ("Hold/Recall", NAVY_2, NAVY_3, self._open_hold_recall),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(36)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg}; color: {WHITE}; border: none;
                    border-radius: 5px; font-size: 11px; font-weight: bold;
                }}
                QPushButton:hover   {{ background-color: {hov}; }}
                QPushButton:pressed {{ background-color: {NAVY_3}; }}
            """)
            b.clicked.connect(handler)
            top_row.addWidget(b)
        layout.addLayout(top_row)

        # ── MIDDLE: numpad ────────────────────────────────────────────────────
        layout.addWidget(self._build_numpad(), 1)

        # ── BOTTOM: dark bar — TOTAL left, PAY right ─────────────────────────
        bottom_bar = QWidget()
        bottom_bar.setFixedHeight(46)
        bottom_bar.setStyleSheet(f"background-color: {NAVY}; border-radius: 5px;")
        bb = QHBoxLayout(bottom_bar)
        bb.setContentsMargins(10, 0, 6, 0)
        bb.setSpacing(8)
        tot_lbl = QLabel("TOTAL")
        tot_lbl.setStyleSheet(
            f"color: {MID}; font-size: 10px; font-weight: bold; background: transparent; letter-spacing: 1px;"
        )
        self._lbl_total = QLabel("0.00")
        self._lbl_total.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._lbl_total.setStyleSheet(
            f"color: {WHITE}; font-size: 20px; font-weight: bold; background: transparent;"
        )
        bb.addWidget(tot_lbl)
        bb.addSpacing(4)
        bb.addWidget(self._lbl_total, 1)
        pay_btn = QPushButton("PAY  F5")
        pay_btn.setFixedSize(88, 34)
        pay_btn.setCursor(Qt.PointingHandCursor)
        pay_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SUCCESS}; color: {WHITE}; border: none;
                border-radius: 4px; font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover   {{ background-color: {SUCCESS_H}; }}
            QPushButton:pressed {{ background-color: {NAVY_3}; }}
        """)
        pay_btn.clicked.connect(self._open_payment)
        bb.addWidget(pay_btn)
        layout.addWidget(bottom_bar)
        return panel

    def _build_numpad(self):
        card = QWidget()
        card.setStyleSheet(
            f"QWidget {{ background-color: {WHITE}; border: 1px solid {BORDER}; border-radius: 8px; }}"
        )
        grid = QGridLayout(card)
        grid.setSpacing(4)
        grid.setContentsMargins(6, 6, 6, 6)

        rows_def = [
            [("7","digit"),("8","digit"),("9","digit"),("−","op"),("X","clear")],
            [("4","digit"),("5","digit"),("6","digit"),("×","op"),("Del\nLine","del")],
            [("1","digit"),("2","digit"),("3","digit")],
            [("0","digit"),(".","digit")],
        ]
        enter_btn = numpad_btn("Enter", "enter")
        enter_btn.clicked.connect(self._numpad_enter)

        for ri, row_def in enumerate(rows_def):
            for ci, (ch, kind) in enumerate(row_def):
                b = numpad_btn(ch, kind)
                if ch in "0123456789.":
                    b.clicked.connect(lambda _, c=ch: self._numpad_press(c))
                elif ch == "−":
                    b.clicked.connect(lambda: self._numpad_press("-"))
                elif ch == "×":
                    b.clicked.connect(lambda: self._numpad_press("×"))
                elif ch == "X":
                    b.clicked.connect(self._numpad_clear)
                elif "Del" in ch:
                    b.clicked.connect(self._numpad_del_line)
                    grid.addWidget(b, ri, ci)

        # Enter spans rows 2-3, cols 3-4
        grid.addWidget(enter_btn, 2, 3, 2, 2)

        # Open Cash — big, spans cols 2-4 on row 3
        cash_btn = numpad_btn("Open\nCash", "cash")
        cash_btn.clicked.connect(lambda: coming_soon(self, "Open Cash Drawer"))
        grid.addWidget(cash_btn, 3, 2, 1, 3)

        return card

    # =========================================================================
    # NUMPAD LOGIC
    # =========================================================================
    def _numpad_press(self, char):
        if self._active_row < 0 or self._active_col < 0:
            r = self._find_next_empty_row()
            self._active_row = r
            self._active_col = 2
            self.invoice_table.setCurrentCell(r, 2)
        if self._active_col in (5, 6):
            return
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
            if item:
                item.setText("")
            self._block_signals = False
            if self._active_col in (2, 3, 4):
                self._recalc_row(self._active_row)

    def _numpad_del_line(self):
        if self._active_row < 0:
            return
        self._block_signals = True
        self._init_row(self._active_row)
        self._block_signals = False
        self._recalc_totals()
        self._numpad_buffer = ""
        self._active_row = -1
        self._active_col = -1

    def _numpad_enter(self):
        if self._active_row < 0:
            return
        self._numpad_buffer = ""
        advance = {0: 1, 1: 2, 2: 3, 3: 4}
        next_col = advance.get(self._active_col)
        if next_col is not None:
            self._active_col = next_col
            self.invoice_table.setCurrentCell(self._active_row, next_col)
        else:
            self._recalc_row(self._active_row)
            next_row = self._active_row + 1
            if next_row < self.MAX_ROWS:
                self._active_row = next_row
                self._active_col = 0
                self.invoice_table.setCurrentCell(next_row, 0)

    # =========================================================================
    # BOTTOM GRID — category tabs (10 visible + arrow scroll) + product cards
    #               + cash quick-tender column
    # =========================================================================
    def _build_bottom_grid(self):
        container = QWidget()
        container.setStyleSheet(f"background-color: {WHITE};")
        outer = QVBoxLayout(container)
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)

        main_row = QHBoxLayout()
        main_row.setSpacing(0)
        main_row.setContentsMargins(0, 0, 0, 0)

        # ── Left: tabs + product grid ─────────────────────────────────────────
        left_widget = QWidget()
        left_widget.setStyleSheet(f"background-color: {WHITE};")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(0)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Load categories
        try:
            from models.product import get_categories
            self._category_names = get_categories()
        except Exception:
            self._category_names = []
        if not self._category_names:
            self._category_names = ["All"]

        # Category tab row with ◀ ▶ arrow buttons when >10 cats
        self._cat_buttons  = []
        self._cat_page     = 0
        self._CATS_VISIBLE = 10

        tab_row_w = QWidget()
        tab_row_w.setFixedHeight(36)
        tab_row_w.setStyleSheet(
            f"background-color: {WHITE}; border-bottom: 1px solid {BORDER};"
        )
        tab_row_h = QHBoxLayout(tab_row_w)
        tab_row_h.setSpacing(0)
        tab_row_h.setContentsMargins(0, 0, 0, 0)

        # Prev arrow (hidden when not needed)
        self._cat_prev_btn = QPushButton("◀")
        self._cat_prev_btn.setFixedSize(28, 36)
        self._cat_prev_btn.setCursor(Qt.PointingHandCursor)
        self._cat_prev_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {LIGHT}; color: {DARK_TEXT};
                border: none; border-right: 1px solid {BORDER}; font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {ACCENT}; color: {WHITE}; }}
        """)
        self._cat_prev_btn.clicked.connect(lambda: self._cat_scroll(-1))
        tab_row_h.addWidget(self._cat_prev_btn)

        # Placeholder buttons (we'll fill them in _refresh_cat_tabs)
        self._cat_tab_container = QWidget()
        self._cat_tab_container.setStyleSheet(f"background-color: {WHITE};")
        self._cat_tab_layout = QHBoxLayout(self._cat_tab_container)
        self._cat_tab_layout.setSpacing(0)
        self._cat_tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_row_h.addWidget(self._cat_tab_container, 1)

        self._cat_next_btn = QPushButton("▶")
        self._cat_next_btn.setFixedSize(28, 36)
        self._cat_next_btn.setCursor(Qt.PointingHandCursor)
        self._cat_next_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {LIGHT}; color: {DARK_TEXT};
                border: none; border-left: 1px solid {BORDER}; font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {ACCENT}; color: {WHITE}; }}
        """)
        self._cat_next_btn.clicked.connect(lambda: self._cat_scroll(1))
        tab_row_h.addWidget(self._cat_next_btn)

        left_layout.addWidget(tab_row_w)

        # Product grid
        self._product_grid_widget = QWidget()
        self._product_grid_widget.setStyleSheet(f"background-color: {WHITE};")
        self._product_grid = QGridLayout(self._product_grid_widget)
        self._product_grid.setSpacing(1)
        self._product_grid.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self._product_grid_widget, 1)
        main_row.addWidget(left_widget, 1)

        # ── Cash / quick-tender column ────────────────────────────────────────
        cash_col = QWidget()
        cash_col.setFixedWidth(100)
        cash_col.setStyleSheet(f"background-color: {WHITE}; border-left: 1px solid {BORDER};")
        cash_layout = QVBoxLayout(cash_col)
        cash_layout.setSpacing(0)
        cash_layout.setContentsMargins(0, 0, 0, 0)

        # Spacer matching tab bar height
        sp = QWidget()
        sp.setFixedHeight(36)
        sp.setStyleSheet(f"background-color: {WHITE}; border-bottom: 1px solid {BORDER};")
        cash_layout.addWidget(sp)

        for amt, hov_color in [
            ("$100", NAVY), ("$50", NAVY), ("$20", NAVY), ("$10", NAVY), ("%Discount", ACCENT),
        ]:
            b = QPushButton(amt)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: {WHITE}; color: {DARK_TEXT};
                    border: none; border-top: 1px solid {BORDER};
                    font-size: 12px; font-weight: bold; text-align: right; padding-right: 8px;
                }}
                QPushButton:hover {{ background-color: {hov_color}; color: {WHITE}; }}
            """)
            if "Discount" in amt:
                b.clicked.connect(lambda: coming_soon(self, "Apply Discount"))
            else:
                val = float(amt.replace("$", ""))
                b.clicked.connect(lambda _, v=val: self._quick_tender(v))
            cash_layout.addWidget(b)

        main_row.addWidget(cash_col)
        outer.addLayout(main_row, 1)

        # Initialise tabs + products
        self._refresh_cat_tabs()
        self._load_category_products(0, self._category_names[0])

        return container

    def _cat_scroll(self, direction):
        total_pages = max(1, (len(self._category_names) + self._CATS_VISIBLE - 1) // self._CATS_VISIBLE)
        self._cat_page = max(0, min(self._cat_page + direction, total_pages - 1))
        self._refresh_cat_tabs()

    def _refresh_cat_tabs(self):
        # Clear old buttons
        while self._cat_tab_layout.count():
            item = self._cat_tab_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cat_buttons.clear()

        start = self._cat_page * self._CATS_VISIBLE
        visible = self._category_names[start: start + self._CATS_VISIBLE]
        global_start = start

        for local_i, name in enumerate(visible):
            global_idx = global_start + local_i
            active = (global_idx == getattr(self, "_active_cat_idx", 0))
            b = QPushButton(name)
            b.setFixedHeight(36)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(self._cat_tab_style(active, TAB_COLORS[global_idx % len(TAB_COLORS)]))
            b.clicked.connect(lambda _, idx=global_idx, n=name: self._on_category_tap(idx, n))
            self._cat_tab_layout.addWidget(b)
            self._cat_buttons.append(b)

        # Show/hide arrows
        total_pages = max(1, (len(self._category_names) + self._CATS_VISIBLE - 1) // self._CATS_VISIBLE)
        self._cat_prev_btn.setVisible(self._cat_page > 0)
        self._cat_next_btn.setVisible(self._cat_page < total_pages - 1)

    def _quick_tender(self, amount):
        self._inp_paid.setText(f"{amount:.2f}")
        self._recalc_totals()

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
            if item.widget():
                item.widget().deleteLater()

        # Load from DB
        try:
            from models.product import get_products_by_category, get_all_products
            db_products = get_all_products() if name == "All" else get_products_by_category(name)
            products = [(p["name"], p["part_no"], p["price"], p["id"]) for p in db_products]
        except Exception:
            products = []

        ROWS, COLS = 4, 10   # 4 rows × 10 cols = 40 slots per category page
        for r in range(ROWS):
            for c in range(COLS):
                flat = r * COLS + c
                if flat < len(products):
                    pname, part_no, price, product_id = products[flat]
                    btn = QPushButton(pname)
                    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.setToolTip("Click to add · Double-click to set image")
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {OFF_WHITE}; color: {DARK_TEXT};
                            border: 1px solid {BORDER}; border-radius: 0px;
                            font-size: 11px; font-weight: bold; text-align: center;
                            padding: 4px 2px;
                        }}
                        QPushButton:hover {{ background-color: {ACCENT}; color: {WHITE}; }}
                        QPushButton:pressed {{ background-color: {ACCENT_H}; color: {WHITE}; }}
                    """)
                    btn.clicked.connect(
                        lambda _, n=pname, pr=price, pno=part_no, pid=product_id:
                        self._add_product_to_invoice(n, pr, pno, pid)
                    )
                    # Double-click → pick image from disk
                    _pid = product_id
                    _pname = pname
                    btn.mouseDoubleClickEvent = (
                        lambda e, b=btn, pid=_pid, pn=_pname:
                        self._pick_product_image(b, pid, pn)
                    )
                else:
                    btn = QPushButton("")
                    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {OFF_WHITE}; border: 1px solid {BORDER};
                            border-radius: 0px;
                        }}
                    """)
                self._product_grid.addWidget(btn, r, c)

    def _pick_product_image(self, btn, product_id, product_name):
        """Double-click a product card → browse for image → show it on the button."""
        from PySide6.QtWidgets import QFileDialog
        from PySide6.QtGui import QIcon, QPixmap
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select image for  {product_name}",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return
        pix = QPixmap(path)
        if pix.isNull():
            QMessageBox.warning(self, "Image Error", "Could not load the selected image.")
            return
        # Image fills top of button; name text stays at bottom (Qt places icon above text)
        from PySide6.QtCore import QSize as _QSz
        btn.setIcon(QIcon(pix.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
        btn.setIconSize(_QSz(9999, 9999))   # Qt clips to button bounds automatically
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {OFF_WHITE}; color: {DARK_TEXT};
                border: 1px solid {BORDER}; border-radius: 0px;
                font-size: 10px; font-weight: bold;
                padding-bottom: 4px;
            }}
            QPushButton:hover {{ background-color: {ACCENT}; color: {WHITE}; }}
            QPushButton:pressed {{ background-color: {ACCENT_H}; color: {WHITE}; }}
        """)
        # Persist image path so it survives category switches (stored in UserRole on the button)
        # BACKEND: save image path to DB via models.product.set_product_image(product_id, path)
        try:
            from models.product import set_product_image
            set_product_image(product_id, path)
        except Exception:
            pass   # silently skip if model not yet wired

    # =========================================================================
    # DIALOG OPENERS
    # =========================================================================
    def _open_day_shift(self):
        if _HAS_DAY_SHIFT:
            DayShiftDialog(self, user=self.user).exec()
        else:
            coming_soon(self, "Day Shift — add views/dialogs/day_shift_dialog.py")

    def _open_stock_file(self):
        if _HAS_STOCK:
            StockFileDialog(self).exec()
        else:
            coming_soon(self, "Stock File — add views/dialogs/stock_file_dialog.py")

    def _open_sales_list(self):
        if _HAS_SALES_LIST:
            dlg = SalesListDialog(self)
            if dlg.exec() == QDialog.Accepted and dlg.selected_sale:
                self._new_sale(confirm=False)
                for item in dlg.selected_items:
                    self._add_product_to_invoice(
                        name=item["product_name"],
                        price=item["price"],
                        part_no=item["part_no"],
                    )
        else:
            coming_soon(self, "Sales List — add views/dialogs/sales_list_dialog.py")

    def _collect_invoice_items(self) -> list[dict]:
        items = []
        for r in range(self.MAX_ROWS):
            try:
                qty = float(self.invoice_table.item(r, 2).text() or "0")
            except (ValueError, AttributeError):
                qty = 0.0
            if qty <= 0:
                continue
            try:
                part_no      = self.invoice_table.item(r, 0).text()
                product_name = self.invoice_table.item(r, 1).text()
                price        = float(self.invoice_table.item(r, 3).text() or "0")
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

    def _open_payment(self):
        try:
            total = float(self._lbl_total.text() or "0")
        except ValueError:
            total = 0.0
        if total <= 0:
            QMessageBox.warning(self, "Empty Invoice", "Add items before payment.")
            return
        dlg = PaymentDialog(self, total=total)
        if dlg.exec() == QDialog.Accepted:
            items = self._collect_invoice_items()
            try:
                tendered = float(dlg._amt.text() or "0")
            except ValueError:
                tendered = total
            try:
                from models.sale import create_sale
                cashier_id = self.user.get("id") if isinstance(self.user, dict) else None
                sale = create_sale(items=items, total=total, tendered=tendered,
                                   method=dlg._method, cashier_id=cashier_id)
                self.invoice_number_input.setText(str(sale["number"] + 1))
            except Exception as e:
                QMessageBox.warning(self, "Save Error", f"DB error:\n{e}")
            self._new_sale(confirm=False)

    def _open_hold_recall(self):
        HoldRecallDialog(self).exec()

    def _new_sale(self, confirm=True):
        if confirm:
            reply = QMessageBox.question(
                self, "New Sale", "Clear the current invoice and start a new sale?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        self._block_signals = True
        for r in range(self.MAX_ROWS):
            self._init_row(r)
        self._block_signals = False
        self._numpad_buffer = ""
        self._active_row = -1
        self._active_col = -1
        self._inp_paid.setText("0.00")
        self._recalc_totals()
        if self.parent_window:
            self.parent_window._set_status("New sale started.")

    def keyPressEvent(self, event):
        key = event.key()
        if   key == Qt.Key_F2:     coming_soon(self, "Save Sale (F2)")
        elif key == Qt.Key_F3:     coming_soon(self, "Print Receipt (F3)")
        elif key == Qt.Key_F5:     self._open_payment()
        elif key == Qt.Key_F7:     self._open_sales_list()
        elif key == Qt.Key_Escape: self._numpad_clear()
        else:
            super().keyPressEvent(event)


# =============================================================================
# MAIN WINDOW  —  orchestrates login-flow, role routing, mode switching
# =============================================================================
class MainWindow(QMainWindow):
    """
    Container window.
    • admin  → starts on AdminDashboard; can switch to POSView and back.
    • cashier → starts directly on POSView; no access to Dashboard.
    """

    def __init__(self, user=None):
        super().__init__()
        self.user = user or {"username": "admin", "role": "admin"}

        self.setWindowTitle("POS System")
        self.setMinimumSize(1280, 820)
        self.setStyleSheet(GLOBAL_STYLE)

        # ── Build stacked layout ──────────────────────────────────────────────
        self._stack = QStackedWidget()

        self._pos_view = POSView(parent_window=self, user=self.user)
        self._stack.addWidget(self._pos_view)           # index 0 = POS

        from models.user import is_admin
        if is_admin(self.user):
            self._dashboard = AdminDashboard(parent_window=self, user=self.user)
            self._stack.addWidget(self._dashboard)      # index 1 = Dashboard

        self.setCentralWidget(self._stack)

        # ── Menu bar (admin only) ─────────────────────────────────────────────
        if is_admin(self.user):
            self._build_menubar()

        # ── Status bar ────────────────────────────────────────────────────────
        self._status_bar = QStatusBar()
        self._status_bar.showMessage(
            f"  {self.user['username']} ({self.user['role']})  |  "
            f"{QDate.currentDate().toString('dd/MM/yyyy')}  |  Ready"
        )
        self.setStatusBar(self._status_bar)

        # ── Start on the right screen ─────────────────────────────────────────
        if is_admin(self.user):
            self._stack.setCurrentIndex(1)   # admins see dashboard first
        else:
            self._stack.setCurrentIndex(0)   # cashiers go straight to POS

    # ── Mode switching ────────────────────────────────────────────────────────
    def switch_to_pos(self):
        self._stack.setCurrentIndex(0)
        self._set_status("POS mode  —  ready to sell.")

    def switch_to_dashboard(self):
        from models.user import is_admin
        if is_admin(self.user):
            self._dashboard._load_data()   # refresh on every visit
            self._stack.setCurrentIndex(1)
            self._set_status("Admin Dashboard.")

    # ── Status bar ────────────────────────────────────────────────────────────
    def _set_status(self, msg):
        self._status_bar.showMessage(f"  {msg}")

    # ── Menu bar (admin only) ─────────────────────────────────────────────────
    def _build_menubar(self):
        mb = self.menuBar()

        pos_menu = mb.addMenu("POS")
        for label, fn in [
            ("New Sale",         lambda: (self.switch_to_pos(), self._pos_view._new_sale())),
            ("Day Shift",        self._pos_view._open_day_shift),
            (None, None),
            ("Open Cash Drawer", lambda: coming_soon(self, "Cash Drawer")),
        ]:
            if label is None:
                pos_menu.addSeparator()
            else:
                a = QAction(label, self)
                a.triggered.connect(fn)
                pos_menu.addAction(a)

        sales_menu = mb.addMenu("Sales")
        for label in ["Sales History", "Returns / Refunds", "Daily Report", "Export CSV"]:
            a = QAction(label, self)
            a.triggered.connect(lambda _, l=label: coming_soon(self, l))
            sales_menu.addAction(a)

        stock_menu = mb.addMenu("Stock")
        a = QAction("Stock File", self)
        a.triggered.connect(self._pos_view._open_stock_file)
        stock_menu.addAction(a)

        settings_menu = mb.addMenu("Settings")
        a_users = QAction("Manage Users", self)
        a_users.triggered.connect(self._open_manage_users)
        settings_menu.addAction(a_users)
        for label in ["Products", "Categories", "Tax Settings", "Printer Setup", "Backup"]:
            a = QAction(label, self)
            a.triggered.connect(lambda _, l=label: coming_soon(self, l))
            settings_menu.addAction(a)

    def _open_manage_users(self):
        dlg = ManageUsersDialog(self, current_user=self.user)
        dlg.exec()

    # ── Logout ────────────────────────────────────────────────────────────────
    def _logout(self):
        reply = QMessageBox.question(
            self, "Logout", "Logout and return to login screen?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.hide()   # hide immediately so it doesn't linger
            try:
                from views.login_dialog import LoginDialog
                dlg = LoginDialog()
                if dlg.exec() == QDialog.Accepted:
                    # Successful re-login — open a fresh MainWindow
                    new_win = MainWindow(user=dlg.logged_in_user)
                    new_win.show()
                    self._next_window = new_win   # hold reference so GC doesn't kill it
                else:
                    # Closed login without signing in → quit cleanly
                    QApplication.quit()
            except Exception:
                QApplication.quit()
            self.close()
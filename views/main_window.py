from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QFrame, QTableWidget, QTableWidgetItem,
    QLineEdit, QGridLayout, QMessageBox, QStatusBar, QSizePolicy,
    QDialog, QHeaderView, QAbstractItemView, QApplication,
    QListWidget, QListWidgetItem, QFormLayout, QComboBox, QScrollArea, QCompleter,
    QSpinBox, QDoubleSpinBox, QTabWidget, QFileDialog, QCheckBox   # ←←← ADD THIS ONE
)
import shutil
import os
from models.advance_settings import AdvanceSettings
from PySide6.QtCore import Qt, QTimer, QDate
# from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtGui import QAction, QColor, QFont, QPixmap
from pathlib import Path
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
except Exception as _settings_import_err:
    _HAS_SETTINGS_DIALOG = False
    import logging as _log
    _log.getLogger("main_window").warning(
        "settings_dialog import failed: %s", _settings_import_err)

try:
    from views.dialogs.laybye_confirm_dialog import LaybyeConfirmDialog
    from views.dialogs.laybye_payment_dialog import LaybyePaymentDialog
    _HAS_LAYBYE = True
except ImportError:
    _HAS_LAYBYE = False

try:
    from models.sales_order import (
        create_sales_order as _create_sales_order,
        ensure_tables as _ensure_so_tables,
        get_unsynced_orders as _get_unsynced_so,
        get_order_by_id as _get_order_by_id,
    )
    _ensure_so_tables()
    _HAS_SALES_ORDER = True
except Exception:
    _HAS_SALES_ORDER = False

try:
    from services.sales_order_print import print_laybye_deposit as _print_laybye_deposit
    _HAS_SO_PRINT = True
except Exception:
    _HAS_SO_PRINT = False

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
NAV_TEXT = "#000000"

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
    background-color: #f0e8d0; color: {NAVY};
    padding: 10px 8px; border: none;
    border-right: 1px solid {BORDER};
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

# =============================================================================
# UOM Picker Dialog — shown when a product has multiple selling UOMs
# =============================================================================
class UomPickerDialog(QDialog):
    """Touch-friendly UOM picker — shows each unit and price as a large tappable button."""

    def __init__(self, product_name: str, uom_prices: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Unit / Pack Size")
        n = len(uom_prices)
        # Width 460, height: header 110 + 80px per option + 60 cancel
        self.setFixedSize(460, min(110 + n * 82 + 60, 580))
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{
                background: {WHITE};
                font-family: 'Segoe UI', sans-serif;
            }}
        """)
        self.selected_uom   = None
        self.selected_price = None
        self._build(product_name, uom_prices)

    def _build(self, product_name: str, uom_prices: list[dict]):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setStyleSheet(f"background:{NAVY}; border-radius:10px;")
        hdr_layout = QVBoxLayout(hdr)
        hdr_layout.setContentsMargins(16, 12, 16, 12)
        hdr_layout.setSpacing(2)

        lbl_prompt = QLabel("Select unit / pack size")
        lbl_prompt.setStyleSheet(
            "color:rgba(255,255,255,0.7); font-size:11px; "
            "font-weight:500; background:transparent;"
        )
        lbl_name = QLabel(product_name)
        lbl_name.setStyleSheet(
            "color:#ffffff; font-size:15px; font-weight:bold; background:transparent;"
        )
        lbl_name.setWordWrap(True)
        hdr_layout.addWidget(lbl_prompt)
        hdr_layout.addWidget(lbl_name)
        root.addWidget(hdr)
        root.addSpacing(14)

        # ── UOM buttons ───────────────────────────────────────────────
        for i, up in enumerate(uom_prices):
            uom   = str(up.get("uom",   "Nos")).strip()
            price = float(up.get("price", 0))

            btn = QPushButton()
            btn.setFixedHeight(70)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)

            # Build button content as two lines via rich-ish layout inside
            btn_layout = QHBoxLayout(btn)
            btn_layout.setContentsMargins(18, 0, 18, 0)

            uom_lbl = QLabel(uom)
            uom_lbl.setStyleSheet(
                f"color:{DARK_TEXT}; font-size:16px; font-weight:bold; "
                "background:transparent;"
            )
            price_lbl = QLabel(f"${price:.2f}")
            price_lbl.setStyleSheet(
                f"color:{ACCENT}; font-size:18px; font-weight:bold; "
                "background:transparent;"
            )
            price_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            btn_layout.addWidget(uom_lbl, 1)
            btn_layout.addWidget(price_lbl)

            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {LIGHT};
                    border: 2px solid {BORDER};
                    border-radius: 10px;
                }}
                QPushButton:hover {{
                    background: {ACCENT};
                    border-color: {ACCENT};
                }}
                QPushButton:hover QLabel {{
                    color: white;
                }}
                QPushButton:pressed {{
                    background: {NAVY};
                    border-color: {NAVY};
                }}
            """)
            btn.clicked.connect(lambda _, u=uom, pr=price: self._pick(u, pr))
            root.addWidget(btn)
            if i < len(uom_prices) - 1:
                root.addSpacing(8)

        root.addSpacing(14)

        # ── Cancel ────────────────────────────────────────────────────
        cancel = QPushButton("✕  Cancel")
        cancel.setFixedHeight(46)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setFocusPolicy(Qt.NoFocus)
        cancel.setStyleSheet(f"""
            QPushButton {{
                background: {WHITE};
                color: {MUTED};
                border: 1px solid {BORDER};
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {LIGHT};
                color: {DARK_TEXT};
            }}
        """)
        cancel.clicked.connect(self.reject)
        root.addWidget(cancel)

    def _pick(self, uom: str, price: float):
        self.selected_uom   = uom
        self.selected_price = price
        self.accept()


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
# CUSTOMER SEARCH POPUP — Updated with Sync, Quick-Add & Database Linking
# =============================================================================
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, 
    QAbstractItemView, QMessageBox
)

class CustomerSearchPopup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_customer = None
        self.setWindowTitle("Select Customer")
        self.setMinimumSize(950, 550) 
        self.setModal(True)
        # Force the dialog background to the WHITE variable
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(20, 16, 20, 16)

        # --- Header ---
        hdr = QWidget()
        hdr.setFixedHeight(44)
        hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        
        title_lbl = QLabel("Select Customer")
        title_lbl.setStyleSheet(f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;")
        
        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(f"font-size:11px;color:{MID};background:transparent;")
        
        hl.addWidget(title_lbl)
        hl.addStretch()
        hl.addWidget(self._status_lbl)
        lay.addWidget(hdr)

        # --- Search & Quick Actions ---
        sr = QHBoxLayout()
        sr.setSpacing(8)
        
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by name, trade name or phone...")
        self._search.setFixedHeight(36)
        self._search.setStyleSheet(f"""
            QLineEdit {{ background:{WHITE}; border:2px solid {ACCENT};
                border-radius:5px; font-size:13px; padding:0 10px; color:{DARK_TEXT}; }}
        """)
        self._search.textChanged.connect(self._do_search)
        self._search.returnPressed.connect(self._pick)

        self._sync_btn = navy_btn("Sync Cloud", height=36, color=NAVY_2, hover=NAVY_3)
        self._sync_btn.clicked.connect(self._on_sync_clicked)

        # Requirement: New Customer Button
        add_btn = navy_btn("+ New", height=36, color=ACCENT, hover=ACCENT_H)
        add_btn.clicked.connect(self._quick_add_customer)

        # WALK-IN REMOVED FROM HERE
        sr.addWidget(self._search, 1)
        sr.addWidget(self._sync_btn)
        sr.addWidget(add_btn)
        lay.addLayout(sr)

        # --- Customer Table ---
        self._tbl = QTableWidget(0, 6)
        self._tbl.setHorizontalHeaderLabels(["Name", "Type", "Phone", "City", "Laybye Bal", "Total Due"])
        
        # TABLE STYLING: Fixes the 'White on White' selection issue
        self._tbl.setStyleSheet(f"""
            QTableWidget {{
                background-color: {WHITE};
                color: {DARK_TEXT};
                gridline-color: #eeeeee;
                border: 1px solid #dddddd;
            }}
            QTableWidget::item:selected {{
                background-color: {ACCENT};
                color: {WHITE};
            }}
            QHeaderView::section {{
                background-color: #f8f9fa;
                padding: 5px;
                border: 1px solid #dddddd;
                font-weight: bold;
                color: {DARK_TEXT};
            }}
        """)

        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch) 
        
        widths = {1: 80, 2: 110, 3: 100, 4: 110, 5: 110}
        for col, width in widths.items():
            hh.setSectionResizeMode(col, QHeaderView.Fixed)
            self._tbl.setColumnWidth(col, width)
            
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        
        self._tbl.doubleClicked.connect(self._pick)
        lay.addWidget(self._tbl, 1)
        
        # --- Bottom Buttons ---
        br = QHBoxLayout()
        br.setSpacing(8)
        ok_btn  = navy_btn("Select Customer", height=40, color=SUCCESS, hover=SUCCESS_H)
        cxl_btn = navy_btn("Cancel", height=40, color=DANGER, hover=DANGER_H)
        
        ok_btn.clicked.connect(self._pick)
        cxl_btn.clicked.connect(self.reject)
        
        br.addStretch()
        br.addWidget(ok_btn)
        br.addWidget(cxl_btn)
        lay.addLayout(br)

        self._load_all()

    def _on_sync_clicked(self):
        self._sync_btn.setEnabled(False)
        self._sync_btn.setText("Syncing...")
        try:
            from services.site_config import get_host_label as _ghl
            _site = _ghl()
        except RuntimeError as e:
            self._status_lbl.setText(f"Error: {e}")
            self._sync_btn.setEnabled(True)
            return
    
    
    
        self._status_lbl.setText(f"Connecting to {_site}...")
        
        try:
            from services.customer_sync_service import sync_customers
            
            class SyncThread(QThread):
                finished = Signal()
                def run(self):
                    try:
                        sync_customers()
                    except Exception as e:
                        print(f"Sync Thread Error: {e}")
                    self.finished.emit()

            self._thread = SyncThread(self)
            self._thread.finished.connect(self._on_sync_finished)
            self._thread.start()
        except (ImportError, Exception):
            self._status_lbl.setText("Error: Sync Service not found")
            self._sync_btn.setEnabled(True)

    def _on_sync_finished(self):
        self._sync_btn.setEnabled(True)
        self._sync_btn.setText("Sync Cloud")
        self._status_lbl.setText("Update Complete")
        self._load_all() 

    def _quick_add_customer(self):
        try:
            from views.dialogs.customer_dialog import QuickAddCustomerDialog
            dlg = QuickAddCustomerDialog(self)
            dlg.customer_created.connect(lambda _: self._load_all())
            dlg.exec()
        except ImportError:
            QMessageBox.warning(self, "Error", "Customer dialog module not found.")

    def _load_all(self):
        try:
            from models.customer import get_all_customers
            data = get_all_customers()
            self._populate(data)
        except Exception as e:
            print(f"Database Load Error: {e}")
            self._populate([])

    def _do_search(self, q):
        if not q.strip():
            self._load_all()
            return
        try:
            from models.customer import search_customers
            self._populate(search_customers(q))
        except Exception:
            self._populate([])

    def _populate(self, custs):
        self._tbl.setRowCount(0)
        for c in custs:
            r = self._tbl.rowCount()
            self._tbl.insertRow(r)
            
            # Text Color Guard: Ensures text is always visible (Black/Dark)
            def create_item(text):
                item = QTableWidgetItem(str(text or ""))
                item.setForeground(QColor(DARK_TEXT)) 
                return item

            # Text columns
            self._tbl.setItem(r, 0, create_item(c.get("customer_name", "")))
            self._tbl.setItem(r, 1, create_item(c.get("customer_type", "")))
            self._tbl.setItem(r, 2, create_item(c.get("custom_telephone_number", "")))
            self._tbl.setItem(r, 3, create_item(c.get("custom_city", "")))

            # Laybye Balance (Column 4)
            l_bal = float(c.get("laybye_balance") or 0.0)
            it_l = QTableWidgetItem(f"{l_bal:,.2f}")
            it_l.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # Readable Blue
            it_l.setForeground(QColor("#0044cc")) if l_bal > 0 else it_l.setForeground(QColor(DARK_TEXT))
            self._tbl.setItem(r, 4, it_l)

            # Outstanding / Total Due (Column 5)
            o_bal = float(c.get("outstanding_amount") or 0.0)
            it_o = QTableWidgetItem(f"{o_bal:,.2f}")
            it_o.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # High Contrast Red
            it_o.setForeground(QColor("#cc0000")) if o_bal > 0 else it_o.setForeground(QColor(DARK_TEXT))
            self._tbl.setItem(r, 5, it_o)

            # Store the dictionary in the first item
            self._tbl.item(r, 0).setData(Qt.UserRole, c)
            self._tbl.setRowHeight(r, 38)
        
        if self._tbl.rowCount() > 0:
            self._tbl.selectRow(0)

    def _pick(self):
        row = self._tbl.currentRow()
        if row < 0: return
        self.selected_customer = self._tbl.item(row, 0).data(Qt.UserRole)
        self.accept()

    # WALK-IN FUNCTION REMOVED FROM HERE

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_F10:
            self._quick_add_customer()
        elif e.key() in [Qt.Key_Return, Qt.Key_Enter]:
            if self._tbl.currentRow() >= 0:
                self._pick()
        else:
            super().keyPressEvent(e)

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

    # =================================================================
    # POS RULES PAGE  (#3 zero-price  #4 zero-stock  #7 pricing rules)
    # =================================================================
    def _page_pos_rules(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background:{WHITE};")
        lay = QVBoxLayout(w)
        lay.setSpacing(0); lay.setContentsMargins(36, 28, 36, 28)

        title = QLabel("POS Business Rules")
        title.setStyleSheet(
            f"font-size:18px; font-weight:bold; color:{NAVY}; background:transparent;"
        )
        lay.addWidget(title); lay.addWidget(hr()); lay.addSpacing(16)

        self._rules_checks = {}

        def _rule_row(key, label, desc, default=False):
            rw = QWidget()
            rw.setStyleSheet(
                f"background:{OFF_WHITE}; border:1px solid {BORDER}; border-radius:8px;"
            )
            rl = QHBoxLayout(rw); rl.setContentsMargins(16, 12, 16, 12); rl.setSpacing(14)
            txt = QVBoxLayout(); txt.setSpacing(2)
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"font-size:13px; font-weight:bold; color:{NAVY}; background:transparent;"
            )
            dlbl = QLabel(desc)
            dlbl.setStyleSheet(f"font-size:11px; color:{MUTED}; background:transparent;")
            dlbl.setWordWrap(True)
            txt.addWidget(lbl); txt.addWidget(dlbl)
            chk = QCheckBox()
            chk.setFixedSize(44, 24)
            chk.setStyleSheet(f"""
                QCheckBox::indicator {{ width:40px; height:20px; border-radius:10px; }}
                QCheckBox::indicator:unchecked {{ background:{BORDER}; border:none; }}
                QCheckBox::indicator:checked   {{ background:{SUCCESS}; border:none; }}
            """)
            try:
                from database.db import get_connection
                conn = get_connection(); cur = conn.cursor()
                cur.execute(
                    "SELECT setting_value FROM pos_settings WHERE setting_key=?", (key,))
                row = cur.fetchone(); conn.close()
                chk.setChecked(bool(int(row[0])) if row else default)
            except Exception:
                chk.setChecked(default)
            rl.addLayout(txt, 1); rl.addWidget(chk)
            self._rules_checks[key] = chk
            lay.addWidget(rw); lay.addSpacing(10)

        _rule_row("block_zero_price",  "Block Zero-Price Sales",
                  "Prevent adding items with a $0.00 selling price to the invoice.",
                  default=True)
        _rule_row("block_zero_stock",  "Block Zero / Negative Stock Sales",
                  "Show 'Insufficient Stock' popup and refuse to add items with no stock on hand.",
                  default=False)
        _rule_row("use_pricing_rules", "Apply Frappe Pricing Rules",
                  "Automatically apply discounts from Frappe pricing rules when adding items.",
                  default=False)

        lay.addSpacing(20)
        save_btn = navy_btn("💾  Save Rules", height=40, color=SUCCESS, hover=SUCCESS_H)
        save_btn.setFixedWidth(160)
        save_btn.clicked.connect(self._save_pos_rules)
        lay.addWidget(save_btn)
        lay.addStretch()
        return w

    def _save_pos_rules(self):
        try:
            from database.db import get_connection
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME='pos_settings'
                )
                CREATE TABLE pos_settings (
                    setting_key   NVARCHAR(80)  NOT NULL PRIMARY KEY,
                    setting_value NVARCHAR(255) NOT NULL DEFAULT '0'
                )
            """)
            for key, chk in self._rules_checks.items():
                val = "1" if chk.isChecked() else "0"
                cur.execute("""
                    MERGE pos_settings AS t
                    USING (SELECT ? AS k, ? AS v) AS s ON t.setting_key = s.k
                    WHEN MATCHED     THEN UPDATE SET setting_value = s.v
                    WHEN NOT MATCHED THEN INSERT (setting_key, setting_value)
                                          VALUES (s.k, s.v);
                """, (key, val))
            conn.commit(); conn.close()
            QMessageBox.information(self, "Saved", "POS rules saved successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save rules:\n{e}")
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
    """
    Full offline-first Add / Edit / Delete customer dialog.

    • All reads & writes go straight to the local DB (models/customer.py).
    • Clicking a row in the table loads that customer into the form for editing.
    • The action button switches between "Add Customer" (new) and "Save Changes" (edit).
    • A "New" button clears the form back to add-mode at any time.
    • Works 100 % offline — no cloud API call here.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editing_id: int | None = None   # None = add mode, int = edit mode
        self.setWindowTitle("Customers")
        self.setMinimumSize(960, 640)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        self._build()
        self._reload()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(20, 16, 20, 16)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QWidget(); hdr.setFixedHeight(44)
        hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16, 0, 16, 0)
        hl.addWidget(QLabel("Customers",
            styleSheet=f"font-size:15px;font-weight:bold;color:{WHITE};background:transparent;"))
        hl.addStretch()
        self._mode_badge = QLabel("  ➕  ADD MODE  ")
        self._mode_badge.setStyleSheet(f"""
            background:{SUCCESS}; color:{WHITE}; border-radius:10px;
            font-size:11px; font-weight:bold; padding:2px 10px;
        """)
        hl.addWidget(self._mode_badge)
        lay.addWidget(hdr)

        # ── Search bar ────────────────────────────────────────────────────────
        sr = QHBoxLayout(); sr.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by name, trade name or phone…")
        self._search.setFixedHeight(34)
        self._search.textChanged.connect(self._do_search)
        sr.addWidget(self._search)
        lay.addLayout(sr)

        # ── Table ─────────────────────────────────────────────────────────────
        self._tbl = QTableWidget(0, 6)
        self._tbl.setHorizontalHeaderLabels(
            ["Name", "Type", "Group", "Phone", "City", "Price List"])
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for ci in [1, 2, 3, 4, 5]:
            hh.setSectionResizeMode(ci, QHeaderView.Fixed)
            self._tbl.setColumnWidth(ci, 110)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tbl.setStyleSheet(_settings_table_style())
        self._tbl.cellClicked.connect(self._on_row_clicked)
        lay.addWidget(self._tbl, 1)
        lay.addWidget(hr())

        # ── Form ──────────────────────────────────────────────────────────────
        form = QGridLayout(); form.setSpacing(8)
        form.setColumnMinimumWidth(1, 260)
        form.setColumnMinimumWidth(3, 260)

        def _le(ph):
            f = QLineEdit(); f.setPlaceholderText(ph); f.setFixedHeight(32)
            return f
        def _cb():
            c = QComboBox(); c.setFixedHeight(32); return c
        def _lbl(t):
            return QLabel(t, styleSheet="background:transparent;font-size:12px;")

        self._f_name  = _le("Customer name *")
        self._f_type  = _cb(); self._f_type.addItems(["", "Individual", "Company"])
        self._f_trade = _le("Trade name")
        self._f_phone = _le("Phone")
        self._f_email = _le("Email")
        self._f_city  = _le("City")
        self._f_house = _le("House No.")
        self._f_group = _cb()
        self._f_wh    = _cb()
        self._f_cc    = _cb()
        self._f_pl    = _cb()

        fields = [
            ("Name *",        self._f_name,  0, 0), ("Type",          self._f_type,  0, 2),
            ("Trade Name",    self._f_trade, 1, 0), ("Phone",         self._f_phone, 1, 2),
            ("Email",         self._f_email, 2, 0), ("City",          self._f_city,  2, 2),
            ("House No.",     self._f_house, 3, 0), ("Group *",       self._f_group, 3, 2),
            ("Warehouse *",   self._f_wh,    4, 0), ("Cost Center *", self._f_cc,    4, 2),
            ("Price List *",  self._f_pl,    5, 0),
        ]
        for lbl_txt, widget, r, c in fields:
            form.addWidget(_lbl(lbl_txt), r, c)
            form.addWidget(widget, r, c + 1)
        lay.addLayout(form)

        # ── Bottom bar ────────────────────────────────────────────────────────
        br = QHBoxLayout(); br.setSpacing(8)
        self._status = QLabel("")
        self._status.setStyleSheet(
            f"font-size:12px; color:{DANGER}; background:transparent;")

        self._save_btn = navy_btn("Add Customer", height=34, color=SUCCESS, hover=SUCCESS_H)
        self._new_btn  = navy_btn("+ New",        height=34, color=ACCENT,  hover=ACCENT_H)
        del_btn        = navy_btn("Delete",        height=34, color=DANGER,  hover=DANGER_H)
        cls_btn        = navy_btn("Close",         height=34)

        self._save_btn.clicked.connect(self._save)
        self._new_btn.clicked.connect(self._enter_add_mode)
        del_btn.clicked.connect(self._delete)
        cls_btn.clicked.connect(self.accept)

        br.addWidget(self._status, 1)
        br.addWidget(self._new_btn)
        br.addWidget(self._save_btn)
        br.addWidget(del_btn)
        br.addWidget(cls_btn)
        lay.addLayout(br)

    # ── Data load ─────────────────────────────────────────────────────────────

    def _reload(self):
        try:
            from models.customer import get_all_customers
            custs = get_all_customers()
        except Exception:
            custs = []
        self._populate_combos()
        self._populate_table(custs)

    def _do_search(self, query):
        if not query.strip():
            self._reload(); return
        try:
            from models.customer import search_customers
            custs = search_customers(query)
        except Exception:
            custs = []
        self._populate_table(custs)

    def _populate_table(self, custs):
        self._tbl.setRowCount(0)
        for c in custs:
            r = self._tbl.rowCount(); self._tbl.insertRow(r)
            for col, val in enumerate([
                c["customer_name"], c.get("customer_type", ""),
                c.get("customer_group_name", ""), c.get("custom_telephone_number", ""),
                c.get("custom_city", ""), c.get("price_list_name", ""),
            ]):
                it = QTableWidgetItem(str(val or ""))
                it.setData(Qt.UserRole, c)
                self._tbl.setItem(r, col, it)
            self._tbl.setRowHeight(r, 32)
            # Highlight row if it matches the currently editing customer
            if self._editing_id and c.get("id") == self._editing_id:
                for col in range(6):
                    item = self._tbl.item(r, col)
                    if item:
                        item.setBackground(__import__('PySide6.QtGui', fromlist=['QColor']).QColor("#fff3cd"))

    def _populate_combos(self):
        try:
            from models.customer_group import get_all_customer_groups
            from models.warehouse      import get_all_warehouses
            from models.cost_center    import get_all_cost_centers
            from models.price_list     import get_all_price_lists
            groups = get_all_customer_groups()
            whs    = get_all_warehouses()
            ccs    = get_all_cost_centers()
            pls    = get_all_price_lists()
        except Exception:
            groups = []; whs = []; ccs = []; pls = []
        for cb in [self._f_group, self._f_wh, self._f_cc, self._f_pl]:
            cb.clear()
        for g in groups:
            self._f_group.addItem(g["name"], g["id"])
        for w in whs:
            self._f_wh.addItem(f"{w['name']} ({w.get('company_name','')})", w["id"])
        for cc in ccs:
            self._f_cc.addItem(f"{cc['name']} ({cc.get('company_name','')})", cc["id"])
        for pl in pls:
            self._f_pl.addItem(pl["name"], pl["id"])

    # ── Row click → load into form for editing ────────────────────────────────

    def _on_row_clicked(self, row, _col):
        item = self._tbl.item(row, 0)
        if not item: return
        c = item.data(Qt.UserRole)
        if not c: return
        self._editing_id = c.get("id")
        self._enter_edit_mode(c)

    def _enter_edit_mode(self, c: dict):
        """Fill the form from a customer dict and switch to Edit mode."""
        self._f_name.setText(c.get("customer_name", ""))

        # Type combo
        typ = c.get("customer_type", "")
        idx = self._f_type.findText(typ or "")
        self._f_type.setCurrentIndex(max(idx, 0))

        self._f_trade.setText(c.get("custom_trade_name", ""))
        self._f_phone.setText(c.get("custom_telephone_number", ""))
        self._f_email.setText(c.get("custom_email_address", ""))
        self._f_city.setText(c.get("custom_city", ""))
        self._f_house.setText(c.get("custom_house_no", ""))

        # Combo fields — match by stored ID
        def _set_combo(cb, id_val):
            for i in range(cb.count()):
                if cb.itemData(i) == id_val:
                    cb.setCurrentIndex(i); return

        _set_combo(self._f_group, c.get("customer_group_id"))
        _set_combo(self._f_wh,    c.get("custom_warehouse_id"))
        _set_combo(self._f_cc,    c.get("custom_cost_center_id"))
        _set_combo(self._f_pl,    c.get("default_price_list_id"))

        # Update UI chrome
        self._save_btn.setText("💾  Save Changes")
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color:{ACCENT}; color:{WHITE}; border:none;
                border-radius:5px; font-size:12px; font-weight:bold; padding:0 14px;
            }}
            QPushButton:hover   {{ background-color:{ACCENT_H}; }}
            QPushButton:pressed {{ background-color:{NAVY_3}; }}
        """)
        self._mode_badge.setText("  ✏️  EDIT MODE  ")
        self._mode_badge.setStyleSheet(f"""
            background:{ACCENT}; color:{WHITE}; border-radius:10px;
            font-size:11px; font-weight:bold; padding:2px 10px;
        """)
        self._set_status(f"Editing: {c.get('customer_name','')}", color=ACCENT)

    def _enter_add_mode(self):
        """Clear form and switch to Add mode."""
        self._editing_id = None
        for f in [self._f_name, self._f_trade, self._f_phone,
                  self._f_email, self._f_city, self._f_house]:
            f.clear()
        self._f_type.setCurrentIndex(0)
        self._save_btn.setText("Add Customer")
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color:{SUCCESS}; color:{WHITE}; border:none;
                border-radius:5px; font-size:12px; font-weight:bold; padding:0 14px;
            }}
            QPushButton:hover   {{ background-color:{SUCCESS_H}; }}
            QPushButton:pressed {{ background-color:{NAVY_3}; }}
        """)
        self._mode_badge.setText("  ➕  ADD MODE  ")
        self._mode_badge.setStyleSheet(f"""
            background:{SUCCESS}; color:{WHITE}; border-radius:10px;
            font-size:11px; font-weight:bold; padding:2px 10px;
        """)
        self._set_status("")
        self._tbl.clearSelection()
        self._f_name.setFocus()

    # ── Status helper ─────────────────────────────────────────────────────────

    def _set_status(self, msg, color=DANGER):
        self._status.setText(msg)
        self._status.setStyleSheet(
            f"font-size:12px; color:{color}; background:transparent;")

    # ── Save (Add or Update) ──────────────────────────────────────────────────

    def _save(self):
        name = self._f_name.text().strip()
        if not name:
            self._set_status("Customer name is required."); return

        gid  = self._f_group.currentData()
        wid  = self._f_wh.currentData()
        ccid = self._f_cc.currentData()
        plid = self._f_pl.currentData()
        if not all([gid, wid, ccid, plid]):
            self._set_status("Group, Warehouse, Cost Center and Price List are required.")
            return

        kwargs = dict(
            customer_type           = self._f_type.currentText() or None,
            custom_trade_name       = self._f_trade.text().strip(),
            custom_telephone_number = self._f_phone.text().strip(),
            custom_email_address    = self._f_email.text().strip(),
            custom_city             = self._f_city.text().strip(),
            custom_house_no         = self._f_house.text().strip(),
        )

        try:
            if self._editing_id:
                # ── Update existing ──────────────────────────────────────────
                from models.customer import update_customer
                update_customer(
                    self._editing_id,
                    customer_name         = name,
                    customer_group_id     = gid,
                    custom_warehouse_id   = wid,
                    custom_cost_center_id = ccid,
                    default_price_list_id = plid,
                    **kwargs,
                )
                self._set_status(f"'{name}' updated successfully.", color=SUCCESS)
            else:
                # ── Insert new ───────────────────────────────────────────────
                from models.customer import create_customer
                create_customer(
                    customer_name         = name,
                    customer_group_id     = gid,
                    custom_warehouse_id   = wid,
                    custom_cost_center_id = ccid,
                    default_price_list_id = plid,
                    **kwargs,
                )
                self._set_status(f"Customer '{name}' added.", color=SUCCESS)

            self._reload()
            self._enter_add_mode()

        except Exception as e:
            self._set_status(_friendly_db_error(e))

    # ── Delete ────────────────────────────────────────────────────────────────

    def _delete(self):
        row = self._tbl.currentRow()
        if row < 0:
            self._set_status("Select a customer from the list first."); return
        c = self._tbl.item(row, 0).data(Qt.UserRole)
        if QMessageBox.question(
            self, "Delete Customer",
            f"Permanently delete '{c['customer_name']}'?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        try:
            from models.customer import delete_customer
            delete_customer(c["id"])
            self._enter_add_mode()
            self._reload()
            self._set_status("Customer deleted.", color=SUCCESS)
        except Exception as e:
            self._set_status(_friendly_db_error(e))

    # ── Keyboard shortcut ─────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._save()
        elif event.key() == Qt.Key_Escape:
            if self._editing_id:
                self._enter_add_mode()
            else:
                self.accept()
        else:
            super().keyPressEvent(event)


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
    """
    Full user management dialog.
    - Lists all local + Frappe-synced users with full details
    - Add new local user (username / password / PIN / role)
    - Select any row → edit panel fills with their data
    - Edit username, password, PIN, role, active status
    - Delete user (cannot delete yourself)
    """

    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.current_user = current_user or {}
        self._editing_id  = None          # id of the user currently loaded in edit panel
        self.setWindowTitle("Manage Users")
        self.setMinimumSize(900, 620)
        self.setStyleSheet(f"QDialog {{ background-color: {OFF_WHITE}; }}")
        self._build()
        self._reload()

    # ─────────────────────────────────────────────────────────────
    def _build(self):
        self.setMinimumSize(1100, 680)
        root = QVBoxLayout(self)
        root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)

        # ── Header bar ────────────────────────────────────────────────────────
        hdr = QWidget(); hdr.setFixedHeight(58)
        hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(24, 0, 20, 0); hl.setSpacing(12)
        icon_lbl = QLabel("👥"); icon_lbl.setStyleSheet("font-size:22px; background:transparent;")
        title_lbl = QLabel("Manage Users")
        title_lbl.setStyleSheet(f"font-size:18px; font-weight:bold; color:{WHITE}; background:transparent;")
        sub_lbl = QLabel("Add · Edit · Delete · Assign roles, PINs & permissions")
        sub_lbl.setStyleSheet(f"font-size:11px; color:{MID}; background:transparent;")
        hl.addWidget(icon_lbl); hl.addWidget(title_lbl); hl.addSpacing(8)
        hl.addWidget(sub_lbl); hl.addStretch()
        close_x = QPushButton("✕"); close_x.setFixedSize(34, 34)
        close_x.setCursor(Qt.PointingHandCursor)
        close_x.setStyleSheet(f"""
            QPushButton {{ background:rgba(255,255,255,0.12); color:{WHITE};
                border:1px solid rgba(255,255,255,0.2); border-radius:6px;
                font-size:15px; font-weight:bold; }}
            QPushButton:hover {{ background:{DANGER}; border-color:{DANGER}; }}
        """)
        close_x.clicked.connect(self.accept)
        hl.addWidget(close_x)
        root.addWidget(hdr)

        # ── Body ──────────────────────────────────────────────────────────────
        body = QWidget(); body.setStyleSheet(f"background:{OFF_WHITE};")
        bl = QHBoxLayout(body); bl.setSpacing(0); bl.setContentsMargins(0, 0, 0, 0)

        # ── LEFT: user list ───────────────────────────────────────────────────
        left = QWidget()
        left.setStyleSheet(f"background:{WHITE}; border-right:1px solid {BORDER};")
        ll = QVBoxLayout(left); ll.setSpacing(0); ll.setContentsMargins(0, 0, 0, 0)

        # Search / toolbar strip
        toolbar = QWidget(); toolbar.setFixedHeight(52)
        toolbar.setStyleSheet(f"background:{WHITE}; border-bottom:1px solid {BORDER};")
        tl = QHBoxLayout(toolbar); tl.setContentsMargins(16, 0, 16, 0); tl.setSpacing(10)
        lbl_all = QLabel("All Users")
        lbl_all.setStyleSheet(f"font-size:14px; font-weight:bold; color:{NAVY}; background:transparent;")
        tl.addWidget(lbl_all); tl.addStretch()
        self._del_btn = QPushButton("🗑  Delete User")
        self._del_btn.setFixedHeight(32); self._del_btn.setCursor(Qt.PointingHandCursor)
        self._del_btn.setEnabled(False)
        self._del_btn.setStyleSheet(f"""
            QPushButton {{ background:{DANGER}14; color:{DANGER}; border:1px solid {DANGER}44;
                border-radius:6px; font-size:12px; font-weight:bold; padding:0 14px; }}
            QPushButton:hover {{ background:{DANGER}; color:{WHITE}; }}
            QPushButton:disabled {{ background:{LIGHT}; color:{BORDER}; border-color:{BORDER}; }}
        """)
        self._del_btn.clicked.connect(self._delete_user)
        tl.addWidget(self._del_btn)
        ll.addWidget(toolbar)

        # Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "Email", "Role", "PIN", "Source"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed); self.table.setColumnWidth(2, 90)
        hh.setSectionResizeMode(3, QHeaderView.Fixed); self.table.setColumnWidth(3, 60)
        hh.setSectionResizeMode(4, QHeaderView.Fixed); self.table.setColumnWidth(4, 80)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background:{WHITE}; border:none; outline:none;
                font-size:13px; gridline-color:transparent;
            }}
            QTableWidget::item {{
                padding:0 14px; border-bottom:1px solid {LIGHT};
                color:{NAVY};
            }}
            QTableWidget::item:selected {{
                background:{ACCENT}14; color:{NAVY};
                border-left:3px solid {ACCENT};
            }}
            QTableWidget::item:alternate {{ background:{OFF_WHITE}; }}
            QHeaderView::section {{
                background:{OFF_WHITE}; color:{MUTED};
                padding:10px 14px; border:none;
                border-bottom:2px solid {BORDER};
                font-size:10px; font-weight:bold;
                letter-spacing:0.8px; text-transform:uppercase;
            }}
        """)
        self.table.cellClicked.connect(self._on_row_click)
        ll.addWidget(self.table, 1)
        bl.addWidget(left, 3)

        # ── RIGHT: form panel ─────────────────────────────────────────────────
        right = QWidget(); right.setFixedWidth(380)
        right.setStyleSheet(f"background:{OFF_WHITE};")
        right_outer = QVBoxLayout(right)
        right_outer.setSpacing(0); right_outer.setContentsMargins(0, 0, 0, 0)

        # Panel header
        ph = QWidget(); ph.setFixedHeight(52)
        ph.setStyleSheet(f"background:{WHITE}; border-bottom:1px solid {BORDER};")
        phl = QHBoxLayout(ph); phl.setContentsMargins(20, 0, 20, 0)
        self._panel_title = QLabel("Add New User")
        self._panel_title.setStyleSheet(
            f"font-size:14px; font-weight:bold; color:{NAVY}; background:transparent;")
        phl.addWidget(self._panel_title); phl.addStretch()
        right_outer.addWidget(ph)

        # Scrollable form area
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet(f"QScrollArea {{ background:{OFF_WHITE}; border:none; }}")

        form_w = QWidget(); form_w.setStyleSheet(f"background:{OFF_WHITE};")
        rl = QVBoxLayout(form_w); rl.setSpacing(16); rl.setContentsMargins(20, 20, 20, 20)

        # ── Helper: card section ───────────────────────────────────────────
        def _section_card(title):
            card = QWidget()
            card.setStyleSheet(f"""
                QWidget {{
                    background:{WHITE};
                    border:1px solid {BORDER};
                    border-radius:10px;
                }}
            """)
            cl = QVBoxLayout(card); cl.setSpacing(12); cl.setContentsMargins(18, 14, 18, 18)
            sec_lbl = QLabel(title)
            sec_lbl.setStyleSheet(
                f"font-size:10px; font-weight:bold; color:{MUTED}; background:transparent;"
                f" letter-spacing:1px; border:none;")
            cl.addWidget(sec_lbl)
            return card, cl

        # ── Helper: inline field ───────────────────────────────────────────
        def _field(label, placeholder, echo=False):
            wrap = QWidget(); wrap.setStyleSheet("background:transparent;")
            wl = QVBoxLayout(wrap); wl.setSpacing(4); wl.setContentsMargins(0,0,0,0)
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"font-size:11px; font-weight:bold; color:{MUTED}; background:transparent; border:none;")
            inp = QLineEdit(); inp.setPlaceholderText(placeholder); inp.setFixedHeight(36)
            if echo: inp.setEchoMode(QLineEdit.Password)
            inp.setStyleSheet(f"""
                QLineEdit {{
                    background:{OFF_WHITE}; color:{NAVY};
                    border:1px solid {BORDER}; border-radius:7px;
                    font-size:13px; padding:0 12px;
                }}
                QLineEdit:focus {{ border:2px solid {ACCENT}; background:{WHITE}; }}
            """)
            wl.addWidget(lbl); wl.addWidget(inp)
            return wrap, inp

        # ── Helper: combo field ────────────────────────────────────────────
        def _combo_field(label, items):
            wrap = QWidget(); wrap.setStyleSheet("background:transparent;")
            wl = QVBoxLayout(wrap); wl.setSpacing(4); wl.setContentsMargins(0,0,0,0)
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"font-size:11px; font-weight:bold; color:{MUTED}; background:transparent; border:none;")
            cb = QComboBox(); cb.addItems(items); cb.setFixedHeight(36)
            cb.setStyleSheet(f"""
                QComboBox {{
                    background:{OFF_WHITE}; color:{NAVY};
                    border:1px solid {BORDER}; border-radius:7px;
                    font-size:13px; padding:0 12px;
                }}
                QComboBox:focus {{ border:2px solid {ACCENT}; }}
                QComboBox::drop-down {{ border:none; width:24px; }}
                QComboBox QAbstractItemView {{
                    background:{WHITE}; border:1px solid {BORDER};
                    selection-background-color:{ACCENT}; selection-color:{WHITE};
                }}
            """)
            wl.addWidget(lbl); wl.addWidget(cb)
            return wrap, cb

        # ── Card 1: Identity ───────────────────────────────────────────────
        c1, c1l = _section_card("IDENTITY")
        w_fn, self._f_fullname = _field("Full Name", "Full name")
        w_un, self._f_username = _field("Username *", "e.g. john.doe")
        w_em, self._f_email    = _field("Email", "user@example.com")
        c1l.addWidget(w_fn); c1l.addWidget(w_un); c1l.addWidget(w_em)
        rl.addWidget(c1)

        # ── Card 2: Security ───────────────────────────────────────────────
        c2, c2l = _section_card("SECURITY")
        # Password row with eye toggle
        pw_wrap = QWidget(); pw_wrap.setStyleSheet("background:transparent;")
        pwl = QVBoxLayout(pw_wrap); pwl.setSpacing(4); pwl.setContentsMargins(0,0,0,0)
        pw_lbl = QLabel("Password *")
        pw_lbl.setStyleSheet(
            f"font-size:11px; font-weight:bold; color:{MUTED}; background:transparent; border:none;")
        pw_inp_row = QWidget(); pw_inp_row.setStyleSheet("background:transparent;")
        pw_ir = QHBoxLayout(pw_inp_row); pw_ir.setSpacing(6); pw_ir.setContentsMargins(0,0,0,0)
        self._f_password = QLineEdit()
        self._f_password.setPlaceholderText("Leave blank to keep existing")
        self._f_password.setFixedHeight(36)
        self._f_password.setEchoMode(QLineEdit.Password)
        self._f_password.setStyleSheet(f"""
            QLineEdit {{
                background:{OFF_WHITE}; color:{NAVY};
                border:1px solid {BORDER}; border-radius:7px;
                font-size:13px; padding:0 12px;
            }}
            QLineEdit:focus {{ border:2px solid {ACCENT}; background:{WHITE}; }}
        """)
        eye_btn = QPushButton("👁"); eye_btn.setFixedSize(36, 36)
        eye_btn.setCursor(Qt.PointingHandCursor); eye_btn.setCheckable(True)
        eye_btn.setStyleSheet(f"""
            QPushButton {{ background:{OFF_WHITE}; border:1px solid {BORDER};
                border-radius:7px; font-size:14px; }}
            QPushButton:checked {{ background:{ACCENT}14; border-color:{ACCENT}; }}
        """)
        eye_btn.toggled.connect(
            lambda c, f=self._f_password:
            f.setEchoMode(QLineEdit.Normal if c else QLineEdit.Password))
        pw_ir.addWidget(self._f_password, 1); pw_ir.addWidget(eye_btn)
        pwl.addWidget(pw_lbl); pwl.addWidget(pw_inp_row)
        c2l.addWidget(pw_wrap)

        w_pi, self._f_pin = _field("PIN", "4–6 digit PIN for quick login")
        c2l.addWidget(w_pi)

        # Two-column row for Role + Active
        row2 = QWidget(); row2.setStyleSheet("background:transparent;")
        row2l = QHBoxLayout(row2); row2l.setSpacing(10); row2l.setContentsMargins(0,0,0,0)
        w_rl, self._f_role   = _combo_field("Role *",  ["cashier", "admin"])
        w_ac, self._f_active = _combo_field("Active",  ["Yes", "No"])
        row2l.addWidget(w_rl, 1); row2l.addWidget(w_ac, 1)
        c2l.addWidget(row2)
        rl.addWidget(c2)

        # ── Card 3: Assignment ─────────────────────────────────────────────
        c3, c3l = _section_card("ASSIGNMENT")
        row3 = QWidget(); row3.setStyleSheet("background:transparent;")
        row3l = QHBoxLayout(row3); row3l.setSpacing(10); row3l.setContentsMargins(0,0,0,0)
        w_cc, self._f_cost   = _field("Cost Centre", "e.g. Main - HQ")
        w_wh, self._f_whouse = _field("Warehouse",   "e.g. Stores - HQ")
        row3l.addWidget(w_cc, 1); row3l.addWidget(w_wh, 1)
        c3l.addWidget(row3)
        rl.addWidget(c3)

        # ── Card 4: Permissions ────────────────────────────────────────────
        c4, c4l = _section_card("PERMISSIONS")

        def _perm_row(label, desc):
            rw = QWidget(); rw.setStyleSheet("background:transparent;")
            rwl = QHBoxLayout(rw); rwl.setContentsMargins(0,4,0,4); rwl.setSpacing(12)
            txt = QVBoxLayout(); txt.setSpacing(1)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"font-size:13px; color:{NAVY}; background:transparent; border:none;")
            dlbl = QLabel(desc)
            dlbl.setStyleSheet(f"font-size:10px; color:{MUTED}; background:transparent; border:none;")
            txt.addWidget(lbl); txt.addWidget(dlbl)
            chk = QCheckBox(); chk.setChecked(True)
            chk.setStyleSheet(f"""
                QCheckBox::indicator {{
                    width:40px; height:22px; border-radius:11px;
                    border:2px solid {BORDER};
                    background:{BORDER};
                }}
                QCheckBox::indicator:checked {{
                    background:{SUCCESS};
                    border-color:{SUCCESS};
                }}
            """)
            rwl.addLayout(txt, 1); rwl.addWidget(chk)
            return rw, chk

        rw1, self._perm_discount = _perm_row("Allow Discounts",    "Can type in the Disc.% column")
        rw2, self._perm_receipt  = _perm_row("Allow Print Receipt", "Can finalise payment / print receipt")
        rw3, self._perm_cn       = _perm_row("Allow Credit Notes",  "Can open Return / Credit Note flow")
        rw4, self._perm_reprint  = _perm_row("Allow Reprint",       "Can reprint past invoices")
        for rw in [rw1, rw2, rw3, rw4]:
            c4l.addWidget(rw)
        rl.addWidget(c4)

        rl.addStretch()
        scroll_area.setWidget(form_w)
        right_outer.addWidget(scroll_area, 1)

        # ── Footer buttons ─────────────────────────────────────────────────
        footer = QWidget(); footer.setFixedHeight(62)
        footer.setStyleSheet(
            f"background:{WHITE}; border-top:1px solid {BORDER};")
        fl = QHBoxLayout(footer); fl.setContentsMargins(20, 0, 20, 0); fl.setSpacing(10)

        self._clear_btn = QPushButton("＋  New User")
        self._clear_btn.setFixedHeight(38); self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.setStyleSheet(f"""
            QPushButton {{ background:{OFF_WHITE}; color:{NAVY};
                border:1px solid {BORDER}; border-radius:8px;
                font-size:13px; font-weight:bold; padding:0 16px; }}
            QPushButton:hover {{ background:{LIGHT}; }}
        """)
        self._clear_btn.clicked.connect(self._clear_form)

        self._save_btn = QPushButton("💾  Save User")
        self._save_btn.setFixedHeight(38); self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.setStyleSheet(f"""
            QPushButton {{ background:{SUCCESS}; color:{WHITE};
                border:none; border-radius:8px;
                font-size:13px; font-weight:bold; padding:0 20px; }}
            QPushButton:hover {{ background:{SUCCESS_H}; }}
        """)
        self._save_btn.clicked.connect(self._save_user)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            f"font-size:11px; background:transparent; color:{SUCCESS}; border:none;")

        fl.addWidget(self._status, 1)
        fl.addWidget(self._clear_btn); fl.addWidget(self._save_btn)
        right_outer.addWidget(footer)

        bl.addWidget(right, 0)
        root.addWidget(body, 1)

    # ─────────────────────────────────────────────────────────────
    def _reload(self):
        self.table.setRowCount(0)
        try:
            from models.user import get_all_users
            users = get_all_users()
        except Exception:
            users = []
        for u in users:
            r = self.table.rowCount(); self.table.insertRow(r)
            name_disp  = u.get("full_name") or u.get("username") or ""
            email_disp = u.get("email") or u.get("frappe_user") or ""
            role   = u.get("role", "cashier")
            pin    = u.get("pin") or "—"
            src    = "☁ Frappe" if u.get("synced_from_frappe") else "Local"
            active = u.get("active", True)

            # cols: Name, Email, Role, PIN, Source
            vals = [name_disp, email_disp, role.capitalize(), pin, src]
            aligns = [
                Qt.AlignLeft | Qt.AlignVCenter,
                Qt.AlignLeft | Qt.AlignVCenter,
                Qt.AlignCenter, Qt.AlignCenter, Qt.AlignCenter,
            ]
            for c, (val, align) in enumerate(zip(vals, aligns)):
                it = QTableWidgetItem(val)
                it.setTextAlignment(align)
                if c == 2:  # Role
                    it.setForeground(QColor(ACCENT if role == "admin" else MUTED))
                    it.setFont(__import__("PySide6.QtGui", fromlist=["QFont"]).QFont(
                        "Segoe UI", 11, 75 if role == "admin" else 50))
                if not active:
                    it.setForeground(QColor(BORDER))
                it.setData(Qt.UserRole, u)
                self.table.setItem(r, c, it)
            self.table.setRowHeight(r, 46)

    def _on_row_click(self, row, _col):
        item = self.table.item(row, 0)
        if not item: return
        u = item.data(Qt.UserRole)
        if not u: return
        self._editing_id = u.get("id")
        self._del_btn.setEnabled(True)
        self._panel_title.setText(f"Edit: {u.get('full_name') or u.get('username','')}")

        self._f_fullname.setText(u.get("full_name") or "")
        self._f_username.setText(u.get("username")  or "")
        self._f_email.setText(u.get("email")         or "")
        self._f_password.clear()   # never pre-fill password
        self._f_password.setPlaceholderText("Leave blank to keep existing")
        self._f_pin.setText(u.get("pin") or "")
        self._f_cost.setText(u.get("cost_center") or "")
        self._f_whouse.setText(u.get("warehouse") or "")
        role = (u.get("role") or "cashier").lower()
        self._f_role.setCurrentIndex(0 if role == "cashier" else 1)
        self._f_active.setCurrentIndex(0 if u.get("active", True) else 1)
        # #23 — load permission flags (default True if column missing)
        self._perm_discount.setChecked(bool(u.get("allow_discount",  True)))
        self._perm_receipt.setChecked( bool(u.get("allow_receipt",   True)))
        self._perm_cn.setChecked(      bool(u.get("allow_credit_note",True)))
        self._perm_reprint.setChecked( bool(u.get("allow_reprint",   True)))

    def _clear_form(self):
        self._editing_id = None
        self._del_btn.setEnabled(False)
        self._panel_title.setText("Add New User")
        for w in [self._f_fullname, self._f_username, self._f_email,
                  self._f_password, self._f_pin, self._f_cost, self._f_whouse]:
            w.clear()
        self._f_password.setPlaceholderText("Password *")
        self._f_role.setCurrentIndex(0)
        self._f_active.setCurrentIndex(0)
        self.table.clearSelection()

    def _save_user(self):
        username = self._f_username.text().strip()
        password = self._f_password.text().strip()
        full_name = self._f_fullname.text().strip()
        email    = self._f_email.text().strip()
        pin      = self._f_pin.text().strip()
        cost     = self._f_cost.text().strip()
        whouse   = self._f_whouse.text().strip()
        role     = self._f_role.currentText()
        active   = self._f_active.currentIndex() == 0
        perm_discount = int(self._perm_discount.isChecked())
        perm_receipt  = int(self._perm_receipt.isChecked())
        perm_cn       = int(self._perm_cn.isChecked())
        perm_reprint  = int(self._perm_reprint.isChecked())

        if not username:
            self._show_status("Username is required.", error=True); return

        try:
            if self._editing_id is None:
                # ── CREATE new user ───────────────────────────────
                if not password:
                    self._show_status("Password is required for a new user.", error=True); return
                from models.user import create_user
                user = create_user(
                    username=username, password=password, role=role,
                    email=email, full_name=full_name, pin=pin,
                    cost_center=cost, warehouse=whouse,
                )
                if user:
                    self._clear_form(); self._reload()
                    self._show_status(f"User '{username}' created.")
                else:
                    self._show_status(f"Username '{username}' already exists.", error=True)
            else:
                # ── UPDATE existing user ──────────────────────────
                conn = None
                try:
                    from database.db import get_connection
                    conn = get_connection(); cur = conn.cursor()

                    # Auto-add permission columns — each ALTER must be committed
                    # separately before the UPDATE runs (SQL Server requirement)
                    for col in ["allow_discount", "allow_receipt",
                                "allow_credit_note", "allow_reprint"]:
                        try:
                            cur.execute(f"""
                                IF NOT EXISTS (
                                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                                    WHERE TABLE_NAME='users' AND COLUMN_NAME='{col}'
                                )
                                ALTER TABLE users ADD {col} BIT NOT NULL DEFAULT 1
                            """)
                            conn.commit()
                        except Exception:
                            pass

                    # Update all user fields including PIN
                    cur.execute("""
                        UPDATE users SET
                            username          = ?,
                            role              = ?,
                            full_name         = ?,
                            email             = ?,
                            pin               = ?,
                            cost_center       = ?,
                            warehouse         = ?,
                            active            = ?,
                            allow_discount    = ?,
                            allow_receipt     = ?,
                            allow_credit_note = ?,
                            allow_reprint     = ?
                        WHERE id = ?
                    """, (username, role,
                          full_name or None,
                          email     or None,
                          pin       or None,
                          cost      or None,
                          whouse    or None,
                          int(active),
                          perm_discount, perm_receipt,
                          perm_cn, perm_reprint,
                          self._editing_id))

                    # Update password only if a new one was typed
                    if password:
                        import hashlib
                        hashed = hashlib.sha256(password.encode()).hexdigest()
                        cur.execute("UPDATE users SET password=? WHERE id=?",
                                    (hashed, self._editing_id))

                    conn.commit()
                finally:
                    if conn: conn.close()
                self._reload()
                self._show_status(f"User '{username}' updated.")
        except Exception as e:
            self._show_status(f"Error: {e}", error=True)

    def _delete_user(self):
        row = self.table.currentRow()
        if row < 0: self._show_status("Select a user to delete.", error=True); return
        item = self.table.item(row, 0)
        if not item: return
        u = item.data(Qt.UserRole)
        if u.get("id") == self.current_user.get("id"):
            self._show_status("You cannot delete your own account.", error=True); return
        name = u.get("full_name") or u.get("username", "")
        if QMessageBox.question(self, "Delete User",
            f"Delete user '{name}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            from models.user import delete_user
            if delete_user(u["id"]):
                self._clear_form(); self._reload()
                self._show_status(f"User '{name}' deleted.")
            else:
                self._show_status("Could not delete user.", error=True)
        except Exception as e:
            self._show_status(f"Error: {e}", error=True)

    def _show_status(self, msg, error=False):
        color = DANGER if error else SUCCESS
        self._status.setStyleSheet(f"font-size:12px; background:transparent; color:{color};")
        self._status.setText(msg)
        QTimer.singleShot(5000, lambda: self._status.setText(""))


# Alias so external files (settings_dialog.py etc.) can reference either name
UsersDialog = ManageUsersDialog


# =============================================================================
# ADMIN DASHBOARD
# =============================================================================

# class AdminDashboard(QWidget):
#     def __init__(self, parent_window=None, user=None):
#         super().__init__()
#         self.parent_window = parent_window
#         self.user = user or {}
#         self._build()
#         self._load_data()

#     def _build(self):
#         root = QVBoxLayout(self)
#         root.setSpacing(0)
#         root.setContentsMargins(0, 0, 0, 0)

#         nav = QWidget(); nav.setFixedHeight(54)
#         nav.setStyleSheet(f"background-color: {NAVY};")
#         nav_layout = QHBoxLayout(nav)
#         nav_layout.setContentsMargins(20, 8, 20, 8); nav_layout.setSpacing(12)

#         logo = QLabel("POS System")
#         logo.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {WHITE}; background: transparent; letter-spacing: 1px;")
#         nav_layout.addWidget(logo)

#         badge = QLabel("ADMIN")
#         badge.setStyleSheet(f"""
#             background-color: {ACCENT}; color: {WHITE};
#             border-radius: 4px; font-size: 10px; font-weight: bold;
#             padding: 2px 8px; letter-spacing: 1px;
#         """)
#         nav_layout.addWidget(badge); nav_layout.addStretch()

#         date_lbl = QLabel(QDate.currentDate().toString("dd MMM yyyy"))
#         date_lbl.setStyleSheet(f"font-size: 12px; color: {NAVY}; background: transparent;")
#         nav_layout.addWidget(date_lbl); nav_layout.addSpacing(16)

#         logout_btn = navy_btn("Logout", height=30, width=72, color=DANGER, hover=DANGER_H)
#         if self.parent_window:
#             logout_btn.clicked.connect(self.parent_window._logout)
#         nav_layout.addWidget(logout_btn)

#         root.addWidget(nav); root.addWidget(hr())

#         scroll = QScrollArea(); scroll.setWidgetResizable(True)
#         scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {OFF_WHITE}; }}")

#         body = QWidget(); body.setStyleSheet(f"background: {OFF_WHITE};")
#         body_layout = QVBoxLayout(body)
#         body_layout.setSpacing(20); body_layout.setContentsMargins(24, 20, 24, 24)

#         body_layout.addWidget(self._section_label("Today at a Glance"))
#         body_layout.addLayout(self._build_stats_row())

#         content_row = QHBoxLayout(); content_row.setSpacing(20)

#         left_col = QVBoxLayout(); left_col.setSpacing(12)
#         left_col.addWidget(self._section_label("Recent Sales  (Today)"))
#         left_col.addWidget(self._build_sales_table())
#         content_row.addLayout(left_col, 3)

#         right_col = QVBoxLayout(); right_col.setSpacing(12)
#         right_col.addWidget(self._section_label("Quick Actions"))
#         right_col.addWidget(self._build_quick_actions())
#         right_col.addWidget(self._section_label("Stock Alerts"))
#         right_col.addWidget(self._build_stock_alerts())
#         right_col.addStretch()
#         content_row.addLayout(right_col, 1)

#         body_layout.addLayout(content_row)
#         scroll.setWidget(body)
#         root.addWidget(scroll, 1)

#     def _section_label(self, text):
#         lbl = QLabel(text)
#         lbl.setStyleSheet(f"""
#             font-size: 13px; font-weight: bold; color: {NAVY};
#             background: transparent;
#             border-left: 3px solid {ACCENT}; padding-left: 8px;
#         """)
#         return lbl

#     def _build_stats_row(self):
#         layout = QHBoxLayout(); layout.setSpacing(14)
#         self._stat_widgets = {}

#         for key, label, initial, color in [
#             ("revenue",     "Today's Revenue",  "$0.00",    NAVY),
#             ("txn_count",   "Transactions",     "0",        ACCENT),
#             ("items_sold",  "Items Sold",        "0",        SUCCESS),
#             ("top_method",  "Top Payment",       "—",        AMBER),
#         ]:
#             card = QWidget()
#             card.setStyleSheet(f"""
#                 QWidget {{
#                     background-color: {WHITE};
#                     border: 1px solid {BORDER};
#                     border-radius: 8px;
#                     border-top: 3px solid {color};
#                 }}
#             """)
#             card.setFixedHeight(90)
#             cl = QVBoxLayout(card); cl.setContentsMargins(16, 12, 16, 12); cl.setSpacing(4)
#             lbl = QLabel(label)
#             lbl.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent; font-weight: bold; letter-spacing: 0.5px;")
#             val = QLabel(initial)
#             val.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: bold; background: transparent;")
#             cl.addWidget(lbl); cl.addWidget(val)
#             layout.addWidget(card, 1)
#             self._stat_widgets[key] = val
#         return layout

#     def _build_sales_table(self):
#         self.sales_table = QTableWidget(0, 6)
#         self.sales_table.setHorizontalHeaderLabels(["Invoice #", "Time", "Cashier", "Method", "Total", "Synced"])
#         hh = self.sales_table.horizontalHeader()
#         hh.setSectionResizeMode(0, QHeaderView.Fixed);  self.sales_table.setColumnWidth(0, 100)
#         hh.setSectionResizeMode(1, QHeaderView.Stretch)
#         hh.setSectionResizeMode(2, QHeaderView.Stretch)
#         hh.setSectionResizeMode(3, QHeaderView.Fixed);  self.sales_table.setColumnWidth(3, 90)
#         hh.setSectionResizeMode(4, QHeaderView.Fixed);  self.sales_table.setColumnWidth(4, 100)
#         hh.setSectionResizeMode(5, QHeaderView.Fixed);  self.sales_table.setColumnWidth(5, 70)
#         self.sales_table.verticalHeader().setVisible(False)
#         self.sales_table.setAlternatingRowColors(True)
#         self.sales_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
#         self.sales_table.setSelectionBehavior(QAbstractItemView.SelectRows)
#         self.sales_table.setFixedHeight(260)
#         self.sales_table.setStyleSheet(f"""
#             QTableWidget {{ background: {WHITE}; border: 1px solid {BORDER};
#                 gridline-color: {LIGHT}; outline: none; }}
#             QTableWidget::item           {{ padding: 6px 8px; }}
#             QTableWidget::item:selected  {{ background-color: {ACCENT}; color: {WHITE}; }}
#             QTableWidget::item:alternate {{ background-color: {ROW_ALT}; }}
#             QHeaderView::section {{
#                 background-color: {NAVY}; color: {WHITE};
#                 padding: 8px; border: none; border-right: 1px solid {NAVY_2};
#                 font-size: 11px; font-weight: bold;
#             }}
#         """)
#         return self.sales_table

#     def _build_quick_actions(self):
#         card = QWidget()
#         card.setStyleSheet(f"QWidget {{ background-color: {WHITE}; border: 1px solid {BORDER}; border-radius: 8px; }}")
#         cl = QVBoxLayout(card); cl.setContentsMargins(16, 14, 16, 14); cl.setSpacing(8)

#         actions = [
#             ("Sync Users",      self._open_user_sync,                 NAVY_3),
#             ("Stock File",      self._open_stock,                     NAVY),
#             ("Sales History",   self._open_sales_history,             NAVY_3),
#             ("Day Shift",       self._open_day_shift,                 NAVY_2),
#             ("Companies",       lambda: self._open_settings_at(1),    MUTED),
#             ("Customer Groups", lambda: self._open_settings_at(2),    MUTED),
#             ("Warehouses",      lambda: self._open_settings_at(3),    MUTED),
#             ("Cost Centers",    lambda: self._open_settings_at(4),    MUTED),
#             ("Price Lists",     lambda: self._open_settings_at(5),    MUTED),
#             ("Customers",       lambda: self._open_settings_at(6),    MUTED),
#             ("Refresh Data",    self._load_data,                      SUCCESS),
#         ]
#         for label, handler, color in actions:
#             btn = QPushButton(label)
#             btn.setFixedHeight(38)
#             btn.setCursor(Qt.PointingHandCursor)
#             btn.setStyleSheet(f"""
#                 QPushButton {{
#                     background-color: {color}14; color: {color};
#                     border: 1px solid {color}44; border-radius: 5px;
#                     font-size: 13px; font-weight: bold;
#                     text-align: left; padding: 0 14px;
#                 }}
#                 QPushButton:hover {{ background-color: {color}; color: {WHITE}; border-color: {color}; }}
#             """)
#             btn.clicked.connect(handler)
#             cl.addWidget(btn)
#         return card

#     def _build_stock_alerts(self):
#         self._stock_alert_widget = QWidget()
#         self._stock_alert_widget.setStyleSheet(f"QWidget {{ background-color: {WHITE}; border: 1px solid {BORDER}; border-radius: 8px; }}")
#         self._stock_alert_layout = QVBoxLayout(self._stock_alert_widget)
#         self._stock_alert_layout.setContentsMargins(14, 12, 14, 12); self._stock_alert_layout.setSpacing(6)
#         lbl = QLabel("No low-stock alerts"); lbl.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
#         self._stock_alert_layout.addWidget(lbl)
#         return self._stock_alert_widget

#     def _load_data(self):
#         try:
#             from models.sale import get_today_sales, get_today_total, get_today_total_by_method
#             sales   = get_today_sales(); total = get_today_total()
#             by_meth = get_today_total_by_method()
#             top_m   = max(by_meth, key=by_meth.get) if by_meth else "—"
#             items   = sum(1 for _ in sales)
#         except Exception:
#             sales, total, top_m, items = [], 0.0, "Cash", 0

#         self._stat_widgets["revenue"].setText(f"${total:,.2f}")
#         self._stat_widgets["txn_count"].setText(str(len(sales)))
#         self._stat_widgets["items_sold"].setText(str(items))
#         self._stat_widgets["top_method"].setText(top_m)

#         self.sales_table.setRowCount(0)
#         for s in sales[:50]:
#             r = self.sales_table.rowCount(); self.sales_table.insertRow(r)
#             for c, (key, fmt) in enumerate([
#                 ("number", lambda v: f"#{v}"),
#                 ("time",   lambda v: str(v)),
#                 ("user",   lambda v: str(v)),
#                 ("method", lambda v: str(v)),
#                 ("total",  lambda v: f"${v:.2f}"),
#                 ("synced", lambda v: "✓" if v else "—"),
#             ]):
#                 raw = s.get(key, ""); text = fmt(raw)
#                 item = QTableWidgetItem(text)
#                 item.setTextAlignment(Qt.AlignCenter if c != 2 else Qt.AlignLeft | Qt.AlignVCenter)
#                 if key == "total": item.setForeground(QColor(ACCENT))
#                 elif key == "synced": item.setForeground(QColor(SUCCESS if s.get("synced") else MUTED))
#                 self.sales_table.setItem(r, c, item)
#             self.sales_table.setRowHeight(r, 34)

#         while self._stock_alert_layout.count():
#             item = self._stock_alert_layout.takeAt(0)
#             if item.widget(): item.widget().deleteLater()

#         try:
#             from models.product import get_all_products
#             low = [p for p in get_all_products() if p["stock"] <= 5]
#         except Exception:
#             low = []

#         if not low:
#             lbl = QLabel("✓  All stock levels OK"); lbl.setStyleSheet(f"color: {SUCCESS}; font-size: 12px; background: transparent;")
#             self._stock_alert_layout.addWidget(lbl)
#         else:
#             for p in low[:8]:
#                 row_w = QWidget(); row_w.setStyleSheet("background: transparent;")
#                 rh = QHBoxLayout(row_w); rh.setContentsMargins(0, 0, 0, 0)
#                 nm = QLabel(p["name"]); nm.setStyleSheet(f"color: {DARK_TEXT}; font-size: 12px; background: transparent;")
#                 st = QLabel(f"Stock: {p['stock']}"); st.setStyleSheet(f"color: {DANGER}; font-size: 12px; font-weight: bold; background: transparent;")
#                 rh.addWidget(nm, 1); rh.addWidget(st)
#                 self._stock_alert_layout.addWidget(row_w)

#     def _open_user_sync(self):
#         try:
#             from views.dialogs.user_sync_dialog import UserSyncDialog
#             UserSyncDialog(self).exec()
#         except Exception as e:
#             QMessageBox.warning(self, "Error", f"Could not open User Sync:\n{e}")

#     def _open_stock(self):
#         if _HAS_STOCK: StockFileDialog(self).exec()
#         else: coming_soon(self, "Stock File")

#     def _open_sales_history(self):
#         if _HAS_SALES_LIST: SalesListDialog(self).exec()
#         else: coming_soon(self, "Sales History")

    
#     def _open_day_shift(self):
#         """Requirement 4: Replaces generic save with Close Shift logic"""
#         # We pass the user ID for the audit trail
#         cashier_id = self.user.get("id") if self.user else None
        
#         dlg = ShiftReconciliationDialog(self, cashier_id=cashier_id)
#         if dlg.exec() == QDialog.Accepted:
#             # Shift successfully closed - Logout to ensure next cashier starts fresh
#             if self.parent_window:
#                 self.parent_window._logout()

#     def _open_settings_at(self, page_index: int = 0):
#         if _HAS_SETTINGS_DIALOG:
#             dlg = SettingsDialog(self, user=self.user)
#             dlg._switch(page_index)
#             dlg.exec()
#         else:
#             coming_soon(self, "Settings — add views/dialogs/settings_dialog.py")
# # =============================================================================
# # OPTIONS DIALOG  —  full dialog replacing the tiny QMenu popup
# # =============================================================================
"""
REPLACE the AdminDashboard class in views/main_window.py with this one.
Points #5 (Stock-on-hand at cost + selling price) and #26 (Full dashboard).

Paste this class in place of the existing AdminDashboard class.
All external method references (_open_user_sync, _open_stock, etc.) are
kept intact so nothing else breaks.
"""

# =============================================================================
# ADMIN DASHBOARD  (Points #5, #26)
# =============================================================================
class AdminDashboard(QWidget):
    def __init__(self, parent_window=None, user=None):
        super().__init__()
        self.parent_window = parent_window
        self.user = user or {}
        self._build()
        self._load_data()

    # =========================================================================
    # BUILD
    # =========================================================================

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Top navigation bar ────────────────────────────────────────────────
        nav = QWidget(); nav.setFixedHeight(54)
        nav.setStyleSheet(f"background-color: {NAVY};")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(20, 8, 20, 8); nav_layout.setSpacing(12)

        logo = QLabel("📊  POS Dashboard")
        logo.setStyleSheet(
            f"font-size:15px; font-weight:bold; color:{WHITE}; "
            "background:transparent; letter-spacing:1px;"
        )
        nav_layout.addWidget(logo)

        badge = QLabel("ADMIN")
        badge.setStyleSheet(f"""
            background-color:{ACCENT}; color:{WHITE};
            border-radius:4px; font-size:10px; font-weight:bold;
            padding:2px 8px; letter-spacing:1px;
        """)
        nav_layout.addWidget(badge)
        nav_layout.addStretch()

        self._date_lbl = QLabel(QDate.currentDate().toString("dd MMM yyyy"))
        self._date_lbl.setStyleSheet(
            f"font-size:12px; color:{MID}; background:transparent;"
        )
        nav_layout.addWidget(self._date_lbl); nav_layout.addSpacing(16)

        refresh_btn = navy_btn("🔄 Refresh", height=30, color=NAVY_2, hover=NAVY_3)
        refresh_btn.clicked.connect(self._load_data)
        nav_layout.addWidget(refresh_btn)

        pos_btn = navy_btn("← POS", height=30, color=NAVY_3, hover=NAVY_2)
        if self.parent_window:
            pos_btn.clicked.connect(self.parent_window.switch_to_pos)
        nav_layout.addWidget(pos_btn)

        logout_btn = navy_btn("Logout", height=30, width=72, color=DANGER, hover=DANGER_H)
        if self.parent_window:
            logout_btn.clicked.connect(self.parent_window._logout)
        nav_layout.addWidget(logout_btn)

        root.addWidget(nav)
        root.addWidget(hr())

        # ── Tab widget ────────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border:none; background:{OFF_WHITE};
            }}
            QTabBar::tab {{
                background:{LIGHT}; color:{NAVY};
                padding:10px 22px; font-size:13px; font-weight:bold;
                border:1px solid {BORDER}; border-bottom:none;
                margin-right:2px; border-radius:4px 4px 0 0;
            }}
            QTabBar::tab:selected {{
                background:{WHITE}; color:{ACCENT};
                border-bottom:2px solid {WHITE};
            }}
            QTabBar::tab:hover {{ background:{BORDER}; }}
        """)
        self._tabs.addTab(self._build_overview_tab(),  "📈  Overview")
        self._tabs.addTab(self._build_stock_tab(),     "📦  Stock on Hand")
        self._tabs.addTab(self._build_top_items_tab(), "🏆  Top Items")
        self._tabs.addTab(self._build_actions_tab(),   "⚙  Actions")
        root.addWidget(self._tabs, 1)

    # =========================================================================
    # TAB 1: OVERVIEW (Point #26)
    # =========================================================================

    def _build_overview_tab(self):
        w = QWidget(); w.setStyleSheet(f"background:{OFF_WHITE};")
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{OFF_WHITE}; }}")
        scroll.setWidget(w)

        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 20, 24, 20); lay.setSpacing(18)

        # ── KPI row 1: Financial ──────────────────────────────────────────────
        lay.addWidget(self._section_label("Financial Summary"))
        lay.addLayout(self._build_kpi_row_1())

        # ── KPI row 2: Stock values ───────────────────────────────────────────
        lay.addWidget(self._section_label("Stock Value Summary"))
        lay.addLayout(self._build_kpi_row_2())

        # ── Recent sales table ────────────────────────────────────────────────
        lay.addWidget(self._section_label("Recent Sales  (Today)"))
        lay.addWidget(self._build_sales_table())

        lay.addStretch()

        container = QWidget(); container.setStyleSheet(f"background:{OFF_WHITE};")
        cl = QVBoxLayout(container); cl.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(scroll, 1)
        return container

    def _build_kpi_row_1(self):
        row = QHBoxLayout(); row.setSpacing(14)
        self._kpi = {}

        for key, label, icon, color in [
            ("sales",           "Total Sales",        "💰", ACCENT),
            ("expenses",        "Expenses",           "📉", DANGER),
            ("profit",          "Gross Profit",       "📈", SUCCESS),
            ("exp_profit",      "Expected Profit",    "🎯", AMBER),
        ]:
            card, val_lbl = self._kpi_card(label, icon, "$0.00", color)
            self._kpi[key] = val_lbl
            row.addWidget(card, 1)
        return row

    def _build_kpi_row_2(self):
        row = QHBoxLayout(); row.setSpacing(14)

        for key, label, icon, color in [
            ("stock_cost",    "Stock @ Cost",      "🏭", NAVY),
            ("stock_sell",    "Stock @ Selling",   "🏷", ACCENT_H),
            ("potential",     "Potential Profit",  "💎", SUCCESS),
        ]:
            card, val_lbl = self._kpi_card(label, icon, "$0.00", color)
            self._kpi[key] = val_lbl
            row.addWidget(card, 1)
        return row

    def _kpi_card(self, label: str, icon: str, initial: str, color: str):
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background:{WHITE}; border:1px solid {BORDER};
                border-radius:8px; border-top:3px solid {color};
            }}
        """)
        card.setFixedHeight(88)
        cl = QVBoxLayout(card); cl.setContentsMargins(16, 10, 16, 10); cl.setSpacing(3)
        top = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color:{MUTED}; font-size:11px; background:transparent; "
            "font-weight:bold; letter-spacing:0.5px;"
        )
        ico = QLabel(icon)
        ico.setStyleSheet(f"font-size:18px; background:transparent;")
        top.addWidget(lbl, 1); top.addWidget(ico)
        val = QLabel(initial)
        val.setStyleSheet(
            f"color:{color}; font-size:20px; font-weight:bold; background:transparent;"
        )
        cl.addLayout(top); cl.addWidget(val)
        return card, val

    def _build_sales_table(self):
        self.sales_table = QTableWidget(0, 6)
        self.sales_table.setHorizontalHeaderLabels(
            ["Invoice #", "Date / Time", "Cashier", "Method", "Total", "Synced"]
        )
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
            QTableWidget {{ background:{WHITE}; border:1px solid {BORDER};
                gridline-color:{LIGHT}; outline:none; }}
            QTableWidget::item           {{ padding:6px 8px; }}
            QTableWidget::item:selected  {{ background-color:{ACCENT}; color:{WHITE}; }}
            QTableWidget::item:alternate {{ background-color:{ROW_ALT}; }}
            QHeaderView::section {{
                background-color:{NAVY}; color:{WHITE};
                padding:8px; border:none; border-right:1px solid {NAVY_2};
                font-size:11px; font-weight:bold;
            }}
        """)
        return self.sales_table

    # =========================================================================
    # TAB 2: STOCK ON HAND  (Point #5)
    # =========================================================================

    def _build_stock_tab(self):
        w = QWidget(); w.setStyleSheet(f"background:{OFF_WHITE};")
        lay = QVBoxLayout(w); lay.setContentsMargins(24, 16, 24, 16); lay.setSpacing(10)

        # Search row
        srch_row = QHBoxLayout()
        srch = QLineEdit()
        srch.setPlaceholderText("🔍  Filter by product name or part number…")
        srch.setFixedHeight(34)
        srch.setStyleSheet(f"""
            QLineEdit {{ background:{WHITE}; color:{DARK_TEXT};
                border:1px solid {BORDER}; border-radius:5px;
                font-size:13px; padding:0 10px; }}
            QLineEdit:focus {{ border:2px solid {ACCENT}; }}
        """)
        srch.textChanged.connect(self._filter_stock)
        self._stock_search = srch
        srch_row.addWidget(srch, 1)

        export_btn = navy_btn("📥  Export CSV", height=34, color=NAVY_2, hover=NAVY_3)
        export_btn.clicked.connect(self._export_stock_csv)
        srch_row.addWidget(export_btn)
        lay.addLayout(srch_row)

        # Totals strip
        totals_w = QWidget()
        totals_w.setStyleSheet(
            f"background:{NAVY}; border-radius:6px;"
        )
        totals_w.setFixedHeight(44)
        tl = QHBoxLayout(totals_w); tl.setContentsMargins(16, 0, 16, 0); tl.setSpacing(32)
        self._lbl_tot_cost = QLabel("Total @ Cost: $0.00")
        self._lbl_tot_sell = QLabel("Total @ Selling: $0.00")
        self._lbl_tot_prof = QLabel("Potential Profit: $0.00")
        for lbl in [self._lbl_tot_cost, self._lbl_tot_sell, self._lbl_tot_prof]:
            lbl.setStyleSheet(
                f"color:{WHITE}; font-size:13px; font-weight:bold; background:transparent;"
            )
        tl.addWidget(self._lbl_tot_cost)
        tl.addWidget(self._lbl_tot_sell)
        tl.addWidget(self._lbl_tot_prof)
        tl.addStretch()
        lay.addWidget(totals_w)

        # Stock table
        self._stock_tbl = QTableWidget(0, 7)
        self._stock_tbl.setHorizontalHeaderLabels([
            "Part No.", "Product Name", "Category",
            "Qty on Hand", "Cost Price", "Selling Price",
            "Value @ Cost", "Value @ Selling",
        ])
        # Fix — we have 7 cols but listed 8 header items — correct to match:
        self._stock_tbl.setColumnCount(8)
        hh = self._stock_tbl.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for ci, w_ in [(0, 90), (2, 100), (3, 90), (4, 100), (5, 100), (6, 110), (7, 110)]:
            hh.setSectionResizeMode(ci, QHeaderView.Fixed)
            self._stock_tbl.setColumnWidth(ci, w_)
        self._stock_tbl.verticalHeader().setVisible(False)
        self._stock_tbl.setAlternatingRowColors(True)
        self._stock_tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._stock_tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._stock_tbl.setStyleSheet(f"""
            QTableWidget {{ background:{WHITE}; border:1px solid {BORDER};
                gridline-color:{LIGHT}; outline:none; font-size:12px; }}
            QTableWidget::item           {{ padding:5px 8px; }}
            QTableWidget::item:selected  {{ background-color:{ACCENT}; color:{WHITE}; }}
            QTableWidget::item:alternate {{ background-color:{ROW_ALT}; }}
            QHeaderView::section {{
                background-color:{NAVY}; color:{WHITE};
                padding:8px; border:none; border-right:1px solid {NAVY_2};
                font-size:11px; font-weight:bold;
            }}
        """)
        lay.addWidget(self._stock_tbl, 1)

        self._stock_count_lbl = QLabel("Loading…")
        self._stock_count_lbl.setStyleSheet(
            f"color:{MUTED}; font-size:11px; background:transparent;"
        )
        lay.addWidget(self._stock_count_lbl)
        return w

    def _filter_stock(self, query: str):
        if not hasattr(self, "_all_stock"):
            return
        ql = query.lower()
        if not ql:
            self._render_stock(self._all_stock)
        else:
            self._render_stock([
                p for p in self._all_stock
                if ql in (p.get("name", "") or "").lower()
                or ql in (p.get("part_no", "") or "").lower()
                or ql in (p.get("category", "") or "").lower()
            ])

    def _render_stock(self, products: list):
        self._stock_tbl.setRowCount(0)
        tot_cost = tot_sell = 0.0
        for p in products:
            qty       = float(p.get("stock", 0) or 0)
            cost      = float(p.get("cost_price", 0) or 0)
            sell      = float(p.get("price", 0) or 0)
            val_cost  = qty * cost
            val_sell  = qty * sell
            tot_cost += val_cost
            tot_sell += val_sell

            r = self._stock_tbl.rowCount()
            self._stock_tbl.insertRow(r)
            vals = [
                p.get("part_no", ""),
                p.get("name", ""),
                p.get("category", ""),
                f"{qty:.2f}",
                f"${cost:.2f}",
                f"${sell:.2f}",
                f"${val_cost:.2f}",
                f"${val_sell:.2f}",
            ]
            alignments = [
                Qt.AlignCenter,
                Qt.AlignLeft | Qt.AlignVCenter,
                Qt.AlignCenter,
                Qt.AlignCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
            ]
            for ci, (val, aln) in enumerate(zip(vals, alignments)):
                it = QTableWidgetItem(val)
                it.setTextAlignment(aln)
                if ci == 3 and qty <= 5:
                    it.setForeground(QColor(DANGER))
                if ci == 6:
                    it.setForeground(QColor(NAVY))
                if ci == 7:
                    it.setForeground(QColor(ACCENT))
                self._stock_tbl.setItem(r, ci, it)
            self._stock_tbl.setRowHeight(r, 32)

        self._lbl_tot_cost.setText(f"Total @ Cost: ${tot_cost:,.2f}")
        self._lbl_tot_sell.setText(f"Total @ Selling: ${tot_sell:,.2f}")
        self._lbl_tot_prof.setText(f"Potential Profit: ${(tot_sell - tot_cost):,.2f}")
        n = self._stock_tbl.rowCount()
        self._stock_count_lbl.setText(f"{n} product{'s' if n != 1 else ''}")

    def _export_stock_csv(self):
        try:
            from PySide6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(
                self, "Export Stock CSV", "stock_on_hand.csv",
                "CSV Files (*.csv)"
            )
            if not path:
                return
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                headers = []
                for ci in range(self._stock_tbl.columnCount()):
                    headers.append(
                        self._stock_tbl.horizontalHeaderItem(ci).text()
                        if self._stock_tbl.horizontalHeaderItem(ci) else ""
                    )
                writer.writerow(headers)
                for r in range(self._stock_tbl.rowCount()):
                    row = []
                    for ci in range(self._stock_tbl.columnCount()):
                        it = self._stock_tbl.item(r, ci)
                        row.append(it.text() if it else "")
                    writer.writerow(row)
            QMessageBox.information(self, "Exported", f"Stock exported to:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Error", str(e))

    # =========================================================================
    # TAB 3: TOP ITEMS  (Point #26 — top 10 profitable & most sold)
    # =========================================================================

    def _build_top_items_tab(self):
        w = QWidget(); w.setStyleSheet(f"background:{OFF_WHITE};")
        lay = QHBoxLayout(w); lay.setContentsMargins(24, 16, 24, 16); lay.setSpacing(20)

        # Left: Top 10 Profitable
        left = QVBoxLayout()
        left.addWidget(self._section_label("🏆  Top 10 Most Profitable Items"))

        self._tbl_profitable = QTableWidget(0, 4)
        self._tbl_profitable.setHorizontalHeaderLabels(
            ["Product", "Qty Sold", "Avg Margin", "Total Profit"]
        )
        hh = self._tbl_profitable.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for ci, w_ in [(1, 80), (2, 90), (3, 100)]:
            hh.setSectionResizeMode(ci, QHeaderView.Fixed)
            self._tbl_profitable.setColumnWidth(ci, w_)
        self._tbl_profitable.verticalHeader().setVisible(False)
        self._tbl_profitable.setAlternatingRowColors(True)
        self._tbl_profitable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl_profitable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl_profitable.setStyleSheet(self._sub_table_style())
        left.addWidget(self._tbl_profitable, 1)
        lay.addLayout(left, 1)

        # Right: Most Sold
        right = QVBoxLayout()
        right.addWidget(self._section_label("📊  Most Sold Items"))

        self._tbl_most_sold = QTableWidget(0, 3)
        self._tbl_most_sold.setHorizontalHeaderLabels(
            ["Product", "Qty Sold", "Revenue"]
        )
        hh2 = self._tbl_most_sold.horizontalHeader()
        hh2.setSectionResizeMode(0, QHeaderView.Stretch)
        for ci, w_ in [(1, 80), (2, 100)]:
            hh2.setSectionResizeMode(ci, QHeaderView.Fixed)
            self._tbl_most_sold.setColumnWidth(ci, w_)
        self._tbl_most_sold.verticalHeader().setVisible(False)
        self._tbl_most_sold.setAlternatingRowColors(True)
        self._tbl_most_sold.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl_most_sold.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl_most_sold.setStyleSheet(self._sub_table_style())
        right.addWidget(self._tbl_most_sold, 1)
        lay.addLayout(right, 1)

        return w

    def _sub_table_style(self):
        return f"""
            QTableWidget {{ background:{WHITE}; border:1px solid {BORDER};
                gridline-color:{LIGHT}; outline:none; font-size:13px; }}
            QTableWidget::item           {{ padding:6px 8px; }}
            QTableWidget::item:selected  {{ background-color:{ACCENT}; color:{WHITE}; }}
            QTableWidget::item:alternate {{ background-color:{ROW_ALT}; }}
            QHeaderView::section {{
                background-color:{NAVY}; color:{WHITE};
                padding:8px; border:none; border-right:1px solid {NAVY_2};
                font-size:11px; font-weight:bold;
            }}
        """

    # =========================================================================
    # TAB 4: ACTIONS (unchanged from old AdminDashboard's Quick Actions)
    # =========================================================================

    def _build_actions_tab(self):
        w = QWidget(); w.setStyleSheet(f"background:{OFF_WHITE};")
        lay = QHBoxLayout(w); lay.setContentsMargins(32, 24, 32, 24); lay.setSpacing(24)

        # Left column: quick actions
        left = QVBoxLayout(); left.setSpacing(10)
        left.addWidget(self._section_label("Quick Actions"))
        left.addWidget(self._build_quick_actions())
        left.addStretch()
        lay.addLayout(left, 1)

        # Right column: stock alerts
        right = QVBoxLayout(); right.setSpacing(10)
        right.addWidget(self._section_label("Low Stock Alerts"))
        right.addWidget(self._build_stock_alerts())
        right.addStretch()
        lay.addLayout(right, 1)

        return w

    # =========================================================================
    # QUICK ACTIONS / STOCK ALERTS (kept from old AdminDashboard)
    # =========================================================================

    def _build_quick_actions(self):
        card = QWidget()
        card.setStyleSheet(
            f"QWidget {{ background-color:{WHITE}; "
            f"border:1px solid {BORDER}; border-radius:8px; }}"
        )
        cl = QVBoxLayout(card); cl.setContentsMargins(16, 14, 16, 14); cl.setSpacing(8)

        actions = [
            ("👥  Sync Users",        self._open_user_sync,              NAVY_3),
            ("📦  Stock File",         self._open_stock,                  NAVY),
            ("📜  Sales History",      self._open_sales_history,          NAVY_3),
            ("📅  Day Shift",          self._open_day_shift,              NAVY_2),
            ("🏢  Companies",          lambda: self._open_settings_at(1), MUTED),
            ("👥  Customer Groups",    lambda: self._open_settings_at(2), MUTED),
            ("🏭  Warehouses",         lambda: self._open_settings_at(3), MUTED),
            ("💰  Cost Centers",       lambda: self._open_settings_at(4), MUTED),
            ("🏷  Price Lists",        lambda: self._open_settings_at(5), MUTED),
            ("👤  Customers",          lambda: self._open_settings_at(6), MUTED),
            ("🔄  Refresh Dashboard",  self._load_data,                   SUCCESS),
        ]
        for label, handler, color in actions:
            btn = QPushButton(label)
            btn.setFixedHeight(38); btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color:{color}14; color:{color};
                    border:1px solid {color}44; border-radius:5px;
                    font-size:13px; font-weight:bold;
                    text-align:left; padding:0 14px;
                }}
                QPushButton:hover {{
                    background-color:{color}; color:{WHITE}; border-color:{color};
                }}
            """)
            btn.clicked.connect(handler)
            cl.addWidget(btn)
        return card

    def _build_stock_alerts(self):
        self._stock_alert_widget = QWidget()
        self._stock_alert_widget.setStyleSheet(
            f"QWidget {{ background-color:{WHITE}; "
            f"border:1px solid {BORDER}; border-radius:8px; }}"
        )
        self._stock_alert_layout = QVBoxLayout(self._stock_alert_widget)
        self._stock_alert_layout.setContentsMargins(14, 12, 14, 12)
        self._stock_alert_layout.setSpacing(6)
        lbl = QLabel("No low-stock alerts")
        lbl.setStyleSheet(f"color:{MUTED}; font-size:12px; background:transparent;")
        self._stock_alert_layout.addWidget(lbl)
        return self._stock_alert_widget

    # =========================================================================
    # SECTION LABEL HELPER
    # =========================================================================

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            font-size:13px; font-weight:bold; color:{NAVY};
            background:transparent;
            border-left:3px solid {ACCENT}; padding-left:8px;
        """)
        return lbl

    # =========================================================================
    # DATA LOADING  (Point #26)
    # =========================================================================

    def _load_data(self):
        self._date_lbl.setText(QDate.currentDate().toString("dd MMM yyyy"))
        self._load_financial_kpis()
        self._load_stock_data()
        self._load_top_items()
        self._load_recent_sales()
        self._load_stock_alerts()

    def _load_financial_kpis(self):
        """Point #26: total sales, expenses, profit, expected profit, stock values."""
        sales_total = expenses = cost_of_goods = 0.0
        try:
            from models.sale import get_all_sales  # type: ignore
            from database.db import get_connection  # type: ignore
            conn = get_connection(); cur = conn.cursor()

            # Total revenue
            try:
                cur.execute("SELECT COALESCE(SUM(total),0) FROM sales")
                row = cur.fetchone()
                sales_total = float(row[0] or 0)
            except Exception:
                pass

            # Expenses (from expenses/journal table if available)
            try:
                cur.execute(
                    "SELECT COALESCE(SUM(amount),0) FROM expenses "
                    "WHERE CAST(expense_date AS DATE)=CAST(GETDATE() AS DATE)"
                )
                row = cur.fetchone()
                expenses = float(row[0] or 0)
            except Exception:
                expenses = 0.0

            conn.close()
        except Exception:
            pass

        # Cost of goods sold: sum(qty * cost_price) for all sale items
        try:
            from database.db import get_connection  # type: ignore
            conn = get_connection(); cur = conn.cursor()
            try:
                cur.execute("""
                    SELECT COALESCE(
                        SUM(si.qty * COALESCE(p.cost_price, 0)), 0
                    )
                    FROM sale_items si
                    LEFT JOIN products p ON si.product_id = p.id
                """)
                row = cur.fetchone()
                cost_of_goods = float(row[0] or 0)
            except Exception:
                cost_of_goods = 0.0
            conn.close()
        except Exception:
            pass

        gross_profit   = sales_total - cost_of_goods
        net_profit     = gross_profit - expenses
        exp_profit     = gross_profit   # expected = gross if no expenses model

        # Stock value KPIs
        stock_cost = stock_sell = 0.0
        if hasattr(self, "_all_stock"):
            for p in self._all_stock:
                qty  = float(p.get("stock", 0) or 0)
                cost = float(p.get("cost_price", 0) or 0)
                sell = float(p.get("price", 0) or 0)
                stock_cost += qty * cost
                stock_sell += qty * sell

        self._kpi["sales"].setText(f"${sales_total:,.2f}")
        self._kpi["expenses"].setText(f"${expenses:,.2f}")
        self._kpi["profit"].setText(f"${net_profit:,.2f}")
        self._kpi["exp_profit"].setText(f"${exp_profit:,.2f}")
        self._kpi["stock_cost"].setText(f"${stock_cost:,.2f}")
        self._kpi["stock_sell"].setText(f"${stock_sell:,.2f}")
        self._kpi["potential"].setText(f"${(stock_sell - stock_cost):,.2f}")

        # colour profit red/green
        for key, val in [("profit", net_profit), ("exp_profit", exp_profit)]:
            color = SUCCESS if val >= 0 else DANGER
            self._kpi[key].setStyleSheet(
                f"color:{color}; font-size:20px; font-weight:bold; background:transparent;"
            )

    def _load_stock_data(self):
        """Point #5: Stock on hand table with cost and selling values."""
        try:
            from models.product import get_all_products  # type: ignore
            products = get_all_products()
        except Exception:
            products = []
        self._all_stock = products
        self._render_stock(products)

        # Update KPI stock values after stock is loaded
        self._load_financial_kpis()

    def _load_top_items(self):
        """Point #26: Top 10 profitable and most sold items."""
        # Gather from sale_items joined with products
        profitable: dict = {}    # name → {qty, revenue, cost}
        most_sold:  dict = {}    # name → {qty, revenue}

        try:
            from database.db import get_connection  # type: ignore
            conn = get_connection(); cur = conn.cursor()
            try:
                cur.execute("""
                    SELECT
                        si.product_name,
                        SUM(si.qty)                                       AS qty,
                        SUM(si.total)                                     AS revenue,
                        SUM(si.qty * COALESCE(p.cost_price, 0))          AS cost_total
                    FROM sale_items si
                    LEFT JOIN products p ON si.product_id = p.id
                    WHERE si.product_name IS NOT NULL
                    GROUP BY si.product_name
                """)
                for row in cur.fetchall():
                    name, qty, rev, cost_tot = (
                        row[0], float(row[1] or 0),
                        float(row[2] or 0), float(row[3] or 0),
                    )
                    profit = rev - cost_tot
                    margin = (profit / rev * 100) if rev else 0
                    profitable[name] = {
                        "qty": qty, "revenue": rev,
                        "cost": cost_tot, "profit": profit, "margin": margin,
                    }
                    most_sold[name] = {"qty": qty, "revenue": rev}
            except Exception:
                pass
            conn.close()
        except Exception:
            pass

        # Profitable table
        self._tbl_profitable.setRowCount(0)
        top_p = sorted(profitable.items(), key=lambda x: x[1]["profit"], reverse=True)[:10]
        for i, (name, d) in enumerate(top_p):
            r = self._tbl_profitable.rowCount()
            self._tbl_profitable.insertRow(r)
            vals = [
                f"{'🥇' if i==0 else '🥈' if i==1 else '🥉' if i==2 else f'{i+1}.'} {name}",
                f"{d['qty']:.0f}",
                f"{d['margin']:.1f}%",
                f"${d['profit']:,.2f}",
            ]
            aligns = [
                Qt.AlignLeft | Qt.AlignVCenter,
                Qt.AlignCenter,
                Qt.AlignCenter,
                Qt.AlignRight | Qt.AlignVCenter,
            ]
            for ci, (val, aln) in enumerate(zip(vals, aligns)):
                it = QTableWidgetItem(val)
                it.setTextAlignment(aln)
                if ci == 3:
                    it.setForeground(QColor(SUCCESS if d["profit"] >= 0 else DANGER))
                self._tbl_profitable.setItem(r, ci, it)
            self._tbl_profitable.setRowHeight(r, 34)

        # Most sold table
        self._tbl_most_sold.setRowCount(0)
        top_s = sorted(most_sold.items(), key=lambda x: x[1]["qty"], reverse=True)[:20]
        for i, (name, d) in enumerate(top_s):
            r = self._tbl_most_sold.rowCount()
            self._tbl_most_sold.insertRow(r)
            vals = [
                f"{'🏅' if i < 3 else f'{i+1}.'} {name}",
                f"{d['qty']:.0f}",
                f"${d['revenue']:,.2f}",
            ]
            aligns = [
                Qt.AlignLeft | Qt.AlignVCenter,
                Qt.AlignCenter,
                Qt.AlignRight | Qt.AlignVCenter,
            ]
            for ci, (val, aln) in enumerate(zip(vals, aligns)):
                it = QTableWidgetItem(val)
                it.setTextAlignment(aln)
                if ci == 2:
                    it.setForeground(QColor(ACCENT))
                self._tbl_most_sold.setItem(r, ci, it)
            self._tbl_most_sold.setRowHeight(r, 34)

    def _load_recent_sales(self):
        try:
            from models.sale import get_today_sales  # type: ignore
            sales = get_today_sales()
        except Exception:
            try:
                from models.sale import get_all_sales  # type: ignore
                sales = get_all_sales()[:50]
            except Exception:
                sales = []

        self.sales_table.setRowCount(0)
        for s in sales[:50]:
            r = self.sales_table.rowCount(); self.sales_table.insertRow(r)
            for c, (key, fmt) in enumerate([
                ("invoice_no",   lambda v: str(v)),
                ("invoice_date", lambda v: str(v)),
                ("user",         lambda v: str(v)),
                ("method",       lambda v: str(v)),
                ("total",        lambda v: f"${float(v or 0):.2f}"),
                ("synced",       lambda v: "✓" if v else "—"),
            ]):
                raw  = s.get(key, "") or s.get("number", "") or ""
                text = fmt(raw)
                item = QTableWidgetItem(text)
                item.setTextAlignment(
                    Qt.AlignCenter if c != 1 else Qt.AlignLeft | Qt.AlignVCenter
                )
                if key == "total":
                    item.setForeground(QColor(ACCENT))
                elif key == "synced":
                    item.setForeground(QColor(SUCCESS if s.get("synced") else MUTED))
                self.sales_table.setItem(r, c, item)
            self.sales_table.setRowHeight(r, 34)

    def _load_stock_alerts(self):
        while self._stock_alert_layout.count():
            it = self._stock_alert_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        try:
            from models.product import get_all_products  # type: ignore
            low = [p for p in get_all_products() if float(p.get("stock", 0) or 0) <= 5]
        except Exception:
            low = []

        if not low:
            lbl = QLabel("✓  All stock levels OK")
            lbl.setStyleSheet(f"color:{SUCCESS}; font-size:12px; background:transparent;")
            self._stock_alert_layout.addWidget(lbl)
        else:
            for p in low[:12]:
                row_w = QWidget(); row_w.setStyleSheet("background:transparent;")
                rh = QHBoxLayout(row_w); rh.setContentsMargins(0, 0, 0, 0); rh.setSpacing(8)
                nm  = QLabel(p.get("name", ""))
                nm.setStyleSheet(f"color:{DARK_TEXT}; font-size:12px; background:transparent;")
                st  = QLabel(f"Qty: {float(p.get('stock', 0) or 0):.1f}")
                st.setStyleSheet(
                    f"color:{DANGER}; font-size:12px; font-weight:bold; background:transparent;"
                )
                rh.addWidget(nm, 1); rh.addWidget(st)
                self._stock_alert_layout.addWidget(row_w)
            if len(low) > 12:
                more = QLabel(f"… and {len(low)-12} more")
                more.setStyleSheet(f"color:{MUTED}; font-size:11px; background:transparent;")
                self._stock_alert_layout.addWidget(more)

    # =========================================================================
    # ACTION HANDLERS (unchanged from original AdminDashboard)
    # =========================================================================

    def _open_user_sync(self):
        try:
            from views.dialogs.user_sync_dialog import UserSyncDialog  # type: ignore
            UserSyncDialog(self).exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open User Sync:\n{e}")

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
        cashier_id = self.user.get("id") if self.user else None
        dlg = ShiftReconciliationDialog(self, cashier_id=cashier_id)
        if dlg.exec() == QDialog.Accepted:
            if self.parent_window:
                self.parent_window._logout()

    def _open_settings_at(self, page_index: int = 0):
        if _HAS_SETTINGS_DIALOG:
            dlg = SettingsDialog(self, user=self.user)
            dlg._switch(page_index)
            dlg.exec()
        else:
            coming_soon(self, "Settings — add views/dialogs/settings_dialog.py")


class OptionsDialog(QDialog):
    """Full-size dialog shown when the cashier presses the Options button."""

    def __init__(self, parent=None, pos_view=None):
        super().__init__(parent)
        self._pos = pos_view
        self.setWindowTitle("Options")
        self.setMinimumSize(480, 360)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── header ────────────────────────────────────────────────────────────
        hdr = QWidget(); hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background-color: {NAVY};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20, 0, 20, 0)
        title = QLabel("Options")
        title.setStyleSheet(f"font-size:17px; font-weight:bold; color:{WHITE}; background:transparent;")
        close_btn = QPushButton("✕  Close")
        close_btn.setFixedSize(90, 32); close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color:{DANGER}; color:{WHITE}; border:none;
                border-radius:4px; font-size:12px; font-weight:bold;
            }}
            QPushButton:hover {{ background-color:{DANGER_H}; }}
        """)
        close_btn.clicked.connect(self.reject)
        hl.addWidget(title); hl.addStretch(); hl.addWidget(close_btn)
        root.addWidget(hdr)

        # ── body ──────────────────────────────────────────────────────────────
        body = QWidget(); body.setStyleSheet(f"background:{OFF_WHITE};")
        bl = QVBoxLayout(body); bl.setSpacing(12); bl.setContentsMargins(28, 24, 28, 24)

        def _section(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"font-size:11px; font-weight:bold; color:{MUTED}; background:transparent;"
                f" letter-spacing:0.8px; text-transform:uppercase;"
            )
            bl.addWidget(lbl)

        def _opt_btn(icon, label, handler, color=NAVY, hov=NAVY_2):
            b = QPushButton(f"  {icon}   {label}")
            b.setFixedHeight(46); b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color:{WHITE}; color:{color};
                    border:1px solid {BORDER}; border-left:4px solid {color};
                    border-radius:6px; font-size:14px; font-weight:bold;
                    text-align:left; padding:0 16px;
                }}
                QPushButton:hover {{
                    background-color:{color}; color:{WHITE}; border-color:{color};
                }}
            """)
            b.clicked.connect(handler)
            bl.addWidget(b)

        # Financial entries
        _section("Financial Entries")
        _opt_btn("💰", "Customer Payment Entry",
                 self._do_payment_entry, color=SUCCESS, hov=SUCCESS_H)
        _opt_btn("🔙", "Create Credit Note (Return)",
                 self._do_credit_note, color=AMBER, hov=ORANGE)
        _opt_btn("🔄", "Credit Note Sync",
                 self._do_cn_sync, color=NAVY_2, hov=NAVY_3)

        bl.addSpacing(8)

        # Invoice actions
        _section("Invoice Actions")
        _opt_btn("🖨", "Reprint Invoice",
                 self._do_reprint, color=NAVY, hov=NAVY_2)
        # _opt_btn("🗑", "Delete Selected Row",
        #          self._do_delete_row, color=DANGER, hov=DANGER_H)
        _opt_btn("🧾", "Sales Invoice List",
                 self._do_sales_list, color=ACCENT, hov=ACCENT_H)

        bl.addSpacing(8)

        # Settings
        _section("Settings")
        _opt_btn("🏢", "Company Defaults",
                 self._do_company_defaults, color=NAVY_3, hov=NAVY_2)
        _opt_btn("📦", "Item Groups",
                 self._do_item_groups, color=NAVY_2, hov=NAVY_3)

        bl.addSpacing(8)

        # Sync
        _section("Sync")
        _opt_btn("🔄", "Sync Accounts & Rates",
                 self._do_sync, color=ACCENT, hov=ACCENT_H)

        bl.addStretch()
        root.addWidget(body, 1)

    # ── handlers ──────────────────────────────────────────────────────────────
    def _do_payment_entry(self):
        self.accept()
        if self._pos:
            self._pos._open_customer_payment_entry()

    def _do_credit_note(self):
        self.accept()
        if self._pos:
            self._pos._open_credit_note_dialog()
        else:
            CreditNoteDialog(self.parent()).exec()

    def _do_cn_sync(self):
        self.accept()
        CreditNoteManagerDialog(self.parent()).exec()

    def _do_delete_row(self):
        self.accept()
        if self._pos:
            self._pos._numpad_del_line()

    def _do_sales_list(self):
        self.accept()
        if self._pos:
            self._pos._open_sales_list()

    def _do_reprint(self):
        self.accept()
        if self._pos:
            self._pos._reprint_by_invoice_no()

    def _do_company_defaults(self):
        self.accept()
        try:
            from views.pages.company_defaults_page import CompanyDefaultsPage
            dlg = QDialog(self.parent())
            dlg.setWindowTitle("Company Defaults")
            dlg.setMinimumSize(1000, 700)
            dlg.setStyleSheet(f"QDialog {{ background: {OFF_WHITE}; }}")
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(CompanyDefaultsPage())
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self.parent(), "Error", f"Could not open Company Defaults:\n{e}")

    def _do_item_groups(self):
        self.accept()
        try:
            from views.dialogs.item_group_dialog import ItemGroupDialog
            ItemGroupDialog(self.parent()).exec()
        except Exception as e:
            QMessageBox.warning(self.parent(), "Error", f"Could not open Item Groups:\n{e}")

    def _do_sync(self):
        self.accept()
        try:
            from views.dialogs.sync_dialog import SyncDialog
            SyncDialog(self.parent()).exec()
        except Exception as e:
            QMessageBox.warning(self.parent(), "Error", f"Could not open Sync:\n{e}")

    def _do_pos_rules(self):
        self.accept()
        POSRulesDialog(self.parent()).exec()

# =============================================================================
# POS RULES DIALOG  —  standalone, accessible from Options menu & Maintenance
# =============================================================================
class POSRulesDialog(QDialog):
    """
    Toggle-based POS business rules:
      #3  Block zero-price sales
      #4  Block zero-stock sales
      #7  Apply Frappe pricing rules
    Also shows per-user permission summary.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("POS Rules & Permissions")
        self.setMinimumSize(540, 480)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background:{WHITE}; }}")
        self._checks = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QWidget(); hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(24, 0, 24, 0)
        t = QLabel("🛡  POS Business Rules")
        t.setStyleSheet(f"font-size:16px; font-weight:bold; color:{WHITE}; background:transparent;")
        hl.addWidget(t); hl.addStretch()
        close_x = QPushButton("✕")
        close_x.setFixedSize(30, 30); close_x.setCursor(Qt.PointingHandCursor)
        close_x.setStyleSheet(
            f"QPushButton {{ background:{DANGER}; color:{WHITE}; border:none;"
            f" border-radius:4px; font-size:13px; font-weight:bold; }}"
            f"QPushButton:hover {{ background:{DANGER_H}; }}")
        close_x.clicked.connect(self.reject)
        hl.addWidget(close_x)
        root.addWidget(hdr)

        body = QWidget(); body.setStyleSheet(f"background:{WHITE};")
        bl = QVBoxLayout(body); bl.setSpacing(10); bl.setContentsMargins(28, 22, 28, 22)

        sec = QLabel("SALE RESTRICTIONS")
        sec.setStyleSheet(
            f"font-size:10px; font-weight:bold; color:{MUTED}; background:transparent;"
            f" letter-spacing:1px;")
        bl.addWidget(sec)

        rules = [
            ("block_zero_price",  "🚫  Block Zero-Price Sales",
             "Prevent adding items with $0.00 price to the invoice.", True),
            ("block_zero_stock",  "📦  Block Zero-Stock Sales",
             "Show 'Insufficient Stock' popup when item has no stock.", False),
            ("use_pricing_rules", "💸  Apply Frappe Pricing Rules",
             "Auto-apply discount rules from Frappe when adding items.", False),
        ]
        for key, label, desc, default in rules:
            self._add_rule_row(bl, key, label, desc, default)

        bl.addSpacing(8)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{BORDER}; border:none;"); sep.setFixedHeight(1)
        bl.addWidget(sep); bl.addSpacing(8)

        note = QLabel(
            "💡  Per-user permissions (Allow Discounts, Reprint, Credit Notes, Receipt)\n"
            "    are configured in  Maintenance → Users → edit a user."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color:{MUTED}; font-size:11px; background:{OFF_WHITE};"
            f" border:1px solid {BORDER}; border-radius:6px; padding:10px 14px;")
        bl.addWidget(note)
        bl.addStretch()

        save_btn = navy_btn("💾  Save Rules", height=42, color=SUCCESS, hover=SUCCESS_H)
        save_btn.clicked.connect(self._save)
        bl.addWidget(save_btn)

        root.addWidget(body, 1)

    def _add_rule_row(self, layout, key, label, desc, default):
        rw = QWidget()
        rw.setStyleSheet(
            f"background:{OFF_WHITE}; border:1px solid {BORDER}; border-radius:8px;")
        rl = QHBoxLayout(rw); rl.setContentsMargins(16, 12, 16, 12); rl.setSpacing(14)
        txt = QVBoxLayout(); txt.setSpacing(2)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"font-size:13px; font-weight:bold; color:{NAVY}; background:transparent;")
        dlbl = QLabel(desc)
        dlbl.setStyleSheet(f"font-size:11px; color:{MUTED}; background:transparent;")
        dlbl.setWordWrap(True)
        txt.addWidget(lbl); txt.addWidget(dlbl)
        chk = QCheckBox()
        chk.setFixedSize(44, 24)
        chk.setStyleSheet(f"""
            QCheckBox::indicator {{ width:40px; height:20px; border-radius:10px; }}
            QCheckBox::indicator:unchecked {{ background:{BORDER}; border:none; }}
            QCheckBox::indicator:checked   {{ background:{SUCCESS}; border:none; }}
        """)
        # Load saved value
        try:
            from database.db import get_connection
            conn = get_connection(); cur = conn.cursor()
            cur.execute(
                "SELECT setting_value FROM pos_settings WHERE setting_key=?", (key,))
            row = cur.fetchone(); conn.close()
            chk.setChecked(bool(int(row[0])) if row else default)
        except Exception:
            chk.setChecked(default)
        rl.addLayout(txt, 1); rl.addWidget(chk)
        self._checks[key] = chk
        layout.addWidget(rw)

    def _save(self):
        try:
            from database.db import get_connection
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""
                IF NOT EXISTS (
                    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME='pos_settings'
                )
                CREATE TABLE pos_settings (
                    setting_key   NVARCHAR(80)  NOT NULL PRIMARY KEY,
                    setting_value NVARCHAR(255) NOT NULL DEFAULT '0'
                )
            """)
            for key, chk in self._checks.items():
                val = "1" if chk.isChecked() else "0"
                cur.execute("""
                    MERGE pos_settings AS t
                    USING (SELECT ? AS k, ? AS v) AS s ON t.setting_key = s.k
                    WHEN MATCHED     THEN UPDATE SET setting_value = s.v
                    WHEN NOT MATCHED THEN INSERT (setting_key, setting_value)
                                          VALUES (s.k, s.v);
                """, (key, val))
            conn.commit(); conn.close()
            QMessageBox.information(self, "Saved", "POS rules saved successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save rules:\n{e}")

# =============================================================================
# CASHIER POS VIEW
# =============================================================================
class POSView(QWidget):
    MAX_ROWS = 999   # safety ceiling — table grows elastically

    def _ensure_rows(self, needed: int):
        """Grow the table in blocks of 20 so there are at least `needed` rows."""
        current = self.invoice_table.rowCount()
        if needed <= current:
            return
        new_count = min(self.MAX_ROWS, ((needed + 19) // 20) * 20)
        self.invoice_table.setRowCount(new_count)
        for r in range(current, new_count):
            self.invoice_table.setRowHeight(r, 20)
            self._init_row(r)

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
        self._prev_invoice: str  = ""

        # Product grid pagination state
        self._product_page     = 0
        self._current_products = []

        # Inline search state
        self._inline_edit   = None
        self._inline_popup  = None
        self._inline_row    = -1
        self._inline_col    = -1
        self._return_mode = False
        self._return_cn   = None
        self.current_discount_percent = 0.0   # ← Discount state (Change 1)
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
        layout.addLayout(body, 3)   # invoice area ~3/7 of page

        layout.addWidget(hr())
        layout.addWidget(self._build_bottom_grid(), 4)   # product grid gets ~4/7 of page

    # =========================================================================
    # NAV BAR
    # =========================================================================
    def _build_nav(self):
        bar = QWidget(); bar.setFixedHeight(48)
        bar.setStyleSheet(f"background-color: {WHITE}; border-bottom: 2px solid {BORDER};")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(6)

        logo = QLabel("Havano POS System")
        logo.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {NAVY}; background: transparent;")
        date_lbl = QLabel(QDate.currentDate().toString("dd/MM/yyyy"))
        date_lbl.setStyleSheet(f"font-size: 12px; color: {NAVY}; background: transparent;")
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

        # #34 — only Maintenance and Sales remain in the nav bar
        layout.addWidget(_npb("Maintenance", self._open_settings))
        layout.addWidget(_npb("Sales",       self._open_sales_list, color=ACCENT, hov=ACCENT_H))
        layout.addSpacing(10)

        # Customer selector — keep here, it's a POS action not a setting
        self._cust_btn = QPushButton("👤  Customer")
        self._cust_btn.setFixedHeight(26); self._cust_btn.setMaximumWidth(170)
        self._cust_btn.setCursor(Qt.PointingHandCursor)
        self._cust_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY_2}; color: {WHITE}; border: 1px solid {NAVY_3};
                border-radius: 3px; font-size: 11px; padding: 0 8px;
            }}
            QPushButton:hover {{ background-color: {NAVY_3}; color: {WHITE}; }}
        """)
        self._cust_btn.clicked.connect(self._select_customer)
        layout.addWidget(self._cust_btn); layout.addSpacing(4)

        # ── Queue badge — shows unsynced invoices + credit notes ──────────────
        self._unsynced_badge = QPushButton("⏳ Q: —")
        self._unsynced_badge.setFixedHeight(26)
        self._unsynced_badge.setMinimumWidth(70)
        self._unsynced_badge.setMaximumWidth(170)
        self._unsynced_badge.setCursor(Qt.PointingHandCursor)
        self._unsynced_badge.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY_2}; color: {WHITE}; border: none;
                border-radius: 3px; font-size: 11px; font-weight: bold; padding: 0 8px;
            }}
            QPushButton:hover {{ background-color: {NAVY_3}; }}
        """)
        self._unsynced_badge.setToolTip("Unsynced invoices / credit notes — click to view")
        self._unsynced_badge.clicked.connect(self._open_sales_list)
        layout.addWidget(self._unsynced_badge); layout.addSpacing(4)

        # ── Laybye button ─────────────────────────────────────────────────────
        laybye_btn = QPushButton("🏷  Laybye")
        laybye_btn.setFixedHeight(32)
        laybye_btn.setMinimumWidth(100)
        laybye_btn.setCursor(Qt.PointingHandCursor)
        laybye_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AMBER}; color: {WHITE}; border: none;
                border-radius: 4px; font-size: 12px; font-weight: bold; padding: 0 14px;
            }}
            QPushButton:hover   {{ background-color: {ORANGE}; }}
            QPushButton:pressed {{ background-color: {NAVY_2}; }}
        """)
        laybye_btn.setToolTip("Save cart as a Laybye (Sales Order)")
        laybye_btn.clicked.connect(self._on_laybye)
        layout.addWidget(laybye_btn); layout.addSpacing(4)

        # ── Return mode indicator (only visible during a return/CN flow) ──────
        self._return_btn = _npb("↩  Return", self._process_return, color=DANGER, hov=DANGER_H)
        self._return_btn.setToolTip("Confirm return (credit note loaded)")
        self._return_btn.setVisible(False)
        layout.addWidget(self._return_btn); layout.addSpacing(4)

        # Refresh on startup and every 5 s
        QTimer.singleShot(500, self._refresh_unsynced_badge)
        self._unsynced_timer = QTimer(self)
        self._unsynced_timer.setInterval(5000)
        self._unsynced_timer.timeout.connect(self._refresh_unsynced_badge)
        self._unsynced_timer.start()

        layout.addStretch(1)

        # #34 — admin Dashboard button (right side only, no switch-to-pos)
        try:
            from models.user import is_admin
            if self.user and is_admin(self.user):
                dash_btn = QPushButton("Dashboard")
                dash_btn.setFixedHeight(26); dash_btn.setCursor(Qt.PointingHandCursor)
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

        logout = QPushButton("Logout")
        logout.setFixedHeight(26); logout.setCursor(Qt.PointingHandCursor)
        logout.setStyleSheet(f"""
            QPushButton {{
                background-color: {DANGER}; color: {WHITE}; border: none;
                border-radius: 4px; font-size: 11px; font-weight: bold; padding: 0 12px;
            }}
            QPushButton:hover   {{ background-color: {DANGER_H}; }}
            QPushButton:pressed {{ background-color: {NAVY_2}; }}
        """)
        if self.parent_window:
            logout.clicked.connect(self.parent_window._logout)
        layout.addWidget(logout)
        return bar
    def _show_options_menu(self):
        """Opens a full-size Options dialog with all available actions."""
        dlg = OptionsDialog(self, pos_view=self)
        dlg.exec()

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
    # ── Invoice column labels — edit here to rename ──────────────────────────
    INVOICE_COL_LABELS = ["Item No.", "Item Details", "Amount $", "Qty", "Disc", "TAX", "Total $"]

    def _build_invoice_table(self):
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(7)
        self.invoice_table.setHorizontalHeaderLabels(self.INVOICE_COL_LABELS)
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
        self.invoice_table.setRowCount(20)
        self.invoice_table.verticalHeader().setDefaultSectionSize(20)
        self.invoice_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.invoice_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # ── No native cell editor — all input goes through numpad / inline search
        self.invoice_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.invoice_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {WHITE}; color: {NAVY};
                border: 1px solid {BORDER}; gridline-color: {LIGHT};
                font-size: 12px; outline: none;
                selection-background-color: transparent;
            }}
            QTableWidget::item {{
                padding: 0 4px; color: {NAVY}; border-bottom: 1px solid {LIGHT};
            }}
            QTableWidget::item:selected {{
                background-color: #fff8e1; color: {NAVY}; border: 1px solid #f9a825;
            }}
            QTableWidget::item:focus {{
                background-color: #fff8e1; color: {NAVY};
                border: 2px solid #f57f17; font-weight: bold;
            }}
            QHeaderView::section {{
                background-color: #f0e8d0; color: {NAVY};
                padding: 4px 6px; border: none; border-right: 1px solid {BORDER};
                font-size: 10px; font-weight: bold; letter-spacing: 0.3px;
            }}
        """)
        for r in range(self.invoice_table.rowCount()):
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
            if c in (2, 6):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setForeground(QColor(ACCENT) if c == 6 else QColor(NAVY))
            else:
                item.setForeground(QColor(NAVY))
            self.invoice_table.setItem(r, c, item)
        self.invoice_table.setRowHeight(r, 20)

    def _find_next_empty_row(self) -> int:
        current = self.invoice_table.rowCount()
        last_filled = -1
        for r in range(current):
            name = self.invoice_table.item(r, 1)
            if name and name.text().strip():
                last_filled = r
        next_row = last_filled + 1
        if next_row >= current:
            self._ensure_rows(next_row + 1)
        return min(next_row, self.MAX_ROWS - 1)

    def _highlight_active_row(self, row: int):
        ACTIVE_BG  = QColor("#e3f2fd")
        ACTIVE_FG  = QColor(DARK_TEXT)
        FILLED_BG  = QColor(WHITE)
        FILLED_FG  = QColor(NAVY)
        ALT_BG     = QColor("#f5f8fc")

        for r in range(self.invoice_table.rowCount()):
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
            amount      = float(self.invoice_table.item(r, 2).text() or "0")
            qty         = float(self.invoice_table.item(r, 3).text() or "0")
            disc_amount = float((self.invoice_table.item(r, 4).text() or "0").replace('%', '').strip())
            total       = max(qty * amount - disc_amount, 0.0)
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
        subtotal  = 0.0
        qty_total = 0.0
        for r in range(self.invoice_table.rowCount()):
            try:
                subtotal  += float(self.invoice_table.item(r, 6).text() or "0")
                qty_total += float(self.invoice_table.item(r, 3).text() or "0")
            except (ValueError, AttributeError):
                pass

        # Apply transaction-level discount
        discount_pct    = getattr(self, "current_discount_percent", 0.0)
        discount_amount = subtotal * (discount_pct / 100.0)
        grand_total     = subtotal - discount_amount

        self._lbl_total.setText(f"{grand_total:.2f}" if grand_total else "")
        self._bin_qty.setText(f"Items: {int(qty_total)}")

        # Show discount badge on the label when active
        if discount_pct > 0:
            self._lbl_total.setToolTip(
                f"Subtotal: ${subtotal:.2f}  |  Discount {discount_pct:.2f}%: -${discount_amount:.2f}"
            )
        else:
            self._lbl_total.setToolTip("")

        # Update row count bar
        if hasattr(self, "_lbl_row_count"):
            filled = sum(
                1 for r in range(self.invoice_table.rowCount())
                if self.invoice_table.item(r, 1) and self.invoice_table.item(r, 1).text().strip()
            )
            self._lbl_row_count.setText(f"Rows: {filled}")

        # Update status bar
        if self.parent_window:
            status = f"  Items: {int(qty_total)}   |   Total: ${grand_total:.2f}"
            if discount_pct > 0:
                status += f"   |   Discount: {discount_pct:.2f}% (-${discount_amount:.2f})"
            self.parent_window._set_status(status)

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
            result = self._maybe_pick_uom(product)
            if result is None:
                return   # user cancelled UOM picker
            uom, price = result
            self._add_product_to_invoice(
                name=product["name"],
                price=price,
                part_no=product.get("part_no", ""),
                product_id=product.get("id"),
            )
        else:
            # #31 — show popup then reopen search on the same row
            msg = QMessageBox(self)
            msg.setWindowTitle("Item Not Found")
            msg.setIcon(QMessageBox.Warning)
            msg.setText(f"No item matched:  \"{query}\"")
            msg.setInformativeText(
                "Check the code or description and try again.\n"
                "Double-click the row to open the full product search."
            )
            msg.setStandardButtons(QMessageBox.Ok)
            msg.setStyleSheet(f"""
                QMessageBox {{ background:{WHITE}; }}
                QLabel       {{ color:{DARK_TEXT}; font-size:13px; }}
                QPushButton  {{
                    background:{ACCENT}; color:{WHITE}; border:none;
                    border-radius:5px; padding:8px 22px; font-size:13px; min-width:80px;
                }}
                QPushButton:hover {{ background:{ACCENT_H}; }}
            """)
            msg.exec()
            # After OK or Enter — reopen search on the same row so user can try again
            self._highlight_active_row(row)
            self.invoice_table.setCurrentCell(row, 0)
            self._active_row = row
            self._active_col = 0
            self._open_inline_search(row, 0)

    def _inline_commit_product(self, product):
        self._close_inline_search()
        if not product:
            return
        result = self._maybe_pick_uom(product)
        if result is None:
            return   # user cancelled UOM picker
        uom, price = result
        self._add_product_to_invoice(
            name=product["name"],
            price=price,
            part_no=product.get("part_no", ""),
            product_id=product.get("id"),
            stock=product.get("stock"),
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

        # ── inline search edit ────────────────────────────────────────────────
        if obj is self._inline_edit and event.type() == QEvent.KeyPress:
            key   = event.key()
            popup = self._inline_popup
            if key == Qt.Key_Down:
                if popup and popup.isVisible():
                    popup.setCurrentRow(min(popup.currentRow() + 1, popup.count() - 1))
                return True
            if key == Qt.Key_Up:
                if popup and popup.isVisible():
                    popup.setCurrentRow(max(popup.currentRow() - 1, 0))
                return True
            if key == Qt.Key_Escape:
                self._close_inline_search()
                self.invoice_table.setFocus()
                return True
            if key == Qt.Key_Tab:
                self._inline_on_enter()
                return True

        # ── invoice table ─────────────────────────────────────────────────────
        if obj is self.invoice_table and event.type() == QEvent.KeyPress:
            key  = event.key()
            mods = event.modifiers()

            # #6 Enter/Return — always advance to next cart line
            if key in (Qt.Key_Return, Qt.Key_Enter):
                if self._inline_edit is not None:
                    self._inline_on_enter()
                    return True
                self._numpad_enter()
                return True

            # #36 Up arrow — move to row above
            if key == Qt.Key_Up:
                self._close_inline_search()
                target = max(0, self._active_row - 1)
                self._active_row = target
                self.invoice_table.setCurrentCell(target, self._active_col)
                self._highlight_active_row(target)
                self.invoice_table.scrollToItem(
                    self.invoice_table.item(target, self._active_col),
                    QAbstractItemView.EnsureVisible)
                if self._active_col in (0, 1):
                    self._open_inline_search(target, self._active_col)
                return True

            # #36 Down arrow — move to row below
            if key == Qt.Key_Down:
                self._close_inline_search()
                target = min(self._active_row + 1, self.invoice_table.rowCount() - 1)
                self._active_row = target
                self.invoice_table.setCurrentCell(target, self._active_col)
                self._highlight_active_row(target)
                self.invoice_table.scrollToItem(
                    self.invoice_table.item(target, self._active_col),
                    QAbstractItemView.EnsureVisible)
                if self._active_col in (0, 1):
                    self._open_inline_search(target, self._active_col)
                return True

            # #36 Tab — cycle Code→Qty→Disc, wrap to next/prev row
            if key == Qt.Key_Tab:
                self._close_inline_search()
                _TAB = [0, 3, 4]
                reverse = bool(mods & Qt.ShiftModifier)
                if reverse:
                    _TAB = list(reversed(_TAB))
                try:
                    nxt = _TAB.index(self._active_col) + 1
                except ValueError:
                    nxt = 0
                if nxt >= len(_TAB):
                    step = -1 if reverse else 1
                    self._active_row = max(0, min(
                        self._active_row + step,
                        self.invoice_table.rowCount() - 1))
                    self._active_col = _TAB[0]
                else:
                    self._active_col = _TAB[nxt]
                self.invoice_table.setCurrentCell(self._active_row, self._active_col)
                self._highlight_active_row(self._active_row)
                if self._active_col in (0, 1):
                    self._open_inline_search(self._active_row, self._active_col)
                return True

            if key == Qt.Key_Delete:    self._numpad_del_line(); return True
            if key == Qt.Key_Asterisk:  self._open_qty_popup();  return True
            if key == Qt.Key_F2:        self._save_sale();        return True
            if key == Qt.Key_F3:        self._print_receipt();    return True
            if key == Qt.Key_F4:        self._on_discount_clicked(); return True
            if key == Qt.Key_F5:        self._open_payment();     return True
            if key == Qt.Key_F7:        self._open_sales_list();  return True
            if key == Qt.Key_Escape:
                self._close_inline_search(); self._numpad_clear(); return True
            if key == Qt.Key_Backspace:
                if self._inline_edit is None and self._active_col in (3, 4):
                    self._numpad_buffer = self._numpad_buffer[:-1]
                    self._block_signals = True
                    item = self.invoice_table.item(self._active_row, self._active_col)
                    if item: item.setText(self._numpad_buffer)
                    self._block_signals = False
                    self._recalc_row(self._active_row)
                    return True
            if self._inline_edit is None and self._active_col in (3, 4):
                ch = None
                if Qt.Key_0 <= key <= Qt.Key_9: ch = chr(key)
                elif key == Qt.Key_Period:       ch = "."
                elif key in (Qt.Key_Minus, Qt.Key_Underscore): ch = "-"
                if ch is not None:
                    self._numpad_press(ch); return True

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
        else:
            # Clicking price/qty/disc cols — close search, ready for keyboard/numpad
            self._close_inline_search()
            self._highlight_active_row(row)
            self.invoice_table.setFocus()

    def _on_cell_double_clicked(self, row, col):
        if col not in (0, 1):
            return
        part_item = self.invoice_table.item(row, 0)
        query = part_item.text().strip() if part_item else ""
        dlg = ProductSearchDialog(self, initial_query=query)
        if dlg.exec() == QDialog.Accepted and dlg.selected_product:
            p = dlg.selected_product
            result = self._maybe_pick_uom(p)
            if result is None:
                return   # user cancelled UOM picker
            uom, price = result
            self._block_signals = True
            self._init_row(row, part_no=p["part_no"], details=p["name"],
                           qty="1", amount=f"{price:.2f}", disc="0.00", tax="")
            item0 = self.invoice_table.item(row, 0)
            if item0: item0.setData(Qt.UserRole, p.get("id"))
            self._block_signals = False
            self._recalc_row(row)
            self.invoice_table.setCurrentCell(row, 3)
            self._active_row = row; self._active_col = 3; self._numpad_buffer = ""

    def _on_product_btn_clicked(self, product: dict):
        """Called when a product tile button is clicked — shows UOM picker if needed."""
        result = self._maybe_pick_uom(product)
        if result is None:
            return
        uom, price = result
        self._add_product_to_invoice(
            name=product.get("name", ""),
            price=price,
            part_no=product.get("part_no", ""),
            product_id=product.get("id"),
            stock=product.get("stock"),
        )

    def _get_uom_prices(self, part_no: str) -> list[dict]:
        """Returns list of {uom, price} for a product from product_uom_prices table."""
        try:
            from database.db import get_connection
            conn = get_connection(); cur = conn.cursor()
            cur.execute(
                "SELECT uom, price FROM product_uom_prices WHERE part_no=? ORDER BY price",
                (part_no,)
            )
            rows = cur.fetchall(); conn.close()
            return [{"uom": r[0], "price": float(r[1])} for r in rows]
        except Exception:
            return []

    def _maybe_pick_uom(self, product: dict) -> tuple[str, float] | None:
        """
        If product has multiple UOM prices, show picker dialog.
        Returns (uom, price) tuple — never returns None for no-data case.
        Returns None only if user explicitly cancels the picker.
        """
        part_no    = product.get("part_no", "")
        base_price = float(product.get("price", 0))
        base_uom   = str(product.get("uom", "Nos") or "Nos")

        uom_prices = self._get_uom_prices(part_no)

        # No UOM table data or table doesn't exist yet —
        # fall through silently with base price, no popup
        if not uom_prices:
            return (base_uom, base_price)

        # Single UOM — no dialog needed, use it directly
        if len(uom_prices) == 1:
            return (uom_prices[0]["uom"], uom_prices[0]["price"])

        # Multiple UOMs — show picker so cashier chooses pack size
        dlg = UomPickerDialog(
            product_name=product.get("name", ""),
            uom_prices=uom_prices,
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted and dlg.selected_uom:
            return (dlg.selected_uom, dlg.selected_price)

        # Cancelled — still add with base price rather than blocking
        return (base_uom, base_price)

    # =========================================================================
    # PERMISSION CHECK HELPER  (#23)
    # =========================================================================
    def _check_permission(self, flag: str, action_label: str = "This action") -> bool:
        """
        Return True if the current user has the given permission flag.
        Shows a denial popup if not. Falls back to True for admins and
        if the column does not exist yet.
        """
        user = self.user or {}
        # Admins always have all permissions
        if (user.get("role") or "").lower() == "admin":
            return True
        # Check flag — default True if not set (backward compat)
        allowed = bool(user.get(flag, True))
        if not allowed:
            self._warn_popup(
                "Permission Denied",
                f"<b>{action_label}</b> is not allowed for your user account.<br>"
                "Contact an administrator to enable this permission.",
                icon=QMessageBox.Warning,
            )
        return allowed

    # =========================================================================
    # SHARED POPUP HELPER
    # =========================================================================
    def _warn_popup(self, title: str, html: str, icon=None):
        """Styled warning/info popup used by POS rule blocks."""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(html)
        msg.setIcon(icon or QMessageBox.Warning)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setStyleSheet(f"""
            QMessageBox {{ background:{WHITE}; }}
            QLabel       {{ color:{DARK_TEXT}; font-size:13px; }}
            QPushButton  {{
                background:{ACCENT}; color:{WHITE}; border:none;
                border-radius:5px; padding:8px 22px; font-size:13px; min-width:80px;
            }}
            QPushButton:hover {{ background:{ACCENT_H}; }}
        """)
        msg.exec()
        # Return focus to the invoice table so the cashier can keep typing
        QTimer.singleShot(0, lambda: (
            self.invoice_table.setFocus(),
            self._open_inline_search(self._active_row, 0)
        ))

    # =========================================================================
    # POS RULES HELPERS  (#3 #4 #7)
    # =========================================================================
    def _get_pos_rule(self, key: str, default: bool = False) -> bool:
        """Read a single toggle from pos_settings table. Fast; falls back to default."""
        try:
            from database.db import get_connection
            conn = get_connection(); cur = conn.cursor()
            cur.execute(
                "SELECT setting_value FROM pos_settings WHERE setting_key=?", (key,))
            row = cur.fetchone(); conn.close()
            return bool(int(row[0])) if row else default
        except Exception:
            return default

    def _apply_pricing_rules(self, product_id, part_no: str, price: float) -> float:
        """#7 — fetch Frappe pricing rule discount and return adjusted price."""
        try:
            from services.frappe_api import get_pricing_rule_discount
            disc_pct = get_pricing_rule_discount(part_no) or 0.0
            if disc_pct > 0:
                return round(price * (1.0 - disc_pct / 100.0), 2)
        except Exception:
            pass
        return price

    def _add_product_to_invoice(self, name, price, part_no="", product_id=None, stock=None):
        # ── Always close any open inline search before we touch the table ─────
        self._close_inline_search()

        # ── #3 Block zero-price ───────────────────────────────────────────────
        if price <= 0 and self._get_pos_rule("block_zero_price", default=True):
            self._warn_popup(
                "Zero Price Blocked",
                f"<b>{name}</b> has no selling price set.<br>"
                "Update the price in Frappe and re-sync, or disable the "
                "'Block Zero-Price Sales' rule in Maintenance → POS Rules.",
                icon=QMessageBox.Warning,
            )
            return

        # ── #4 Block zero/negative stock ─────────────────────────────────────
        if self._get_pos_rule("block_zero_stock", default=False):
            # stock may be passed in; if not, look it up
            item_stock = stock
            if item_stock is None and product_id:
                try:
                    from models.product import get_product_by_id
                    p = get_product_by_id(product_id)
                    item_stock = float(p.get("stock", 1)) if p else 1
                except Exception:
                    item_stock = 1
            if item_stock is not None and item_stock <= 0:
                self._warn_popup(
                    "Insufficient Stock",
                    f"<b>{name}</b> is out of stock.<br>"
                    "Cannot add this item to the invoice.<br><br>"
                    "Disable 'Block Zero/Negative Stock Sales' in "
                    "Maintenance → POS Rules to override.",
                    icon=QMessageBox.Warning,
                )
                return

        # ── #7 Apply Frappe pricing rules ─────────────────────────────────────
        if self._get_pos_rule("use_pricing_rules", default=False):
            price = self._apply_pricing_rules(product_id, part_no, price)
        for r in range(self.invoice_table.rowCount()):
            try:
                row_name   = self.invoice_table.item(r, 1).text().strip()
                row_amount = self.invoice_table.item(r, 2).text().strip()
                row_qty    = self.invoice_table.item(r, 3).text().strip()
            except AttributeError:
                continue
            if not row_name:
                continue
            row_pid = self.invoice_table.item(r, 0).data(Qt.UserRole) if self.invoice_table.item(r, 0) else None
            # Must match BOTH product_id AND price — different UOMs have same id but different price
            match = (row_pid and row_pid == product_id and row_amount == f"{price:.2f}") or \
                    (not product_id and row_name == name and row_amount == f"{price:.2f}")
            if match:
                try:
                    current_qty = float(row_qty or "0")
                except ValueError:
                    current_qty = 0.0
                new_qty = current_qty + 1

                # ── Collect this row's data so we can move it ─────────────────
                def _cell_text(row, col):
                    it = self.invoice_table.item(row, col)
                    return it.text() if it else ""
                def _cell_data(row, col):
                    it = self.invoice_table.item(row, col)
                    return it.data(Qt.UserRole) if it else None

                saved_part_no    = _cell_text(r, 0)
                saved_pid        = _cell_data(r, 0)
                saved_name       = _cell_text(r, 1)
                saved_price      = _cell_text(r, 2)
                saved_disc       = _cell_text(r, 4)
                saved_tax        = _cell_text(r, 5)

                # ── Remove this row and compact upward ────────────────────────
                self._block_signals = True
                self._init_row(r)
                # Shift all filled rows above the gap down by one
                for shift in range(r, self.invoice_table.rowCount() - 1):
                    try:
                        next_name = self.invoice_table.item(shift + 1, 1).text().strip()
                    except AttributeError:
                        next_name = ""
                    if not next_name:
                        break
                    # copy shift+1 → shift
                    for col in range(7):
                        src = self.invoice_table.item(shift + 1, col)
                        dst = self.invoice_table.item(shift, col)
                        if src and dst:
                            dst.setText(src.text())
                            dst.setTextAlignment(src.textAlignment())
                            dst.setData(Qt.UserRole, src.data(Qt.UserRole))
                    # clear the row we just copied from
                    self._init_row(shift + 1)
                self._block_signals = False

                # ── Find last filled row after compaction ─────────────────────
                last_filled = -1
                for scan in range(self.invoice_table.rowCount()):
                    try:
                        if self.invoice_table.item(scan, 1).text().strip():
                            last_filled = scan
                    except AttributeError:
                        pass

                dest = last_filled + 1
                self._ensure_rows(dest + 1)

                # ── Write to destination row ──────────────────────────────────
                self._block_signals = True
                self._init_row(dest, part_no=saved_part_no, details=saved_name,
                               qty=f"{new_qty:.4g}", amount=saved_price,
                               disc=saved_disc or "0.00", tax=saved_tax)
                item0 = self.invoice_table.item(dest, 0)
                if item0:
                    item0.setData(Qt.UserRole, saved_pid)
                qty_item = self.invoice_table.item(dest, 3)
                if qty_item:
                    qty_item.setTextAlignment(Qt.AlignCenter)
                self._block_signals = False

                self._recalc_row(dest)
                self._recalc_totals()
                self._active_row      = dest
                self._active_col      = 3
                self._last_filled_row = dest
                self._numpad_buffer   = ""
                self.invoice_table.setCurrentCell(dest, 3)
                self.invoice_table.scrollToItem(
                    self.invoice_table.item(dest, 3),
                    QAbstractItemView.PositionAtBottom
                )
                self._highlight_active_row(dest)
                self.invoice_table.setFocus()
                if self.parent_window:
                    self.parent_window._set_status(f"{name}  ×{new_qty:.4g}  @ ${price:.2f}")
                # Open inline search on the NEXT empty row
                next_r = self._find_next_empty_row()
                if next_r != dest:
                    self._active_row = next_r
                    self._active_col = 0
                    self.invoice_table.setCurrentCell(next_r, 0)
                    self._highlight_active_row(next_r)
                    QTimer.singleShot(0, lambda r=next_r: self._open_inline_search(r, 0))
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
        self.invoice_table.scrollToItem(
            self.invoice_table.item(r, 1),
            QAbstractItemView.PositionAtBottom
        )
        self.invoice_table.setFocus()
        if self.parent_window:
            self.parent_window._set_status(f"Added: {name} @ ${price:.2f}")
        # Move cursor to the NEXT empty row and open inline search there.
        # Deferred so the current Enter keypress is fully consumed first —
        # prevents it re-firing on the newly created QLineEdit.
        next_r = self._find_next_empty_row()
        self._active_row = next_r
        self._active_col = 0
        self.invoice_table.setCurrentCell(next_r, 0)
        self._highlight_active_row(next_r)
        QTimer.singleShot(0, lambda: self._open_inline_search(next_r, 0))

    # ── Invoice footer — Items | Paid | Change+InvoiceNo | TOTAL ─────────────
    def _build_invoice_footer(self):
        bar = QWidget(); bar.setFixedHeight(42)
        bar.setStyleSheet(f"background-color: #f0e8d0; border-top: 2px solid {BORDER};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(0)

        self._bin_qty = QLabel("Items: 0")
        self._bin_qty.setStyleSheet(f"color: {NAVY}; font-size: 11px; background: transparent;")
        layout.addWidget(self._bin_qty)
        layout.addSpacing(12)

        sep1 = QLabel("|")
        sep1.setStyleSheet(f"color: {BORDER}; font-size: 11px; background: transparent;")
        layout.addWidget(sep1)
        layout.addSpacing(12)

        self._lbl_row_count = QLabel("Rows: 0")
        self._lbl_row_count.setStyleSheet(f"color: {NAVY}; font-size: 11px; background: transparent;")
        layout.addWidget(self._lbl_row_count)
        layout.addSpacing(16)

        prev_paid_lbl = QLabel("Paid")
        prev_paid_lbl.setStyleSheet(f"color: {NAVY}; font-size: 10px; background: transparent;")
        layout.addWidget(prev_paid_lbl); layout.addSpacing(4)

        self._lbl_prev_paid = QLabel("—")
        self._lbl_prev_paid.setStyleSheet(f"color: {NAVY}; font-size: 13px; font-weight: bold; background: transparent; min-width: 70px;")
        self._lbl_prev_paid.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._lbl_prev_paid)
        layout.addSpacing(16)

        prev_chg_lbl = QLabel("Change")
        prev_chg_lbl.setStyleSheet(f"color: {NAVY}; font-size: 10px; background: transparent;")
        layout.addWidget(prev_chg_lbl); layout.addSpacing(4)

        self._lbl_prev_change = QLabel("—")
        self._lbl_prev_change.setStyleSheet(
            f"color: {NAVY}; font-size: 13px; font-weight: bold; background: transparent; min-width: 70px;")
        self._lbl_prev_change.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._lbl_prev_change)
        layout.addSpacing(10)

        inv_sep = QLabel("|")
        inv_sep.setStyleSheet(f"color: {BORDER}; font-size: 13px; background: transparent;")
        layout.addWidget(inv_sep)
        layout.addSpacing(10)

        inv_lbl = QLabel("Invoice")
        inv_lbl.setStyleSheet(f"color: {NAVY}; font-size: 10px; background: transparent;")
        layout.addWidget(inv_lbl); layout.addSpacing(4)

        self._lbl_prev_invoice = QLabel("—")
        self._lbl_prev_invoice.setStyleSheet(
            f"color: {ACCENT}; font-size: 13px; font-weight: bold; background: transparent; min-width: 120px;")
        self._lbl_prev_invoice.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self._lbl_prev_invoice)

        layout.addStretch(1)

        tot_lbl = QLabel("TOTAL")
        tot_lbl.setStyleSheet(f"color: {NAVY}; font-size: 11px; font-weight: bold; letter-spacing: 1.5px; background: transparent;")
        tot_lbl.setAlignment(Qt.AlignVCenter)
        self._lbl_total = QLabel("")
        self._lbl_total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._lbl_total.setStyleSheet(f"color: {NAVY}; font-size: 22px; font-weight: bold; background: transparent; min-width: 110px;")
        layout.addWidget(tot_lbl); layout.addSpacing(8); layout.addWidget(self._lbl_total)

        return bar

    def _update_prev_txn_display(self, paid: float, change: float, invoice_no: str = ""):
        """Refresh footer: Paid | Change | Invoice No. — all on one line."""
        self._prev_paid    = paid
        self._prev_change  = change
        self._prev_invoice = invoice_no
        self._lbl_prev_paid.setText(f"${paid:.2f}")
        self._lbl_prev_change.setText(f"${change:.2f}")
        self._lbl_prev_invoice.setText(invoice_no if invoice_no else "—")

    # =========================================================================
    # RIGHT PANEL
    # =========================================================================
    def _build_right_panel(self):
        panel = QWidget()
        panel.setFixedWidth(500)
        panel.setStyleSheet(f"background-color: {OFF_WHITE};")
        layout = QVBoxLayout(panel)
        layout.setSpacing(4)
        layout.setContentsMargins(4, 4, 4, 4)

        # --- Top Row: Shift & Options (Requirement 4, 2 & 3) ---
        top_row = QHBoxLayout()
        top_row.setSpacing(4)

        def _top_btn(label, bg, hov, handler):
            b = QPushButton(label)
            b.setFixedHeight(52)
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

        # Requirement 4: Close Shift at top left
        top_row.addWidget(_top_btn("CLOSE\nSHIFT (F2)", ORANGE,    AMBER,     self._open_day_shift))
        top_row.addWidget(_top_btn("Reprint\nF3",        NAVY,      NAVY_2,    self._reprint_by_invoice_no))
        top_row.addWidget(_top_btn("Discount\nF4 (%)",   "#e67e22", "#d35400", self._on_discount_clicked))
        top_row.addWidget(_top_btn("Hold/\nRecall",      NAVY_2,    NAVY_3,    self._open_hold_recall))

        # Options Button
        opt_btn = QPushButton("Options\n▼")
        opt_btn.setFixedHeight(52)
        opt_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        opt_btn.setCursor(Qt.PointingHandCursor)
        opt_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY_3}; color: {WHITE}; border: none;
                border-radius: 6px; font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {NAVY_2}; }}
        """)
        opt_btn.clicked.connect(self._show_options_menu)
        top_row.addWidget(opt_btn)

        layout.addLayout(top_row)

        # --- Middle: Numpad ---
        layout.addWidget(self._build_numpad(), 1)

        # --- Bottom Row: New Transaction + PAY ---
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(4)

        new_txn_btn = QPushButton("New\nTransaction")
        new_txn_btn.setFixedHeight(52)
        new_txn_btn.setFixedWidth(120)
        new_txn_btn.setCursor(Qt.PointingHandCursor)
        new_txn_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY_2}; color: {WHITE}; border: none;
                border-radius: 6px; font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover   {{ background-color: {NAVY_3}; }}
            QPushButton:pressed {{ background-color: {NAVY};   }}
        """)
        new_txn_btn.clicked.connect(lambda: self._new_sale(confirm=False))
        bottom_row.addWidget(new_txn_btn)

        pay_btn = QPushButton("PAY  F5")
        pay_btn.setFixedHeight(52)
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
            [("0","digit"),(".","digit"),("%","op")                                     ],
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
                elif ch == "%":
                    b.setStyleSheet(f"""
                        QPushButton {{
                            background-color: #e67e22; color: {WHITE};
                            border: 1px solid {BORDER}; border-radius: 6px;
                            font-size: 16px; font-weight: bold;
                        }}
                        QPushButton:hover   {{ background-color: #d35400; }}
                        QPushButton:pressed {{ background-color: {NAVY_3}; color: {WHITE}; }}
                    """)
                    b.clicked.connect(self._on_discount_clicked)
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
        if self._active_col in (2, 5, 6):
            return
        # #23 — block discount entry if not permitted
        if self._active_col == 4 and not self._check_permission(
                "allow_discount", "Apply Discounts"):
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
        """
        Requirement 8: Clears the row, resets the input buffer, 
        and jumps the cursor back to the LAST column (Total $)
        to signal the line is empty and deleted.
        """
        row = self.invoice_table.currentRow()
        if row < 0:
            row = self._last_filled_row
            
        if row < 0: 
            return

        # 1. Clear the typing buffer so new typing doesn't include old character data
        self._numpad_buffer = "" 

        self._block_signals = True
        # 2. Wipe every cell in the row and clear hidden UserRole data (product IDs)
        for col in range(self.invoice_table.columnCount()):
            item = self.invoice_table.item(row, col)
            if item:
                item.setText("")
                item.setData(Qt.UserRole, None)
        
        # 3. Compact the invoice: shift all filled rows below this one upward
        for shift in range(row, self.invoice_table.rowCount() - 1):
            try:
                next_item = self.invoice_table.item(shift + 1, 1)
                next_name = next_item.text().strip() if next_item else ""
            except AttributeError:
                next_name = ""
            
            if not next_name:
                break
                
            # Copy data from the row below to the current row
            for col in range(7):
                src = self.invoice_table.item(shift + 1, col)
                dst = self.invoice_table.item(shift, col)
                if src and dst:
                    dst.setText(src.text())
                    dst.setTextAlignment(src.textAlignment())
                    dst.setData(Qt.UserRole, src.data(Qt.UserRole))
            
            # Reset the row we just copied from so it's fresh for new data
            self._init_row(shift + 1)
            
        self._block_signals = False

        # 4. Update financial totals (subtotals and grand total)
        self._recalc_totals()
        
        # 5. After deletion: jump cursor to the first empty row, column 0, and open inline search
        first_empty = self._find_next_empty_row()
        self._active_row = first_empty
        self._active_col = 0

        self.invoice_table.setCurrentCell(first_empty, 0)
        self._highlight_active_row(first_empty)

        # 6. Close any open search popups then reopen at the new empty row
        self._close_inline_search()
        self._open_inline_search(first_empty, 0)

        # Provide status feedback in the main window status bar
        if self.parent_window:
            self.parent_window._set_status("Line deleted — ready for next item.")
    def _numpad_enter(self):
        """#6 Enter always advances to next cart line.
        Cols 0/1/2 (Code/Details/Price) → land on Qty.
        Col 3+ (Qty/Disc/Tax/Total)     → finalise, open search on next row.
        """
        if self._active_row < 0:
            return
        self._numpad_buffer = ""

        if self._active_col in (0, 1, 2):
            self._active_col = 3
            self.invoice_table.setCurrentCell(self._active_row, 3)
            self._close_inline_search()
            self._highlight_active_row(self._active_row)
        else:
            self._recalc_row(self._active_row)
            self._recalc_totals()
            next_row = self._find_next_empty_row()
            self._active_row = next_row
            self._active_col = 0
            self.invoice_table.setCurrentCell(next_row, 0)
            self.invoice_table.scrollToItem(
                self.invoice_table.item(next_row, 0),
                QAbstractItemView.EnsureVisible)
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

        # Always ensure "All" tab exists — products synced from server have no category
        if "All" not in self._category_names:
            self._category_names = ["All"] + self._category_names
        if not self._category_names:
            self._category_names = ["All"]

        self._cat_buttons  = []
        self._cat_page     = 0
        self._CATS_VISIBLE = 6

        tab_row_w = QWidget(); tab_row_w.setFixedHeight(55)
        tab_row_w.setStyleSheet(f"background-color: {WHITE}; border-bottom: 1px solid {BORDER};")
        tab_row_h = QHBoxLayout(tab_row_w)
        tab_row_h.setSpacing(0); tab_row_h.setContentsMargins(0, 0, 0, 0)

        self._cat_prev_btn = QPushButton("◀")
        self._cat_prev_btn.setFixedWidth(60)
        self._cat_prev_btn.setMinimumHeight(55)
        self._cat_prev_btn.setCursor(Qt.PointingHandCursor)
        self._cat_prev_btn.setStyleSheet(f"""
       QPushButton {{ background-color: {NAVY_2}; color: {WHITE}; border: none; border-right: 2px solid {BORDER}; font-size: 22px; font-weight: bold; }}
    QPushButton:hover {{ background-color: {ACCENT}; color: {WHITE}; }}
""")
        self._cat_prev_btn.clicked.connect(lambda: self._cat_scroll(-1))
        tab_row_h.addWidget(self._cat_prev_btn)

        self._cat_tab_container = QWidget(); self._cat_tab_container.setStyleSheet(f"background-color: {WHITE};")
        self._cat_tab_layout = QHBoxLayout(self._cat_tab_container)
        self._cat_tab_layout.setSpacing(4); self._cat_tab_layout.setContentsMargins(4, 4, 4, 4)
        tab_row_h.addWidget(self._cat_tab_container, 1)

        self._cat_next_btn = QPushButton("▶")
        self._cat_next_btn.setFixedWidth(60)
        self._cat_next_btn.setMinimumHeight(55)
        self._cat_next_btn.setCursor(Qt.PointingHandCursor)
        self._cat_next_btn.setStyleSheet(f"""
    QPushButton {{ background-color: {NAVY_2}; color: {WHITE}; border: none; border-left: 2px solid {BORDER}; font-size: 22px; font-weight: bold; }}
    QPushButton:hover {{ background-color: {ACCENT}; color: {WHITE}; }}
""")
        self._cat_next_btn.clicked.connect(lambda: self._cat_scroll(1))
        tab_row_h.addWidget(self._cat_next_btn)
        outer.addWidget(tab_row_w)

        self._product_grid_widget = QWidget(); self._product_grid_widget.setStyleSheet(f"background-color: {WHITE};")
        self._product_grid_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._product_grid = QGridLayout(self._product_grid_widget)
        self._product_grid.setSpacing(2); self._product_grid.setContentsMargins(2, 2, 2, 2)
        outer.addWidget(self._product_grid_widget, 1)

        # Re-render on resize so cell sizes stay adaptive
        _pos_self = self
        class _GridResizeFilter(QWidget):
            def eventFilter(self, obj, event):
                from PySide6.QtCore import QEvent
                if event.type() == QEvent.Resize:
                    QTimer.singleShot(0, _pos_self._render_product_page)
                return False
        self._grid_resize_filter = _GridResizeFilter()
        self._product_grid_widget.installEventFilter(self._grid_resize_filter)

        # ── Pagination bar ─────────────────────────────────────────────────────
        page_bar = QWidget(); page_bar.setFixedHeight(22)
        page_bar.setStyleSheet(f"background-color: #f0e8d0; border-top: 1px solid {BORDER};")
        page_bar_h = QHBoxLayout(page_bar)
        page_bar_h.setContentsMargins(0, 0, 0, 0); page_bar_h.setSpacing(4)

        page_bar_h.addStretch(1)

        _btn_style = f"""
            QPushButton {{ background-color: {NAVY}; color: {WHITE}; border: none;
                border-radius: 3px; font-size: 9px; font-weight: bold; padding: 0 6px; }}
            QPushButton:hover {{ background-color: {NAVY_2}; }}
            QPushButton:disabled {{ background-color: {BORDER}; color: {MUTED}; }}
        """

        self._grid_prev_btn = QPushButton("◀ Prev")
        self._grid_prev_btn.setFixedSize(52, 16)
        self._grid_prev_btn.setCursor(Qt.PointingHandCursor)
        self._grid_prev_btn.setStyleSheet(_btn_style)
        self._grid_prev_btn.clicked.connect(lambda: self._grid_turn_page(-1))

        self._grid_page_lbl = QLabel("Page 1 / 1")
        self._grid_page_lbl.setAlignment(Qt.AlignCenter)
        self._grid_page_lbl.setStyleSheet(f"color: {NAVY}; font-size: 9px; background: transparent;")
        self._grid_page_lbl.setFixedWidth(80)

        self._grid_next_btn = QPushButton("Next ▶")
        self._grid_next_btn.setFixedSize(52, 16)
        self._grid_next_btn.setCursor(Qt.PointingHandCursor)
        self._grid_next_btn.setStyleSheet(_btn_style)
        self._grid_next_btn.clicked.connect(lambda: self._grid_turn_page(1))

        page_bar_h.addWidget(self._grid_prev_btn)
        page_bar_h.addWidget(self._grid_page_lbl)
        page_bar_h.addWidget(self._grid_next_btn)
        page_bar_h.addStretch(1)
        outer.addWidget(page_bar)

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
            f"  background-color: {bg_color}; color: {NAVY};"
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
        # Load ALL products for this category into memory
        try:
            from models.product import get_products_by_category, get_all_products
            if name == "All":
                db_products = get_all_products()
            else:
                db_products = get_products_by_category(name)
                # If a category is empty, fall back to everything
                if not db_products:
                    db_products = get_all_products()

            self._current_products = [
                (p["name"], p["part_no"], p["price"], p["id"], p.get("image_path", ""))
                for p in db_products
            ]
        except Exception as e:
            print(f"[grid] Error loading products: {e}")
            self._current_products = []

        # Always reset to first page when switching categories
        self._product_page = 0
        self._render_product_page()

    def _grid_turn_page(self, direction: int):
        """Navigate product grid pages (prev / next)."""
        any_img  = any(ip for _, _, _, _, ip in self._current_products)
        ROWS     = 3 if any_img else 4
        COLS     = 12
        per_page = ROWS * COLS
        total       = len(self._current_products)
        total_pages = max(1, (total + per_page - 1) // per_page)
        new_page    = self._product_page + direction
        if new_page < 0 or new_page >= total_pages:
            return
        self._product_page = new_page
        self._render_product_page()

    def _render_product_page(self):
        """Render the current page of products into the 4×12 grid."""
        # Clear existing buttons
        while self._product_grid.count():
            item = self._product_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Rows: 3 with images (square), 4 without (shorter)
        any_image_all = any(ip for _, _, _, _, ip in self._current_products)
        ROWS = 3 if any_image_all else 4
        COLS = 12
        per_page    = ROWS * COLS
        total       = len(self._current_products)
        total_pages = max(1, (total + per_page - 1) // per_page)

        start         = self._product_page * per_page
        page_products = self._current_products[start: start + per_page]

        any_image = any(ip for _, _, _, _, ip in page_products)

        # Uniform fixed cell size — computed from widget dimensions
        GAP  = 2
        gw   = self._product_grid_widget.width()
        gh   = self._product_grid_widget.height()
        if gw < 10: gw = 1200
        if gh < 10: gh = 400

        # Width same always; height = width (square) when images, fills rows otherwise
        cell_w = max(60, (gw - (COLS + 1) * GAP) // COLS)
        cell_h = min(cell_w, 100) if any_image else max(40, (gh - (ROWS + 1) * GAP) // ROWS)

        font_size = "7pt" if any_image else "9pt"
        BTN_STYLE = f"""
            QToolButton {{
                background-color: {OFF_WHITE}; color: {NAVY};
                border: 1px solid {BORDER}; border-radius: 0px;
                font-size: {font_size}; font-weight: bold;
                padding: 2px; spacing: 2px;
            }}
            QToolButton:hover   {{ background-color: {ACCENT}; color: {WHITE}; }}
            QToolButton:pressed {{ background-color: {ACCENT_H}; color: {WHITE}; }}
        """

        self._product_grid.setSpacing(GAP)
        self._product_grid.setContentsMargins(GAP, GAP, GAP, GAP)
        # All rows and columns fixed — nothing stretches
        for r in range(ROWS):
            self._product_grid.setRowStretch(r, 0)
            self._product_grid.setRowMinimumHeight(r, cell_h)
        for c in range(COLS):
            self._product_grid.setColumnStretch(c, 0)
            self._product_grid.setColumnMinimumWidth(c, cell_w)

        from PySide6.QtWidgets import QToolButton

        for r in range(ROWS):
            for c in range(COLS):
                flat = r * COLS + c
                if flat < len(page_products):
                    pname, part_no, price, product_id, image_path = page_products[flat]
                    btn = QToolButton()
                    btn.setFixedSize(cell_w, cell_h)
                    btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.setAutoRaise(False)
                    btn.setToolTip(f"{pname}  ${price:.2f}\nRight-click for image options")
                    self._apply_btn_image(btn, pname, price, image_path,
                                         icon_size=cell_h if any_image else 0,
                                         has_any_image=any_image)
                    btn.setStyleSheet(BTN_STYLE)
                    btn.clicked.connect(
                        lambda _, prod=dict(name=pname,price=price,part_no=part_no,id=product_id): self._on_product_btn_clicked(prod)
                    )
                    btn.setContextMenuPolicy(Qt.CustomContextMenu)
                    btn.customContextMenuRequested.connect(
                        lambda pos, b=btn, pid=product_id, pn=pname, ip=image_path:
                        self._product_btn_context_menu(b, pid, pn, ip)
                    )
                else:
                    btn = QToolButton()
                    btn.setFixedSize(cell_w, cell_h)
                    btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                    btn.setEnabled(False)
                    btn.setStyleSheet(
                        f"QToolButton {{ background-color: {OFF_WHITE}; "
                        f"border: 1px solid {BORDER}; border-radius: 0px; }}"
                    )
                self._product_grid.addWidget(btn, r, c)

        # Update pagination bar
        self._grid_page_lbl.setText(f"{self._product_page + 1} / {total_pages}")
        self._grid_prev_btn.setEnabled(self._product_page > 0)
        self._grid_next_btn.setEnabled(self._product_page < total_pages - 1)

    def _apply_btn_image(self, btn, pname, price, image_path, icon_size: int = 48, has_any_image: bool = True):
        from PySide6.QtGui import QIcon, QPixmap
        from PySide6.QtCore import QSize, Qt as _Qt

        MAX_NAME = 14
        display_name = pname if len(pname) <= MAX_NAME else pname[:MAX_NAME - 1] + "…"
        price_str = f"${price:.2f}" if price else ""

        if image_path and has_any_image:
            try:
                pix = QPixmap(image_path)
                if not pix.isNull():
                    # Fixed 32px icon — always leaves room for name + price
                    ICON_PX = 32
                    pix_sq = pix.scaled(ICON_PX, ICON_PX,
                                        _Qt.KeepAspectRatioByExpanding,
                                        _Qt.SmoothTransformation)
                    if pix_sq.width() > ICON_PX or pix_sq.height() > ICON_PX:
                        x = (pix_sq.width()  - ICON_PX) // 2
                        y = (pix_sq.height() - ICON_PX) // 2
                        pix_sq = pix_sq.copy(x, y, ICON_PX, ICON_PX)
                    btn.setIcon(QIcon(pix_sq))
                    btn.setIconSize(QSize(ICON_PX, ICON_PX))
                    btn.setText(f"{display_name}\n{price_str}")
                    btn.setToolButtonStyle(_Qt.ToolButtonTextUnderIcon)
                    return
            except Exception:
                pass

        btn.setIcon(QIcon())
        btn.setText(f"{display_name}\n{price_str}" if price_str else display_name)
        if has_any_image:
            btn.setIconSize(QSize(32, 32))
            btn.setToolButtonStyle(_Qt.ToolButtonTextUnderIcon)
        else:
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
        name = self._category_names[idx] if idx < len(self._category_names) else "All"
        self._load_category_products(idx, name)

    # =========================================================================
    # DIALOG OPENERS
    # =========================================================================
    def _open_day_shift(self):
        """Close Shift — opens reconciliation dialog, logs out on confirm."""
        cashier_id = self.user.get("id") if isinstance(self.user, dict) else None
        dlg = ShiftReconciliationDialog(self, cashier_id=cashier_id)
        if dlg.exec() == QDialog.Accepted:
            if self.parent_window:
                self.parent_window._logout()

    def _open_stock_file(self):
        if _HAS_STOCK: StockFileDialog(self).exec()
        else: coming_soon(self, "Stock File — add views/dialogs/stock_file_dialog.py")

    def _open_settings(self):
        if _HAS_SETTINGS_DIALOG:
            dlg = SettingsDialog(self, user=self.user)
        else:
            try:
                dlg = _InlineSettingsDialog(self, user=self.user)
            except TypeError:
                dlg = _InlineSettingsDialog(self)
                dlg.user = self.user or {}
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
            dlg.show()
        else:
            coming_soon(self, "Sales List — add views/dialogs/sales_list_dialog.py")

    def _collect_invoice_items(self) -> list[dict]:
        items = []
        for r in range(self.invoice_table.rowCount()):
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
                disc         = float((self.invoice_table.item(r, 4).text() or "0").replace('%', '').strip())
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
            self._update_prev_txn_display(paid=total, change=0.0, invoice_no=sale.get("invoice_no",""))
            if self.parent_window:
                self.parent_window._set_status(f"Sale #{sale['number']} saved — ${total:.2f}")
            # ── Badge refresh: immediately after DB write, before UI reset ──
            self._refresh_unsynced_badge()
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

    def _print_receipt_for_sale(self, sale: dict):
        """Reprint a sales invoice via printing_service (same path as original print)."""
        try:
            from models.receipt import ReceiptData, Item
            from models.company_defaults import get_defaults
            from services.printing_service import printing_service
            import json
            from pathlib import Path

            co = get_defaults() or {}

            receipt = ReceiptData(
                doc_type        = "receipt",
                receiptType     = sale.get("receipt_type", "Invoice"),
                companyName     = co.get("company_name", ""),
                companyAddress  = co.get("address_1", ""),
                companyAddressLine1 = co.get("address_2", ""),
                companyEmail    = co.get("email", ""),
                tel             = co.get("phone", ""),
                tin             = co.get("tin_number", ""),
                vatNo           = co.get("vat_number", ""),
                deviceSerial    = co.get("zimra_serial_no", ""),
                deviceId        = co.get("zimra_device_id", ""),
                invoiceNo       = sale.get("invoice_no", ""),
                invoiceDate     = sale.get("invoice_date", "") or sale.get("date", ""),
                cashierName     = sale.get("cashier_name", ""),
                customerName    = sale.get("customer_name", "") or "Walk-in",
                customerContact = sale.get("customer_contact", ""),
                grandTotal      = float(sale.get("total", 0)),
                subtotal        = float(sale.get("subtotal", 0) or sale.get("total", 0)),
                totalVat        = float(sale.get("total_vat", 0)),
                amountTendered  = float(sale.get("tendered", 0) or sale.get("total", 0)),
                change          = float(sale.get("change_amount", 0)),
                discAmt         = float(sale.get("discount_amount", 0)),
                paymentMode     = sale.get("method", "CASH"),
                currency        = sale.get("currency", "USD"),
                footer          = co.get("footer_text", "Thank you for your purchase!"),
            )

            for it in sale.get("items", []):
                qty   = float(it.get("qty", 1))
                price = float(it.get("price", 0))
                total = float(it.get("total", 0) or qty * price)
                receipt.items.append(Item(
                    productName = it.get("product_name", "") or it.get("item_name", ""),
                    productid   = it.get("part_no", "") or it.get("item_code", ""),
                    qty         = qty,
                    price       = price,
                    amount      = total,
                    tax_amount  = float(it.get("tax_amount", 0)),
                ))
            receipt.itemlist = receipt.items

            # resolve printer
            hw_file = Path("app_data/hardware_settings.json")
            printers = []
            try:
                with open(hw_file, "r", encoding="utf-8") as f:
                    hw = json.load(f)
                if hw.get("main_printer") and hw["main_printer"] != "(None)":
                    printers.append(hw["main_printer"])
            except Exception:
                pass

            if not printers:
                QMessageBox.warning(self, "No Printer", "No active printer configured in hardware settings.")
                return

            ok = False
            for p in printers:
                if printing_service.print_receipt(receipt, printer_name=p):
                    ok = True
            if ok:
                QMessageBox.information(self, "Reprint", f"Invoice {sale.get('invoice_no', '')} sent to printer.")
            else:
                QMessageBox.warning(self, "Reprint Failed", "Printing failed. Check printer connection.")
        except Exception as e:
            QMessageBox.warning(self, "Reprint Error", f"Could not reprint:\n{e}")

    def _reprint_by_invoice_no(self):
        """Open the ReprintDialog — autocomplete invoice search then reprint."""
        if not self._check_permission("allow_reprint", "Reprint Invoice"):
            return
        dlg = ReprintDialog(self)
        dlg.exec()

    def _open_payment(self):
        if not self._check_permission("allow_receipt", "Process Payment / Print Receipt"):
            return
        try:
            total = float(self._lbl_total.text() or "0")
        except ValueError:
            total = 0.0
            
        if total <= 0:
            QMessageBox.warning(self, "Empty Invoice", "Add items before payment.")
            return

        # Pass the full database dictionary of the selected customer
        # This allows the PaymentDialog to access customer IDs, group settings, or credit limits
        if _HAS_PAYMENT_DIALOG:
            dlg = _ExternalPaymentDialog(self, total=total, customer=self._selected_customer)
        else:
            dlg = PaymentDialog(self, total=total, customer=self._selected_customer)

        if dlg.exec() == QDialog.Accepted:
            items = self._collect_invoice_items()
            
            # Extract data from the Dialog results
            if hasattr(dlg, "accepted_tendered"):
                tendered       = dlg.accepted_tendered
                method         = dlg.accepted_method
                change_out     = getattr(dlg, "accepted_change", max(tendered - total, 0.0))
                # The dialog may have updated the customer (e.g., via a quick-add or picker)
                final_customer = getattr(dlg, "accepted_customer", self._selected_customer)
            else:
                try:
                    tendered = float(dlg._amt.text() or "0")
                except (ValueError, AttributeError):
                    tendered = total
                method         = getattr(dlg, "_method", "CASH")
                change_out     = max(tendered - total, 0.0)
                final_customer = self._selected_customer

            # Extract customer details from the database object
            cust_name    = final_customer.get("customer_name", "Walk-in") if final_customer else "Walk-in"
            cust_contact = final_customer.get("custom_telephone_number", "") if final_customer else ""
            company_name = getattr(dlg, "accepted_company_name", "")

            try:
                from models.sale import create_sale
                
                # Get current logged-in user context
                cashier_id   = self.user.get("id") if isinstance(self.user, dict) else None
                cashier_name = self.user.get("username", "") if isinstance(self.user, dict) else ""

                # Capture transaction-level discount BEFORE create_sale so it's persisted
                discount_pct = getattr(self, "current_discount_percent", 0.0)
                try:
                    subtotal_raw = sum(
                        float(self.invoice_table.item(r, 6).text() or "0")
                        for r in range(self.invoice_table.rowCount())
                    )
                except Exception:
                    subtotal_raw = total
                discount_amt = round(subtotal_raw * (discount_pct / 100.0), 4)

                # Save the sale to SQL Server
                sale = create_sale(
                    items=items, 
                    total=total, 
                    tendered=tendered,
                    method=method, 
                    cashier_id=cashier_id, 
                    cashier_name=cashier_name,
                    customer_name=cust_name, 
                    customer_contact=cust_contact,
                    company_name=company_name,
                    change_amount=change_out,
                    discount_percent=discount_pct,
                    discount_amount=discount_amt,
                )
                
                # ── Store local payment entry for Frappe sync ──────────
                # #6: Do NOT create a payment entry for credit/account sales —
                # those are settled later via a separate payment entry.
                try:
                    _credit_methods = {"credit", "account", "on account", "on-account"}
                    if str(method).lower().strip() not in _credit_methods:
                        from services.payment_entry_service import create_payment_entry
                        create_payment_entry(sale)
                    else:
                        import logging as _lg
                        _lg.getLogger("POSView").info(
                            "Skipped payment entry for credit/account sale %s.", sale.get("invoice_no", "")
                        )
                except Exception as _pe_err:
                    log.warning("Could not create local payment entry: %s", _pe_err)

                # ── Update UI Feedback ─────────────
                self._update_prev_txn_display(
                    paid=tendered, change=change_out,
                    invoice_no=sale.get("invoice_no", "")
                )
                
                if self.parent_window:
                    status = f"Sale #{sale['number']} saved — ${total:.2f} ({method})"
                    if cust_name and cust_name != "Walk-in": 
                        status += f" — {cust_name}"
                    self.parent_window._set_status(status)

                # ── Badge refresh: immediately after DB write, before UI reset ──
                self._refresh_unsynced_badge()

            except Exception as e:
                # _friendly_db_error is your helper in main_window.py
                QMessageBox.warning(self, "Save Error", _friendly_db_error(e))
                return

            # Clear invoice for next customer
            self._new_sale(confirm=False)
    def _open_customer_payment_entry(self):
        """Open the customer payment entry dialog.
        If no customer is selected on POS, open customer search first then proceed."""
        customer = self._selected_customer

        if not customer:
            # No customer on invoice — open search so cashier picks one first
            dlg_search = CustomerSearchPopup(self)
            if dlg_search.exec() != QDialog.Accepted or not dlg_search.selected_customer:
                return   # cashier cancelled
            customer = dlg_search.selected_customer

        dlg = CustomerPaymentDialog(self, customer=customer)
        if dlg.exec() == QDialog.Accepted:
            if self.parent_window:
                cname = dlg._customer.get("customer_name", "") if dlg._customer else ""
                self.parent_window._set_status(
                    f"Payment recorded for {cname}.")
    
    
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

    def _refresh_unsynced_badge(self):
        """Update the Unsynced badge: sales + credit notes + laybye orders pending sync."""
        try:
            from models.sale import get_all_sales
            sales    = get_all_sales()
            unsynced = sum(1 for s in sales if not s.get("synced"))
        except Exception:
            unsynced = 0
        try:
            from database.db import get_connection
            conn = get_connection(); cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM credit_notes "
                "WHERE cn_status IN ('ready','pending_sync')")
            row = cur.fetchone(); conn.close()
            cn_pending = int(row[0] or 0) if row else 0
        except Exception:
            cn_pending = 0
        # Laybye / Sales Orders pending sync
        so_pending = 0
        if _HAS_SALES_ORDER:
            try:
                so_pending = len(_get_unsynced_so())
            except Exception:
                so_pending = 0

        total_pending = unsynced + cn_pending + so_pending

        # Build label: show each component only when non-zero
        parts = []
        if unsynced:   parts.append(f"{unsynced} SI")
        if cn_pending: parts.append(f"{cn_pending} CN")
        if so_pending: parts.append(f"{so_pending} SO")
        text = f"⏳ Q: {' + '.join(parts)}" if parts else "⏳ Q: 0"

        if total_pending == 0:
            bg, hov = NAVY_2, NAVY_3
        elif total_pending < 5:
            bg, hov = AMBER, ORANGE
        else:
            bg, hov = DANGER, DANGER_H
        self._unsynced_badge.setText(text)
        self._unsynced_badge.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg}; color: {WHITE}; border: none;
                border-radius: 3px; font-size: 11px; font-weight: bold; padding: 0 8px;
            }}
            QPushButton:hover {{ background-color: {hov}; }}
        """)

    # =========================================================================
    # RETURN / CREDIT NOTE MODE
    # =========================================================================
    def _open_credit_note_dialog(self):
        if not self._check_permission("allow_credit_note", "Create Credit Notes"):
            return
        dlg = CreditNoteDialog(self)
        dlg.credit_note_ready.connect(self._load_credit_note_into_table)
        dlg.exec()

    def _load_credit_note_into_table(self, cn):
        items = cn.get("items_to_return", cn.get("items", []))
        if not items:
            return
        self._block_signals = True
        self.invoice_table.setRowCount(max(20, len(items) + 5))
        for r in range(self.invoice_table.rowCount()):
            self._init_row(r)
        self._block_signals = False
        for i, item in enumerate(items):
            self._ensure_rows(i + 1)
            self._block_signals = True
            vals = [
                item.get("part_no", ""),
                item.get("product_name", ""),
                f"{float(item.get('price', 0)):.2f}",
                f"{float(item.get('qty', 0)):.0f}",
                f"{float(item.get('discount', 0)):.0f}",
                item.get("tax", ""),
                f"{float(item.get('total', 0)):.2f}",
            ]
            for c, val in enumerate(vals):
                cell = self.invoice_table.item(i, c)
                if cell:
                    cell.setText(str(val))
                    cell.setForeground(QColor(DANGER))
                    cell.setBackground(QColor("#fff0f0"))
            self._block_signals = False
            self.invoice_table.setRowHeight(i, 20)
        self._return_mode = True
        self._return_cn = cn
        self._return_btn.setVisible(True)
        self._recalc_totals()
        red = (" QHeaderView::section { background-color: "
               + DANGER + "; color: " + WHITE + "; }")
        self.invoice_table.setStyleSheet(
            self.invoice_table.styleSheet() + red)
        cust = cn.get("customer_name", "")
        if cust:
            self._cust_btn.setText(f"↩  {cust}  (RETURN)")
            self._cust_btn.setStyleSheet(
                "QPushButton { background-color: " + DANGER
                + "; color: " + WHITE + "; border: none;"
                " border-radius: 3px; font-size: 11px;"
                " font-weight: bold; padding: 0 8px; }"
            )
        if self.parent_window:
            self.parent_window._set_status(
                f"RETURN MODE  ·  Return: {cn.get('invoice_no', '')}")

    def _exit_return_mode(self):
        self._return_mode = False
        self._return_cn = None
        self._return_btn.setVisible(False)
        norm = (
            "QTableWidget { background-color: " + WHITE
            + "; color: " + NAVY + ";"
            " border: 1px solid " + BORDER
            + "; gridline-color: " + LIGHT + ";"
            " font-size: 12px; outline: none;"
            " selection-background-color: transparent; }"
            "QTableWidget::item { padding: 0 4px; color: " + NAVY
            + "; border-bottom: 1px solid " + LIGHT + "; }"
            "QTableWidget::item:selected { background-color: #fff8e1;"
            " color: " + NAVY + "; border: 1px solid #f9a825; }"
            "QHeaderView::section { background-color: #f0e8d0;"
            " color: " + NAVY + ";"
            " padding: 4px 6px; border: none;"
            " border-right: 1px solid " + BORDER + ";"
            " font-size: 10px; font-weight: bold;"
            " letter-spacing: 0.3px; }"
        )
        self.invoice_table.setStyleSheet(norm)

    def _process_return(self):
        """Return button — returns exactly what is currently in the invoice table."""
        if not self._return_mode or not self._return_cn:
            return
        cn = self._return_cn

        # Read what is CURRENTLY in the table (cashier may have deleted/changed qty)
        items = []
        for r in range(self.invoice_table.rowCount()):
            try:
                qty = float(self.invoice_table.item(r, 3).text() or "0")
            except (ValueError, AttributeError):
                qty = 0.0
            if qty <= 0:
                continue
            try:
                part_no  = self.invoice_table.item(r, 0).text()
                name     = self.invoice_table.item(r, 1).text()
                price    = float(self.invoice_table.item(r, 2).text() or "0")
                total_ln = float(self.invoice_table.item(r, 6).text() or "0")
                product_id = self.invoice_table.item(r, 0).data(Qt.UserRole)
            except (ValueError, AttributeError):
                continue
            items.append({
                "part_no":      part_no,
                "product_name": name,
                "qty":          qty,
                "price":        price,
                "total":        total_ln,
                "product_id":   product_id,
            })

        if not items:
            QMessageBox.warning(self, "Nothing to Return",
                                "The table is empty. Add items to return.")
            return

        total = sum(i["total"] for i in items)
        reply = QMessageBox.question(
            self, "Confirm Return",
            f"Process return for {cn.get('invoice_no', '')}?\n"
            f"Customer: {cn.get('customer_name', 'Walk-in')}\n"
            f"Items: {len(items)}   Credit: ${total:.2f}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        cashier_name = self.user.get("username", "") if isinstance(self.user, dict) else ""
        try:
            from models.credit_note import create_credit_note
            create_credit_note(
                original_sale_id=cn["id"],
                items_to_return=items,
                currency=cn.get("currency", "USD"),
                customer_name=cn.get("customer_name", ""),
                cashier_name=cashier_name,
            )
        except Exception as e:
            QMessageBox.warning(self, "Credit Note Error", str(e))
            return

        if self.parent_window:
            self.parent_window._set_status(
                f"Return processed  ·  {cn.get('invoice_no', '')}  ·  ${total:.2f}")
        # ── Badge refresh: immediately after DB write, before UI reset ──
        self._refresh_unsynced_badge()
        self._new_sale(confirm=False)

    def _new_sale(self, confirm=True):
        if confirm:
            reply = QMessageBox.question(self, "New Sale", "Clear the current invoice and start a new sale?", QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes: return
        self._block_signals = True
        self.invoice_table.setRowCount(20)
        for r in range(20): self._init_row(r)
        self._block_signals = False
        self._exit_return_mode()
        self._numpad_buffer           = ""
        self._active_row              = 0
        self._active_col              = 0
        self._last_filled_row         = -1
        self.current_discount_percent = 0.0   # ← Reset discount for next customer
        self._reset_customer_btn()
        self._recalc_totals()
        self._highlight_active_row(0)
        self.invoice_table.setCurrentCell(0, 0)
        self.invoice_table.setFocus()
        self._open_inline_search(0, 0)
        if self.parent_window:
            self.parent_window._set_status("New sale started.")

    # =========================================================================
    # DISCOUNT (F4 / % button)
    # =========================================================================
    def _on_discount_clicked(self):
        """Traffic controller for the Discount (%) button and F4 key."""
        from PySide6.QtWidgets import QInputDialog, QLineEdit
        from models.user import authenticate_by_pin

        # ── 1. Find which row to discount ────────────────────────────────────
        # Prefer the internally-tracked active row; fall back to Qt selection
        row = getattr(self, '_active_row', -1)
        if row < 0:
            row = self.invoice_table.currentRow()

        print(f"[discount] _active_row={getattr(self,'_active_row',-1)}  currentRow={self.invoice_table.currentRow()}  using row={row}")

        # ── 2. Validate the row has a product ────────────────────────────────
        if row < 0:
            QMessageBox.information(self, "No Item Selected", "Please select a cart line first.")
            return

        item_check = self.invoice_table.item(row, 1)
        has_product = bool(item_check and item_check.text().strip())
        print(f"[discount] row={row}  col1 text='{item_check.text() if item_check else None}'  has_product={has_product}")

        if not has_product:
            QMessageBox.information(self, "Empty Row", "Please select a row that has a product.")
            return

        # ── 3. Get current user ───────────────────────────────────────────────
        current_user = (getattr(self, 'user', None)
                        or (getattr(self.parent_window, 'user', {}) if self.parent_window else {}))
        print(f"[discount] user={current_user}")

        can_disc = current_user.get("allow_discount", False)
        limit    = current_user.get("max_discount_percent", 0) or 0

        # ── 4. Permission / admin PIN bypass ─────────────────────────────────
        if not can_disc:
            pin, ok = QInputDialog.getText(
                self, "Authorization",
                "Manager PIN required for discount:",
                QLineEdit.Password
            )
            if not ok or not pin:
                return
            manager = authenticate_by_pin(pin)
            if not manager or manager.get("role") != "admin":
                QMessageBox.critical(self, "Access Denied", "Invalid Manager PIN.")
                return
            limit = 100

        # ── 5. Read existing value to pre-fill ───────────────────────────────
        existing = self.invoice_table.item(row, 4)
        current_val = 0.0
        if existing and existing.text().strip():
            try:
                current_val = float(existing.text().replace('%', '').strip())
            except (ValueError, AttributeError):
                current_val = 0.0

        print(f"[discount] can_disc={can_disc}  limit={limit}  current_val={current_val}")

        # ── 6. Get line total for conversion ─────────────────────────────────
        try:
            line_price = float(self.invoice_table.item(row, 2).text() or "0")
            line_qty   = float(self.invoice_table.item(row, 3).text() or "1")
            line_total = line_price * line_qty
        except (ValueError, AttributeError):
            line_total = 0.0

        # ── 7. Custom discount dialog ─────────────────────────────────────────
        disc_dlg = QDialog(self)
        disc_dlg.setWindowTitle("Apply Discount")
        disc_dlg.setFixedSize(400, 260)
        disc_dlg.setWindowFlags(
            disc_dlg.windowFlags()
            & ~Qt.WindowMinimizeButtonHint
            & ~Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )
        disc_dlg.setStyleSheet(f"""
            QDialog   {{ background: {WHITE}; }}
            QLabel    {{ background: transparent; color: {DARK_TEXT}; }}
            QLineEdit {{
                background: {WHITE}; color: {DARK_TEXT};
                border: 2px solid {BORDER}; border-radius: 6px;
                padding: 8px 12px; font-size: 20px; font-weight: bold;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)

        dlg_lay = QVBoxLayout(disc_dlg)
        dlg_lay.setContentsMargins(24, 20, 24, 20)
        dlg_lay.setSpacing(12)

        title_lbl = QLabel("🏷  Apply Discount")
        title_lbl.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {NAVY};")
        dlg_lay.addWidget(title_lbl)
        dlg_lay.addWidget(hr())

        # Toggle: Fixed Amount / Percentage
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(0)
        btn_amt = QPushButton("Fixed Amount")
        btn_pct = QPushButton("Percentage  %")
        for b in (btn_amt, btn_pct):
            b.setFixedHeight(34)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)

        def _style_toggle():
            on  = f"background:{ACCENT}; color:{WHITE}; border:none; font-weight:bold; font-size:12px;"
            off = f"background:{LIGHT}; color:{DARK_TEXT}; border:1px solid {BORDER}; font-size:12px;"
            btn_amt.setStyleSheet(f"QPushButton {{ {on if btn_amt.isChecked() else off} border-radius:0; border-top-left-radius:6px; border-bottom-left-radius:6px; padding:0 16px; }}")
            btn_pct.setStyleSheet(f"QPushButton {{ {on if btn_pct.isChecked() else off} border-radius:0; border-top-right-radius:6px; border-bottom-right-radius:6px; padding:0 16px; }}")

        btn_amt.setChecked(True)
        _style_toggle()

        def _pick_amt():
            btn_amt.setChecked(True); btn_pct.setChecked(False); _style_toggle()
            hint_lbl.setText(f"Enter discount amount  (line total: ${line_total:.2f})")

        def _pick_pct():
            btn_pct.setChecked(True); btn_amt.setChecked(False); _style_toggle()
            hint_lbl.setText(f"Enter % between 0 and {limit}%  — will be converted to amount")

        btn_amt.clicked.connect(_pick_amt)
        btn_pct.clicked.connect(_pick_pct)
        toggle_row.addWidget(btn_amt)
        toggle_row.addWidget(btn_pct)
        dlg_lay.addLayout(toggle_row)

        disc_input = QLineEdit()
        disc_input.setPlaceholderText("0")
        disc_input.setText(f"{current_val:.2f}" if current_val else "")
        disc_input.selectAll()
        dlg_lay.addWidget(disc_input)

        hint_lbl = QLabel(f"Enter discount amount  (line total: ${line_total:.2f})")
        hint_lbl.setStyleSheet(f"font-size: 11px; color: {MUTED};")
        dlg_lay.addWidget(hint_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        apply_btn  = navy_btn("Apply",  height=40, color=SUCCESS, hover=SUCCESS_H)
        cancel_btn = navy_btn("Cancel", height=40, color=NAVY_2,  hover=NAVY_3)
        btn_row.addStretch()
        btn_row.addWidget(apply_btn)
        btn_row.addWidget(cancel_btn)
        dlg_lay.addLayout(btn_row)

        apply_btn.clicked.connect(disc_dlg.accept)
        cancel_btn.clicked.connect(disc_dlg.reject)
        disc_input.returnPressed.connect(disc_dlg.accept)
        disc_input.setFocus()

        if disc_dlg.exec() != QDialog.Accepted:
            return

        try:
            raw = float(disc_input.text().strip() or "0")
        except ValueError:
            QMessageBox.warning(self, "Invalid", "Please enter a valid number.")
            return

        # Always store as a fixed amount figure
        if btn_pct.isChecked():
            # Convert % → amount
            if raw < 0 or raw > float(limit):
                QMessageBox.warning(self, "Out of Range", f"Percentage must be 0 – {limit}%.")
                return
            disc_amount = line_total * (raw / 100.0)
            msg = f"Discount {raw:.2f}% (${disc_amount:.2f}) applied to row {row+1}." if raw > 0 else "Discount cleared."
        else:
            disc_amount = raw
            if disc_amount < 0 or (line_total > 0 and disc_amount > line_total):
                QMessageBox.warning(self, "Out of Range", f"Amount must be 0 – ${line_total:.2f}.")
                return
            msg = f"Discount ${disc_amount:.2f} applied to row {row+1}." if disc_amount > 0 else "Discount cleared."

        print(f"[discount] dialog result: disc_amount={disc_amount:.2f}")

        # ── 8. Write plain amount to col 4 and recalc ────────────────────────
        disc_item = QTableWidgetItem(f"{disc_amount:.2f}")
        disc_item.setTextAlignment(Qt.AlignCenter)
        if disc_amount > 0:
            disc_item.setForeground(QColor("#e67e22"))
            bold = QFont(); bold.setBold(True)
            disc_item.setFont(bold)
        else:
            disc_item.setForeground(QColor(NAVY))

        self.invoice_table.setItem(row, 4, disc_item)
        self._recalc_row(row)
        self._recalc_totals()

        print(f"[discount] {msg}")
        if self.parent_window:
            self.parent_window._set_status(msg)

    def _quick_tender(self, _amount):
        pass  # no-op

    # =========================================================================
    # LAYBYE FLOW
    # =========================================================================
    def _on_laybye(self):
        """
        Full Laybye flow:
          1. Collect current cart items.
          2. Show LaybyeConfirmDialog — forces cashier to select a named customer.
          3. Show LaybyePaymentDialog — deposit (optional) + delivery date + order type.
          4. Save to sales_order table locally (synced=0).
          5. Refresh unsynced badge → ERPNext sync picks it up in background.
        """
        if not _HAS_LAYBYE:
            QMessageBox.warning(self, "Not Available",
                                "Laybye dialogs could not be loaded.\n"
                                "Ensure laybye_confirm_dialog.py and "
                                "laybye_payment_dialog.py are in views/dialogs/.")
            return

        # ── 1. Collect cart ──────────────────────────────────────────────────
        cart_items = self._collect_invoice_items()
        if not cart_items:
            QMessageBox.information(self, "Empty Cart",
                                    "Add items to the cart before saving a Laybye.")
            return

        try:
            cart_total = float(self._lbl_total.text() or "0")
        except ValueError:
            cart_total = sum(float(it.get("total", 0)) for it in cart_items)

        if cart_total <= 0:
            QMessageBox.information(self, "Zero Total",
                                    "Cart total is zero — add items before saving a Laybye.")
            return

        # ── 2. Confirmation + customer selection ─────────────────────────────
        # Pass the currently-selected customer (may be None / walk-in).
        # LaybyeConfirmDialog will force the cashier to pick a real one.
        confirm_dlg = LaybyeConfirmDialog(
            parent=self,
            cart_items=cart_items,
            cart_total=cart_total,
            customer=self._selected_customer,   # dict, not name string
        )
        if confirm_dlg.exec() != LaybyeConfirmDialog.Accepted:
            return

        # Customer is now guaranteed to be a real named customer
        confirmed_customer = confirm_dlg.selected_customer

        # ── 3. Deposit dialog ────────────────────────────────────────────────
        deposit_dlg = LaybyePaymentDialog(
            parent=self,
            total=cart_total,
            customer=confirmed_customer,
        )
        if deposit_dlg.exec() != LaybyePaymentDialog.Accepted:
            return

        deposit_amount = deposit_dlg.deposit_amount
        deposit_method = deposit_dlg.deposit_method
        company_name   = deposit_dlg.accepted_company_name
        delivery_date  = deposit_dlg.delivery_date
        order_type     = deposit_dlg.order_type

        # ── 4. Save Sales Order to local DB ─────────────────────────────────
        if not _HAS_SALES_ORDER:
            QMessageBox.critical(self, "DB Error",
                                 "models/sales_order.py not found — cannot save Laybye.")
            return

        # Map cart item keys to what create_sales_order expects
        so_items = []
        for it in cart_items:
            so_items.append({
                "item_code":  it.get("part_no", ""),
                "item_name":  it.get("product_name", ""),
                "qty":        it.get("qty", 1),
                "rate":       it.get("price", 0.0),
                "amount":     it.get("total", 0.0),
            })

        try:
            order_id = _create_sales_order(
                cart_items     = so_items,
                total          = cart_total,
                deposit_amount = deposit_amount,
                deposit_method = deposit_method,
                customer       = confirmed_customer,
                company        = company_name,
                delivery_date  = delivery_date,
                order_type     = order_type,
            )
        except Exception as e:
            QMessageBox.critical(self, "Save Failed",
                                 f"Could not save Laybye:\n{_friendly_db_error(e)}")
            return

        # ── 4b. Queue deposit payment entry for ERPNext sync ─────────────────
        if deposit_amount and deposit_amount > 0:
            try:
                from services.laybye_payment_entry_service import create_laybye_payment_entry
                create_laybye_payment_entry(_get_order_by_id(order_id))
            except Exception as _lpe:
                import logging as _lg
                _lg.getLogger("Laybye").warning("Laybye payment entry skipped: %s", _lpe)

        # ── 4c. Print deposit slip ────────────────────────────────────────────────────────
        if _HAS_SO_PRINT:
            try:
                _print_laybye_deposit(order_id)
            except Exception as _pe:
                import logging as _lg
                _lg.getLogger("Laybye").warning("Laybye print failed: %s", _pe)

        # ── 5. Feedback + clear cart ─────────────────────────────────────────
        balance   = round(cart_total - deposit_amount, 2)
        cust_name = (confirmed_customer or {}).get("customer_name", "")
        QMessageBox.information(
            self, "Laybye Saved ✔",
            f"Laybye saved successfully!\n\n"
            f"  Customer    :  {cust_name}\n"
            f"  Order Total :  ${cart_total:.2f}\n"
            f"  Deposit Paid:  ${deposit_amount:.2f}\n"
            f"  Balance Due :  ${balance:.2f}\n"
            f"  Delivery    :  {delivery_date}\n"
            f"  Order Type  :  {order_type}\n\n"
            "The order is queued for ERPNext sync."
        )

        self._refresh_unsynced_badge()
        self._new_sale(confirm=False)
        if self.parent_window:
            self.parent_window._set_status(
                f"Laybye #{order_id}  {cust_name}  "
                f"Total ${cart_total:.2f}  Deposit ${deposit_amount:.2f}"
            )


# =============================================================================
# MAIN WINDOW
# =============================================================================
class MainWindow(QMainWindow):
    # Class-level socket — lives for the entire process lifetime.
    # Never released on logout so re-login never drops the lock.
    _instance_sock = None

    @staticmethod
    def _acquire_instance_lock() -> bool:
        """
        Bind the sentinel port once per process.
        Returns True if this is the first (and only) instance.
        Returns False if another EXE already owns the port.
        Safe to call multiple times (re-login path): if already bound,
        returns True immediately without touching the socket.
        """
        import socket as _socket
        if MainWindow._instance_sock is not None:
            return True   # already locked by this process
        sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 0)
        try:
            sock.bind(("127.0.0.1", 47634))
            MainWindow._instance_sock = sock   # keep alive at class level
            return True
        except OSError:
            try:
                sock.close()
            except Exception:
                pass
            return False

    def __init__(self, user=None):
        super().__init__()

        # Single-instance guard — works correctly across logout/re-login cycles
        # because the socket lives at class level, not on self.
        if not MainWindow._acquire_instance_lock():
            from PySide6.QtWidgets import QMessageBox as _MB
            _MB.warning(None, "Already Running",
                        "Havano POS is already open.\nPlease use the existing window.")
            import sys; sys.exit(0)

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
        self.menuBar().setVisible(False)   # #30/#34 — top menubar hidden; all actions via white nav bar

        self._status_bar = QStatusBar()
        self._status_bar.setSizeGripEnabled(False)
        self._status_bar.showMessage("  Ready")
        self.setStatusBar(self._status_bar)

        # #37 — logged-in user in footer
        _uname = self.user.get("username", "")
        _urole = self.user.get("role", "cashier")
        _user_lbl = QLabel(f"  👤 {_uname} [{_urole.upper()}]  ")
        _user_lbl.setStyleSheet(f"color: {MID}; font-size: 11px; background: transparent;")
        self._status_bar.addPermanentWidget(_user_lbl)

        _sep1 = QLabel("|")
        _sep1.setStyleSheet(f"color: {NAVY_2}; background: transparent;")
        self._status_bar.addPermanentWidget(_sep1)

        # #38 — server URL in footer
        try:
            from services.site_config import get_host_label as _ghl
            _srv = _ghl()
        except Exception:
            _srv = "—"
        _srv_lbl = QLabel(f"  🌐 {_srv}  ")
        _srv_lbl.setStyleSheet(f"color: {MID}; font-size: 11px; background: transparent;")
        self._status_bar.addPermanentWidget(_srv_lbl)

        _sep2 = QLabel("|")
        _sep2.setStyleSheet(f"color: {NAVY_2}; background: transparent;")
        self._status_bar.addPermanentWidget(_sep2)

        # #39 — SQL connection string in footer
        _sql = ""
        try:
            from database.db import get_connection as _gc
            _conn = _gc()
            try: _sql = _conn.getinfo(2)
            except Exception: pass
            _conn.close()
        except Exception:
            pass
        if not _sql:
            try:
                from models.company_defaults import get_defaults as _gd
                _d = _gd() or {}
                _sql = _d.get("db_server", "") or _d.get("server", "") or "localhost"
            except Exception:
                _sql = "localhost"
        _sql_lbl = QLabel(f"  🗄 {_sql}  ")
        _sql_lbl.setStyleSheet(f"color: {MID}; font-size: 11px; background: transparent;")
        self._status_bar.addPermanentWidget(_sql_lbl)

        # #18 — everyone lands on POS first, always
        self._stack.setCurrentIndex(0)

        # ── Background sync services ──────────────────────────────────────────
        # Product sync (every 5 min) — keeps local product list up to date
        try:
            from services.sync_service import SyncWorker
            from PySide6.QtCore import QThread
            self._product_sync_thread = QThread()
            self._product_sync_worker = SyncWorker()
            self._product_sync_worker.moveToThread(self._product_sync_thread)
            self._product_sync_thread.started.connect(self._product_sync_worker.run)
            self._product_sync_thread.start()
        except Exception as _e:
            import logging
            logging.getLogger("MainWindow").warning(
                "Product sync service could not start: %s", _e)

        # POS upload (every 60 s) — pushes local unsynced sales → Frappe
        try:
            from services.pos_upload_service import start_upload_thread
            self._upload_worker = start_upload_thread()
        except Exception as _e:
            import logging
            logging.getLogger("MainWindow").warning(
                "POS upload service could not start: %s", _e)

        # Payment entry sync — pushes local payment entries → Frappe
        try:
            from services.payment_entry_service import start_payment_sync_daemon
            self._payment_sync = start_payment_sync_daemon()
        except Exception as _e:
            import logging
            logging.getLogger("MainWindow").warning(
                "Payment entry sync could not start: %s", _e)

        # Accounts + exchange rates sync (hourly)
        try:
            from services.accounts_sync_service import start_accounts_sync_daemon
            self._accounts_sync = start_accounts_sync_daemon()
        except Exception as _e:
            import logging
            logging.getLogger("MainWindow").warning(
                "Accounts sync could not start: %s", _e)

        # Credit note sync (every 60s) -- pushes ready CNs to Frappe
        try:
            from services.credit_note_sync_service import start_credit_note_sync_daemon
            self._cn_sync = start_credit_note_sync_daemon()
        except Exception as _e:
            import logging
            logging.getLogger("MainWindow").warning(
                "Credit note sync could not start: %s", _e)

        # Sales Order (Laybye) sync — pushes unsynced SOs → ERPNext
        try:
            from services.sales_order_upload_service import start_so_upload_thread
            self._so_upload_thread = start_so_upload_thread()
        except Exception as _e:
            import logging
            logging.getLogger("MainWindow").warning(
                "Sales Order upload service could not start: %s", _e)

        # ── One-shot startup sync (runs immediately in background on login) ──
        # Fires once right after MainWindow opens so products, customers,
        # users, accounts and exchange rates are all refreshed without the
        # cashier having to click anything manually.
        QTimer.singleShot(2000, self._run_startup_sync)   # 2 s delay lets the
        # UI finish rendering before the network calls start.

    # =========================================================================
    # STARTUP SYNC — runs once on login, in a background thread so the UI
    # stays fully responsive.  Every sync function is already daemon-safe;
    # we just call them once up-front so the cashier never has to manually
    # trigger "Sync Cloud".
    # =========================================================================
    def _run_startup_sync(self):
        """
        Called automatically 2 seconds after MainWindow opens.
        Runs every sync in a single background QThread so none of them
        block the UI.  Errors are logged and silently swallowed — the
        periodic daemons will retry on their own schedules.
        """
        import logging
        log = logging.getLogger("StartupSync")

        from PySide6.QtCore import QThread

        class _StartupSyncWorker(QThread):
            def run(self_inner):                          # noqa: N805
                log.info("[startup-sync] Starting full sync on login…")

                # 1. Accounts + exchange rates  (needed first: other syncs
                #    may depend on company_currency from defaults)
                try:
                    from services.accounts_sync_service import sync_accounts_and_rates
                    r = sync_accounts_and_rates()
                    log.info("[startup-sync] Accounts: %d  Rates: %d",
                             r.get("accounts", 0), r.get("rates", 0))
                except Exception as exc:
                    log.warning("[startup-sync] Accounts/rates error: %s", exc)

                # 2. Products  (largest payload — run second so accounts are
                #    already in DB if any product logic needs them)
                try:
                    from services.sync_service import sync_products, _read_credentials
                    api_key, api_secret = _read_credentials()
                    if api_key and api_secret:
                        r = sync_products(api_key=api_key, api_secret=api_secret)
                        log.info(
                            "[startup-sync] Products: %d inserted, %d updated, %d skipped",
                            r.get("products_inserted", 0),
                            r.get("products_updated",  0),
                            r.get("skipped", 0),
                        )
                    else:
                        log.warning("[startup-sync] No credentials — product sync skipped.")
                except Exception as exc:
                    log.warning("[startup-sync] Products error: %s", exc)

                # 3. Customers
                try:
                    from services.customer_sync_service import sync_customers
                    sync_customers()
                    log.info("[startup-sync] Customers synced.")
                except Exception as exc:
                    log.warning("[startup-sync] Customers error: %s", exc)

                # 4. Users
                try:
                    from services.user_sync_service import sync_users
                    r = sync_users()
                    log.info(
                        "[startup-sync] Users: %d synced, %d skipped, %d errors",
                        r.get("synced", 0), r.get("skipped", 0), r.get("errors", 0),
                    )
                except Exception as exc:
                    log.warning("[startup-sync] Users error: %s", exc)

                # 5. Invoice back-matching  (links Frappe SI names to local sales)
                try:
                    from services.invoice_sync_services import sync_invoices_from_frappe
                    r = sync_invoices_from_frappe()
                    log.info(
                        "[startup-sync] Invoices: %d matched, %d already set, %d unmatched",
                        r.get("matched", 0), r.get("already_set", 0), r.get("unmatched", 0),
                    )
                except Exception as exc:
                    log.warning("[startup-sync] Invoices error: %s", exc)

                log.info("[startup-sync] ✅ All startup syncs complete.")

        self._startup_sync_thread = _StartupSyncWorker(self)
        self._startup_sync_thread.start()

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

        # ── POS ───────────────────────────────────────────────────────────────
        pos_menu = mb.addMenu("POS")
        for label, fn in [
            ("New Sale",               lambda: (self.switch_to_pos(), self._pos_view._new_sale())),
            ("Sales List",             self._pos_view._open_sales_list),
            (None, None),
            ("Customer Payment Entry", self._pos_view._open_customer_payment_entry),
            ("Create Credit Note",     lambda: CreditNoteDialog(self).exec()),
            ("Credit Note Sync",       lambda: CreditNoteManagerDialog(self).exec()),
            (None, None),
            ("X-Report",               self._open_pos_reports),
        ]:
            if label is None:
                pos_menu.addSeparator()
            else:
                a = QAction(label, self); a.triggered.connect(fn); pos_menu.addAction(a)

        # ── Maintenance (#30 #34 #35 — single menu, replaces Settings) ────────
        maint = mb.addMenu("Maintenance")
        for label, fn in [
            ("🏢 Companies",         lambda: CompanyDialog(self).exec()),
            ("👥 Customer Groups",   lambda: CustomerGroupDialog(self).exec()),
            ("🏭 Warehouses",        lambda: WarehouseDialog(self).exec()),
            ("💰 Cost Centers",      lambda: CostCenterDialog(self).exec()),
            ("🏷 Price Lists",       lambda: PriceListDialog(self).exec()),
            ("👤 Customers",         lambda: CustomerDialog(self).exec()),
            ("🧑‍💼 Users",            lambda: UserManagementPage(self, current_user=self.user).exec() if hasattr(UserManagementPage, 'exec') else coming_soon(self, "Users")),
            (None, None),
            ("📅 Day Shift",         self._pos_view._open_day_shift),
            ("⏳ Sync Queue",        self._pos_view._open_sales_list),
            (None, None),
            ("📦 Stock File",        self._pos_view._open_stock_file),
            (None, None),
            ("🖨 Advanced Printing", lambda: AdvanceSettingsDialog(self).exec()),
            (None, None),
            ("🛡 POS Rules",         lambda: POSRulesDialog(self).exec()),
            (None, None),
            ("Products",             lambda: coming_soon(self, "Products")),
            ("Tax Settings",         lambda: coming_soon(self, "Tax Settings")),
            ("Printer Setup",        lambda: coming_soon(self, "Printer Setup")),
            ("Backup",               lambda: coming_soon(self, "Backup")),
        ]:
            if label is None:
                maint.addSeparator()
            else:
                a = QAction(label, self); a.triggered.connect(fn); maint.addAction(a)
    
    def _open_pos_reports(self):
        """Requirement 5 & 7: Launches the Reporting Center"""
        from views.dialogs.pos_reports import POSReportsDialog
        POSReportsDialog(self).exec()

    def _release_instance_lock(self):
        # The class-level socket is intentionally kept alive for the whole
        # process lifetime so that logout + re-login does NOT drop the lock
        # and allow a second instance to start.  Do nothing here.
        pass

    def closeEvent(self, event):
        # Only release the port lock when the application is genuinely closing
        # (not during a logout/re-login cycle).  We detect a re-login by
        # checking whether a next window was already created.
        if not getattr(self, "_next_window", None):
            # True exit — release so the OS port is freed immediately.
            try:
                if MainWindow._instance_sock is not None:
                    MainWindow._instance_sock.close()
                    MainWindow._instance_sock = None
            except Exception:
                pass
        super().closeEvent(event)

    def _logout(self):
        reply = QMessageBox.question(
            self, "Logout", "Logout and return to login screen?",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.hide()
            # Do NOT release the instance lock here.  The lock lives at class
            # level for the whole process.  Releasing it would let a second
            # EXE start before the login dialog finishes.
            try:
                from views.login_dialog import LoginDialog
                dlg = LoginDialog()
                if dlg.exec() == QDialog.Accepted:
                    new_win = MainWindow(user=dlg.logged_in_user)
                    new_win.show()
                    # Keep a reference so the window is not garbage-collected.
                    self._next_window = new_win
                else:
                    QApplication.quit()
            except Exception:
                QApplication.quit()
            self.close()
            
            
# =============================================================================
# CUSTOMER PAYMENT ENTRY DIALOG (Requirement 3)
# Updated with premium styled Payment Type dropdown selector
# Just deducts from customer.laybye_balance or customer.outstanding_amount
# =============================================================================
class CustomerPaymentDialog(QDialog):
    """
    Full customer payment entry dialog.
    - Customer search at top (pre-filled if selected on POS)
    - Elegant dropdown to select: Outstanding Balance vs Laybye Payment
    - Payment methods pulled from GL accounts (same as PaymentDialog)
    - Numpad for amount entry
    - Saves to local DB + queues for Frappe sync
    - Automatically deducts from customer.laybye_balance or customer.outstanding_amount
    """

    # ── colours (same palette as rest of main_window) ─────────────────────
    _NAVY      = "#0d1f3c"
    _NAVY_2    = "#162d52"
    _NAVY_3    = "#1e3d6e"
    _ACCENT    = "#1a5fb4"
    _ACCENT_H  = "#1c6dd0"
    _WHITE     = "#ffffff"
    _OFF_WHITE = "#f5f8fc"
    _LIGHT     = "#e4eaf4"
    _MID       = "#8fa8c8"
    _MUTED     = "#5a7a9a"
    _BORDER    = "#c8d8ec"
    _SUCCESS   = "#1a7a3c"
    _SUCCESS_H = "#1f9447"
    _DANGER    = "#b02020"
    _DANGER_H  = "#cc2828"
    _AMBER     = "#c05a00"
    _ORANGE    = "#b06000"

    def __init__(self, parent=None, customer=None):
        super().__init__(parent)
        self._customer   = customer   # always set — enforced by caller
        self._methods:    list[dict] = []
        self._active_method: str     = ""
        self._method_rows: dict      = {}   # label → (btn, QLineEdit)
        self._payment_type: str      = "outstanding"  # default

        self.setWindowTitle("Customer Payment Entry")
        self.setMinimumSize(820, 580)
        self.setModal(True)
        self.setWindowState(Qt.WindowMaximized)
        self.setStyleSheet(
            f"QDialog {{ background:{self._OFF_WHITE}; font-family:'Segoe UI',sans-serif; }}"
            f"QLabel   {{ background:transparent; color:{self._NAVY}; }}"
        )
        self._load_data()
        self._build_ui()
        self._refresh_balances()

    # ── data loading ──────────────────────────────────────────────────────
    def _load_data(self):
        company = ""
        try:
            from models.company_defaults import get_defaults
            company = (get_defaults() or {}).get("server_company", "")
        except Exception:
            pass

        try:
            from models.gl_account import get_all_accounts
            all_accts = get_all_accounts()
            accts = [a for a in all_accts if a.get("company") == company] or all_accts
        except Exception:
            accts = []

        seen = set()
        for a in accts:
            curr  = (a.get("account_currency") or "USD").upper()
            atype = (a.get("account_name") or a.get("name") or "Cash").strip()
            key   = (atype.lower(), curr)
            if key in seen:
                continue
            seen.add(key)
            rate = 1.0
            try:
                from models.exchange_rate import get_rate
                r = get_rate(curr, "USD")
                if r:
                    rate = float(r)
            except Exception:
                pass
            self._methods.append({"label": atype, "currency": curr, "rate": rate})

        if not self._methods:
            self._methods = [
                {"label": "Cash",       "currency": "USD", "rate": 1.0},
                {"label": "Cash (ZIG)", "currency": "ZIG", "rate": 1.0},
                {"label": "Card",       "currency": "USD", "rate": 1.0},
                {"label": "Bank / EFT", "currency": "USD", "rate": 1.0},
            ]

        if self._methods:
            self._active_method = self._methods[0]["label"]

    def _refresh_balances(self):
        """Refresh both outstanding and laybye balances from the customer record."""
        if not self._customer:
            return

        try:
            from models.customer import get_customer_by_id
            updated = get_customer_by_id(self._customer["id"])
            if updated:
                self._customer = updated

            outstanding = float(self._customer.get("outstanding_amount", 0))
            laybye = float(self._customer.get("laybye_balance", 0))

            self._lbl_outstanding_bal.setText(f"${outstanding:.2f}")
            color = self._DANGER if outstanding > 0 else self._SUCCESS
            self._lbl_outstanding_bal.setStyleSheet(
                f"font-size:13px; font-weight:bold; color:{color}; background:transparent;"
            )

            self._lbl_laybye_bal.setText(f"${laybye:.2f}")
            color = self._DANGER if laybye > 0 else self._SUCCESS
            self._lbl_laybye_bal.setStyleSheet(
                f"font-size:13px; font-weight:bold; color:{color}; background:transparent;"
            )

            # Highlight active balance card
            self._update_balance_highlights()

        except Exception as e:
            print(f"Error refreshing balances: {e}")
    def _update_balance_highlights(self):
        """Visually highlight the balance card matching the current payment type."""
        
        # Helper to simplify getting values
        cust = self._customer or {}
        outstanding = float(cust.get("outstanding_amount", 0))
        laybye = float(cust.get("laybye_balance", 0))

        # --- 1. Outstanding Card Highlight ---
        if self._payment_type == "outstanding":
            # Active State: Using Accent/Blue background
            self._card_outstanding.setStyleSheet(
                f"QFrame {{ background: {self._ACCENT}; border: 2px solid {self._ACCENT}; border-radius: 10px; }}"
            )
            self._card_outstanding_title.setStyleSheet(
                "font-size: 9px; font-weight: bold; letter-spacing: 1px; color: rgba(255,255,255,0.8); background: transparent;"
            )
            # Use a brighter white/tint when the background is already dark blue
            bal_color = "#FFFFFF" 
            self._lbl_outstanding_bal.setStyleSheet(
                f"font-size: 15px; font-weight: bold; color: {bal_color}; background: transparent;"
            )
        else:
            # Inactive State: Clean white background
            self._card_outstanding.setStyleSheet(
                f"QFrame {{ background: {self._WHITE}; border: 1.5px solid {self._BORDER}; border-radius: 10px; }}"
            )
            self._card_outstanding_title.setStyleSheet(
                f"font-size: 9px; font-weight: bold; letter-spacing: 1px; color: {self._MUTED}; background: transparent;"
            )
            bal_color = self._DANGER if outstanding > 0 else self._SUCCESS
            self._lbl_outstanding_bal.setStyleSheet(
                f"font-size: 14px; font-weight: bold; color: {bal_color}; background: transparent;"
            )

        # --- 2. Laybye Card Highlight ---
        if self._payment_type == "laybye":
            # Active State: Using Amber/Yellow background
            self._card_laybye.setStyleSheet(
                f"QFrame {{ background: {self._AMBER}; border: 2px solid {self._AMBER}; border-radius: 10px; }}"
            )
            self._card_laybye_title.setStyleSheet(
                "font-size: 9px; font-weight: bold; letter-spacing: 1px; color: rgba(0,0,0,0.6); background: transparent;"
            )
            # Darker text for Amber because white on yellow is hard to read
            self._lbl_laybye_bal.setStyleSheet(
                "font-size: 15px; font-weight: bold; color: #000000; background: transparent;"
            )
        else:
            # Inactive State
            self._card_laybye.setStyleSheet(
                f"QFrame {{ background: {self._WHITE}; border: 1.5px solid {self._BORDER}; border-radius: 10px; }}"
            )
            self._card_laybye_title.setStyleSheet(
                f"font-size: 9px; font-weight: bold; letter-spacing: 1px; color: {self._MUTED}; background: transparent;"
            )
            bal_color = self._DANGER if laybye > 0 else self._SUCCESS
            self._lbl_laybye_bal.setStyleSheet(
                f"font-size: 14px; font-weight: bold; color: {bal_color}; background: transparent;"
            )
    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)

        # header bar
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{self._WHITE}; border-bottom:2px solid {self._BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(28, 0, 28, 0)
        title = QLabel("💰  Customer Payment Entry")
        title.setStyleSheet(f"color:{self._NAVY}; font-size:17px; font-weight:bold;")
        hint = QLabel("Select payment type · Enter amount · Save")
        hint.setStyleSheet(f"color:{self._MUTED}; font-size:10px;")
        hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(hint)
        outer.addWidget(hdr)

        # customer display bar
        outer.addWidget(self._build_customer_bar())

        # body — left (methods) + right (numpad)
        body_w = QWidget()
        body_w.setStyleSheet(f"background:{self._OFF_WHITE};")
        body_l = QHBoxLayout(body_w)
        body_l.setContentsMargins(32, 20, 32, 20)
        body_l.setSpacing(28)
        body_l.addLayout(self._build_left(), stretch=5)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet(f"background:{self._BORDER}; border:none;")
        sep.setFixedWidth(1)
        body_l.addWidget(sep)

        body_l.addLayout(self._build_right(), stretch=4)
        outer.addWidget(body_w, stretch=1)

    def _build_customer_bar(self):
        """
        Customer bar with:
          • Top row  — avatar icon, name, phone/group, badge
          • Bottom row — [Payment Type Dropdown]  |  [Outstanding card]  [Laybye card]
        """
        bar = QWidget()
        bar.setFixedHeight(110)
        bar.setStyleSheet(
            f"background:{self._LIGHT}; border-bottom:1px solid {self._BORDER};"
        )
        bl = QVBoxLayout(bar)
        bl.setContentsMargins(28, 10, 28, 10)
        bl.setSpacing(10)

        # ── Top row: Customer info ────────────────────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        icon = QLabel("👤")
        icon.setStyleSheet("font-size:20px; background:transparent;")
        top_row.addWidget(icon)

        name  = self._customer.get("customer_name", "Unknown") if self._customer else "Unknown"
        phone = self._customer.get("custom_telephone_number", "") if self._customer else ""
        group = self._customer.get("customer_group_name", "") if self._customer else ""

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"font-size:15px; font-weight:bold; color:{self._NAVY}; background:transparent;"
        )
        top_row.addWidget(name_lbl)

        if phone or group:
            detail = QLabel(f"{phone}{'  ·  ' if phone and group else ''}{group}")
            detail.setStyleSheet(
                f"font-size:11px; color:{self._MUTED}; background:transparent;"
            )
            top_row.addWidget(detail)

        top_row.addStretch()

        badge = QLabel("PAYMENT ENTRY")
        badge.setStyleSheet(
            f"background:{self._ACCENT}; color:{self._WHITE}; border-radius:4px;"
            f" font-size:10px; font-weight:bold; padding:3px 10px;"
        )
        top_row.addWidget(badge)
        bl.addLayout(top_row)

        # ── Bottom row: Dropdown + Balance cards ──────────────────────────
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(16)

        # ── Payment Type Dropdown ─────────────────────────────────────────
        from PySide6.QtWidgets import QComboBox

        dropdown_wrap = QWidget()
        dropdown_wrap.setStyleSheet("background:transparent;")
        dw_lay = QVBoxLayout(dropdown_wrap)
        dw_lay.setContentsMargins(0, 0, 0, 0)
        dw_lay.setSpacing(3)

        pt_label = QLabel("PAYMENT TYPE")
        pt_label.setStyleSheet(
            f"font-size:8px; font-weight:bold; letter-spacing:1.2px;"
            f" color:{self._MUTED}; background:transparent;"
        )
        dw_lay.addWidget(pt_label)

        self._payment_type_combo = QComboBox()
        self._payment_type_combo.setFixedHeight(36)
        self._payment_type_combo.setFixedWidth(230)
        self._payment_type_combo.setCursor(Qt.PointingHandCursor)

        # Add items with icons
        self._payment_type_combo.addItem("⬜  Outstanding Balance", userData="outstanding")
        self._payment_type_combo.addItem("🏷️  Laybye Payment",      userData="laybye")

        self._payment_type_combo.setStyleSheet(f"""
            QComboBox {{
                background: {self._WHITE};
                color: {self._NAVY};
                border: 2px solid {self._ACCENT};
                border-radius: 8px;
                font-size: 12px;
                font-weight: bold;
                padding: 0 14px;
                selection-background-color: {self._ACCENT};
            }}
            QComboBox:hover {{
                border: 2px solid {self._ACCENT_H};
                background: {self._OFF_WHITE};
            }}
            QComboBox:focus {{
                border: 2px solid {self._ACCENT_H};
                outline: none;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 32px;
                border-left: 1px solid {self._BORDER};
                border-top-right-radius: 7px;
                border-bottom-right-radius: 7px;
                background: {self._LIGHT};
            }}
            QComboBox::down-arrow {{
                image: none;
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {self._ACCENT};
            }}
            QComboBox QAbstractItemView {{
                background: {self._WHITE};
                color: {self._NAVY};
                border: 1.5px solid {self._BORDER};
                border-radius: 8px;
                outline: none;
                padding: 4px;
                selection-background-color: {self._ACCENT};
                selection-color: {self._WHITE};
                font-size: 12px;
                font-weight: bold;
            }}
            QComboBox QAbstractItemView::item {{
                height: 36px;
                padding-left: 12px;
                border-radius: 6px;
                margin: 2px 4px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background: {self._LIGHT};
                color: {self._NAVY};
            }}
        """)

        self._payment_type_combo.currentIndexChanged.connect(self._on_payment_type_changed)
        dw_lay.addWidget(self._payment_type_combo)
        bottom_row.addWidget(dropdown_wrap)

        # Vertical separator
        vline = QFrame()
        vline.setFrameShape(QFrame.VLine)
        vline.setStyleSheet(f"background:{self._BORDER}; border:none;")
        vline.setFixedWidth(1)
        bottom_row.addWidget(vline)

        # ── Balance Cards ─────────────────────────────────────────────────
        # Outstanding balance card
        self._card_outstanding = QFrame()
        self._card_outstanding.setFixedSize(170, 52)
        self._card_outstanding.setStyleSheet(
            f"QFrame {{ background:{self._WHITE}; border:1.5px solid {self._BORDER};"
            f" border-radius:10px; }}"
        )
        co_lay = QVBoxLayout(self._card_outstanding)
        co_lay.setContentsMargins(12, 6, 12, 6)
        co_lay.setSpacing(2)

        self._card_outstanding_title = QLabel("OUTSTANDING BALANCE")
        self._card_outstanding_title.setStyleSheet(
            f"font-size:8px; font-weight:bold; letter-spacing:0.8px;"
            f" color:{self._MUTED}; background:transparent;"
        )
        self._lbl_outstanding_bal = QLabel("$0.00")
        self._lbl_outstanding_bal.setStyleSheet(
            f"font-size:14px; font-weight:bold; color:{self._NAVY}; background:transparent;"
        )
        co_lay.addWidget(self._card_outstanding_title)
        co_lay.addWidget(self._lbl_outstanding_bal)

        # Laybye balance card
        self._card_laybye = QFrame()
        self._card_laybye.setFixedSize(150, 52)
        self._card_laybye.setStyleSheet(
            f"QFrame {{ background:{self._WHITE}; border:1.5px solid {self._BORDER};"
            f" border-radius:10px; }}"
        )
        cl_lay = QVBoxLayout(self._card_laybye)
        cl_lay.setContentsMargins(12, 6, 12, 6)
        cl_lay.setSpacing(2)

        self._card_laybye_title = QLabel("LAYBYE BALANCE")
        self._card_laybye_title.setStyleSheet(
            f"font-size:8px; font-weight:bold; letter-spacing:0.8px;"
            f" color:{self._MUTED}; background:transparent;"
        )
        self._lbl_laybye_bal = QLabel("$0.00")
        self._lbl_laybye_bal.setStyleSheet(
            f"font-size:14px; font-weight:bold; color:{self._NAVY}; background:transparent;"
        )
        cl_lay.addWidget(self._card_laybye_title)
        cl_lay.addWidget(self._lbl_laybye_bal)

        bottom_row.addWidget(self._card_outstanding)
        bottom_row.addWidget(self._card_laybye)
        bottom_row.addStretch()
        bl.addLayout(bottom_row)

        return bar

    def _on_payment_type_changed(self, idx: int):
        """Slot triggered when the payment type dropdown changes."""
        ptype = self._payment_type_combo.itemData(idx)
        if ptype:
            self._set_payment_type(ptype)

    def _set_payment_type(self, ptype: str):
        """Switch between Outstanding Balance and Laybye payment modes."""
        self._payment_type = ptype

        # Sync dropdown if called programmatically (not from combo signal)
        combo_ptype = self._payment_type_combo.currentData()
        if combo_ptype != ptype:
            for i in range(self._payment_type_combo.count()):
                if self._payment_type_combo.itemData(i) == ptype:
                    self._payment_type_combo.blockSignals(True)
                    self._payment_type_combo.setCurrentIndex(i)
                    self._payment_type_combo.blockSignals(False)
                    break

        # Update combo border color to match context
        if ptype == "laybye":
            self._payment_type_combo.setStyleSheet(
                self._payment_type_combo.styleSheet().replace(
                    f"border: 2px solid {self._ACCENT};",
                    f"border: 2px solid {self._AMBER};"
                ).replace(
                    f"border: 2px solid {self._ACCENT_H};",
                    f"border: 2px solid {self._AMBER};"
                )
            )
            self._info_label.setText("🏷️  Enter amount to pay toward laybye balance")
            self._info_label.setStyleSheet(
                f"color:{self._AMBER}; font-size:11px; margin-top:5px;"
                f" font-weight:bold; background:transparent;"
            )
        else:
            self._payment_type_combo.setStyleSheet(
                self._payment_type_combo.styleSheet().replace(
                    f"border: 2px solid {self._AMBER};",
                    f"border: 2px solid {self._ACCENT};"
                )
            )
            self._info_label.setText("⬜  Enter amount to pay toward outstanding balance")
            self._info_label.setStyleSheet(
                f"color:{self._ACCENT}; font-size:11px; margin-top:5px;"
                f" font-weight:bold; background:transparent;"
            )

        self._update_balance_highlights()

    # ── left panel — payment methods ──────────────────────────────────────
    def _build_left(self):
        vbox = QVBoxLayout()
        vbox.setSpacing(10)

        # ── Date field ────────────────────────────────────────────────────────
        from PySide6.QtWidgets import QDateEdit
        from PySide6.QtCore import QDate
        date_row = QHBoxLayout()
        date_lbl = QLabel("Date:")
        date_lbl.setFixedWidth(80)
        date_lbl.setStyleSheet(f"font-size:11px; color:{self._MUTED}; font-weight:bold;")
        self._date_edit = QDateEdit(QDate.currentDate())
        self._date_edit.setFixedHeight(32)
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("dd/MM/yyyy")
        self._date_edit.setStyleSheet(
            f"QDateEdit {{ background:{self._WHITE}; color:{self._NAVY};"
            f" border:1px solid {self._BORDER}; border-radius:6px;"
            f" font-size:12px; padding:0 10px; }}"
            f"QDateEdit:focus {{ border:2px solid {self._ACCENT}; }}"
        )
        date_row.addWidget(date_lbl)
        date_row.addWidget(self._date_edit, 1)
        vbox.addLayout(date_row)

        # ── Account (mode of payment) selector ────────────────────────────────
        acct_row = QHBoxLayout()
        acct_lbl = QLabel("Account:")
        acct_lbl.setFixedWidth(80)
        acct_lbl.setStyleSheet(f"font-size:11px; color:{self._MUTED}; font-weight:bold;")
        self._acct_combo = QComboBox()
        self._acct_combo.setFixedHeight(32)
        for m in self._methods:
            self._acct_combo.addItem(f"{m['label']}  ({m['currency']})", userData=m)
        self._acct_combo.setStyleSheet(
            f"QComboBox {{ background:{self._WHITE}; color:{self._NAVY};"
            f" border:1px solid {self._BORDER}; border-radius:6px;"
            f" font-size:12px; padding:0 10px; }}"
            f"QComboBox::drop-down {{ border:none; width:20px; }}"
            f"QComboBox QAbstractItemView {{ background:{self._WHITE}; border:1px solid {self._BORDER};"
            f" selection-background-color:{self._ACCENT}; selection-color:{self._WHITE}; }}"
        )
        self._acct_combo.currentIndexChanged.connect(self._on_acct_changed)
        acct_row.addWidget(acct_lbl)
        acct_row.addWidget(self._acct_combo, 1)
        vbox.addLayout(acct_row)

        # Info label for payment type
        self._info_label = QLabel("⬜  Enter amount to pay toward outstanding balance")
        self._info_label.setStyleSheet(
            f"color:{self._ACCENT}; font-size:11px; margin-top:5px;"
            f" font-weight:bold; background:transparent;"
        )
        vbox.addWidget(self._info_label)

        # amount card
        cards = QHBoxLayout()
        cards.setSpacing(10)
        amt_card = QFrame()
        amt_card.setFixedHeight(72)
        amt_card.setStyleSheet(
            f"QFrame {{ background:{self._WHITE}; border:2px solid {self._BORDER}; border-radius:8px; }}"
        )
        acl = QVBoxLayout(amt_card)
        acl.setContentsMargins(14, 6, 14, 6)
        cap = QLabel("PAYMENT AMOUNT")
        cap.setAlignment(Qt.AlignCenter)
        cap.setStyleSheet(
            f"color:{self._MUTED}; font-size:9px; font-weight:bold; letter-spacing:1px;"
        )
        self._total_lbl = QLabel("USD  0.00")
        self._total_lbl.setAlignment(Qt.AlignCenter)
        self._total_lbl.setStyleSheet(
            f"color:{self._NAVY}; font-size:20px; font-weight:bold;"
            f" font-family:'Courier New',monospace;"
        )
        acl.addWidget(cap)
        acl.addWidget(self._total_lbl)
        cards.addWidget(amt_card)
        vbox.addLayout(cards)

        # reference field
        ref_row = QHBoxLayout()
        ref_lbl = QLabel("Ref / Note:")
        ref_lbl.setFixedWidth(80)
        ref_lbl.setStyleSheet(f"font-size:11px; color:{self._MUTED}; font-weight:bold;")
        self._ref_input = QLineEdit()
        self._ref_input.setFixedHeight(32)
        self._ref_input.setPlaceholderText("Receipt / cheque number (optional)")
        self._ref_input.setStyleSheet(
            f"QLineEdit {{ background:{self._WHITE}; color:{self._NAVY};"
            f" border:1px solid {self._BORDER}; border-radius:6px;"
            f" font-size:12px; padding:0 10px; }}"
            f"QLineEdit:focus {{ border:2px solid {self._ACCENT}; }}"
        )
        ref_row.addWidget(ref_lbl)
        ref_row.addWidget(self._ref_input, 1)
        vbox.addLayout(ref_row)

        # column headers
        ch = QWidget()
        ch.setFixedHeight(18)
        ch.setStyleSheet("background:transparent;")
        chl = QHBoxLayout(ch)
        chl.setContentsMargins(0, 0, 0, 0)
        for txt, st, al in [
            ("MODE OF PAYMENT", 4, Qt.AlignLeft),
            ("CCY",             1, Qt.AlignCenter),
            ("AMOUNT",         3, Qt.AlignRight),
        ]:
            l = QLabel(txt)
            l.setStyleSheet(
                f"color:{self._MUTED}; font-size:9px; font-weight:bold; letter-spacing:0.7px;"
            )
            l.setAlignment(al)
            chl.addWidget(l, st)
        vbox.addWidget(ch)

        # method rows
        from PySide6.QtGui import QDoubleValidator
        from PySide6.QtCore import QLocale as _QLocale
        validator = QDoubleValidator(0.0, 999999.99, 2)
        validator.setLocale(_QLocale(_QLocale.English))

        rows_w = QWidget()
        rows_w.setStyleSheet("background:transparent;")
        rows_l = QVBoxLayout(rows_w)
        rows_l.setSpacing(4)
        rows_l.setContentsMargins(0, 0, 0, 0)

        for m in self._methods:
            label = m["label"]
            curr  = m["currency"]

            rw = QWidget()
            rw.setFixedHeight(40)
            rw.setStyleSheet("background:transparent;")
            rl = QHBoxLayout(rw)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(8)

            mb = QPushButton(f"  {label}")
            mb.setFixedHeight(32)
            mb.setCursor(Qt.PointingHandCursor)
            mb.setFocusPolicy(Qt.NoFocus)
            mb.setStyleSheet(self._method_style(False))
            mb.clicked.connect(lambda _, lbl=label: self._activate(lbl))

            cb = QLabel(curr)
            cb.setFixedSize(46, 32)
            cb.setAlignment(Qt.AlignCenter)
            cb.setStyleSheet(
                f"background:{self._LIGHT}; color:{self._ACCENT}; border:1px solid {self._BORDER};"
                f" border-radius:6px; font-size:10px; font-weight:bold;"
            )

            ae = QLineEdit()
            ae.setFixedHeight(32)
            ae.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            ae.setValidator(validator)
            ae.setStyleSheet(self._field_style(False))
            ae.focusInEvent = lambda e, lbl=label, orig=ae.focusInEvent: (
                self._activate(lbl, focus=False), orig(e))
            ae.textChanged.connect(self._update_due)

            rl.addWidget(mb, 4)
            rl.addWidget(cb, 1)
            rl.addWidget(ae, 3)
            rows_l.addWidget(rw)
            self._method_rows[label] = (mb, ae)

        rows_l.addStretch(1)

        sa = QScrollArea()
        sa.setWidget(rows_w)
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sa.setStyleSheet("background:transparent;")
        vbox.addWidget(sa, stretch=1)

        return vbox

    # ── right panel — numpad ──────────────────────────────────────────────
    def _build_right(self):
        vbox = QVBoxLayout()
        vbox.setSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(6)

        def _nb(text, kind="digit"):
            btn = QPushButton(text)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            styles = {
                "digit": (self._WHITE,   self._LIGHT,    self._NAVY),
                "quick": (self._NAVY_3,  self._NAVY_2,   self._WHITE),
                "del":   (self._NAVY_2,  self._NAVY_3,   self._WHITE),
                "clear": ("#b02020",     "#cc2828",      self._WHITE),
            }
            bg, hov, fg = styles.get(kind, styles["digit"])
            btn.setStyleSheet(
                f"QPushButton {{ background:{bg}; color:{fg}; border:1px solid {self._BORDER};"
                f" border-radius:6px; font-size:15px; font-weight:bold; }}"
                f"QPushButton:hover {{ background:{hov}; }}"
                f"QPushButton:pressed {{ background:{self._NAVY_3}; color:{self._WHITE}; }}"
            )
            return btn

        bback = _nb("⌫", "del");   bback.clicked.connect(self._nb_back);  grid.addWidget(bback, 0, 0)
        bclr  = _nb("Clear","clear"); bclr.clicked.connect(self._nb_clear); grid.addWidget(bclr,  0, 1)
        bcan  = _nb("Cancel","clear"); bcan.clicked.connect(self.reject);   grid.addWidget(bcan,  0, 2, 1, 2)

        for ri, (digs, qa) in enumerate(
            [("789", 10), ("456", 20), ("123", 50), ("0.", 100)], 1
        ):
            for ci, d in enumerate(digs):
                b = _nb(d); b.clicked.connect(lambda _, x=d: self._nb_press(x))
                grid.addWidget(b, ri, ci)
            qb = _nb(str(qa), "quick")
            qb.clicked.connect(lambda _, a=qa: self._nb_quick(a))
            grid.addWidget(qb, ri, 3)

        for r in range(5): grid.setRowStretch(r, 1)
        for c in range(4): grid.setColumnStretch(c, 1)

        vbox.addLayout(grid, stretch=5)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{self._BORDER}; border:none;"); sep.setFixedHeight(1)
        vbox.addWidget(sep)

        brow = QHBoxLayout(); brow.setSpacing(8)
        bsave = QPushButton("🖨  Print & Post to Frappe")
        bsave.setFixedHeight(48)
        bsave.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bsave.setCursor(Qt.PointingHandCursor)
        bsave.setStyleSheet(
            f"QPushButton {{ background:{self._SUCCESS}; color:{self._WHITE}; border:none;"
            f" border-radius:6px; font-size:13px; font-weight:bold; }}"
            f"QPushButton:hover {{ background:{self._SUCCESS_H}; }}"
        )
        bsave.clicked.connect(self._save)
        brow.addWidget(bsave)
        vbox.addLayout(brow, stretch=1)

        return vbox

    # ── account / balance helpers ─────────────────────────────────────────
    def _on_acct_changed(self, idx: int):
        """Sync active payment method when the account combo changes."""
        m = self._acct_combo.itemData(idx)
        if m and m["label"] in self._method_rows:
            self._activate(m["label"])

    # ── style helpers ─────────────────────────────────────────────────────
    def _method_style(self, active: bool) -> str:
        if active:
            return (f"QPushButton {{ background:{self._ACCENT}; color:{self._WHITE}; border:none;"
                    f" border-radius:6px; font-size:12px; font-weight:bold;"
                    f" text-align:left; padding:0 12px; }}"
                    f"QPushButton:hover {{ background:{self._ACCENT_H}; }}")
        return (f"QPushButton {{ background:{self._WHITE}; color:{self._NAVY};"
                f" border:1px solid {self._BORDER}; border-radius:6px;"
                f" font-size:12px; text-align:left; padding:0 12px; }}"
                f"QPushButton:hover {{ background:{self._LIGHT}; }}")

    def _field_style(self, active: bool) -> str:
        border = f"2px solid {self._ACCENT}" if active else f"1px solid {self._BORDER}"
        return (f"QLineEdit {{ background:{self._WHITE}; color:{self._NAVY};"
                f" border:{border}; border-radius:6px;"
                f" font-size:14px; font-weight:bold; padding:0 10px; }}")

    # ── method activation ─────────────────────────────────────────────────
    def _activate(self, label: str, focus: bool = True):
        self._active_method = label
        for lbl, (mb, ae) in self._method_rows.items():
            mb.setStyleSheet(self._method_style(lbl == label))
            ae.setStyleSheet(self._field_style(lbl == label))
        if focus and label in self._method_rows:
            ae = self._method_rows[label][1]
            ae.setFocus(); ae.selectAll()

    def _active_field(self) -> QLineEdit:
        if self._active_method in self._method_rows:
            return self._method_rows[self._active_method][1]
        return next(iter(self._method_rows.values()))[1]

    # ── numpad ────────────────────────────────────────────────────────────
    def _nb_press(self, key: str):
        f = self._active_field()
        cur = f.text()
        if key == ".":
            if "." not in cur:
                f.setText(cur + ".")
        else:
            ip = cur.split(".")[0]
            if "." in cur:
                if len(cur.split(".")[1]) < 2:
                    f.setText(cur + key)
            elif len(ip) < 8:
                f.setText(cur + key)

    def _nb_back(self):
        f = self._active_field(); f.setText(f.text()[:-1])

    def _nb_clear(self):
        self._active_field().clear()

    def _nb_quick(self, amt: int):
        self._active_field().setText(f"{amt:.2f}")

    # ── live total ────────────────────────────────────────────────────────
    def _get_paid_usd(self, label: str) -> float:
        if label not in self._method_rows:
            return 0.0
        _, ae = self._method_rows[label]
        try:
            val = float(ae.text() or "0")
        except ValueError:
            val = 0.0
        rate = next((m["rate"] for m in self._methods if m["label"] == label), 1.0)
        return val * rate

    def _update_due(self):
        total_usd = sum(self._get_paid_usd(m["label"]) for m in self._methods)
        self._total_lbl.setText(f"USD  {total_usd:.2f}")
        color = self._SUCCESS if total_usd > 0 else self._NAVY
        self._total_lbl.setStyleSheet(
            f"color:{color}; font-size:20px; font-weight:bold;"
            f" font-family:'Courier New',monospace;"
        )

    # ── save ──────────────────────────────────────────────────────────────
    def _save(self):
        if not self._customer:
            QMessageBox.warning(self, "No Customer",
                                "Please select a customer before recording a payment.")
            return

        total_usd = sum(self._get_paid_usd(m["label"]) for m in self._methods)
        if total_usd <= 0:
            QMessageBox.warning(self, "No Amount", "Please enter the payment amount.")
            self._active_field().setFocus()
            return

        # Get current balances
        outstanding = float(self._customer.get("outstanding_amount", 0))
        laybye = float(self._customer.get("laybye_balance", 0))

        # Validate based on payment type
        if self._payment_type == "laybye":
            if laybye <= 0:
                QMessageBox.warning(self, "No Laybye Balance",
                                    "This customer has no laybye balance to pay.")
                return
            if total_usd > laybye:
                QMessageBox.warning(self, "Amount Exceeds Balance",
                                    f"Payment amount (${total_usd:.2f}) exceeds laybye balance (${laybye:.2f}).")
                return
        else:
            # Outstanding balance payment - can overpay to create credit
            if total_usd > outstanding and outstanding > 0:
                reply = QMessageBox.question(
                    self, "Amount Exceeds Balance",
                    f"Payment amount (${total_usd:.2f}) exceeds outstanding balance (${outstanding:.2f}).\n"
                    f"This will overpay and create a credit.\n\nContinue?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

        # 1. Collect splits
        splits = []
        for m in self._methods:
            _, ae = self._method_rows[m["label"]]
            try:
                val = float(ae.text() or "0")
            except ValueError:
                val = 0.0
            if val > 0:
                splits.append({
                    "method":     m["label"],
                    "currency":   m["currency"],
                    "amount":     val,
                    "amount_usd": self._get_paid_usd(m["label"]),
                })

        method_label = splits[0]["method"]   if len(splits) == 1 else "SPLIT"
        currency     = splits[0]["currency"] if len(splits) == 1 else "USD"

        # Date from the date picker
        payment_date = self._date_edit.date().toString("yyyy-MM-dd")

        # Account from the combo
        acct_data    = self._acct_combo.currentData() or {}
        account_name = acct_data.get("label", method_label)

        # Retrieve Cashier ID from parent hierarchy
        cashier_id = None
        try:
            p = self.parent()
            while p:
                if hasattr(p, "user") and p.user:
                    cashier_id = p.user.get("id")
                    break
                p = p.parent()
        except Exception:
            pass

        # 2. Save to Local DB and update balances
        payment_id = None
        try:
            from models.payment import create_customer_payment
            from database.db import get_connection

            if self._payment_type == "laybye":
                payment = create_customer_payment(
                    customer_id     = self._customer["id"],
                    amount          = total_usd,
                    method          = method_label,
                    currency        = currency,
                    reference       = self._ref_input.text().strip(),
                    cashier_id      = cashier_id,
                    splits          = splits,
                    payment_date    = payment_date,
                    account_name    = account_name,
                )
                payment_id = payment.get("id") if payment else None

                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE customers
                    SET laybye_balance = COALESCE(laybye_balance, 0) - ?
                    WHERE id = ?
                """, (total_usd, self._customer["id"]))
                conn.commit()
                conn.close()

            else:
                payment = create_customer_payment(
                    customer_id     = self._customer["id"],
                    amount          = total_usd,
                    method          = method_label,
                    currency        = currency,
                    reference       = self._ref_input.text().strip(),
                    cashier_id      = cashier_id,
                    splits          = splits,
                    payment_date    = payment_date,
                    account_name    = account_name,
                )
                payment_id = payment.get("id") if payment else None

                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE customers
                    SET outstanding_amount = COALESCE(outstanding_amount, 0) - ?
                    WHERE id = ?
                """, (total_usd, self._customer["id"]))
                conn.commit()
                conn.close()

            from models.customer import get_customer_by_id
            updated_customer = get_customer_by_id(self._customer["id"])
            if updated_customer:
                self._customer = updated_customer
                self._refresh_balances()

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save payment:\n{e}")
            return

        # 3. Post to Frappe (Background)
        frappe_status = "queued"
        if payment_id:
            try:
                from services.payment_entry_service import post_payment_entry_to_frappe
                result = post_payment_entry_to_frappe(payment_id)
                frappe_status = "posted" if result else "queued"
            except Exception:
                frappe_status = "queued"

        # 4. Print Receipt Slip
        if payment_id:
            self._print_payment_slip(payment_id, frappe_status)

        cname = self._customer.get("customer_name", "Customer")
        if self._payment_type == "laybye":
            new_balance = laybye - total_usd
            QMessageBox.information(
                self, "Payment Recorded",
                f"✅  USD {total_usd:.2f} laybye payment recorded for {cname}.\n"
                f"Previous Laybye Balance: ${laybye:.2f}\n"
                f"New Laybye Balance: ${new_balance:.2f}\n"
                f"Frappe: {frappe_status}.\n"
                f"Receipt sent to printer."
            )
        else:
            new_balance = outstanding - total_usd
            QMessageBox.information(
                self, "Payment Recorded",
                f"✅  USD {total_usd:.2f} payment recorded for {cname}.\n"
                f"Previous Outstanding Balance: ${outstanding:.2f}\n"
                f"New Outstanding Balance: ${new_balance:.2f}\n"
                f"Frappe: {frappe_status}.\n"
                f"Receipt sent to printer."
            )
        self.accept()

    def _print_payment_slip(self, payment_id, frappe_status: str = "queued"):
        """Show a printable payment receipt slip on screen and send to thermal printer."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
        from PySide6.QtGui import QFont
        from PySide6.QtCore import Qt

        payment_data = {}
        try:
            from models.payment import get_payment_by_id
            payment_data = get_payment_by_id(payment_id) or {}
        except Exception:
            pass

        try:
            from models.payment import print_customer_payment
            print_customer_payment(payment_id)
        except Exception as e:
            print(f"Thermal Print Error: {e}")

        cname   = self._customer.get("customer_name", "") if self._customer else payment_data.get("customer_name", "Customer")
        amount  = float(payment_data.get("amount", 0))
        method  = payment_data.get("method", "")
        ref     = payment_data.get("reference", "") or ""
        pdate   = payment_data.get("payment_date") or self._date_edit.date().toString("yyyy-MM-dd")
        account = self._acct_combo.currentText()
        p_id_str = f"PAY-{payment_id:05d}" if payment_id else "NEW"

        outstanding = float(self._customer.get("outstanding_amount", 0))
        laybye = float(self._customer.get("laybye_balance", 0))

        W = 40
        lines = [
            "=" * W,
            "      HAVANO POS — PAYMENT RECEIPT",
            f"  Receipt No: {p_id_str}",
            f"  Date:       {pdate}",
            f"  Customer:   {cname}",
        ]

        if self._payment_type == "laybye":
            lines.append(f"  Payment Type: LAYBYE PAYMENT")
            lines.append(f"  Balance After: ${laybye:.2f}")
        else:
            lines.append(f"  Payment Type: OUTSTANDING BALANCE")
            lines.append(f"  Balance After: ${outstanding:.2f}")

        lines += [
            "-" * W,
            f"  Account:    {account}",
            f"  Method:     {method}",
            f"  Amount:     USD {amount:.2f}",
        ]
        if ref:
            lines.append(f"  Ref:        {ref}")
        lines += [
            "-" * W,
            f"  Frappe:     {frappe_status.upper()}",
            "=" * W,
            "\n   Thank you for your payment!",
        ]

        dlg = QDialog(self)
        dlg.setWindowTitle("Payment Receipt Preview")
        dlg.setMinimumSize(380, 420)
        white  = getattr(self, '_WHITE',  '#FFFFFF')
        navy   = getattr(self, '_NAVY',   '#001f3f')
        border = getattr(self, '_BORDER', '#CCCCCC')
        navy2  = getattr(self, '_NAVY_2', '#003366')

        dlg.setStyleSheet(f"QDialog {{ background:{white}; }}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setFont(QFont("Courier New", 10))
        txt.setPlainText("\n".join(lines))
        txt.setStyleSheet(
            f"QTextEdit {{ background:{white}; color:{navy};"
            f" border:1px solid {border}; border-radius:4px; }}"
        )
        lay.addWidget(txt, 1)

        br = QHBoxLayout()
        br.setSpacing(8)
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(36)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton {{ background:{navy}; color:{white}; border:none;"
            f" border-radius:5px; font-size:13px; font-weight:bold; padding:0 20px; }}"
            f"QPushButton:hover {{ background:{navy2}; }}"
        )
        close_btn.clicked.connect(dlg.accept)
        br.addStretch()
        br.addWidget(close_btn)
        lay.addLayout(br)

        dlg.exec()

    # ── keyboard ──────────────────────────────────────────────────────────
    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_balances()
        if self._active_method:
            self._activate(self._active_method)       
# # =============================================================================
# # CUSTOMER PAYMENT ENTRY DIALOG (Requirement 3)
# # =============================================================================
# # =============================================================================
# # CUSTOMER PAYMENT ENTRY DIALOG (Requirement 3)
# # Updated with simple Laybye vs Outstanding Balance toggle
# # Just deducts from customer.laybye_balance or customer.outstanding_amount
# # =============================================================================
# class CustomerPaymentDialog(QDialog):
#     """
#     Full customer payment entry dialog.
#     - Customer search at top (pre-filled if selected on POS)
#     - Toggle between Laybye Payment and Outstanding Balance Payment
#     - Payment methods pulled from GL accounts (same as PaymentDialog)
#     - Numpad for amount entry
#     - Saves to local DB + queues for Frappe sync
#     - Automatically deducts from customer.laybye_balance or customer.outstanding_amount
#     """

#     # ── colours (same palette as rest of main_window) ─────────────────────
#     _NAVY      = "#0d1f3c"
#     _NAVY_2    = "#162d52"
#     _NAVY_3    = "#1e3d6e"
#     _ACCENT    = "#1a5fb4"
#     _ACCENT_H  = "#1c6dd0"
#     _WHITE     = "#ffffff"
#     _OFF_WHITE = "#f5f8fc"
#     _LIGHT     = "#e4eaf4"
#     _MID       = "#8fa8c8"
#     _MUTED     = "#5a7a9a"
#     _BORDER    = "#c8d8ec"
#     _SUCCESS   = "#1a7a3c"
#     _SUCCESS_H = "#1f9447"
#     _DANGER    = "#b02020"
#     _DANGER_H  = "#cc2828"
#     _AMBER     = "#c05a00"
#     _ORANGE    = "#b06000"

#     def __init__(self, parent=None, customer=None):
#         super().__init__(parent)
#         self._customer   = customer   # always set — enforced by caller
#         self._methods:    list[dict] = []
#         self._active_method: str     = ""
#         self._method_rows: dict      = {}   # label → (btn, QLineEdit)

#         self.setWindowTitle("Customer Payment Entry")
#         self.setMinimumSize(820, 580)
#         self.setModal(True)
#         self.setWindowState(Qt.WindowMaximized)
#         self.setStyleSheet(
#             f"QDialog {{ background:{self._OFF_WHITE}; font-family:'Segoe UI',sans-serif; }}"
#             f"QLabel   {{ background:transparent; color:{self._NAVY}; }}"
#         )
#         self._load_data()
#         self._build_ui()
#         self._refresh_balances()

#     # ── data loading ──────────────────────────────────────────────────────
#     def _load_data(self):
#         company = ""
#         try:
#             from models.company_defaults import get_defaults
#             company = (get_defaults() or {}).get("server_company", "")
#         except Exception:
#             pass

#         try:
#             from models.gl_account import get_all_accounts
#             all_accts = get_all_accounts()
#             accts = [a for a in all_accts if a.get("company") == company] or all_accts
#         except Exception:
#             accts = []

#         seen = set()
#         for a in accts:
#             curr  = (a.get("account_currency") or "USD").upper()
#             atype = (a.get("account_name") or a.get("name") or "Cash").strip()
#             key   = (atype.lower(), curr)
#             if key in seen:
#                 continue
#             seen.add(key)
#             rate = 1.0
#             try:
#                 from models.exchange_rate import get_rate
#                 r = get_rate(curr, "USD")
#                 if r:
#                     rate = float(r)
#             except Exception:
#                 pass
#             self._methods.append({"label": atype, "currency": curr, "rate": rate})

#         if not self._methods:
#             self._methods = [
#                 {"label": "Cash",       "currency": "USD", "rate": 1.0},
#                 {"label": "Cash (ZIG)", "currency": "ZIG", "rate": 1.0},
#                 {"label": "Card",       "currency": "USD", "rate": 1.0},
#                 {"label": "Bank / EFT", "currency": "USD", "rate": 1.0},
#             ]

#         if self._methods:
#             self._active_method = self._methods[0]["label"]

#     def _refresh_balances(self):
#         """Refresh both outstanding and laybye balances from the customer record."""
#         if not self._customer:
#             return
        
#         try:
#             from models.customer import get_customer_by_id
#             updated = get_customer_by_id(self._customer["id"])
#             if updated:
#                 self._customer = updated
            
#             outstanding = float(self._customer.get("outstanding_amount", 0))
#             laybye = float(self._customer.get("laybye_balance", 0))
            
#             self._lbl_outstanding_bal.setText(f"${outstanding:.2f}")
#             color = self._DANGER if outstanding > 0 else self._SUCCESS
#             self._lbl_outstanding_bal.setStyleSheet(f"font-size:13px; font-weight:bold; color:{color};")
            
#             self._lbl_laybye_bal.setText(f"${laybye:.2f}")
#             color = self._DANGER if laybye > 0 else self._SUCCESS
#             self._lbl_laybye_bal.setStyleSheet(f"font-size:13px; font-weight:bold; color:{color};")
#         except Exception as e:
#             print(f"Error refreshing balances: {e}")

#     # ── UI ────────────────────────────────────────────────────────────────
#     def _build_ui(self):
#         outer = QVBoxLayout(self)
#         outer.setSpacing(0)
#         outer.setContentsMargins(0, 0, 0, 0)

#         # header bar
#         hdr = QWidget()
#         hdr.setFixedHeight(52)
#         hdr.setStyleSheet(f"background:{self._WHITE}; border-bottom:2px solid {self._BORDER};")
#         hl = QHBoxLayout(hdr)
#         hl.setContentsMargins(28, 0, 28, 0)
#         title = QLabel("💰  Customer Payment Entry")
#         title.setStyleSheet(f"color:{self._NAVY}; font-size:17px; font-weight:bold;")
#         hint = QLabel("Select payment type · Enter amount · Save")
#         hint.setStyleSheet(f"color:{self._MUTED}; font-size:10px;")
#         hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
#         hl.addWidget(title)
#         hl.addStretch()
#         hl.addWidget(hint)
#         outer.addWidget(hdr)

#         # customer display bar
#         outer.addWidget(self._build_customer_bar())

#         # body — left (methods) + right (numpad)
#         body_w = QWidget()
#         body_w.setStyleSheet(f"background:{self._OFF_WHITE};")
#         body_l = QHBoxLayout(body_w)
#         body_l.setContentsMargins(32, 20, 32, 20)
#         body_l.setSpacing(28)
#         body_l.addLayout(self._build_left(), stretch=5)

#         sep = QFrame()
#         sep.setFrameShape(QFrame.VLine)
#         sep.setStyleSheet(f"background:{self._BORDER}; border:none;")
#         sep.setFixedWidth(1)
#         body_l.addWidget(sep)

#         body_l.addLayout(self._build_right(), stretch=4)
#         outer.addWidget(body_w, stretch=1)

#     def _build_customer_bar(self):
#         """Fixed customer display with payment type toggle and balances."""
#         bar = QWidget()
#         bar.setFixedHeight(90)
#         bar.setStyleSheet(
#             f"background:{self._LIGHT}; border-bottom:1px solid {self._BORDER};"
#         )
#         bl = QVBoxLayout(bar)
#         bl.setContentsMargins(28, 8, 28, 8)
#         bl.setSpacing(8)

#         # Top row: Customer info
#         top_row = QHBoxLayout()
        
#         icon = QLabel("👤")
#         icon.setStyleSheet("font-size:20px; background:transparent;")
#         top_row.addWidget(icon)

#         name = self._customer.get("customer_name", "Unknown") if self._customer else "Unknown"
#         phone = self._customer.get("custom_telephone_number", "") if self._customer else ""
#         group = self._customer.get("customer_group_name", "") if self._customer else ""

#         name_lbl = QLabel(name)
#         name_lbl.setStyleSheet(
#             f"font-size:15px; font-weight:bold; color:{self._NAVY}; background:transparent;"
#         )
#         top_row.addWidget(name_lbl)

#         if phone or group:
#             detail = QLabel(f"{phone}{'  ·  ' if phone and group else ''}{group}")
#             detail.setStyleSheet(f"font-size:11px; color:{self._MUTED}; background:transparent;")
#             top_row.addWidget(detail)

#         top_row.addStretch()
        
#         badge = QLabel("PAYMENT ENTRY")
#         badge.setStyleSheet(
#             f"background:{self._ACCENT}; color:{self._WHITE}; border-radius:4px;"
#             f" font-size:10px; font-weight:bold; padding:3px 10px;"
#         )
#         top_row.addWidget(badge)
        
#         bl.addLayout(top_row)

#         # Bottom row: Payment Type Toggle + Balances
#         bottom_row = QHBoxLayout()
#         bottom_row.setSpacing(20)

#         # Payment type toggle
#         payment_type_group = QWidget()
#         payment_type_group.setStyleSheet("background:transparent;")
#         pt_layout = QHBoxLayout(payment_type_group)
#         pt_layout.setSpacing(0)
#         pt_layout.setContentsMargins(0, 0, 0, 0)

#         self._btn_outstanding = QPushButton("Outstanding Balance")
#         self._btn_laybye = QPushButton("Laybye Payment")

#         for btn in (self._btn_outstanding, self._btn_laybye):
#             btn.setCheckable(True)
#             btn.setFixedHeight(32)
#             btn.setCursor(Qt.PointingHandCursor)
#             btn.setStyleSheet("""
#                 QPushButton {
#                     background: #f0f0f0;
#                     color: #555;
#                     border: 1px solid #ccc;
#                     padding: 0 15px;
#                     font-size: 11px;
#                     font-weight: bold;
#                 }
#                 QPushButton:checked {
#                     background: #1a5fb4;
#                     color: white;
#                     border: 1px solid #1a5fb4;
#                 }
#             """)

#         self._btn_outstanding.setChecked(True)
#         self._btn_outstanding.clicked.connect(lambda: self._set_payment_type("outstanding"))
#         self._btn_laybye.clicked.connect(lambda: self._set_payment_type("laybye"))

#         pt_layout.addWidget(self._btn_outstanding)
#         pt_layout.addWidget(self._btn_laybye)
#         bottom_row.addWidget(payment_type_group)

#         # Separator
#         sep_line = QFrame()
#         sep_line.setFrameShape(QFrame.VLine)
#         sep_line.setStyleSheet(f"background:{self._BORDER};")
#         sep_line.setFixedWidth(1)
#         sep_line.setFixedHeight(32)
#         bottom_row.addWidget(sep_line)

#         # Balances display
#         balances_widget = QWidget()
#         balances_layout = QHBoxLayout(balances_widget)
#         balances_layout.setSpacing(20)
#         balances_layout.setContentsMargins(0, 0, 0, 0)

#         # Outstanding balance display
#         outstanding_widget = QWidget()
#         out_layout = QHBoxLayout(outstanding_widget)
#         out_layout.setSpacing(6)
#         out_layout.setContentsMargins(0, 0, 0, 0)
#         out_label = QLabel("Outstanding:")
#         out_label.setStyleSheet(f"font-size:11px; color:{self._MUTED}; font-weight:bold;")
#         self._lbl_outstanding_bal = QLabel("$0.00")
#         self._lbl_outstanding_bal.setStyleSheet(f"font-size:12px; font-weight:bold; color:{self._NAVY};")
#         out_layout.addWidget(out_label)
#         out_layout.addWidget(self._lbl_outstanding_bal)
        
#         # Laybye balance display
#         laybye_widget = QWidget()
#         laybye_layout = QHBoxLayout(laybye_widget)
#         laybye_layout.setSpacing(6)
#         laybye_layout.setContentsMargins(0, 0, 0, 0)
#         laybye_label = QLabel("Laybye:")
#         laybye_label.setStyleSheet(f"font-size:11px; color:{self._MUTED}; font-weight:bold;")
#         self._lbl_laybye_bal = QLabel("$0.00")
#         self._lbl_laybye_bal.setStyleSheet(f"font-size:12px; font-weight:bold; color:{self._NAVY};")
#         laybye_layout.addWidget(laybye_label)
#         laybye_layout.addWidget(self._lbl_laybye_bal)
        
#         balances_layout.addWidget(outstanding_widget)
#         balances_layout.addWidget(laybye_widget)
#         bottom_row.addWidget(balances_widget)
        
#         bottom_row.addStretch()
#         bl.addLayout(bottom_row)

#         return bar

#     def _set_payment_type(self, ptype: str):
#         """Toggle between Outstanding Balance and Laybye payment modes."""
#         self._payment_type = ptype
#         if ptype == "laybye":
#             self._info_label.setText("💰  Enter amount to pay toward laybye balance")
#             self._info_label.setStyleSheet(f"color:{self._AMBER}; font-size:11px; margin-top:5px;")
#         else:
#             self._info_label.setText("💰  Enter amount to pay toward outstanding balance")
#             self._info_label.setStyleSheet(f"color:{self._ACCENT}; font-size:11px; margin-top:5px;")

#     # ── left panel — payment methods ──────────────────────────────────────
#     def _build_left(self):
#         vbox = QVBoxLayout()
#         vbox.setSpacing(10)

#         # ── Date field ────────────────────────────────────────────────────────
#         from PySide6.QtWidgets import QDateEdit
#         from PySide6.QtCore import QDate
#         date_row = QHBoxLayout()
#         date_lbl = QLabel("Date:")
#         date_lbl.setFixedWidth(80)
#         date_lbl.setStyleSheet(f"font-size:11px; color:{self._MUTED}; font-weight:bold;")
#         self._date_edit = QDateEdit(QDate.currentDate())
#         self._date_edit.setFixedHeight(32)
#         self._date_edit.setCalendarPopup(True)
#         self._date_edit.setDisplayFormat("dd/MM/yyyy")
#         self._date_edit.setStyleSheet(
#             f"QDateEdit {{ background:{self._WHITE}; color:{self._NAVY};"
#             f" border:1px solid {self._BORDER}; border-radius:6px;"
#             f" font-size:12px; padding:0 10px; }}"
#             f"QDateEdit:focus {{ border:2px solid {self._ACCENT}; }}"
#         )
#         date_row.addWidget(date_lbl)
#         date_row.addWidget(self._date_edit, 1)
#         vbox.addLayout(date_row)

#         # ── Account (mode of payment) selector ────────────────────────────────
#         acct_row = QHBoxLayout()
#         acct_lbl = QLabel("Account:")
#         acct_lbl.setFixedWidth(80)
#         acct_lbl.setStyleSheet(f"font-size:11px; color:{self._MUTED}; font-weight:bold;")
#         self._acct_combo = QComboBox()
#         self._acct_combo.setFixedHeight(32)
#         for m in self._methods:
#             self._acct_combo.addItem(f"{m['label']}  ({m['currency']})", userData=m)
#         self._acct_combo.setStyleSheet(
#             f"QComboBox {{ background:{self._WHITE}; color:{self._NAVY};"
#             f" border:1px solid {self._BORDER}; border-radius:6px;"
#             f" font-size:12px; padding:0 10px; }}"
#             f"QComboBox::drop-down {{ border:none; width:20px; }}"
#             f"QComboBox QAbstractItemView {{ background:{self._WHITE}; border:1px solid {self._BORDER};"
#             f" selection-background-color:{self._ACCENT}; selection-color:{self._WHITE}; }}"
#         )
#         self._acct_combo.currentIndexChanged.connect(self._on_acct_changed)
#         acct_row.addWidget(acct_lbl)
#         acct_row.addWidget(self._acct_combo, 1)
#         vbox.addLayout(acct_row)

#         # Info label for payment type
#         self._info_label = QLabel("💰  Enter amount to pay toward outstanding balance")
#         self._info_label.setStyleSheet(f"color:{self._ACCENT}; font-size:11px; margin-top:5px;")
#         vbox.addWidget(self._info_label)

#         # amount card
#         cards = QHBoxLayout()
#         cards.setSpacing(10)
#         amt_card = QFrame()
#         amt_card.setFixedHeight(72)
#         amt_card.setStyleSheet(
#             f"QFrame {{ background:{self._WHITE}; border:2px solid {self._BORDER}; border-radius:8px; }}"
#         )
#         acl = QVBoxLayout(amt_card)
#         acl.setContentsMargins(14, 6, 14, 6)
#         cap = QLabel("PAYMENT AMOUNT")
#         cap.setAlignment(Qt.AlignCenter)
#         cap.setStyleSheet(
#             f"color:{self._MUTED}; font-size:9px; font-weight:bold; letter-spacing:1px;"
#         )
#         self._total_lbl = QLabel("USD  0.00")
#         self._total_lbl.setAlignment(Qt.AlignCenter)
#         self._total_lbl.setStyleSheet(
#             f"color:{self._NAVY}; font-size:20px; font-weight:bold;"
#             f" font-family:'Courier New',monospace;"
#         )
#         acl.addWidget(cap)
#         acl.addWidget(self._total_lbl)
#         cards.addWidget(amt_card)
#         vbox.addLayout(cards)

#         # reference field
#         ref_row = QHBoxLayout()
#         ref_lbl = QLabel("Ref / Note:")
#         ref_lbl.setFixedWidth(80)
#         ref_lbl.setStyleSheet(f"font-size:11px; color:{self._MUTED}; font-weight:bold;")
#         self._ref_input = QLineEdit()
#         self._ref_input.setFixedHeight(32)
#         self._ref_input.setPlaceholderText("Receipt / cheque number (optional)")
#         self._ref_input.setStyleSheet(
#             f"QLineEdit {{ background:{self._WHITE}; color:{self._NAVY};"
#             f" border:1px solid {self._BORDER}; border-radius:6px;"
#             f" font-size:12px; padding:0 10px; }}"
#             f"QLineEdit:focus {{ border:2px solid {self._ACCENT}; }}"
#         )
#         ref_row.addWidget(ref_lbl)
#         ref_row.addWidget(self._ref_input, 1)
#         vbox.addLayout(ref_row)

#         # column headers
#         ch = QWidget()
#         ch.setFixedHeight(18)
#         ch.setStyleSheet("background:transparent;")
#         chl = QHBoxLayout(ch)
#         chl.setContentsMargins(0, 0, 0, 0)
#         for txt, st, al in [
#             ("MODE OF PAYMENT", 4, Qt.AlignLeft),
#             ("CCY",             1, Qt.AlignCenter),
#             ("AMOUNT",         3, Qt.AlignRight),
#         ]:
#             l = QLabel(txt)
#             l.setStyleSheet(
#                 f"color:{self._MUTED}; font-size:9px; font-weight:bold; letter-spacing:0.7px;"
#             )
#             l.setAlignment(al)
#             chl.addWidget(l, st)
#         vbox.addWidget(ch)

#         # method rows
#         from PySide6.QtGui import QDoubleValidator
#         from PySide6.QtCore import QLocale as _QLocale
#         validator = QDoubleValidator(0.0, 999999.99, 2)
#         validator.setLocale(_QLocale(_QLocale.English))

#         rows_w = QWidget()
#         rows_w.setStyleSheet("background:transparent;")
#         rows_l = QVBoxLayout(rows_w)
#         rows_l.setSpacing(4)
#         rows_l.setContentsMargins(0, 0, 0, 0)

#         for m in self._methods:
#             label = m["label"]
#             curr  = m["currency"]

#             rw = QWidget()
#             rw.setFixedHeight(40)
#             rw.setStyleSheet("background:transparent;")
#             rl = QHBoxLayout(rw)
#             rl.setContentsMargins(0, 0, 0, 0)
#             rl.setSpacing(8)

#             mb = QPushButton(f"  {label}")
#             mb.setFixedHeight(32)
#             mb.setCursor(Qt.PointingHandCursor)
#             mb.setFocusPolicy(Qt.NoFocus)
#             mb.setStyleSheet(self._method_style(False))
#             mb.clicked.connect(lambda _, lbl=label: self._activate(lbl))

#             cb = QLabel(curr)
#             cb.setFixedSize(46, 32)
#             cb.setAlignment(Qt.AlignCenter)
#             cb.setStyleSheet(
#                 f"background:{self._LIGHT}; color:{self._ACCENT}; border:1px solid {self._BORDER};"
#                 f" border-radius:6px; font-size:10px; font-weight:bold;"
#             )

#             ae = QLineEdit()
#             ae.setFixedHeight(32)
#             ae.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
#             ae.setValidator(validator)
#             ae.setStyleSheet(self._field_style(False))
#             ae.focusInEvent = lambda e, lbl=label, orig=ae.focusInEvent: (
#                 self._activate(lbl, focus=False), orig(e))
#             ae.textChanged.connect(self._update_due)

#             rl.addWidget(mb, 4)
#             rl.addWidget(cb, 1)
#             rl.addWidget(ae, 3)
#             rows_l.addWidget(rw)
#             self._method_rows[label] = (mb, ae)

#         rows_l.addStretch(1)

#         sa = QScrollArea()
#         sa.setWidget(rows_w)
#         sa.setWidgetResizable(True)
#         sa.setFrameShape(QFrame.NoFrame)
#         sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
#         sa.setStyleSheet("background:transparent;")
#         vbox.addWidget(sa, stretch=1)

#         return vbox

#     # ── right panel — numpad ──────────────────────────────────────────────
#     def _build_right(self):
#         vbox = QVBoxLayout()
#         vbox.setSpacing(8)

#         grid = QGridLayout()
#         grid.setSpacing(6)

#         def _nb(text, kind="digit"):
#             btn = QPushButton(text)
#             btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
#             btn.setCursor(Qt.PointingHandCursor)
#             btn.setFocusPolicy(Qt.NoFocus)
#             styles = {
#                 "digit": (self._WHITE,   self._LIGHT,    self._NAVY),
#                 "quick": (self._NAVY_3,  self._NAVY_2,   self._WHITE),
#                 "del":   (self._NAVY_2,  self._NAVY_3,   self._WHITE),
#                 "clear": ("#b02020",     "#cc2828",      self._WHITE),
#             }
#             bg, hov, fg = styles.get(kind, styles["digit"])
#             btn.setStyleSheet(
#                 f"QPushButton {{ background:{bg}; color:{fg}; border:1px solid {self._BORDER};"
#                 f" border-radius:6px; font-size:15px; font-weight:bold; }}"
#                 f"QPushButton:hover {{ background:{hov}; }}"
#                 f"QPushButton:pressed {{ background:{self._NAVY_3}; color:{self._WHITE}; }}"
#             )
#             return btn

#         bback = _nb("⌫", "del");   bback.clicked.connect(self._nb_back);  grid.addWidget(bback, 0, 0)
#         bclr  = _nb("Clear","clear"); bclr.clicked.connect(self._nb_clear); grid.addWidget(bclr,  0, 1)
#         bcan  = _nb("Cancel","clear"); bcan.clicked.connect(self.reject);   grid.addWidget(bcan,  0, 2, 1, 2)

#         for ri, (digs, qa) in enumerate(
#             [("789", 10), ("456", 20), ("123", 50), ("0.", 100)], 1
#         ):
#             for ci, d in enumerate(digs):
#                 b = _nb(d); b.clicked.connect(lambda _, x=d: self._nb_press(x))
#                 grid.addWidget(b, ri, ci)
#             qb = _nb(str(qa), "quick")
#             qb.clicked.connect(lambda _, a=qa: self._nb_quick(a))
#             grid.addWidget(qb, ri, 3)

#         for r in range(5): grid.setRowStretch(r, 1)
#         for c in range(4): grid.setColumnStretch(c, 1)

#         vbox.addLayout(grid, stretch=5)

#         sep = QFrame(); sep.setFrameShape(QFrame.HLine)
#         sep.setStyleSheet(f"background:{self._BORDER}; border:none;"); sep.setFixedHeight(1)
#         vbox.addWidget(sep)

#         brow = QHBoxLayout(); brow.setSpacing(8)
#         bsave = QPushButton("🖨  Print & Post to Frappe")
#         bsave.setFixedHeight(48)
#         bsave.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
#         bsave.setCursor(Qt.PointingHandCursor)
#         bsave.setStyleSheet(
#             f"QPushButton {{ background:{self._SUCCESS}; color:{self._WHITE}; border:none;"
#             f" border-radius:6px; font-size:13px; font-weight:bold; }}"
#             f"QPushButton:hover {{ background:{self._SUCCESS_H}; }}"
#         )
#         bsave.clicked.connect(self._save)
#         brow.addWidget(bsave)
#         vbox.addLayout(brow, stretch=1)

#         return vbox

#     # ── account / balance helpers ─────────────────────────────────────────
#     def _on_acct_changed(self, idx: int):
#         """Sync active payment method when the account combo changes."""
#         m = self._acct_combo.itemData(idx)
#         if m and m["label"] in self._method_rows:
#             self._activate(m["label"])

#     # ── style helpers ─────────────────────────────────────────────────────
#     def _method_style(self, active: bool) -> str:
#         if active:
#             return (f"QPushButton {{ background:{self._ACCENT}; color:{self._WHITE}; border:none;"
#                     f" border-radius:6px; font-size:12px; font-weight:bold;"
#                     f" text-align:left; padding:0 12px; }}"
#                     f"QPushButton:hover {{ background:{self._ACCENT_H}; }}")
#         return (f"QPushButton {{ background:{self._WHITE}; color:{self._NAVY};"
#                 f" border:1px solid {self._BORDER}; border-radius:6px;"
#                 f" font-size:12px; text-align:left; padding:0 12px; }}"
#                 f"QPushButton:hover {{ background:{self._LIGHT}; }}")

#     def _field_style(self, active: bool) -> str:
#         border = f"2px solid {self._ACCENT}" if active else f"1px solid {self._BORDER}"
#         return (f"QLineEdit {{ background:{self._WHITE}; color:{self._NAVY};"
#                 f" border:{border}; border-radius:6px;"
#                 f" font-size:14px; font-weight:bold; padding:0 10px; }}")

#     # ── method activation ─────────────────────────────────────────────────
#     def _activate(self, label: str, focus: bool = True):
#         self._active_method = label
#         for lbl, (mb, ae) in self._method_rows.items():
#             mb.setStyleSheet(self._method_style(lbl == label))
#             ae.setStyleSheet(self._field_style(lbl == label))
#         if focus and label in self._method_rows:
#             ae = self._method_rows[label][1]
#             ae.setFocus(); ae.selectAll()

#     def _active_field(self) -> QLineEdit:
#         if self._active_method in self._method_rows:
#             return self._method_rows[self._active_method][1]
#         return next(iter(self._method_rows.values()))[1]

#     # ── numpad ────────────────────────────────────────────────────────────
#     def _nb_press(self, key: str):
#         f = self._active_field()
#         cur = f.text()
#         if key == ".":
#             if "." not in cur:
#                 f.setText(cur + ".")
#         else:
#             ip = cur.split(".")[0]
#             if "." in cur:
#                 if len(cur.split(".")[1]) < 2:
#                     f.setText(cur + key)
#             elif len(ip) < 8:
#                 f.setText(cur + key)

#     def _nb_back(self):
#         f = self._active_field(); f.setText(f.text()[:-1])

#     def _nb_clear(self):
#         self._active_field().clear()

#     def _nb_quick(self, amt: int):
#         self._active_field().setText(f"{amt:.2f}")

#     # ── live total ────────────────────────────────────────────────────────
#     def _get_paid_usd(self, label: str) -> float:
#         if label not in self._method_rows:
#             return 0.0
#         _, ae = self._method_rows[label]
#         try:
#             val = float(ae.text() or "0")
#         except ValueError:
#             val = 0.0
#         rate = next((m["rate"] for m in self._methods if m["label"] == label), 1.0)
#         return val * rate

#     def _update_due(self):
#         total_usd = sum(self._get_paid_usd(m["label"]) for m in self._methods)
#         self._total_lbl.setText(f"USD  {total_usd:.2f}")
#         color = self._SUCCESS if total_usd > 0 else self._NAVY
#         self._total_lbl.setStyleSheet(
#             f"color:{color}; font-size:20px; font-weight:bold;"
#             f" font-family:'Courier New',monospace;"
#         )

#     # ── save ──────────────────────────────────────────────────────────────
#     def _save(self):
#         if not self._customer:
#             QMessageBox.warning(self, "No Customer",
#                                 "Please select a customer before recording a payment.")
#             return

#         total_usd = sum(self._get_paid_usd(m["label"]) for m in self._methods)
#         if total_usd <= 0:
#             QMessageBox.warning(self, "No Amount", "Please enter the payment amount.")
#             self._active_field().setFocus()
#             return

#         # Get current balances
#         outstanding = float(self._customer.get("outstanding_amount", 0))
#         laybye = float(self._customer.get("laybye_balance", 0))

#         # Validate based on payment type
#         if self._payment_type == "laybye":
#             if laybye <= 0:
#                 QMessageBox.warning(self, "No Laybye Balance",
#                                     "This customer has no laybye balance to pay.")
#                 return
#             if total_usd > laybye:
#                 QMessageBox.warning(self, "Amount Exceeds Balance",
#                                     f"Payment amount (${total_usd:.2f}) exceeds laybye balance (${laybye:.2f}).")
#                 return
#         else:
#             # Outstanding balance payment - can overpay to create credit
#             if total_usd > outstanding and outstanding > 0:
#                 reply = QMessageBox.question(
#                     self, "Amount Exceeds Balance",
#                     f"Payment amount (${total_usd:.2f}) exceeds outstanding balance (${outstanding:.2f}).\n"
#                     f"This will overpay and create a credit.\n\n"
#                     f"Continue?",
#                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No
#                 )
#                 if reply != QMessageBox.Yes:
#                     return

#         # 1. Collect splits
#         splits = []
#         for m in self._methods:
#             _, ae = self._method_rows[m["label"]]
#             try:
#                 val = float(ae.text() or "0")
#             except ValueError:
#                 val = 0.0
#             if val > 0:
#                 splits.append({
#                     "method":     m["label"],
#                     "currency":   m["currency"],
#                     "amount":     val,
#                     "amount_usd": self._get_paid_usd(m["label"]),
#                 })

#         method_label = splits[0]["method"]   if len(splits) == 1 else "SPLIT"
#         currency     = splits[0]["currency"] if len(splits) == 1 else "USD"

#         # Date from the date picker
#         payment_date = self._date_edit.date().toString("yyyy-MM-dd")

#         # Account from the combo
#         acct_data    = self._acct_combo.currentData() or {}
#         account_name = acct_data.get("label", method_label)

#         # Retrieve Cashier ID from parent hierarchy
#         cashier_id = None
#         try:
#             p = self.parent()
#             while p:
#                 if hasattr(p, "user") and p.user:
#                     cashier_id = p.user.get("id")
#                     break
#                 p = p.parent()
#         except Exception:
#             pass

#         # 2. Save to Local DB and update balances
#         payment_id = None
#         try:
#             from models.payment import create_customer_payment
#             from database.db import get_connection

#             if self._payment_type == "laybye":
#                 # Create payment (no sales_order_id for simple laybye payment)
#                 payment = create_customer_payment(
#                     customer_id     = self._customer["id"],
#                     amount          = total_usd,
#                     method          = method_label,
#                     currency        = currency,
#                     reference       = self._ref_input.text().strip(),
#                     cashier_id      = cashier_id,
#                     splits          = splits,
#                     payment_date    = payment_date,
#                     account_name    = account_name,
#                     # No sales_order_id for simple laybye balance payment
#                 )
#                 payment_id = payment.get("id") if payment else None

#                 # Update customer laybye_balance
#                 conn = get_connection()
#                 cur = conn.cursor()
#                 cur.execute("""
#                     UPDATE customers 
#                     SET laybye_balance = COALESCE(laybye_balance, 0) - ?
#                     WHERE id = ?
#                 """, (total_usd, self._customer["id"]))
#                 conn.commit()
#                 conn.close()

#             else:
#                 # Outstanding balance payment - update customer outstanding_amount
#                 payment = create_customer_payment(
#                     customer_id     = self._customer["id"],
#                     amount          = total_usd,
#                     method          = method_label,
#                     currency        = currency,
#                     reference       = self._ref_input.text().strip(),
#                     cashier_id      = cashier_id,
#                     splits          = splits,
#                     payment_date    = payment_date,
#                     account_name    = account_name,
#                 )
#                 payment_id = payment.get("id") if payment else None

#                 # Update customer outstanding amount (can go negative for credit)
#                 conn = get_connection()
#                 cur = conn.cursor()
#                 cur.execute("""
#                     UPDATE customers 
#                     SET outstanding_amount = COALESCE(outstanding_amount, 0) - ?
#                     WHERE id = ?
#                 """, (total_usd, self._customer["id"]))
#                 conn.commit()
#                 conn.close()

#             # Refresh the customer data
#             from models.customer import get_customer_by_id
#             updated_customer = get_customer_by_id(self._customer["id"])
#             if updated_customer:
#                 self._customer = updated_customer
#                 self._refresh_balances()

#         except Exception as e:
#             QMessageBox.warning(self, "Error", f"Could not save payment:\n{e}")
#             return

#         # 3. Post to Frappe (Background)
#         frappe_status = "queued"
#         if payment_id:
#             try:
#                 from services.payment_entry_service import post_payment_entry_to_frappe
#                 result = post_payment_entry_to_frappe(payment_id)
#                 frappe_status = "posted" if result else "queued"
#             except Exception:
#                 frappe_status = "queued"

#         # 4. Print Receipt Slip
#         if payment_id:
#             self._print_payment_slip(payment_id, frappe_status)

#         cname = self._customer.get("customer_name", "Customer")
#         if self._payment_type == "laybye":
#             new_balance = laybye - total_usd
#             QMessageBox.information(
#                 self, "Payment Recorded",
#                 f"✅  USD {total_usd:.2f} laybye payment recorded for {cname}.\n"
#                 f"Previous Laybye Balance: ${laybye:.2f}\n"
#                 f"New Laybye Balance: ${new_balance:.2f}\n"
#                 f"Frappe: {frappe_status}.\n"
#                 f"Receipt sent to printer."
#             )
#         else:
#             new_balance = outstanding - total_usd
#             QMessageBox.information(
#                 self, "Payment Recorded",
#                 f"✅  USD {total_usd:.2f} payment recorded for {cname}.\n"
#                 f"Previous Outstanding Balance: ${outstanding:.2f}\n"
#                 f"New Outstanding Balance: ${new_balance:.2f}\n"
#                 f"Frappe: {frappe_status}.\n"
#                 f"Receipt sent to printer."
#             )
#         self.accept()

#     def _print_payment_slip(self, payment_id, frappe_status: str = "queued"):
#         """
#         Show a printable payment receipt slip on screen and send to thermal printer.
#         """
#         from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
#         from PySide6.QtGui import QFont
#         from PySide6.QtCore import Qt

#         # 1. Ensure we have a dictionary of data
#         payment_data = {}
#         try:
#             from models.payment import get_payment_by_id
#             payment_data = get_payment_by_id(payment_id) or {}
#         except Exception:
#             pass

#         # 2. Trigger the actual Thermal Printer
#         try:
#             from models.payment import print_customer_payment
#             print_customer_payment(payment_id)
#         except Exception as e:
#             print(f"Thermal Print Error: {e}")

#         # 3. Prepare the On-Screen Preview Dialog
#         cname   = self._customer.get("customer_name", "") if self._customer else payment_data.get("customer_name", "Customer")
#         amount  = float(payment_data.get("amount", 0))
#         method  = payment_data.get("method", "")
#         ref     = payment_data.get("reference", "") or ""
#         pdate   = payment_data.get("payment_date") or self._date_edit.date().toString("yyyy-MM-dd")
#         account = self._acct_combo.currentText()
#         p_id_str = f"PAY-{payment_id:05d}" if payment_id else "NEW"

#         # Get current balances
#         outstanding = float(self._customer.get("outstanding_amount", 0))
#         laybye = float(self._customer.get("laybye_balance", 0))

#         W = 40
#         lines = [
#             "=" * W,
#             "      HAVANO POS — PAYMENT RECEIPT",
#             f"  Receipt No: {p_id_str}",
#             f"  Date:       {pdate}",
#             f"  Customer:   {cname}",
#         ]

#         if self._payment_type == "laybye":
#             lines.append(f"  Payment Type: LAYBYE PAYMENT")
#             lines.append(f"  Balance After: ${laybye:.2f}")
#         else:
#             lines.append(f"  Payment Type: OUTSTANDING BALANCE")
#             lines.append(f"  Balance After: ${outstanding:.2f}")

#         lines += [
#             "-" * W,
#             f"  Account:    {account}",
#             f"  Method:     {method}",
#             f"  Amount:     USD {amount:.2f}",
#         ]
#         if ref:
#             lines.append(f"  Ref:        {ref}")
#         lines += [
#             "-" * W,
#             f"  Frappe:     {frappe_status.upper()}",
#             "=" * W,
#             "\n   Thank you for your payment!",
#         ]

#         # 4. Create and Show the Dialog
#         dlg = QDialog(self)
#         dlg.setWindowTitle("Payment Receipt Preview")
#         dlg.setMinimumSize(380, 420)
#         white = getattr(self, '_WHITE', '#FFFFFF')
#         navy = getattr(self, '_NAVY', '#001f3f')
#         border = getattr(self, '_BORDER', '#CCCCCC')
#         navy2 = getattr(self, '_NAVY_2', '#003366')

#         dlg.setStyleSheet(f"QDialog {{ background:{white}; }}")
#         lay = QVBoxLayout(dlg)
#         lay.setContentsMargins(16,16,16,16)
#         lay.setSpacing(10)

#         txt = QTextEdit()
#         txt.setReadOnly(True)
#         txt.setFont(QFont("Courier New", 10))
#         txt.setPlainText("\n".join(lines))
#         txt.setStyleSheet(
#             f"QTextEdit {{ background:{white}; color:{navy};"
#             f" border:1px solid {border}; border-radius:4px; }}"
#         )
#         lay.addWidget(txt, 1)

#         br = QHBoxLayout()
#         br.setSpacing(8)
#         close_btn = QPushButton("Close")
#         close_btn.setFixedHeight(36)
#         close_btn.setCursor(Qt.PointingHandCursor)
#         close_btn.setStyleSheet(
#             f"QPushButton {{ background:{navy}; color:{white}; border:none;"
#             f" border-radius:5px; font-size:13px; font-weight:bold; padding:0 20px; }}"
#             f"QPushButton:hover {{ background:{navy2}; }}"
#         )
#         close_btn.clicked.connect(dlg.accept)
#         br.addStretch()
#         br.addWidget(close_btn)
#         lay.addLayout(br)

#         dlg.exec()

#     # ── keyboard ──────────────────────────────────────────────────────────
#     def keyPressEvent(self, event):
#         k = event.key()
#         if k == Qt.Key_Escape:
#             self.reject()
#         else:
#             super().keyPressEvent(event)

#     def showEvent(self, event):
#         super().showEvent(event)
#         self._refresh_balances()
#         if self._active_method:
# 
# self._activate(self._active_method)
# =============================================================================
# REPRINT DIALOG  —  two tabs: Sales Invoice  |  Sales Order
# =============================================================================
class ReprintDialog(QDialog):
    """
    Two-tab reprint dialog.
      Tab 1 — Sales Invoice : search by invoice number or customer name
      Tab 2 — Sales Order   : search by order number or customer name
    Select a record → click Reprint → sends straight to the configured printer.
    """

    # shared stylesheet pieces
    _SEARCH_SS = f"""
        QLineEdit {{
            background:{WHITE}; color:{NAVY};
            border:2px solid {BORDER}; border-radius:6px;
            font-size:13px; padding:0 12px;
        }}
        QLineEdit:focus {{ border:2px solid {ACCENT}; }}
    """
    _LIST_SS = f"""
        QListWidget {{
            background:{WHITE}; border:2px solid {ACCENT};
            border-top:none; border-radius:0 0 6px 6px;
            font-size:13px; color:{NAVY}; outline:none;
        }}
        QListWidget::item                  {{ padding:7px 14px; min-height:28px; color:{NAVY}; }}
        QListWidget::item:hover            {{ background:{LIGHT}; color:{NAVY}; }}
        QListWidget::item:selected         {{ background:{ACCENT}; color:{WHITE}; }}
        QListWidget::item:selected:active  {{ background:{ACCENT}; color:{WHITE}; }}
        QListWidget::item:selected:!active {{ background:{ACCENT}; color:{WHITE}; }}
    """
    _BTN_REPRINT_SS = f"""
        QPushButton {{ background:{ACCENT}; color:{WHITE}; border:none;
            border-radius:6px; font-size:13px; font-weight:bold; }}
        QPushButton:hover    {{ background:{ACCENT_H}; }}
        QPushButton:disabled {{ background:{LIGHT}; color:{MUTED}; }}
    """
    _BTN_CANCEL_SS = f"""
        QPushButton {{ background:{LIGHT}; color:{NAVY};
            border:1px solid {BORDER}; border-radius:6px;
            font-size:13px; font-weight:bold; }}
        QPushButton:hover {{ background:{BORDER}; }}
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reprint")
        self.setMinimumSize(660, 240)
        self.setModal(True)
        self.setStyleSheet(
            f"QDialog {{ background:{OFF_WHITE}; font-family:'Segoe UI',sans-serif; }}"
        )

        # ── data stores ───────────────────────────────────────────────────────
        self._inv_sales: list[dict] = []   # all sales invoices
        self._so_orders: list[dict] = []   # all sales orders

        self._inv_selected: dict | None = None
        self._so_selected:  dict | None = None

        # ── debounce timers ───────────────────────────────────────────────────
        self._inv_timer = QTimer(self); self._inv_timer.setSingleShot(True); self._inv_timer.setInterval(200)
        self._so_timer  = QTimer(self); self._so_timer.setSingleShot(True);  self._so_timer.setInterval(200)
        self._inv_timer.timeout.connect(self._inv_search)
        self._so_timer.timeout.connect(self._so_search)

        self._build()
        QTimer.singleShot(0, self._preload)

    # ── preload ───────────────────────────────────────────────────────────────

    def _preload(self):
        try:
            from models.sale import get_all_sales
            self._inv_sales = get_all_sales()
        except Exception:
            self._inv_sales = []

        try:
            from models.sales_order import get_all_sales_orders
            self._so_orders = get_all_sales_orders()
        except Exception:
            self._so_orders = []

        # run initial search if boxes are pre-filled
        if self._inv_search_box.text().strip():
            self._inv_search()
        if self._so_search_box.text().strip():
            self._so_search()

    # ── build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)

        # ── header ────────────────────────────────────────────────────────────
        hdr = QWidget(); hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{WHITE}; border-bottom:2px solid {BORDER};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20, 0, 20, 0)
        title = QLabel("🖨  Reprint")
        title.setStyleSheet(f"color:{NAVY}; font-size:16px; font-weight:bold; background:transparent;")
        sub = QLabel("Choose Sales Invoice or Sales Order")
        sub.setStyleSheet(f"color:{MUTED}; font-size:11px; background:transparent;")
        hl.addWidget(title); hl.addSpacing(12); hl.addWidget(sub); hl.addStretch()
        root.addWidget(hdr)

        # ── tabs ──────────────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane   {{ border:none; background:{OFF_WHITE}; }}
            QTabBar::tab       {{ background:{LIGHT}; color:{NAVY}; padding:8px 22px;
                                  font-size:13px; font-weight:bold; border:none;
                                  border-bottom:3px solid transparent; }}
            QTabBar::tab:selected  {{ background:{OFF_WHITE}; border-bottom:3px solid {ACCENT}; }}
            QTabBar::tab:hover     {{ background:{BORDER}; }}
        """)
        self._tabs.addTab(self._build_invoice_tab(), "🧾  Sales Invoice")
        self._tabs.addTab(self._build_order_tab(),   "📋  Sales Order")
        root.addWidget(self._tabs, 1)

    def _build_invoice_tab(self) -> QWidget:
        """Sales Invoice search + reprint panel."""
        w  = QWidget(); w.setStyleSheet(f"background:{OFF_WHITE};")
        bl = QVBoxLayout(w); bl.setContentsMargins(24, 16, 24, 16); bl.setSpacing(6)

        # search row
        sr = QHBoxLayout(); sr.setSpacing(8)
        lbl = QLabel("Invoice / Customer:"); lbl.setFixedWidth(140)
        lbl.setStyleSheet(f"color:{MUTED}; font-size:11px; font-weight:bold; background:transparent;")
        self._inv_search_box = QLineEdit()
        self._inv_search_box.setPlaceholderText("Type invoice number or customer name…")
        self._inv_search_box.setFixedHeight(38)
        self._inv_search_box.setStyleSheet(self._SEARCH_SS)
        try:
            prefill = getattr(self.parent(), "_prev_invoice", "")
            if prefill: self._inv_search_box.setText(prefill)
        except Exception:
            pass
        self._inv_search_box.textChanged.connect(lambda _: self._inv_timer.start())
        self._inv_search_box.returnPressed.connect(self._inv_on_enter)
        sr.addWidget(lbl); sr.addWidget(self._inv_search_box, 1)
        bl.addLayout(sr)

        # autocomplete list
        self._inv_ac = QListWidget(); self._inv_ac.setFixedHeight(0)
        self._inv_ac.setStyleSheet(self._LIST_SS)
        self._inv_ac.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._inv_ac.itemClicked.connect(self._inv_item_clicked)
        self._inv_ac.itemActivated.connect(self._inv_item_activated)
        ac_row = QHBoxLayout(); ac_row.setContentsMargins(148, 0, 0, 0)
        ac_row.addWidget(self._inv_ac)
        bl.addLayout(ac_row)

        # buttons
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        bcancel = QPushButton("Cancel"); bcancel.setFixedHeight(40); bcancel.setFixedWidth(90)
        bcancel.setCursor(Qt.PointingHandCursor); bcancel.setStyleSheet(self._BTN_CANCEL_SS)
        bcancel.clicked.connect(self.reject)
        self._inv_btn = QPushButton("🖨  Reprint Invoice")
        self._inv_btn.setFixedHeight(40); self._inv_btn.setEnabled(False)
        self._inv_btn.setCursor(Qt.PointingHandCursor)
        self._inv_btn.setStyleSheet(self._BTN_REPRINT_SS)
        self._inv_btn.clicked.connect(self._inv_do_reprint)
        btn_row.addWidget(bcancel); btn_row.addStretch(); btn_row.addWidget(self._inv_btn)
        bl.addLayout(btn_row)
        return w

    def _build_order_tab(self) -> QWidget:
        """Sales Order search + reprint panel."""
        w  = QWidget(); w.setStyleSheet(f"background:{OFF_WHITE};")
        bl = QVBoxLayout(w); bl.setContentsMargins(24, 16, 24, 16); bl.setSpacing(6)

        # search row
        sr = QHBoxLayout(); sr.setSpacing(8)
        lbl = QLabel("Order No / Customer:"); lbl.setFixedWidth(140)
        lbl.setStyleSheet(f"color:{MUTED}; font-size:11px; font-weight:bold; background:transparent;")
        self._so_search_box = QLineEdit()
        self._so_search_box.setPlaceholderText("Type order number or customer name…")
        self._so_search_box.setFixedHeight(38)
        self._so_search_box.setStyleSheet(self._SEARCH_SS)
        self._so_search_box.textChanged.connect(lambda _: self._so_timer.start())
        self._so_search_box.returnPressed.connect(self._so_on_enter)
        sr.addWidget(lbl); sr.addWidget(self._so_search_box, 1)
        bl.addLayout(sr)

        # autocomplete list
        self._so_ac = QListWidget(); self._so_ac.setFixedHeight(0)
        self._so_ac.setStyleSheet(self._LIST_SS)
        self._so_ac.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._so_ac.itemClicked.connect(self._so_item_clicked)
        self._so_ac.itemActivated.connect(self._so_item_activated)
        ac_row = QHBoxLayout(); ac_row.setContentsMargins(148, 0, 0, 0)
        ac_row.addWidget(self._so_ac)
        bl.addLayout(ac_row)

        # buttons
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        bcancel = QPushButton("Cancel"); bcancel.setFixedHeight(40); bcancel.setFixedWidth(90)
        bcancel.setCursor(Qt.PointingHandCursor); bcancel.setStyleSheet(self._BTN_CANCEL_SS)
        bcancel.clicked.connect(self.reject)
        self._so_btn = QPushButton("🖨  Reprint Sales Order")
        self._so_btn.setFixedHeight(40); self._so_btn.setEnabled(False)
        self._so_btn.setCursor(Qt.PointingHandCursor)
        self._so_btn.setStyleSheet(self._BTN_REPRINT_SS)
        self._so_btn.clicked.connect(self._so_do_reprint)
        btn_row.addWidget(bcancel); btn_row.addStretch(); btn_row.addWidget(self._so_btn)
        bl.addLayout(btn_row)
        return w

    # ── Sales Invoice search / select / reprint ───────────────────────────────

    def _inv_search(self):
        q = self._inv_search_box.text().strip().lower()
        self._inv_ac.clear(); self._inv_selected = None; self._inv_btn.setEnabled(False)
        if not q: self._inv_ac.setFixedHeight(0); return
        matches = [s for s in self._inv_sales
                   if q in (s.get("invoice_no") or "").lower()
                   or q in (s.get("customer_name") or "").lower()][:15]
        if not matches: self._inv_ac.setFixedHeight(0); return
        for s in matches:
            inv  = s.get("invoice_no", "")
            cust = s.get("customer_name") or "Walk-in"
            amt  = float(s.get("total", 0))
            dt   = s.get("invoice_date", "") or s.get("date", "")
            it = QListWidgetItem(f"{inv}   ·   {cust}   ·   ${amt:.2f}   ·   {dt}")
            it.setData(Qt.UserRole, s); self._inv_ac.addItem(it)
        self._inv_ac.setFixedHeight(min(len(matches), 6) * 42)
        self._inv_ac.setCurrentRow(0)

    def _inv_item_clicked(self, item):
        s = item.data(Qt.UserRole)
        self._inv_selected = s
        self._inv_search_box.setText(s.get("invoice_no", ""))
        self._inv_ac.setFixedHeight(0); self._inv_ac.clear()
        self._inv_btn.setEnabled(True)

    def _inv_item_activated(self, item):
        self._inv_item_clicked(item); self._inv_do_reprint()

    def _inv_on_enter(self):
        cur = self._inv_ac.currentItem()
        if cur and self._inv_ac.count():
            self._inv_item_activated(cur)
        elif self._inv_selected:
            self._inv_do_reprint()
        else:
            self._inv_search()
            if self._inv_ac.count() == 1:
                self._inv_item_activated(self._inv_ac.item(0))

    def _inv_do_reprint(self):
        sale = self._inv_selected
        if not sale: return
        try:
            from models.sale import get_sale_items
            sale["items"] = get_sale_items(sale["id"])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load items:\n{e}"); return
        try:
            self.parent()._print_receipt_for_sale(sale)
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not print:\n{e}")

    # ── Sales Order search / select / reprint ─────────────────────────────────

    def _so_search(self):
        q = self._so_search_box.text().strip().lower()
        self._so_ac.clear(); self._so_selected = None; self._so_btn.setEnabled(False)
        if not q: self._so_ac.setFixedHeight(0); return
        matches = [o for o in self._so_orders
                   if q in (o.get("order_no") or "").lower()
                   or q in (o.get("customer_name") or "").lower()][:15]
        if not matches: self._so_ac.setFixedHeight(0); return
        for o in matches:
            ono  = o.get("order_no", "")
            cust = o.get("customer_name") or "Walk-in"
            amt  = float(o.get("total", 0))
            bal  = float(o.get("balance_due", 0))
            dt   = o.get("order_date", "")
            it = QListWidgetItem(f"{ono}   ·   {cust}   ·   ${amt:.2f}   ·   Bal ${bal:.2f}   ·   {dt}")
            it.setData(Qt.UserRole, o); self._so_ac.addItem(it)
        self._so_ac.setFixedHeight(min(len(matches), 6) * 42)
        self._so_ac.setCurrentRow(0)

    def _so_item_clicked(self, item):
        o = item.data(Qt.UserRole)
        self._so_selected = o
        self._so_search_box.setText(o.get("order_no", ""))
        self._so_ac.setFixedHeight(0); self._so_ac.clear()
        self._so_btn.setEnabled(True)

    def _so_item_activated(self, item):
        self._so_item_clicked(item); self._so_do_reprint()

    def _so_on_enter(self):
        cur = self._so_ac.currentItem()
        if cur and self._so_ac.count():
            self._so_item_activated(cur)
        elif self._so_selected:
            self._so_do_reprint()
        else:
            self._so_search()
            if self._so_ac.count() == 1:
                self._so_item_activated(self._so_ac.item(0))

    def _so_do_reprint(self):
        order = self._so_selected
        if not order: return
        try:
            from models.sales_order import get_order_by_id
            full_order = get_order_by_id(order["id"])
            if not full_order:
                QMessageBox.warning(self, "Error", "Could not load order details."); return
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load order:\n{e}"); return
        try:
            from services.sales_order_print import print_sales_order
            ok = print_sales_order(full_order["id"])
            if ok:
                QMessageBox.information(self, "Reprint", f"Sales Order {full_order.get('order_no', '')} sent to printer.")
                self.accept()
            else:
                QMessageBox.warning(self, "Reprint Failed", "Printing failed. Check printer connection.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not print:\n{e}")

    # ── keyboard navigation ───────────────────────────────────────────────────

    def keyPressEvent(self, e):
        k = e.key()
        # figure out which tab is active
        idx = self._tabs.currentIndex()
        ac       = self._inv_ac       if idx == 0 else self._so_ac
        on_enter = self._inv_on_enter if idx == 0 else self._so_on_enter

        if k in (Qt.Key_Return, Qt.Key_Enter):
            on_enter()
        elif k == Qt.Key_Escape:
            self.reject()
        elif k == Qt.Key_Down:
            if ac.count():
                ac.setCurrentRow(min(ac.currentRow() + 1, ac.count() - 1))
                ac.setFocus()
        elif k == Qt.Key_Up:
            if ac.count():
                ac.setCurrentRow(max(ac.currentRow() - 1, 0))
                ac.setFocus()
        else:
            super().keyPressEvent(e)


class CreditNoteDialog(QDialog):
    """Search-only dialog. Enter/click → confirmation popup → items load into POSView."""

    credit_note_ready = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Credit Note / Return")
        self.setFixedSize(600, 170)
        self.setModal(True)
        self.setStyleSheet(
            f"QDialog {{ background:{WHITE}; font-family:'Segoe UI',sans-serif; }}"
        )
        self._all_sales = []
        self._stimer = QTimer(self)
        self._stimer.setSingleShot(True)
        self._stimer.setInterval(200)
        self._stimer.timeout.connect(self._run_search)
        self._build()
        QTimer.singleShot(0, self._preload)

    def _preload(self):
        try:
            from models.sale import get_all_sales
            self._all_sales = get_all_sales()
        except Exception:
            self._all_sales = []

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 14)
        root.setSpacing(10)
        title = QLabel("Credit Note / Return")
        title.setStyleSheet(
            f"color:{NAVY}; font-size:15px; font-weight:bold; background:transparent;"
        )
        root.addWidget(title)
        row = QHBoxLayout(); row.setSpacing(8)
        lbl = QLabel("Invoice / Customer:")
        lbl.setFixedWidth(140)
        lbl.setStyleSheet(
            f"color:{MUTED}; font-size:11px; font-weight:bold; background:transparent;"
        )
        self._search = QLineEdit()
        self._search.setPlaceholderText("Type invoice number or customer name…")
        self._search.setFixedHeight(36)
        self._search.setStyleSheet(
            f"QLineEdit {{ background:{WHITE}; color:{DARK_TEXT};"
            f" border:2px solid {BORDER}; border-radius:6px;"
            f" font-size:13px; padding:0 12px; }}"
            f"QLineEdit:focus {{ border:2px solid {ACCENT}; }}"
        )
        self._search.textChanged.connect(lambda _: self._stimer.start())
        self._search.returnPressed.connect(self._run_search)
        row.addWidget(lbl); row.addWidget(self._search, 1)
        root.addLayout(row)
        self._ac = QListWidget()
        self._ac.setFixedHeight(0)
        self._ac.setStyleSheet(
            f"QListWidget {{ background:{WHITE}; border:2px solid {ACCENT};"
            f" border-top:none; font-size:13px; color:{DARK_TEXT}; outline:none; }}"
            f"QListWidget::item {{ padding:7px 14px; min-height:28px; }}"
            f"QListWidget::item:selected {{ background:{ACCENT}; color:{WHITE}; }}"
            f"QListWidget::item:hover {{ background:{LIGHT}; }}"
        )
        self._ac.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._ac.itemClicked.connect(self._pick)
        ac_row = QHBoxLayout()
        ac_row.setContentsMargins(148, 0, 0, 0)
        ac_row.addWidget(self._ac)
        root.addLayout(ac_row)
        btn_row = QHBoxLayout(); btn_row.addStretch()
        bc = QPushButton("Cancel")
        bc.setFixedHeight(32); bc.setFixedWidth(80)
        bc.setCursor(Qt.PointingHandCursor); bc.setFocusPolicy(Qt.NoFocus)
        bc.setStyleSheet(
            f"QPushButton {{ background:{LIGHT}; color:{DARK_TEXT};"
            f" border:1px solid {BORDER}; border-radius:6px; font-size:12px; }}"
            f"QPushButton:hover {{ background:{BORDER}; }}"
        )
        bc.clicked.connect(self.reject)
        btn_row.addWidget(bc)
        root.addLayout(btn_row)

    def _run_search(self):
        q = self._search.text().strip()
        self._ac.clear()
        if not q:
            self._ac.setFixedHeight(0); self.setFixedSize(600, 170); return
        ql = q.lower()
        matches = [
            s for s in self._all_sales
            if ql in (s.get("invoice_no")    or "").lower()
            or ql in (s.get("frappe_ref")    or "").lower()
            or ql in (s.get("customer_name") or "").lower()
        ][:15]
        if not matches:
            self._ac.setFixedHeight(0); self.setFixedSize(600, 170); return
        # Exact match on local invoice_no OR frappe_ref → confirm then load
        exact = [
            s for s in matches
            if (s.get("invoice_no") or "").lower() == ql
            or (s.get("frappe_ref") or "").lower() == ql
        ]
        if exact:
            self._confirm_and_load(exact[0]); return
        if len(matches) == 1:
            self._confirm_and_load(matches[0]); return
        for s in matches:
            frappe = s.get("frappe_ref") or ""
            label = (
                f"{s.get('invoice_no', '?')}"
                + (f"  [{frappe}]" if frappe else "")
                + f"   ·   {s.get('customer_name') or 'Walk-in'}"
                + f"   ·   ${float(s.get('total', 0)):.2f}"
                + f"   ·   {s.get('invoice_date', '')}"
            )
            it = QListWidgetItem(label); it.setData(Qt.UserRole, s)
            self._ac.addItem(it)
        h = min(len(matches), 6) * 42
        self._ac.setFixedHeight(h); self.setFixedSize(600, 170 + h)

    def _pick(self, item: QListWidgetItem):
        self._confirm_and_load(item.data(Qt.UserRole))

    def _confirm_and_load(self, stub: dict):
        """Show confirmation popup before loading invoice into return mode."""
        inv_no   = stub.get("invoice_no", "?")
        customer = stub.get("customer_name") or "Walk-in"
        total    = float(stub.get("total", 0))
        inv_date = stub.get("invoice_date", "")
        frappe   = stub.get("frappe_ref", "")

        detail = (
            f"Invoice:   {inv_no}"
            + (f"  [{frappe}]" if frappe else "")
            + f"\nCustomer:  {customer}"
            + (f"\nDate:      {inv_date}" if inv_date else "")
            + f"\nTotal:     ${total:.2f}"
        )

        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Return")
        msg.setText(f"Load invoice <b>{inv_no}</b> for return?")
        msg.setInformativeText(detail)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        msg.setStyleSheet(f"""
            QMessageBox {{ background:{WHITE}; }}
            QLabel      {{ color:{DARK_TEXT}; font-size:13px; background:transparent; }}
            QPushButton {{
                background:{ACCENT}; color:{WHITE}; border:none;
                border-radius:6px; padding:8px 24px;
                font-size:13px; font-weight:bold; min-width:80px;
            }}
            QPushButton:hover {{ background:{ACCENT_H}; }}
        """)
        if msg.exec() != QMessageBox.Yes:
            return

        self._load_and_close(stub)

    def _load_and_close(self, stub: dict):
        sid = stub["id"]
        try:
            from models.sale import get_sale_by_id, get_sale_items
            full = get_sale_by_id(sid)
            if full and not full.get("items"):
                full["items"] = get_sale_items(sid)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load sale:\n{e}"); return
        if not full:
            QMessageBox.warning(self, "Not Found", "Sale not found."); return
        if not full.get("items"):
            QMessageBox.warning(
                self, "No Items",
                f"No items found for {full.get('invoice_no', '')}."
            ); return
        self.credit_note_ready.emit(full)
        self.accept()


class CreditNoteManagerDialog(QDialog):
    """Shows all credit notes with sync status. Select and push manually."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Credit Note Sync")
        self.setFixedSize(900, 520)
        self.setModal(True)
        self.setStyleSheet(
            f"QDialog {{ background:{OFF_WHITE}; font-family:'Segoe UI',sans-serif; }}"
        )
        self._cns = []
        self._build()
        QTimer.singleShot(0, self._load)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        hdr = QWidget(); hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{WHITE}; border-bottom:2px solid {BORDER};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(24, 0, 24, 0)
        t = QLabel("Credit Note Sync")
        t.setStyleSheet(f"color:{NAVY}; font-size:16px; font-weight:bold; background:transparent;")
        s = QLabel("Select credit notes and push to Frappe.")
        s.setStyleSheet(f"color:{MUTED}; font-size:11px; background:transparent;")
        hl.addWidget(t); hl.addSpacing(14); hl.addWidget(s); hl.addStretch()
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color:{SUCCESS}; font-size:11px; font-weight:bold; background:transparent;")
        hl.addWidget(self._status_lbl)
        root.addWidget(hdr)

        body = QWidget(); body.setStyleSheet(f"background:{OFF_WHITE};")
        bl = QVBoxLayout(body); bl.setContentsMargins(20, 14, 20, 14); bl.setSpacing(10)

        self._tbl = QTableWidget(0, 7)
        self._tbl.setHorizontalHeaderLabels(
            ["", "CN NUMBER", "INVOICE", "CUSTOMER", "TOTAL", "STATUS", "FRAPPE REF"])
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed);  self._tbl.setColumnWidth(0, 32)
        hh.setSectionResizeMode(1, QHeaderView.Fixed);  self._tbl.setColumnWidth(1, 130)
        hh.setSectionResizeMode(2, QHeaderView.Fixed);  self._tbl.setColumnWidth(2, 150)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.Fixed);  self._tbl.setColumnWidth(4, 80)
        hh.setSectionResizeMode(5, QHeaderView.Fixed);  self._tbl.setColumnWidth(5, 100)
        hh.setSectionResizeMode(6, QHeaderView.Fixed);  self._tbl.setColumnWidth(6, 160)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionMode(QAbstractItemView.NoSelection)
        self._tbl.setStyleSheet(
            f"QTableWidget {{ background:{WHITE}; border:1px solid {BORDER};"
            f" gridline-color:{LIGHT}; font-size:12px; outline:none; }}"
            f"QTableWidget::item {{ padding:4px 8px; }}"
            f"QTableWidget::item:alternate {{ background:{OFF_WHITE}; }}"
            f"QHeaderView::section {{ background:{NAVY}; color:{WHITE}; padding:6px;"
            f" border:none; border-right:1px solid {NAVY_2};"
            f" font-size:10px; font-weight:bold; }}"
        )
        self._tbl.cellClicked.connect(lambda r, c: self._toggle(r))
        bl.addWidget(self._tbl, 1)

        br = QHBoxLayout(); br.setSpacing(8)
        def _btn(text, w=None):
            b = QPushButton(text); b.setFixedHeight(36)
            b.setCursor(Qt.PointingHandCursor); b.setFocusPolicy(Qt.NoFocus)
            if w: b.setFixedWidth(w)
            b.setStyleSheet(
                f"QPushButton {{ background:{LIGHT}; color:{DARK_TEXT}; border:1px solid {BORDER};"
                f" border-radius:6px; font-size:12px; font-weight:bold; }}"
                f"QPushButton:hover {{ background:{BORDER}; }}"
            )
            return b

        sel_btn = _btn("Select Unsynced")
        sel_btn.clicked.connect(self._select_unsynced)
        ref_btn = _btn("Refresh")
        ref_btn.clicked.connect(self._load)

        self._sync_btn = QPushButton("\u2b06  Sync Selected")
        self._sync_btn.setFixedHeight(36); self._sync_btn.setFixedWidth(160)
        self._sync_btn.setCursor(Qt.PointingHandCursor)
        self._sync_btn.setFocusPolicy(Qt.NoFocus)
        self._sync_btn.setEnabled(False)
        self._sync_btn.setStyleSheet(
            f"QPushButton {{ background:{SUCCESS}; color:{WHITE}; border:none;"
            f" border-radius:6px; font-size:12px; font-weight:bold; }}"
            f"QPushButton:hover    {{ background:{SUCCESS_H}; }}"
            f"QPushButton:disabled {{ background:{LIGHT}; color:{MUTED}; }}"
        )
        self._sync_btn.clicked.connect(self._sync_selected)

        close_btn = _btn("Close", 80)
        close_btn.clicked.connect(self.accept)

        br.addWidget(sel_btn); br.addWidget(ref_btn)
        br.addStretch()
        br.addWidget(self._sync_btn); br.addWidget(close_btn)
        bl.addLayout(br)
        root.addWidget(body, 1)

    def _load(self):
        try:
            from database.db import get_connection
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""
                SELECT id, cn_number, original_invoice_no,
                       customer_name, total, cn_status,
                       COALESCE(frappe_cn_ref,'') AS frappe_cn_ref,
                       COALESCE(frappe_ref,'')    AS frappe_ref
                FROM   credit_notes
                ORDER  BY created_at DESC
            """)
            cols = [d[0] for d in cur.description]
            self._cns = [dict(zip(cols, r)) for r in cur.fetchall()]
            conn.close()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load credit notes:\n{e}"); return

        self._tbl.setRowCount(0)
        for cn in self._cns:
            r = self._tbl.rowCount(); self._tbl.insertRow(r)
            self._tbl.setRowHeight(r, 36)
            chk = QTableWidgetItem(); chk.setCheckState(Qt.Unchecked)
            chk.setTextAlignment(Qt.AlignCenter); self._tbl.setItem(r, 0, chk)
            self._tbl.setItem(r, 1, QTableWidgetItem(cn.get("cn_number","")))
            self._tbl.setItem(r, 2, QTableWidgetItem(cn.get("original_invoice_no","")))
            self._tbl.setItem(r, 3, QTableWidgetItem(cn.get("customer_name","") or "Walk-in"))
            amt = QTableWidgetItem(f"${float(cn.get('total',0)):.2f}")
            amt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter); self._tbl.setItem(r, 4, amt)
            status = cn.get("cn_status","")
            si = QTableWidgetItem(status)
            si.setForeground(QColor(
                SUCCESS if status=="synced" else AMBER if status=="ready" else MUTED))
            si.setTextAlignment(Qt.AlignCenter); self._tbl.setItem(r, 5, si)
            self._tbl.setItem(r, 6, QTableWidgetItem(
                cn.get("frappe_cn_ref","") or cn.get("frappe_ref","") or "—"))

        ready = sum(1 for c in self._cns if c.get("cn_status") != "synced")
        self._status_lbl.setText(f"{len(self._cns)} total  \u00b7  {ready} unsynced")
        self._update_sync_btn()

    def _toggle(self, row):
        chk = self._tbl.item(row, 0)
        if chk:
            chk.setCheckState(Qt.Unchecked if chk.checkState()==Qt.Checked else Qt.Checked)
        self._update_sync_btn()

    def _select_unsynced(self):
        for r in range(self._tbl.rowCount()):
            st = self._tbl.item(r, 5).text() if self._tbl.item(r, 5) else ""
            chk = self._tbl.item(r, 0)
            if chk:
                chk.setCheckState(Qt.Checked if st != "synced" else Qt.Unchecked)
        self._update_sync_btn()

    def _update_sync_btn(self):
        n = sum(1 for r in range(self._tbl.rowCount())
                if self._tbl.item(r,0) and self._tbl.item(r,0).checkState()==Qt.Checked)
        self._sync_btn.setEnabled(n > 0)
        self._sync_btn.setText(f"\u2b06  Sync {n} Selected" if n else "\u2b06  Sync Selected")

    def _sync_selected(self):
        ids = []
        for r in range(self._tbl.rowCount()):
            chk = self._tbl.item(r, 0)
            if chk and chk.checkState()==Qt.Checked and r < len(self._cns):
                ids.append(self._cns[r]["id"])
        if not ids: return

        self._sync_btn.setEnabled(False)
        self._sync_btn.setText("Syncing\u2026")
        QApplication.processEvents()

        pushed=0; failed=0; no_ref=0
        try:
            from services.credit_note_sync_service import (
                _push_cn, _get_credentials, _get_defaults, _get_host)
            from models.credit_note import mark_cn_synced
            from database.db import get_connection

            api_key, api_secret = _get_credentials()
            if not api_key:
                QMessageBox.warning(self, "No Credentials",
                    "No API credentials found.\nCheck company settings.")
                return

            host=_get_host(); defaults=_get_defaults()
            conn=get_connection(); cur=conn.cursor()
            for cn_id in ids:
                cur.execute("""
                    SELECT id, cn_number, original_invoice_no, customer_name,
                           total, currency, cn_status,
                           COALESCE(frappe_ref,'')    AS frappe_ref,
                           COALESCE(frappe_cn_ref,'') AS frappe_cn_ref
                    FROM credit_notes WHERE id=?
                """, (cn_id,))
                row=cur.fetchone()
                if not row: continue
                cols=[d[0] for d in cur.description]; cn=dict(zip(cols,row))
                cur.execute(
                    "SELECT part_no,product_name,qty,price,total,reason "
                    "FROM credit_note_items WHERE credit_note_id=?", (cn_id,))
                ic=[d[0] for d in cur.description]
                cn["items_to_return"]=[dict(zip(ic,ir)) for ir in cur.fetchall()]
                if not cn.get("frappe_ref"): no_ref+=1; continue
                val=_push_cn(cn, api_key, api_secret, defaults, host)
                if val:
                    mark_cn_synced(cn["id"], val if isinstance(val,str) else "")
                    pushed+=1
                else:
                    failed+=1
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "Sync Error", str(e)); return
        finally:
            self._load()

        msg = f"\u2705 Pushed: {pushed}"
        if failed: msg += f"  \u274c Failed: {failed}"
        if no_ref: msg += f"  \u23f3 No Frappe ref: {no_ref}"
        self._status_lbl.setText(msg)
        if no_ref:
            QMessageBox.information(self, "Some Skipped",
                f"{no_ref} credit note(s) skipped — original sale not yet in Frappe.\n"
                "Wait for the sale to sync first, then retry.")

# =============================================================================
# ADD THIS CLASS TO views/main_window.py
# (Paste it near the bottom, after CreditNoteDialog / ShiftReconciliationDialog)
# =============================================================================

# =============================================================================
# ADVANCE SETTINGS DIALOG (with logo copy + preview)
# =============================================================================
class AdvanceSettingsDialog(QDialog):
    """
    Full UI for advanced printing settings
    - Logo is copied to app_data/logos/logo.png
    - Preview shown immediately
    - Only relative path is saved
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🖨 Advanced Printing & Receipt Settings")
        self.setMinimumSize(920, 680)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background-color: {OFF_WHITE}; }}")

        self.settings = AdvanceSettings.load_from_file()

        # Logo destination folder
        self.app_data_dir = Path("app_data/logos")
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        self.default_logo_name = "logo.png"

        self.selected_logo_path = None   # temporary path chosen by user

        self._build_ui()
        self._update_logo_preview()      # show current logo if any

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 20, 20, 20)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:8px;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 0, 20, 0)
        title = QLabel("Advanced Printing Settings")
        title.setStyleSheet(f"font-size:18px; font-weight:bold; color:{WHITE};")
        hl.addWidget(title)
        hl.addStretch()
        root.addWidget(hdr)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_fonts_tab(), "Fonts")
        self.tabs.addTab(self._create_logo_tab(), "Logo & Layout")
        self.tabs.addTab(self._create_receipt_tab(), "Receipt Layout")
        root.addWidget(self.tabs, 1)

        # Bottom buttons
        btn_row = QHBoxLayout()
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setFixedHeight(40)
        reset_btn.clicked.connect(self._reset_to_defaults)

        save_btn = navy_btn("💾 Save & Apply", height=40, color=SUCCESS, hover=SUCCESS_H)
        save_btn.clicked.connect(self._save_and_close)

        cancel_btn = navy_btn("Cancel", height=40, color=DANGER, hover=DANGER_H)
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        root.addLayout(btn_row)

    # =====================================================================
    # TAB 1 – Fonts
    # =====================================================================
    def _create_fonts_tab(self):
        w = QWidget()
        lay = QFormLayout(w)
        lay.setSpacing(16)
        lay.setLabelAlignment(Qt.AlignRight)

        def font_row(label, name_val, size_val, style_val):
            name_cb = self._font_combo(name_val)
            size_sb = QSpinBox(); size_sb.setRange(6, 30); size_sb.setValue(size_val)
            style_cb = self._style_combo(style_val)
            row = QHBoxLayout()
            row.addWidget(name_cb, 3)
            row.addWidget(size_sb, 1)
            row.addWidget(style_cb, 2)
            lay.addRow(label + ":", row)
            return name_cb, size_sb, style_cb

        self.cb_content_name, self.sb_content_size, self.cb_content_style = font_row(
            "Content Font", self.settings.contentFontName, self.settings.contentFontSize, self.settings.contentFontStyle)

        self.cb_header_name, self.sb_header_size, self.cb_header_style = font_row(
            "Header Font", self.settings.contentHeaderFontName, self.settings.contentHeaderSize, self.settings.contentHeaderStyle)

        self.cb_sub_name, self.sb_sub_size, self.cb_sub_style = font_row(
            "Subheader Font", self.settings.subheaderFontName, self.settings.subheaderSize, self.settings.subheaderStyle)

        self.cb_order_name, self.sb_order_size, self.cb_order_style = font_row(
            "Order Content", self.settings.orderContentFontName, self.settings.orderContentFontSize, self.settings.orderContentStyle)

        return w

    # =====================================================================
    # TAB 2 – Logo & Layout (with preview + copy)
    # =====================================================================
    def _create_logo_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(20)
        lay.setContentsMargins(20, 20, 20, 20)

        # Characters per line
        row = QHBoxLayout()
        row.addWidget(QLabel("Characters per line:"))
        self.sb_chars = QSpinBox()
        self.sb_chars.setRange(30, 80)
        self.sb_chars.setValue(self.settings.charactersPerLine)
        row.addWidget(self.sb_chars)
        lay.addLayout(row)

        # Logo section
        group = QVBoxLayout()
        group.setSpacing(12)

        lbl = QLabel("Receipt Logo")
        lbl.setStyleSheet("font-weight:bold; font-size:14px;")
        group.addWidget(lbl)

        sel_row = QHBoxLayout()
        self.btn_browse = QPushButton("Select Logo Image...")
        self.btn_browse.setFixedWidth(180)
        self.btn_browse.clicked.connect(self._browse_logo)

        self.lbl_path = QLabel(self.settings.logoDirectory or "No logo selected")
        self.lbl_path.setWordWrap(True)
        self.lbl_path.setStyleSheet(f"color:{MUTED};")

        sel_row.addWidget(self.btn_browse)
        sel_row.addWidget(self.lbl_path, 1)
        group.addLayout(sel_row)

        # Preview
        self.preview_label = QLabel()
        self.preview_label.setFixedSize(240, 120)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet(f"QLabel {{ background:white; border:2px dashed {BORDER}; border-radius:6px; }}")
        group.addWidget(self.preview_label, alignment=Qt.AlignCenter)

        note = QLabel("Logo will be copied to app_data/logos/logo.png")
        note.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        group.addWidget(note)

        lay.addLayout(group)
        lay.addStretch()
        return w

    def _browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Logo", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self.selected_logo_path = path
            self.lbl_path.setText(path)
            self._update_logo_preview(path)

    def _update_logo_preview(self, path=None):
        if path is None:
            path = self.settings.logoDirectory
        if not path or not os.path.isfile(path):
            self.preview_label.setText("No logo\nPreview")
            self.preview_label.setPixmap(QPixmap())
            return

        pix = QPixmap(path)
        if pix.isNull():
            self.preview_label.setText("Invalid image")
        else:
            scaled = pix.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setPixmap(scaled)

    # =====================================================================
    # TAB 3 – Receipt Layout
    # =====================================================================
    def _create_receipt_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)

        self.chk_subtotal = QCheckBox("Show Subtotal line (exclusive of VAT)")
        self.chk_subtotal.setChecked(self.settings.showSubtotalExclusive)

        self.chk_inclusive = QCheckBox("Show Inclusive VAT total")
        self.chk_inclusive.setChecked(self.settings.showInclusive)

        self.chk_desc = QCheckBox("Show \"Description\" label")
        self.chk_desc.setChecked(self.settings.showDescriptionLabel)

        self.chk_payment = QCheckBox("Show Paid / Change / Payment Mode")
        self.chk_payment.setChecked(self.settings.showPayment)

        for chk in (self.chk_subtotal, self.chk_inclusive, self.chk_desc, self.chk_payment):
            lay.addWidget(chk)
        lay.addStretch()
        return w

    # =====================================================================
    # Helpers
    # =====================================================================
    def _font_combo(self, current):
        cb = QComboBox()
        cb.addItems(["Arial", "Times New Roman", "Courier New", "Helvetica", "Verdana", "Calibri"])
        cb.setCurrentText(current if current in ["Arial", "Times New Roman", "Courier New", "Helvetica", "Verdana", "Calibri"] else "Arial")
        return cb

    def _style_combo(self, current):
        cb = QComboBox()
        cb.addItems(["Regular", "Bold", "Italic", "Bold Italic"])
        cb.setCurrentText(current)
        return cb

    def _reset_to_defaults(self):
        if QMessageBox.question(self, "Reset", "Reset all settings to defaults?") != QMessageBox.Yes:
            return
        default = AdvanceSettings()
        # Fonts
        self.cb_content_name.setCurrentText(default.contentFontName)
        self.sb_content_size.setValue(default.contentFontSize)
        self.cb_content_style.setCurrentText(default.contentFontStyle)
        # ... (repeat for header, subheader, order — same as before)
        self.le_logo.setText("") if hasattr(self, 'le_logo') else None
        self.sb_chars.setValue(default.charactersPerLine)
        self.chk_subtotal.setChecked(default.showSubtotalExclusive)
        self.chk_inclusive.setChecked(default.showInclusive)
        self.chk_desc.setChecked(default.showDescriptionLabel)
        self.chk_payment.setChecked(default.showPayment)
        QMessageBox.information(self, "Reset", "Defaults loaded. Click Save to apply.")

    # =====================================================================
    # SAVE
    # =====================================================================
    
    def _save_and_close(self):
        # ── Fonts ─────────────────────────────────────────────────────
        self.settings.contentFontName      = self.cb_content_name.currentText()
        self.settings.contentFontSize      = self.sb_content_size.value()
        self.settings.contentFontStyle     = self.cb_content_style.currentText()

        self.settings.contentHeaderFontName = self.cb_header_name.currentText()
        self.settings.contentHeaderSize     = self.sb_header_size.value()
        self.settings.contentHeaderStyle    = self.cb_header_style.currentText()

        self.settings.subheaderFontName     = self.cb_sub_name.currentText()
        self.settings.subheaderSize         = self.sb_sub_size.value()
        self.settings.subheaderStyle        = self.cb_sub_style.currentText()

        self.settings.orderContentFontName  = self.cb_order_name.currentText()
        self.settings.orderContentFontSize  = self.sb_order_size.value()
        self.settings.orderContentStyle     = self.cb_order_style.currentText()

        # ── Layout ────────────────────────────────────────────────────
        self.settings.charactersPerLine = self.sb_chars.value()

        self.settings.showSubtotalExclusive = self.chk_subtotal.isChecked()
        self.settings.showInclusive         = self.chk_inclusive.isChecked()
        self.settings.showDescriptionLabel  = self.chk_desc.isChecked()
        self.settings.showPayment           = self.chk_payment.isChecked()

        # ── LOGO — FIXED VERSION ──────────────────────────────────────
        if self.selected_logo_path and os.path.isfile(self.selected_logo_path):
            try:
                dest_path = self.app_data_dir / self.default_logo_name
                shutil.copy2(self.selected_logo_path, dest_path)
                # We now store ONLY the filename (safest & cleanest)
                self.settings.logoDirectory = self.default_logo_name
            except Exception as e:
                QMessageBox.warning(self, "Logo Copy Failed",
                                    f"Could not copy logo:\n{str(e)}\n\n"
                                    "Settings saved without logo update.")
                self.settings.logoDirectory = ""
        # else: keep previous value (no change)

        # Save to JSON
        self.settings.save_to_file()

        QMessageBox.information(self, "Settings Saved",
            "Advanced printing settings updated.\n\n"
            "Logo has been copied to:\n"
            f"app_data\\logos\\{self.default_logo_name}\n\n"
            "Changes take effect on the next receipt print.")
        self.accept()
# =============================================================================
# ADD THIS TO THE MENU (inside MainWindow._build_menubar)
# =============================================================================


# =============================================================================
# SHIFT RECONCILIATION DIALOG (Requirement 4)
# =============================================================================
class ShiftReconciliationDialog(QDialog):
    def __init__(self, parent=None, cashier_id=None):
        super().__init__(parent)
        self.cashier_id = cashier_id
        self.setWindowTitle("Close Shift - Final Reconciliation")
        self.setFixedSize(500, 550)
        self.setStyleSheet(f"QDialog {{ background: {WHITE}; }}")
        self.final_data = []
        self._build_ui()
        self._load_expected_data()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        
        hdr = QLabel("🏁 End of Shift Reconciliation")
        hdr.setStyleSheet(f"background: {ORANGE}; color: {WHITE}; padding: 12px; font-weight: bold; border-radius: 5px; font-size: 14px;")
        lay.addWidget(hdr)

        instr = QLabel("Count your drawer and enter the actual amounts available below:")
        instr.setStyleSheet(f"color: {MUTED}; font-size: 11px; margin: 5px 0;")
        lay.addWidget(instr)

        # Table for Expected vs Actual
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Method", "Expected", "Actual", "Variance"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers) # We will use custom cell widgets
        lay.addWidget(self.table)

        # Totals Summary
        self.lbl_summary = QLabel("Total Variance: $0.00")
        self.lbl_summary.setAlignment(Qt.AlignCenter)
        self.lbl_summary.setStyleSheet(f"font-weight: bold; font-size: 15px; color: {NAVY}; padding: 10px; background: {LIGHT}; border-radius: 5px;")
        lay.addWidget(self.lbl_summary)

        # Buttons
        btns = QHBoxLayout()
        self.close_btn = navy_btn("Finalize & Close Shift", color=SUCCESS, hover=SUCCESS_H, height=45)
        self.close_btn.clicked.connect(self._on_finalize)
        
        cancel_btn = navy_btn("Back to POS", color=DANGER, hover=DANGER_H, height=45)
        cancel_btn.clicked.connect(self.reject)
        
        btns.addWidget(self.close_btn)
        btns.addWidget(cancel_btn)
        lay.addLayout(btns)

    def _load_expected_data(self):
        """Requirement 4: Fetches expected totals from sales + account payments"""
        try:
            from models.shift import get_income_by_method
            expected_map = get_income_by_method() # Now includes Account Payments
            
            methods = ["CASH", "C / CARD", "EFTPOS", "CHECK"]
            self.table.setRowCount(len(methods))
            
            for i, m in enumerate(methods):
                exp = expected_map.get(m, 0.0)
                
                # Method Name
                self.table.setItem(i, 0, QTableWidgetItem(m))
                
                # Expected (Read Only)
                exp_item = QTableWidgetItem(f"{exp:.2f}")
                exp_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, 1, exp_item)
                
                # Actual Input (Editable)
                actual_input = QLineEdit("0.00")
                actual_input.setAlignment(Qt.AlignRight)
                actual_input.setStyleSheet("border: 1px solid #1a5fb4; font-weight: bold;")
                actual_input.textChanged.connect(lambda _, row=i: self._update_variance(row))
                self.table.setCellWidget(i, 2, actual_input)
                
                # Variance (Calculated)
                var_item = QTableWidgetItem("0.00")
                var_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, 3, var_item)
                
        except Exception as e:
            QMessageBox.critical(self, "Data Error", f"Could not load shift totals: {str(e)}")

    def _update_variance(self, row):
        try:
            expected = float(self.table.item(row, 1).text())
            actual = float(self.table.cellWidget(row, 2).text() or 0)
            variance = actual - expected
            
            var_item = self.table.item(row, 3)
            var_item.setText(f"{variance:.2f}")
            
            # Visual feedback: Red for shortage
            if variance < 0:
                var_item.setForeground(QColor(DANGER))
            else:
                var_item.setForeground(QColor(SUCCESS))
                
            self._update_total_summary()
        except ValueError: pass

    def _update_total_summary(self):
        total_var = 0.0
        for r in range(self.table.rowCount()):
            total_var += float(self.table.item(r, 3).text())
        
        self.lbl_summary.setText(f"Total Shift Variance: ${total_var:.2f}")
        color = DANGER if total_var < 0 else SUCCESS
        self.lbl_summary.setStyleSheet(f"font-weight: bold; font-size: 15px; color: {color}; padding: 10px; background: {LIGHT}; border-radius: 5px;")

    def _on_finalize(self):
        """Requirement 4: Saves the final report with method, expected, available, and variance"""
        if QMessageBox.question(self, "Confirm", "Are you sure you want to close this shift? This will log you out.") != QMessageBox.Yes:
            return
            
        # Collect data for DB
        totals = []
        for r in range(self.table.rowCount()):
            totals.append({
                "method": self.table.item(r, 0).text(),
                "expected": float(self.table.item(r, 1).text()),
                "actual": float(self.table.cellWidget(r, 2).text() or 0)
            })
            
        try:
            from models.shift import end_shift
            # Retrieve active shift ID
            from models.shift import get_active_shift
            active = get_active_shift()
            
            if active:
                counted_map = {t['method']: t['actual'] for t in totals}
                end_shift(active['id'], counted_map)
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "No active shift found to close.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))


from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QFrame, QTableWidget, QTableWidgetItem,
    QLineEdit, QGridLayout, QMessageBox, QStatusBar, QSizePolicy,
    QDialog, QHeaderView, QAbstractItemView, QApplication,
    QListWidget, QListWidgetItem, QFormLayout, QComboBox, QScrollArea, QCompleter,
    QSpinBox, QDoubleSpinBox, QTabWidget, QFileDialog, QCheckBox, QMenu,
    QDateEdit,
)
import shutil
import os
import qtawesome as qta
from models.advance_settings import AdvanceSettings
from PySide6.QtCore import Qt, QTimer, QDate, Slot
# from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtGui import QAction, QColor, QFont, QPixmap
from pathlib import Path
try:
    from views.dialogs.day_shift_dialog import DayShiftDialog
    _HAS_DAY_SHIFT = True
except ImportError:
    _HAS_DAY_SHIFT = False

try:
    from views.dialogs.day_shift_dialog import ShiftChooserDialog
    _HAS_SHIFT_CHOOSER = True
except ImportError:
    _HAS_SHIFT_CHOOSER = False

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
from views.dialogs.quotation_dialog import show_quotation_dialog
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
from services.quotation_sync_service import start_quotation_sync_thread

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


# =============================================================================
# HOVER MENU BUTTON
# A nav-bar button that opens its QMenu both on click AND on hover.
# The menu stays open ("sticks") until the user clicks outside or presses Esc.
# =============================================================================

# =============================================================================
# SYNC ERROR BUS
# A singleton QObject that background sync threads post errors to (thread-safe).
# =============================================================================
try:
    from PySide6.QtCore import QObject as _QObj, Signal as _Sig

    class _SyncErrorBus(_QObj):
        error_posted = _Sig(str, str, str)   # (service, order_ref, message)
        _instance = None

        @classmethod
        def instance(cls):
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

        def post_error(self, service: str, order_ref: str, message: str):
            """Thread-safe: queued connection delivers to GUI thread."""
            self.error_posted.emit(service, order_ref, message)

    sync_error_bus = _SyncErrorBus.instance()

except Exception:
    class _DummyBus:
        def post_error(self, *a): pass
        class _FakeSig:
            def connect(self, *a): pass
            def emit(self, *a): pass
        error_posted = _FakeSig()
    sync_error_bus = _DummyBus()

class HoverMenuButton(QPushButton):
    """
    Drop-in replacement for a plain QPushButton when you want the popup menu
    to appear immediately on mouse-enter (hover) as well as on click.

    Usage:
        btn = HoverMenuButton("Maintenance", color=NAVY_2, hov=NAVY_3)
        btn.addItem("Companies",    some_callable)
        btn.addSeparator()
        btn.addItem("Users",        another_callable)
        layout.addWidget(btn)
    """

    def __init__(self, text: str, color=None, hov=None, height=26, parent=None):
        super().__init__(text, parent)
        self._bg  = color or NAVY_2
        self._hov = hov   or NAVY_3
        self._menu = QMenu(self)
        self._menu.setStyleSheet(f"""
            QMenu {{
                background-color: {WHITE};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 4px 0;
                font-size: 12px;
                color: {DARK_TEXT};
            }}
            QMenu::item {{
                padding: 8px 22px;
                border-radius: 4px;
                margin: 1px 4px;
            }}
            QMenu::item:selected {{
                background-color: {ACCENT};
                color: {WHITE};
            }}
            QMenu::separator {{
                height: 1px;
                background: {BORDER};
                margin: 3px 10px;
            }}
        """)
        self.setFixedHeight(height)
        self.setCursor(Qt.PointingHandCursor)
        self._apply_style(False)

        # Open menu on click too
        self.clicked.connect(self._show_menu)

    def addItem(self, label: str, callback):
        """Add a menu item (no emoji — keep labels clean)."""
        a = QAction(label, self)
        a.triggered.connect(callback)
        self._menu.addAction(a)

    def addSeparator(self):
        self._menu.addSeparator()

    def _apply_style(self, hovered: bool):
        bg = self._hov if hovered else self._bg
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg}; color: {WHITE}; border: none;
                border-radius: 3px; font-size: 11px; font-weight: bold; padding: 0 9px;
            }}
        """)

    def _show_menu(self):
        """Pop the menu directly below this button."""
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._apply_style(True)
        self._menu.exec(pos)
        self._apply_style(False)

    def enterEvent(self, event):
        """Hover → immediately show the menu."""
        super().enterEvent(event)
        self._show_menu()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._apply_style(False)


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
        self._uom_buttons: list[tuple[QPushButton, str, float]] = []
        self._active_idx = 0
        self._build(product_name, uom_prices)
        self._refresh_active_highlight()

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
            self._uom_buttons.append((btn, uom, price))
            root.addWidget(btn)
            if i < len(uom_prices) - 1:
                root.addSpacing(8)

        root.addSpacing(14)

        # ── Cancel ────────────────────────────────────────────────────
        cancel = QPushButton("Cancel")
        cancel.setIcon(qta.icon("fa5s.times"))
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

    # ── Keyboard navigation ──────────────────────────────────────────────
    def _refresh_active_highlight(self):
        """Apply a bright border to the active button, neutral to the rest.
        Buttons have Qt.NoFocus, so we style manually instead of relying on focus."""
        for i, (btn, _u, _p) in enumerate(self._uom_buttons):
            if i == self._active_idx:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {ACCENT};
                        border: 2px solid {NAVY};
                        border-radius: 10px;
                    }}
                    QPushButton QLabel {{ color: white; }}
                """)
            else:
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
                    QPushButton:hover QLabel {{ color: white; }}
                    QPushButton:pressed {{
                        background: {NAVY};
                        border-color: {NAVY};
                    }}
                """)

    def keyPressEvent(self, event):
        k = event.key()
        n = len(self._uom_buttons)
        if n == 0:
            return super().keyPressEvent(event)
        if k == Qt.Key_Up:
            self._active_idx = (self._active_idx - 1) % n
            self._refresh_active_highlight()
            return
        if k == Qt.Key_Down:
            self._active_idx = (self._active_idx + 1) % n
            self._refresh_active_highlight()
            return
        if k in (Qt.Key_Return, Qt.Key_Enter):
            _btn, uom, price = self._uom_buttons[self._active_idx]
            self._pick(uom, price)
            return
        if k == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)


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
        # Price List column shows the customer's `default_price_list` —
        # this is what governs pricing on the POS after selection.
        self._tbl = QTableWidget(0, 7)
        self._tbl.setHorizontalHeaderLabels([
            "Name", "Type", "Phone", "City", "Price List", "Laybye Bal", "Total Due",
        ])

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

        # Column order:  0 Name  1 Type  2 Phone  3 City
        #                4 Price List  5 Laybye  6 Total Due
        widths = {1: 80, 2: 110, 3: 100, 4: 140, 5: 110, 6: 110}
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
            
            # This handles making the new customer selected automatically
            def _handle_new_customer(cust_dict):
                self.selected_customer = cust_dict
                self.accept() # Close the popup immediately with this customer selected

            dlg.customer_created.connect(_handle_new_customer)
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

            # Price List (Column 4) — customer's default_price_list. Greyed
            # out when unset so cashiers notice the gap (sales will be
            # blocked for these customers).
            pl_name = (c.get("price_list_name") or "").strip()
            it_pl = create_item(pl_name or "—")
            if not pl_name:
                it_pl.setForeground(QColor(MUTED))
            self._tbl.setItem(r, 4, it_pl)

            # Laybye Balance (Column 5)
            l_bal = float(c.get("laybye_balance") or 0.0)
            it_l = QTableWidgetItem(f"{l_bal:,.2f}")
            it_l.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # Readable Blue
            it_l.setForeground(QColor("#0044cc")) if l_bal > 0 else it_l.setForeground(QColor(DARK_TEXT))
            self._tbl.setItem(r, 5, it_l)

            # Outstanding / Total Due (Column 6)
            o_bal = float(c.get("outstanding_amount") or 0.0)
            it_o = QTableWidgetItem(f"{o_bal:,.2f}")
            it_o.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # High Contrast Red
            it_o.setForeground(QColor("#cc0000")) if o_bal > 0 else it_o.setForeground(QColor(DARK_TEXT))
            self._tbl.setItem(r, 6, it_o)

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
            ("General",        self._page_general()),
            ("Companies",      CompanyDialog(self)),
            ("Customer Groups",CustomerGroupDialog(self)),
            ("Warehouses",     WarehouseDialog(self)),
            ("Cost Centers",   CostCenterDialog(self)),
            ("Price Lists",    PriceListDialog(self)),
            ("Customers",      CustomerDialog(self)),
            ("Users",          ManageUsersDialog(self, current_user=self.user)),
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
            "Use the sidebar to manage Companies, Customers, Warehouses, "
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
    # POS BUSINESS RULES (Simple & Clean)
    # =================================================================
    # _page_pos_rules

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
        ok_btn  = navy_btn("Set Qty", height=40, color=SUCCESS, hover=SUCCESS_H)
        ok_btn.setIcon(qta.icon("fa5s.check", color="white"))
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
        self._mode_badge = QLabel("  ADD MODE  ")
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
        self._save_btn.setText("Save Changes")
        self._save_btn.setIcon(qta.icon("fa5s.save", color="white"))
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color:{ACCENT}; color:{WHITE}; border:none;
                border-radius:5px; font-size:12px; font-weight:bold; padding:0 14px;
            }}
            QPushButton:hover   {{ background-color:{ACCENT_H}; }}
            QPushButton:pressed {{ background-color:{NAVY_3}; }}
        """)
        self._mode_badge.setText("  EDIT MODE  ")
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
        self._mode_badge.setText("  ADD MODE  ")
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
    - Lists all local + cloud-synced users with full details
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
        icon_lbl = QLabel(); icon_lbl.setPixmap(qta.icon("fa5s.users", color="white").pixmap(22, 22))
        icon_lbl.setStyleSheet("background:transparent;")
        title_lbl = QLabel("Manage Users")
        title_lbl.setStyleSheet(f"font-size:18px; font-weight:bold; color:{WHITE}; background:transparent;")
        sub_lbl = QLabel("Add · Edit · Delete · Assign roles, PINs & permissions")
        sub_lbl.setStyleSheet(f"font-size:11px; color:{MID}; background:transparent;")
        hl.addWidget(icon_lbl); hl.addWidget(title_lbl); hl.addSpacing(8)
        hl.addWidget(sub_lbl); hl.addStretch()
        close_x = QPushButton(); close_x.setIcon(qta.icon("fa5s.times", color="white"))
        close_x.setFixedSize(34, 34)
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
        self._del_btn = QPushButton("Delete User")
        self._del_btn.setIcon(qta.icon("fa5s.trash", color="white"))
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
        eye_btn = QPushButton(); eye_btn.setIcon(qta.icon("fa5s.eye"))
        eye_btn.setFixedSize(36, 36)
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
        rw5, self._perm_laybye   = _perm_row("Allow Laybye",        "Can save a cart as a Laybye order")
        rw6, self._perm_quote    = _perm_row("Allow Quotation",     "Can create and print Quotations")
        for rw in [rw1, rw2, rw3, rw4, rw5, rw6]:
            c4l.addWidget(rw)

        # ── Discount limits row ────────────────────────────────────────────
        disc_lim_wrap = QWidget(); disc_lim_wrap.setStyleSheet("background:transparent;")
        disc_lim_lay  = QHBoxLayout(disc_lim_wrap)
        disc_lim_lay.setContentsMargins(0, 6, 0, 2); disc_lim_lay.setSpacing(14)

        # Max % spinbox
        _disc_lbl_wrap = QWidget(); _disc_lbl_wrap.setStyleSheet("background:transparent;")
        _dlw = QVBoxLayout(_disc_lbl_wrap); _dlw.setSpacing(3); _dlw.setContentsMargins(0,0,0,0)
        _dlbl = QLabel("Max Discount %")
        _dlbl.setStyleSheet(f"font-size:11px;font-weight:bold;color:{MUTED};background:transparent;border:none;")
        self._f_max_disc = QSpinBox()
        self._f_max_disc.setRange(0, 100)
        self._f_max_disc.setSuffix(" %")
        self._f_max_disc.setFixedHeight(36)
        self._f_max_disc.setStyleSheet(f"""
            QSpinBox {{
                background:{OFF_WHITE}; color:{NAVY};
                border:1px solid {BORDER}; border-radius:7px;
                font-size:13px; padding:0 12px;
            }}
            QSpinBox:focus {{ border:2px solid {ACCENT}; background:{WHITE}; }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width:22px; border:none; background:{LIGHT}; border-radius:3px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background:{BORDER}; }}
        """)
        _dlw.addWidget(_dlbl); _dlw.addWidget(self._f_max_disc)
        disc_lim_lay.addWidget(_disc_lbl_wrap, 1)

        # Expiry date picker
        _exp_wrap = QWidget(); _exp_wrap.setStyleSheet("background:transparent;")
        _ew = QVBoxLayout(_exp_wrap); _ew.setSpacing(3); _ew.setContentsMargins(0,0,0,0)
        _elbl = QLabel("Disc. Expires")
        _elbl.setStyleSheet(f"font-size:11px;font-weight:bold;color:{MUTED};background:transparent;border:none;")
        self._f_disc_expiry = QDateEdit()
        self._f_disc_expiry.setCalendarPopup(True)
        self._f_disc_expiry.setDisplayFormat("dd/MM/yyyy")
        self._f_disc_expiry.setDate(QDate.currentDate().addYears(1))
        self._f_disc_expiry.setFixedHeight(36)
        self._f_disc_expiry.setStyleSheet(f"""
            QDateEdit {{
                background:{OFF_WHITE}; color:{NAVY};
                border:1px solid {BORDER}; border-radius:7px;
                font-size:13px; padding:0 12px;
            }}
            QDateEdit:focus {{ border:2px solid {ACCENT}; background:{WHITE}; }}
            QDateEdit::drop-down {{ border:none; width:24px; }}
        """)
        _ew.addWidget(_elbl); _ew.addWidget(self._f_disc_expiry)
        disc_lim_lay.addWidget(_exp_wrap, 1)

        c4l.addWidget(disc_lim_wrap)

        # Helper note
        _disc_note = QLabel("Discount is blocked after the expiry date, even if % > 0.")
        _disc_note.setStyleSheet(f"font-size:10px;color:{MUTED};font-style:italic;background:transparent;border:none;")
        _disc_note.setWordWrap(True)
        c4l.addWidget(_disc_note)

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

        self._save_btn = QPushButton("Save User")
        self._save_btn.setIcon(qta.icon("fa5s.save", color="white"))
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
            is_cloud = bool(u.get("synced_from_frappe"))
            src    = "Cloud" if is_cloud else "Local"
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
                if c == 4 and is_cloud:
                    it.setIcon(qta.icon("fa5s.cloud"))
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
        self._perm_laybye.setChecked(  bool(u.get("allow_laybye",    True)))
        self._perm_quote.setChecked(   bool(u.get("allow_quote",     True)))
        # Discount limits
        self._f_max_disc.setValue(int(u.get("max_discount_percent", 0) or 0))
        expiry_str = u.get("discount_expiry_date", "") or ""
        if expiry_str:
            try:
                ed = QDate.fromString(expiry_str, "yyyy-MM-dd")
                if not ed.isValid():
                    ed = QDate.fromString(expiry_str, "dd/MM/yyyy")
                if ed.isValid():
                    self._f_disc_expiry.setDate(ed)
            except Exception:
                pass
        else:
            self._f_disc_expiry.setDate(QDate.currentDate().addYears(1))

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
        self._f_max_disc.setValue(0)
        self._f_disc_expiry.setDate(QDate.currentDate().addYears(1))
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
        perm_laybye   = int(self._perm_laybye.isChecked())
        perm_quote    = int(self._perm_quote.isChecked())
        max_disc_pct  = self._f_max_disc.value()
        disc_expiry   = self._f_disc_expiry.date().toString("yyyy-MM-dd")

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
                                "allow_credit_note", "allow_reprint",
                                "allow_laybye", "allow_quote"]:
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

                    # Ensure discount limit columns exist
                    for col_def in [
                        ("max_discount_percent", "INT NOT NULL DEFAULT 0"),
                        ("discount_expiry_date", "NVARCHAR(20) NULL"),
                    ]:
                        try:
                            cur.execute(f"""
                                IF NOT EXISTS (
                                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                                    WHERE TABLE_NAME='users' AND COLUMN_NAME='{col_def[0]}'
                                )
                                ALTER TABLE users ADD {col_def[0]} {col_def[1]}
                            """)
                            conn.commit()
                        except Exception:
                            pass

                    # Update all user fields including PIN
                    cur.execute("""
                        UPDATE users SET
                            username             = ?,
                            role                 = ?,
                            full_name            = ?,
                            email                = ?,
                            pin                  = ?,
                            cost_center          = ?,
                            warehouse            = ?,
                            active               = ?,
                            allow_discount       = ?,
                            allow_receipt        = ?,
                            allow_credit_note    = ?,
                            allow_reprint        = ?,
                            allow_laybye         = ?,
                            allow_quote          = ?,
                            max_discount_percent = ?,
                            discount_expiry_date = ?
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
                          perm_laybye, perm_quote,
                          max_disc_pct, disc_expiry,
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

        # Header with POS Switcher
        header = QWidget()
        header.setFixedHeight(50)
        header.setStyleSheet(f"background-color: {WHITE}; border-bottom: 1px solid {BORDER};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        title = QLabel("Dashboard")
        title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {NAVY};")
        
        # POS Switcher Button
        pos_btn = QPushButton("◀  Switch to POS")
        pos_btn.setFixedHeight(32)
        pos_btn.setCursor(Qt.PointingHandCursor)
        pos_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background-color: {ACCENT_H};
            }}
        """)
        if self.parent_window:
            pos_btn.clicked.connect(self.parent_window.switch_to_pos)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(pos_btn)
        root.addWidget(header)

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
        self._tabs.addTab(self._build_overview_tab(),  "  Overview")
        self._tabs.addTab(self._build_stock_tab(),     "  Stock on Hand")
        self._tabs.addTab(self._build_top_items_tab(), "  Top Items")
        self._tabs.addTab(self._build_actions_tab(),   "  Actions")
        root.addWidget(self._tabs, 1)

    # =========================================================================
    # TAB 1: OVERVIEW
    # =========================================================================

    def _build_overview_tab(self):
        w = QWidget()
        w.setStyleSheet(f"background:{OFF_WHITE};")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{OFF_WHITE}; }}")
        scroll.setWidget(w)

        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(18)

        # KPI row 1: Financial
        lay.addWidget(self._section_label("Financial Summary"))
        lay.addLayout(self._build_kpi_row_1())

        # KPI row 2: Stock values
        lay.addWidget(self._section_label("Stock Value Summary"))
        lay.addLayout(self._build_kpi_row_2())

        # Recent sales table
        lay.addWidget(self._section_label("Recent Sales (Today)"))
        lay.addWidget(self._build_sales_table())

        lay.addStretch()

        container = QWidget()
        container.setStyleSheet(f"background:{OFF_WHITE};")
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(scroll, 1)
        return container

    def _build_kpi_row_1(self):
        row = QHBoxLayout()
        row.setSpacing(14)
        self._kpi = {}

        for key, label, icon, color in [
            ("sales", "Total Sales", "fa5s.money-bill", ACCENT),
            ("expenses", "Expenses", "fa5s.chart-line", DANGER),
            ("profit", "Gross Profit", "fa5s.chart-line", SUCCESS),
            ("exp_profit", "Expected Profit", "fa5s.bullseye", AMBER),
        ]:
            card, val_lbl = self._kpi_card(label, icon, "$0.00", color)
            self._kpi[key] = val_lbl
            row.addWidget(card, 1)
        return row

    def _build_kpi_row_2(self):
        row = QHBoxLayout()
        row.setSpacing(14)

        for key, label, icon, color in [
            ("stock_cost", "Stock @ Cost", "fa5s.industry", NAVY),
            ("stock_sell", "Stock @ Selling", "fa5s.tag", ACCENT_H),
            ("potential", "Potential Profit", "fa5s.gem", SUCCESS),
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
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 10, 16, 10)
        cl.setSpacing(3)

        top = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color:{MUTED}; font-size:11px; background:transparent; "
            "font-weight:bold; letter-spacing:0.5px;"
        )
        ico = QLabel()
        ico.setPixmap(qta.icon(icon, color=color).pixmap(18, 18))
        ico.setStyleSheet("background:transparent;")
        top.addWidget(lbl, 1)
        top.addWidget(ico)
        
        val = QLabel(initial)
        val.setStyleSheet(
            f"color:{color}; font-size:20px; font-weight:bold; background:transparent;"
        )
        cl.addLayout(top)
        cl.addWidget(val)
        return card, val

    def _build_sales_table(self):
        self.sales_table = QTableWidget(0, 6)
        self.sales_table.setHorizontalHeaderLabels(
            ["Invoice #", "Date / Time", "Cashier", "Method", "Total", "Synced"]
        )
        hh = self.sales_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        self.sales_table.setColumnWidth(0, 100)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        self.sales_table.setColumnWidth(3, 90)
        hh.setSectionResizeMode(4, QHeaderView.Fixed)
        self.sales_table.setColumnWidth(4, 100)
        hh.setSectionResizeMode(5, QHeaderView.Fixed)
        self.sales_table.setColumnWidth(5, 70)
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
    # TAB 2: STOCK ON HAND
    # =========================================================================

    def _build_stock_tab(self):
        w = QWidget()
        w.setStyleSheet(f"background:{OFF_WHITE};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(10)

        # Search row
        srch_row = QHBoxLayout()
        srch = QLineEdit()
        srch.setPlaceholderText("Filter by product name or part number…")
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

        export_btn = navy_btn("Export CSV", height=34, color=NAVY_2, hover=NAVY_3)
        export_btn.setIcon(qta.icon("fa5s.download", color="white"))
        export_btn.clicked.connect(self._export_stock_csv)
        srch_row.addWidget(export_btn)
        lay.addLayout(srch_row)

        # Totals strip
        totals_w = QWidget()
        totals_w.setStyleSheet(f"background:{NAVY}; border-radius:6px;")
        totals_w.setFixedHeight(44)
        tl = QHBoxLayout(totals_w)
        tl.setContentsMargins(16, 0, 16, 0)
        tl.setSpacing(32)
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
        self._stock_tbl = QTableWidget(0, 8)
        self._stock_tbl.setHorizontalHeaderLabels([
            "Part No.", "Product Name", "Category",
            "Qty on Hand", "Cost Price", "Selling Price",
            "Value @ Cost", "Value @ Selling",
        ])
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
            qty = float(p.get("stock", 0) or 0)
            cost = float(p.get("cost_price", 0) or 0)
            sell = float(p.get("price", 0) or 0)
            val_cost = qty * cost
            val_sell = qty * sell
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
    # TAB 3: TOP ITEMS
    # =========================================================================

    def _build_top_items_tab(self):
        w = QWidget()
        w.setStyleSheet(f"background:{OFF_WHITE};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(20)

        # Left: Top 10 Profitable
        left = QVBoxLayout()
        left.addWidget(self._section_label("Top 10 Most Profitable Items"))

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
        right.addWidget(self._section_label("Most Sold Items"))

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
    # TAB 4: ACTIONS
    # =========================================================================

    def _build_actions_tab(self):
        w = QWidget()
        w.setStyleSheet(f"background:{OFF_WHITE};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(32, 24, 32, 24)
        lay.setSpacing(24)

        # Left column: quick actions
        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(self._section_label("Quick Actions"))
        left.addWidget(self._build_quick_actions())
        left.addStretch()
        lay.addLayout(left, 1)

        # Right column: stock alerts
        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(self._section_label("Low Stock Alerts"))
        right.addWidget(self._build_stock_alerts())
        right.addStretch()
        lay.addLayout(right, 1)

        return w

    # =========================================================================
    # QUICK ACTIONS / STOCK ALERTS
    # =========================================================================

    def _build_quick_actions(self):
        card = QWidget()
        card.setStyleSheet(
            f"QWidget {{ background-color:{WHITE}; "
            f"border:1px solid {BORDER}; border-radius:8px; }}"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(8)

        actions = [
            (" Sync Users", self._open_user_sync, NAVY_3),
            ("  Stock File", self._open_stock, NAVY),
            ("  Sales History", self._open_sales_history, NAVY_3),
            ("  Day Shift", self._open_day_shift, NAVY_2),
            ("  Companies", lambda: self._open_settings_at(1), MUTED),
            ("  Customer Groups", lambda: self._open_settings_at(2), MUTED),
            ("  Warehouses", lambda: self._open_settings_at(3), MUTED),
            ("  Cost Centers", lambda: self._open_settings_at(4), MUTED),
            ("  Price Lists", lambda: self._open_settings_at(5), MUTED),
            ("  Customers", lambda: self._open_settings_at(6), MUTED),
            ("  Refresh Dashboard", self._load_data, SUCCESS),
        ]
        for label, handler, color in actions:
            btn = QPushButton(label)
            btn.setFixedHeight(38)
            btn.setCursor(Qt.PointingHandCursor)
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
    # DATA LOADING
    # =========================================================================

    def _load_data(self):
        self._load_financial_kpis()
        self._load_stock_data()
        self._load_top_items()
        self._load_recent_sales()
        self._load_stock_alerts()

    def _load_financial_kpis(self):
        sales_total = expenses = cost_of_goods = 0.0
        try:
            from models.sale import get_all_sales
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()

            try:
                cur.execute("SELECT COALESCE(SUM(total),0) FROM sales")
                row = cur.fetchone()
                sales_total = float(row[0] or 0)
            except Exception:
                pass

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

        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
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

        gross_profit = sales_total - cost_of_goods
        net_profit = gross_profit - expenses
        exp_profit = gross_profit

        stock_cost = stock_sell = 0.0
        if hasattr(self, "_all_stock"):
            for p in self._all_stock:
                qty = float(p.get("stock", 0) or 0)
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

        for key, val in [("profit", net_profit), ("exp_profit", exp_profit)]:
            color = SUCCESS if val >= 0 else DANGER
            self._kpi[key].setStyleSheet(
                f"color:{color}; font-size:20px; font-weight:bold; background:transparent;"
            )

    def _load_stock_data(self):
        try:
            from models.product import get_all_products
            products = get_all_products()
        except Exception:
            products = []
        self._all_stock = products
        self._render_stock(products)
        self._load_financial_kpis()

    def _load_top_items(self):
        profitable = {}
        most_sold = {}

        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            try:
                cur.execute("""
                    SELECT
                        si.product_name,
                        SUM(si.qty) AS qty,
                        SUM(si.total) AS revenue,
                        SUM(si.qty * COALESCE(p.cost_price, 0)) AS cost_total
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

        self._tbl_profitable.setRowCount(0)
        top_p = sorted(profitable.items(), key=lambda x: x[1]["profit"], reverse=True)[:10]
        medal_colors = {0: "#d4af37", 1: "#c0c0c0", 2: "#cd7f32"}
        for i, (name, d) in enumerate(top_p):
            r = self._tbl_profitable.rowCount()
            self._tbl_profitable.insertRow(r)
            first_col_text = f" {name}" if i < 3 else f"{i+1}. {name}"
            vals = [
                first_col_text,
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
                if ci == 0 and i < 3:
                    it.setIcon(qta.icon("fa5s.medal", color=medal_colors[i]))
                if ci == 3:
                    it.setForeground(QColor(SUCCESS if d["profit"] >= 0 else DANGER))
                self._tbl_profitable.setItem(r, ci, it)
            self._tbl_profitable.setRowHeight(r, 34)

        self._tbl_most_sold.setRowCount(0)
        top_s = sorted(most_sold.items(), key=lambda x: x[1]["qty"], reverse=True)[:20]
        for i, (name, d) in enumerate(top_s):
            r = self._tbl_most_sold.rowCount()
            self._tbl_most_sold.insertRow(r)
            first_col_text = f" {name}" if i < 3 else f"{i+1}. {name}"
            vals = [
                first_col_text,
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
                if ci == 0 and i < 3:
                    it.setIcon(qta.icon("fa5s.medal", color="#777"))
                if ci == 2:
                    it.setForeground(QColor(ACCENT))
                self._tbl_most_sold.setItem(r, ci, it)
            self._tbl_most_sold.setRowHeight(r, 34)

    def _load_recent_sales(self):
        try:
            from models.sale import get_today_sales
            sales = get_today_sales()
        except Exception:
            try:
                from models.sale import get_all_sales
                sales = get_all_sales()[:50]
            except Exception:
                sales = []

        self.sales_table.setRowCount(0)
        for s in sales[:50]:
            r = self.sales_table.rowCount()
            self.sales_table.insertRow(r)
            for c, (key, fmt) in enumerate([
                ("invoice_no", lambda v: str(v)),
                ("invoice_date", lambda v: str(v)),
                ("user", lambda v: str(v)),
                ("method", lambda v: str(v)),
                ("total", lambda v: f"${float(v or 0):.2f}"),
                ("synced", lambda v: "" if v else "—"),
            ]):
                raw = s.get(key, "") or s.get("number", "") or ""
                text = fmt(raw)
                item = QTableWidgetItem(text)
                item.setTextAlignment(
                    Qt.AlignCenter if c != 1 else Qt.AlignLeft | Qt.AlignVCenter
                )
                if key == "total":
                    item.setForeground(QColor(ACCENT))
                elif key == "synced":
                    if s.get("synced"):
                        item.setIcon(qta.icon("fa5s.check", color=SUCCESS))
                    item.setForeground(QColor(SUCCESS if s.get("synced") else MUTED))
                self.sales_table.setItem(r, c, item)
            self.sales_table.setRowHeight(r, 34)

    def _load_stock_alerts(self):
        while self._stock_alert_layout.count():
            it = self._stock_alert_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        try:
            from models.product import get_all_products
            low = [p for p in get_all_products() if float(p.get("stock", 0) or 0) <= 5]
        except Exception:
            low = []

        if not low:
            row_w = QWidget(); row_w.setStyleSheet("background: transparent;")
            rh = QHBoxLayout(row_w); rh.setContentsMargins(0, 0, 0, 0); rh.setSpacing(6)
            ic = QLabel(); ic.setPixmap(qta.icon("fa5s.check", color=SUCCESS).pixmap(14, 14))
            ic.setStyleSheet("background:transparent;")
            lbl = QLabel("All stock levels OK")
            lbl.setStyleSheet(f"color:{SUCCESS}; font-size:12px; background:transparent;")
            rh.addWidget(ic); rh.addWidget(lbl); rh.addStretch()
            self._stock_alert_layout.addWidget(row_w)
        else:
            for p in low[:12]:
                row_w = QWidget()
                row_w.setStyleSheet("background:transparent;")
                rh = QHBoxLayout(row_w)
                rh.setContentsMargins(0, 0, 0, 0)
                rh.setSpacing(8)
                nm = QLabel(p.get("name", ""))
                nm.setStyleSheet(f"color:{DARK_TEXT}; font-size:12px; background:transparent;")
                st = QLabel(f"Qty: {float(p.get('stock', 0) or 0):.1f}")
                st.setStyleSheet(
                    f"color:{DANGER}; font-size:12px; font-weight:bold; background:transparent;"
                )
                rh.addWidget(nm, 1)
                rh.addWidget(st)
                self._stock_alert_layout.addWidget(row_w)
            if len(low) > 12:
                more = QLabel(f"… and {len(low)-12} more")
                more.setStyleSheet(f"color:{MUTED}; font-size:11px; background:transparent;")
                self._stock_alert_layout.addWidget(more)

    # =========================================================================
    # ACTION HANDLERS
    # =========================================================================

    def _open_user_sync(self):
        try:
            from views.dialogs.user_sync_dialog import UserSyncDialog
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
        from views.dialogs.shift_reconciliation_dialog import ShiftReconciliationDialog
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
    """
    Clean, minimal options panel for cashiers.
    Contains only transaction-level actions: Return, Quotation, Reprint.
    Maintenance / sync actions live in the nav-bar Maintenance menu.
    """

    def __init__(self, parent=None, pos_view=None):
        super().__init__(parent)
        self._pos = pos_view
        self.setWindowTitle("Options")
        self.setFixedSize(380, 420)  # Sized for the full button list + sync status line
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowMinimizeButtonHint
            & ~Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )
        self.setStyleSheet(f"""
            QDialog {{ background-color: {WHITE}; border-radius: 10px; }}
        """)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(f"background-color: {NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(18, 0, 12, 0)
        title = QLabel("Options")
        title.setStyleSheet(
            f"font-size:15px; font-weight:bold; color:{WHITE}; background:transparent;"
        )
        close_btn = QPushButton(); close_btn.setIcon(qta.icon("fa5s.times", color="white"))
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{MID}; border:none;
                font-size:14px; font-weight:bold; border-radius:4px;
            }}
            QPushButton:hover {{ background:{DANGER}; color:{WHITE}; }}
        """)
        close_btn.clicked.connect(self.reject)
        hl.addWidget(title); hl.addStretch(); hl.addWidget(close_btn)
        root.addWidget(hdr)

        # ── Body ──────────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet(f"background:{WHITE};")
        bl = QVBoxLayout(body)
        bl.setSpacing(8)
        bl.setContentsMargins(20, 18, 20, 18)

        def _row(label, handler, color=NAVY, hov=NAVY_2):
            b = QPushButton(label)
            b.setFixedHeight(44)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background:{WHITE}; color:{DARK_TEXT};
                    border:1px solid {BORDER};
                    border-left: 4px solid {color};
                    border-radius: 6px;
                    font-size:13px; font-weight:600;
                    text-align:left; padding:0 16px;
                }}
                QPushButton:hover {{
                    background:{color}; color:{WHITE}; border-color:{color};
                }}
                QPushButton:pressed {{
                    background:{hov}; color:{WHITE};
                }}
            """)
            b.clicked.connect(handler)
            return b

        bl.addWidget(_row("Create Credit Note  (Return)",
                          self._do_credit_note, AMBER, ORANGE))
        # Pharmacy: relabel "Save / Print Quotation" → "Dispense" for Pharmacist users
        self._save_quote_btn = _row("Save / Print Quotation",
                          self._do_save_quotation, NAVY_3, NAVY_2)
        try:
            from utils.roles import is_pharmacist as _is_pharm
            _user = getattr(self._pos, "user", None) if self._pos else None
            if _is_pharm(_user):
                self._save_quote_btn.setText("Dispense")
                try:
                    # Prefer prescription-bottle-alt; fall back silently on missing glyph
                    self._save_quote_btn.setIcon(qta.icon("fa5s.prescription-bottle-alt", color="white"))
                except Exception:
                    try:
                        self._save_quote_btn.setIcon(qta.icon("fa5s.pills", color="white"))
                    except Exception:
                        pass
        except Exception:
            pass
        bl.addWidget(self._save_quote_btn)
        bl.addWidget(_row("Manage Quotations",
                          self._do_manage_quotations, NAVY, NAVY_2))
        bl.addWidget(_row("Reprint Invoice",
                          self._do_reprint, NAVY, NAVY_2))
        self._sync_products_btn = _row("Sync Products from Server",
                                       self._do_sync_products, ACCENT, ACCENT_H)
        bl.addWidget(self._sync_products_btn)

        # Inline status line for the sync action
        from PySide6.QtWidgets import QLabel as _QL
        self._sync_status_lbl = _QL("")
        self._sync_status_lbl.setStyleSheet(
            f"font-size:11px; color:{MUTED}; background:transparent; padding:0 4px;"
        )
        self._sync_status_lbl.setWordWrap(True)
        bl.addWidget(self._sync_status_lbl)

        bl.addStretch()
        root.addWidget(body, 1)

    # ── handlers ──────────────────────────────────────────────────────────────
    def _do_save_quotation(self):
        self.accept()
        if self._pos:
            self._pos._save_quotation()

    def _do_manage_quotations(self):
        self.accept()
        if self._pos:
            self._pos._open_quotation_manager()

    def _do_credit_note(self):
        self.accept()
        if self._pos:
            self._pos._open_credit_note_dialog()
        else:
            CreditNoteDialog(self.parent()).exec()

    def _do_reprint(self):
        self.accept()
        if self._pos:
            self._pos._reprint_by_invoice_no()

    def _do_pos_rules(self):
        self.accept()
        POSRulesDialog(self.parent()).exec()

    # =========================================================================
    # PRODUCT SYNC — one-shot pull from Frappe
    # =========================================================================
    def _do_sync_products(self):
        """Fire a one-shot product sync in the background. Keeps the dialog
        open so the cashier sees the status line; disables the button while
        running so double-taps don't stack requests."""
        from PySide6.QtCore import QThread, Signal as _Sig, QObject as _QObj

        class _ProductSyncJob(_QObj):
            done   = _Sig(dict)
            failed = _Sig(str)

            def run(self):
                try:
                    from services.credentials import get_credentials
                    key, secret = get_credentials()
                    if not key or not secret:
                        self.failed.emit("No credentials — log in once so the sync can authenticate.")
                        return
                    from services.product_sync_windows_service import sync_products_smart
                    res = sync_products_smart(key, secret) or {}
                    self.done.emit(res)
                except Exception as e:
                    self.failed.emit(str(e))

        self._sync_products_btn.setEnabled(False)
        self._sync_status_lbl.setStyleSheet(
            f"font-size:11px; color:{MUTED}; background:transparent; padding:0 4px;"
        )
        self._sync_status_lbl.setText("Syncing products from server…")

        self._sync_thread = QThread(self)
        self._sync_job    = _ProductSyncJob()
        self._sync_job.moveToThread(self._sync_thread)
        self._sync_thread.started.connect(self._sync_job.run)
        self._sync_job.done.connect(self._on_sync_products_done)
        self._sync_job.failed.connect(self._on_sync_products_failed)
        self._sync_job.done.connect(self._sync_thread.quit)
        self._sync_job.failed.connect(self._sync_thread.quit)
        self._sync_thread.finished.connect(self._sync_job.deleteLater)
        self._sync_thread.finished.connect(self._sync_thread.deleteLater)
        self._sync_thread.start()

    def _on_sync_products_done(self, res: dict):
        # Refresh the POS product grid so newly-synced items appear without a
        # restart. _reload_current_category preserves the active category/page.
        try:
            if self._pos and hasattr(self._pos, "_reload_current_category"):
                self._pos._reload_current_category()
        except Exception as e:
            print(f"[OptionsDialog] product grid refresh failed: {e}")

        # Surface the sync summary on the parent status bar (dialog is about
        # to close so writing to the inline status line would be invisible).
        try:
            inserted = res.get("inserted", 0)
            updated  = res.get("updated", 0)
            total    = res.get("total_api", 0)
            errors   = res.get("errors", 0)
            msg = f"Sync done — {inserted} new, {updated} updated (of {total})"
            if errors:
                msg += f", {errors} error(s)"
            pw = getattr(self._pos, "parent_window", None)
            if pw and hasattr(pw, "_set_status"):
                pw._set_status(msg)
            else:
                print(f"[OptionsDialog] {msg}")
        except Exception:
            pass

        self.accept()

    def _on_sync_products_failed(self, msg: str):
        if hasattr(self, "_sync_products_btn"):
            self._sync_products_btn.setEnabled(True)
        if hasattr(self, "_sync_status_lbl"):
            self._sync_status_lbl.setStyleSheet(
                f"font-size:11px; color:{DANGER}; background:transparent; padding:0 4px; font-weight:bold;"
            )
            self._sync_status_lbl.setText(f"Failed: {msg[:120]}")
# =============================================================================
# POS RULES DIALOG  —  standalone, accessible from Options menu & Maintenance
# =============================================================================
class POSRulesDialog(QDialog):
    """
    Toggle-based POS business rules:
      #3  Block zero-price sales
      #4  Block zero-stock sales
      #7  Apply pricing rules
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
        t = QLabel("POS Business Rules")
        t.setStyleSheet(f"font-size:16px; font-weight:bold; color:{WHITE}; background:transparent;")
        hl.addWidget(t); hl.addStretch()
        close_x = QPushButton(); close_x.setIcon(qta.icon("fa5s.times", color="white"))
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
            ("block_zero_price",  "Block Zero-Price Sales",
             "Prevent adding items with $0.00 price to the invoice.", True),
            ("block_zero_stock",  "Block Zero-Stock Sales",
             "Show 'Insufficient Stock' popup when item has no stock.", False),
            ("use_pricing_rules", "Apply Pricing Rules",
             "Auto-apply discount rules when adding items.", False),
        ]
        for key, label, desc, default in rules:
            self._add_rule_row(bl, key, label, desc, default)

        bl.addSpacing(8)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{BORDER}; border:none;"); sep.setFixedHeight(1)
        bl.addWidget(sep); bl.addSpacing(8)

        note = QLabel(
            "Per-user permissions (Allow Discounts, Reprint, Credit Notes, Receipt)\n"
            "    are configured in  Maintenance → Users → edit a user."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color:{MUTED}; font-size:11px; background:{OFF_WHITE};"
            f" border:1px solid {BORDER}; border-radius:6px; padding:10px 14px;")
        bl.addWidget(note)
        bl.addStretch()

        save_btn = navy_btn("Save Rules", height=42, color=SUCCESS, hover=SUCCESS_H)
        save_btn.setIcon(qta.icon("fa5s.save", color="white"))
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
# FRAPPE ERROR CLEANER
# =============================================================================
def _clean_frappe_error(raw: str) -> str:
    """Strip HTML tags and noise from server error messages."""
    if not raw:
        return ""
    import re as _re
    text = _re.sub(r"<[^>]+>", " ", str(raw))
    text = _re.sub(r"\\n|\\r", " ", text)
    text = _re.sub(r"\s+", " ", text).strip()
    for prefix in ("frappe.exceptions.", "ValidationError:", "LinkValidationError:",
                   "frappe.exceptions.ValidationError"):
        text = text.replace(prefix, "")
    return text.strip()[:320]


# =============================================================================
# UNSYNCED ITEMS POPUP
# Shown when user clicks SI / CN / SO badge.
# Displays only the pending rows for that document type, with error messages
# and a "Contact Admin" advisory.
# =============================================================================
# =============================================================================
# UNSYNCED ITEMS POPUP  (upgraded)
# Tabbed SI / CN / SO view.  Raw API errors shown verbatim and are copyable.
# Header shows count per tab.  Smart open: opens the right tab automatically.
# =============================================================================
class UnsyncedPopup(QDialog):
    """
    kind = "SI"  → opens on the Sales Invoices tab
    kind = "CN"  → opens on the Credit Notes tab
    kind = "SO"  → opens on the Sales Orders tab
    kind = ""    → opens on whichever tab has errors (smart)
    """

    
    _TAB_META = {
        "SI":   ("  Sales Invoices",   DANGER,  DANGER_H),
        "CN":   ("  Credit Notes",     AMBER,   ORANGE),
        "SO":   ("  Sales Orders",     AMBER,   ORANGE),
        "PAY":  ("  Payment Entries",  ACCENT,  ACCENT_H),
        "CUST": ("  Customers",        NAVY_3,  NAVY_2),
    }

    def __init__(self, kind: str = "", parent=None):
        super().__init__(parent)
        self._start_kind = kind
        self.setWindowTitle("Unsynced Items")
        self.setMinimumSize(980, 580)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background:{OFF_WHITE}; }}")
        self._tables  = {}   # kind → QTableWidget
        self._counts  = {}   # kind → int
        self._build()
        self._load_all()
        self._select_smart_tab()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QWidget(); hdr.setFixedHeight(54)
        hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20, 0, 20, 0)
        t = QLabel("Unsynced Items")
        t.setStyleSheet(
            f"font-size:15px; font-weight:bold; color:{WHITE}; background:transparent;")
        self._hdr_count = QLabel("")
        self._hdr_count.setStyleSheet(
            f"color:{MID}; font-size:12px; background:transparent;")
        close_x = QPushButton("Close")
        close_x.setIcon(qta.icon("fa5s.times", color="white"))
        close_x.setFixedSize(92, 32); close_x.setCursor(Qt.PointingHandCursor)
        close_x.setStyleSheet(f"""
            QPushButton {{ background:{DANGER};color:{WHITE};border:none;
                           border-radius:4px;font-size:12px;font-weight:bold; }}
            QPushButton:hover {{ background:{DANGER_H}; }}
        """)
        close_x.clicked.connect(self.reject)
        hl.addWidget(t); hl.addSpacing(16); hl.addWidget(self._hdr_count)
        hl.addStretch(); hl.addWidget(close_x)
        root.addWidget(hdr)

        # Tab widget
        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{ border:none; background:{OFF_WHITE}; }}
            QTabBar::tab {{
                background:{LIGHT}; color:{NAVY};
                padding:9px 22px; font-size:12px; font-weight:bold;
                border:1px solid {BORDER}; border-bottom:none;
                margin-right:2px; border-radius:4px 4px 0 0;
            }}
            QTabBar::tab:selected {{
                background:{WHITE}; color:{ACCENT};
                border-bottom:2px solid {WHITE};
            }}
            QTabBar::tab:hover {{ background:{BORDER}; }}
        """)

        for kind, (label, accent, _) in self._TAB_META.items():
            tab_widget = self._build_tab(kind, label, accent)
            self._tab_widget.addTab(tab_widget, label)

        root.addWidget(self._tab_widget, 1)

        # Admin hint
        hint = QLabel(
            "Check above for any errors and just copy and send to admin "
        )
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.RichText)
        hint.setStyleSheet(f"""
            background:{LIGHT}; color:{DARK_TEXT};
            border:1px solid {BORDER}; border-left:4px solid {DANGER};
            font-size:11px; padding:10px 16px;
        """)
        root.addWidget(hint)

    def _build_tab(self, kind: str, label: str, accent: str) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background:{OFF_WHITE};")
        bl = QVBoxLayout(w); bl.setContentsMargins(16, 12, 16, 10); bl.setSpacing(8)

        # Count label
        count_lbl = QLabel("Loading…")
        count_lbl.setStyleSheet(
            f"color:{MUTED}; font-size:11px; background:transparent;")
        setattr(self, f"_count_lbl_{kind}", count_lbl)
        bl.addWidget(count_lbl)

        # Table — 4 columns: Q: Ref | Customer | Amount | Raw Error
        tbl = QTableWidget(0, 4)
        tbl.setHorizontalHeaderLabels(["Q: Ref / No.", "Customer", "Amount", "Raw API Error"])
        hh = tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed);  tbl.setColumnWidth(0, 150)
        hh.setSectionResizeMode(1, QHeaderView.Fixed);  tbl.setColumnWidth(1, 160)
        hh.setSectionResizeMode(2, QHeaderView.Fixed);  tbl.setColumnWidth(2, 90)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setAlternatingRowColors(True)
        tbl.setStyleSheet(f"""
            QTableWidget {{
                background:{WHITE}; border:1px solid {BORDER};
                gridline-color:{LIGHT}; font-size:12px; outline:none;
            }}
            QTableWidget::item           {{ padding:6px 10px; }}
            QTableWidget::item:alternate {{ background:{ROW_ALT}; }}
            QHeaderView::section {{
                background:#f0e8d0; color:{NAVY};
                padding:8px 10px; border:none;
                border-right:1px solid {BORDER};
                font-size:11px; font-weight:bold;
            }}
        """)
        # Allow text selection so errors can be copied
        tbl.setTextElideMode(Qt.ElideNone)
        self._tables[kind] = tbl
        bl.addWidget(tbl, 1)

        # Copy button + retry button
        foot = QHBoxLayout(); foot.setSpacing(10)

        copy_btn = QPushButton("Copy Selected Error")
        copy_btn.setIcon(qta.icon("fa5s.clipboard", color="white"))
        copy_btn.setFixedHeight(34); copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet(f"""
            QPushButton {{ background:{NAVY_2};color:{WHITE};border:none;
                           border-radius:5px;font-size:12px;font-weight:bold; }}
            QPushButton:hover {{ background:{NAVY_3}; }}
        """)
        copy_btn.clicked.connect(lambda _=False, k=kind: self._copy_error(k))

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setIcon(qta.icon("fa5s.sync-alt", color="white"))
        refresh_btn.setFixedHeight(34); refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{ background:{NAVY_2};color:{WHITE};border:none;
                           border-radius:5px;font-size:12px;font-weight:bold; }}
            QPushButton:hover {{ background:{NAVY_3}; }}
        """)
        refresh_btn.clicked.connect(lambda _=False, k=kind: self._load_tab(k))

        retry_btn = QPushButton("Retry Sync Now")
        retry_btn.setIcon(qta.icon("fa5s.sync-alt", color="white"))
        retry_btn.setFixedHeight(34); retry_btn.setCursor(Qt.PointingHandCursor)
        retry_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT};color:{WHITE};border:none;
                           border-radius:5px;font-size:12px;font-weight:bold; }}
            QPushButton:hover {{ background:{ACCENT_H}; }}
            QPushButton:disabled {{ background:{LIGHT};color:{MUTED}; }}
        """)
        retry_btn.clicked.connect(lambda _=False, k=kind, b=retry_btn: self._on_retry(k, b))

        foot.addWidget(copy_btn)
        foot.addWidget(refresh_btn)
        foot.addStretch()
        foot.addWidget(retry_btn)
        bl.addLayout(foot)
        return w

    # ── Data ──────────────────────────────────────────────────────────────────
    def _load_all(self):
        total = 0
        for kind in self._TAB_META:
            n = self._load_tab(kind)
            self._counts[kind] = n
            total += n
        self._hdr_count.setText(
            f"{total} item{'s' if total != 1 else ''} pending sync across all types")
        # Update tab labels with counts
        for i, kind in enumerate(self._TAB_META):
            label, _, _ = self._TAB_META[kind]
            n = self._counts.get(kind, 0)
            suffix = f"  ({n})" if n > 0 else ""
            self._tab_widget.setTabText(i, label + suffix)

    def _load_tab(self, kind: str) -> int:
        """Load rows for one tab. Returns row count."""
        tbl = self._tables[kind]
        tbl.setRowCount(0)
        rows = self._fetch_rows(kind)
        n = len(rows)

        lbl = getattr(self, f"_count_lbl_{kind}", None)
        if lbl:
            lbl.setText(f"{n} item{'s' if n != 1 else ''} pending sync")

        for ref, customer, amount, raw_error in rows:
            r = tbl.rowCount()
            tbl.insertRow(r)
            tbl.setRowHeight(r, 42)

            def _cell(text, color=None, align=Qt.AlignLeft | Qt.AlignVCenter):
                it = QTableWidgetItem(str(text or ""))
                # Make selectable so user can Ctrl+C
                it.setFlags(it.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                it.setTextAlignment(align)
                if color:
                    it.setForeground(QColor(color))
                return it

            tbl.setItem(r, 0, _cell(ref, ACCENT))
            tbl.setItem(r, 1, _cell(customer))
            tbl.setItem(r, 2, _cell(amount, align=Qt.AlignRight | Qt.AlignVCenter))
            # Raw error — red, full text in tooltip too
            err_item = _cell(raw_error or "—", DANGER if raw_error else MUTED)
            if raw_error:
                err_item.setToolTip(raw_error)   # full text on hover
            tbl.setItem(r, 3, err_item)

        return n

    def _fetch_rows(self, kind: str):
        """
        Returns list of (ref, customer, amount_str, raw_error_str).
        Every query mirrors the badge SQL so popup count == badge count.
        Raw error_msg is pulled verbatim from sync_errors table — no cleaning,
        no truncation.  Falls back to "Pending" only when no error row exists.
        """
        rows = []
        try:
            from database.db import get_connection

            def _get_raw_errors(conn, doc_type_code: str) -> dict:
                """
                Returns {doc_ref: error_msg} for all unresolved rows of
                this doc_type.  Verbatim — newest row wins per ref.
                """
                errors = {}
                try:
                    cur2 = conn.cursor()
                    cur2.execute(
                        """
                        SELECT doc_ref, error_msg
                        FROM   sync_errors
                        WHERE  doc_type = ?
                          AND  resolved = 0
                        ORDER  BY id DESC
                        """,
                        (doc_type_code,),
                    )
                    for doc_ref, error_msg in cur2.fetchall():
                        if doc_ref not in errors:
                            errors[doc_ref] = error_msg or ""
                except Exception:
                    pass
                return errors

            def _match_error(error_map: dict, key: str) -> str:
                """Exact match first, then substring fallback."""
                if not key:
                    return ""
                if key in error_map:
                    return error_map[key]
                key_l = key.lower()
                for k, v in error_map.items():
                    if k and (k.lower() in key_l or key_l in k.lower()):
                        return v
                return ""

            if kind == "SI":
                try:
                    conn = get_connection()
                    # collect errors under both code variants services may use
                    error_map = _get_raw_errors(conn, "SI")
                    for k, v in _get_raw_errors(conn, "sales_invoice").items():
                        error_map.setdefault(k, v)
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT invoice_no, customer_name, total, method
                        FROM   sales
                        WHERE  synced = 0 OR synced IS NULL
                        ORDER  BY id DESC
                    """)
                    for inv, cust, amt, meth in cur.fetchall():
                        inv_key = inv or ""
                        raw_err = _match_error(error_map, inv_key)
                        display_err = (
                            raw_err if raw_err
                            else f"Pending — not yet attempted  (method: {meth or 'unknown'})"
                        )
                        rows.append((
                            inv_key or "—",
                            cust or "Walk-in",
                            f"${float(amt or 0):.2f}",
                            display_err,
                        ))
                    conn.close()
                except Exception as e:
                    rows.append(("—", "—", "—", f"DB error: {e}"))

            elif kind == "CN":
                try:
                    conn = get_connection()
                    error_map = _get_raw_errors(conn, "CN")
                    for k, v in _get_raw_errors(conn, "credit_note").items():
                        error_map.setdefault(k, v)
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT cn_number, customer_name, total, cn_status
                        FROM   credit_notes
                        WHERE  cn_status IN ('ready','pending_sync')
                        ORDER  BY id DESC
                    """)
                    for cn_no, cust, amt, status in cur.fetchall():
                        cn_key = cn_no or ""
                        raw_err = _match_error(error_map, cn_key)
                        display_err = (
                            raw_err if raw_err
                            else f"Pending — status: {status or 'ready'}"
                        )
                        rows.append((
                            cn_key or "—",
                            cust or "—",
                            f"${float(amt or 0):.2f}",
                            display_err,
                        ))
                    conn.close()
                except Exception as e:
                    rows.append(("—", "—", "—", f"DB error: {e}"))

            elif kind == "SO":
                try:
                    conn = get_connection()
                    error_map = _get_raw_errors(conn, "SO")
                    for k, v in _get_raw_errors(conn, "sales_order").items():
                        error_map.setdefault(k, v)
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT order_no, customer_name, total
                        FROM   sales_order
                        WHERE  synced = 0 OR synced IS NULL
                        ORDER  BY id DESC
                    """)
                    for ono, cust, amt in cur.fetchall():
                        so_key = ono or ""
                        raw_err = _match_error(error_map, so_key)
                        display_err = (
                            raw_err if raw_err
                            else "Pending — not yet attempted"
                        )
                        rows.append((
                            so_key or "—",
                            cust or "—",
                            f"${float(amt or 0):.2f}",
                            display_err,
                        ))
                    conn.close()
                except Exception as e:
                    rows.append(("—", "—", "—", f"DB error: {e}"))

            elif kind == "PAY":
                try:
                    conn = get_connection()
                    error_map = _get_raw_errors(conn, "PAY")
                    for k, v in _get_raw_errors(conn, "PE").items():
                        error_map.setdefault(k, v)
                    for k, v in _get_raw_errors(conn, "payment_entry").items():
                        error_map.setdefault(k, v)
                    
                    cur = conn.cursor()
                    # Show ALL unsynced payment entries — including sale-linked ones.
                    # Currency column included so ZiG/ZWD entries are clearly labelled.
                    cur.execute("""
                        SELECT reference_no, party_name, paid_amount, currency, last_error, sync_attempts FROM (
                            SELECT pe.reference_no, pe.party_name, pe.paid_amount,
                                   pe.currency, ISNULL(pe.sync_error, pe.last_error) as last_error, pe.sync_attempts, pe.id
                            FROM   payment_entries pe
                            WHERE  (pe.synced = 0 OR pe.synced IS NULL)
                            
                            UNION ALL
                            
                            SELECT le.order_no as reference_no, le.customer_name as party_name, le.deposit_amount as paid_amount,
                                   le.deposit_currency as currency, ISNULL(le.sync_error, le.error_message) as last_error, le.sync_attempts, le.id
                            FROM   laybye_payment_entries le
                            WHERE  le.status != 'synced'

                            UNION ALL

                            SELECT cp.reference as reference_no, c.customer_name as party_name, cp.amount as paid_amount,
                                   cp.currency, cp.sync_error as last_error, cp.sync_attempts, cp.id
                            FROM   customer_payments cp
                            LEFT JOIN customers c ON cp.customer_id = c.id
                            WHERE  (cp.synced = 0 OR cp.synced IS NULL)
                        ) as combined
                        ORDER BY id DESC
                    """)
                    for ref, cust, amt, curr, db_err, attempts in cur.fetchall():
                        pay_key = ref or ""
                        raw_err = (db_err or "").strip() or _match_error(error_map, pay_key)
                        att = attempts or 0
                        if att >= 60:
                            attempt_str = f" (Max retries reached — click Retry to reset)"
                        elif att > 0:
                            attempt_str = f" (Attempt {att}/60)"
                        else:
                            attempt_str = ""
                        display_err = (
                            f"{raw_err}{attempt_str}" if raw_err
                            else "Pending — not yet attempted"
                        )
                        curr_display = (curr or "USD").upper()
                        rows.append((
                            pay_key or "—",
                            cust or "Walk-in",
                            f"{curr_display}  {float(amt or 0):,.2f}",
                            display_err,
                        ))
                    conn.close()
                except Exception as e:
                    rows.append(("—", "—", "—", f"DB error: {e}"))

            elif kind == "CUST":
                try:
                    conn = get_connection()
                    error_map = _get_raw_errors(conn, "CUST")
                    for k, v in _get_raw_errors(conn, "customer").items():
                        error_map.setdefault(k, v)
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT id, customer_name, custom_telephone_number
                        FROM   customers
                        WHERE  frappe_synced = 0 OR frappe_synced IS NULL
                        ORDER  BY id DESC
                    """)
                    for cid, cname, phone in cur.fetchall():
                        cust_key = f"CUST-{cid}"
                        raw_err = (
                            _match_error(error_map, cust_key)
                            or _match_error(error_map, str(cid))
                            or (_match_error(error_map, cname) if cname else "")
                        )
                        display_err = (
                            raw_err if raw_err
                            else "Not yet synced to server"
                        )
                        rows.append((
                            cust_key,
                            cname or "—",
                            phone or "—",
                            display_err,
                        ))
                    conn.close()
                except Exception as e:
                    rows.append(("—", "—", "—", f"DB error: {e}"))

        except Exception:
            pass

        return rows

    # ── Smart tab selection ───────────────────────────────────────────────────
    def _select_smart_tab(self):
        kinds = list(self._TAB_META.keys())   # ["SI","CN","SO"]

        # If caller specified a kind, use it
        if self._start_kind in kinds:
            self._tab_widget.setCurrentIndex(kinds.index(self._start_kind))
            return

        # Auto: pick first tab that has errors
        for i, kind in enumerate(kinds):
            if self._counts.get(kind, 0) > 0:
                self._tab_widget.setCurrentIndex(i)
                return

    # ── Copy error ────────────────────────────────────────────────────────────
    def _copy_error(self, kind: str):
        tbl = self._tables[kind]
        rows = tbl.selectedItems()
        if not rows:
            # copy all errors for this tab
            lines = []
            for r in range(tbl.rowCount()):
                ref   = (tbl.item(r, 0) or QTableWidgetItem("")).text()
                cust  = (tbl.item(r, 1) or QTableWidgetItem("")).text()
                amt   = (tbl.item(r, 2) or QTableWidgetItem("")).text()
                err   = (tbl.item(r, 3) or QTableWidgetItem("")).text()
                lines.append(f"{ref} | {cust} | {amt} | {err}")
            text = "\n".join(lines) if lines else ""
        else:
            # copy error column of selected row(s)
            seen = set()
            parts = []
            for it in rows:
                r = it.row()
                if r in seen:
                    continue
                seen.add(r)
                ref  = (tbl.item(r, 0) or QTableWidgetItem("")).text()
                cust = (tbl.item(r, 1) or QTableWidgetItem("")).text()
                amt  = (tbl.item(r, 2) or QTableWidgetItem("")).text()
                err  = (tbl.item(r, 3) or QTableWidgetItem("")).text()
                parts.append(f"{ref} | {cust} | {amt}\n{err}")
            text = "\n\n".join(parts)

        if text:
            QApplication.clipboard().setText(text)
            # Show confirmation tooltip so cashier knows copy worked
            try:
                from PySide6.QtWidgets import QToolTip
                from PySide6.QtGui import QCursor
                tbl = self._tables.get(kind)
                if tbl:
                    QToolTip.showText(QCursor.pos(), "Copied to clipboard!", tbl, tbl.rect(), 2000)
            except Exception:
                pass

    # ── Retry ─────────────────────────────────────────────────────────────────
    def _on_retry(self, kind: str, btn: QPushButton):
        btn.setEnabled(False)
        btn.setText("Retrying…")
        import threading

        def _do():
            try:
                from database.db import get_connection
                conn = get_connection()

                # ── STEP 1: Release all stale locks for this kind ──────────────
                try:
                    if kind == "PAY":
                        # Reset stuck 'syncing' laybye entries → retry
                        conn.execute("""
                            UPDATE laybye_payment_entries
                            SET status = 'retry'
                            WHERE status = 'syncing'
                              OR  status = 'failed'
                        """)
                        # Reset stuck standard payment entries
                        conn.execute("""
                            UPDATE payment_entries
                            SET synced = 0, syncing = 0
                            WHERE (synced = 0 OR synced IS NULL)
                              AND syncing = 1
                        """)
                        # Reset stuck customer payments (dialog)
                        conn.execute("""
                            UPDATE customer_payments
                            SET syncing = 0, sync_attempts = 0
                            WHERE (synced = 0 OR synced IS NULL)
                              AND syncing = 1
                        """)
                        conn.commit()
                    elif kind == "SI":
                        conn.execute("UPDATE sales SET syncing = 0 WHERE syncing = 1")
                        conn.commit()
                    elif kind == "CN":
                        conn.execute("UPDATE credit_notes SET syncing = 0 WHERE syncing = 1")
                        conn.commit()
                    elif kind == "SO":
                        conn.execute("""
                            UPDATE sales_order
                            SET synced = 0
                            WHERE synced = 2
                        """)
                        conn.commit()
                except Exception as lock_e:
                    print(f"[retry] Lock reset error for {kind}: {lock_e}")
                finally:
                    try: conn.close()
                    except: pass

                # ── STEP 2: Trigger the sync service ──────────────────────────
                if kind == "SI":
                    try:
                        from services.pos_upload_service import push_unsynced_sales
                        push_unsynced_sales()
                    except ImportError:
                        from services.pos_upload_service import push_unsynced_invoices
                        push_unsynced_invoices()
                elif kind == "CN":
                    from services.credit_note_sync_service import push_unsynced_credit_notes
                    push_unsynced_credit_notes(force=True)
                elif kind == "SO":
                    from services.sales_order_upload_service import push_unsynced_orders
                    push_unsynced_orders()
                elif kind == "PAY":
                    try:
                        from services.payment_entry_sync_service import push_unsynced_payment_entries
                        push_unsynced_payment_entries()
                    except Exception as e:
                        print(f"[retry] standard PE sync error: {e}")
                    try:
                        from services.laybye_payment_entry_service import sync_laybye_payment_entries
                        sync_laybye_payment_entries(force=True)
                    except Exception as e:
                        print(f"[retry] laybye PE sync error: {e}")
                elif kind == "CUST":
                    from services.customer_sync_service import push_unsynced_customers
                    push_unsynced_customers()
            except Exception as e:
                print(f"[retry] _on_retry error for kind={kind}: {e}")

            from PySide6.QtCore import QMetaObject, Qt as _Qt2
            QMetaObject.invokeMethod(self, "_after_retry", _Qt2.QueuedConnection)

        threading.Thread(target=_do, daemon=True).start()

    @Slot()
    def _after_retry(self):
        # Re-enable all retry buttons and reload
        self._load_all()
        # Re-enable buttons (find them)
        for i in range(self._tab_widget.count()):
            tab = self._tab_widget.widget(i)
            if tab:
                for child in tab.findChildren(QPushButton):
                    if "Retry" in child.text() or "Retrying" in child.text():
                        child.setEnabled(True)
                        child.setText("Retry Sync Now")
                        child.setIcon(qta.icon("fa5s.sync-alt", color="white"))
from PySide6.QtCore import QThread, Signal as _Signal

class _BadgeWorker(QThread):
    done = _Signal(int, int, int, int, int, int)   # si, cn, so, pay, cust, fiscal

    def run(self):
        si = cn = so = pay = cust = fiscal = 0
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()

            # SI — unsynced sales invoices
            try:
                cur.execute(
                    "SELECT COUNT(*) FROM sales "
                    "WHERE synced = 0 OR synced IS NULL"
                )
                si = int(cur.fetchone()[0] or 0)
                
                # FISCAL — pending/failed fiscalization (for Z badge)
                cur.execute(
                    "SELECT COUNT(*) FROM sales "
                    "WHERE fiscal_status IN ('pending', 'failed')"
                )
                fiscal = int(cur.fetchone()[0] or 0)
            except Exception: pass

            # CN — Credit Notes
            try:
                cur.execute(
                    "SELECT COUNT(*) FROM credit_notes "
                    "WHERE cn_status IN ('ready', 'pending_sync')"
                )
                cn = int(cur.fetchone()[0] or 0)
            except Exception: pass

            # SO — Sales Orders / Laybyes
            try:
                cur.execute(
                    "SELECT COUNT(*) FROM sales_order "
                    "WHERE synced = 0 OR synced IS NULL"
                )
                so = int(cur.fetchone()[0] or 0)
            except Exception: pass

            try:
                cur.execute("""
                        SELECT SUM(c) FROM (
                            SELECT COUNT(*) as c FROM payment_entries pe 
                            WHERE (pe.synced = 0 OR pe.synced IS NULL)
                            UNION ALL
                            SELECT COUNT(*) as c FROM laybye_payment_entries le
                            WHERE le.status != 'synced'
                            UNION ALL
                            SELECT COUNT(*) as c FROM customer_payments cp
                            WHERE (cp.synced = 0 OR cp.synced IS NULL)
                        ) as combined
                """)
                pay = int(cur.fetchone()[0] or 0)
            except Exception: pass

            # CUST — locally-created customers not yet pushed
            try:
                cur.execute(
                    "SELECT COUNT(*) FROM customers "
                    "WHERE frappe_synced = 0 OR frappe_synced IS NULL"
                )
                cust = int(cur.fetchone()[0] or 0)
            except Exception: pass

            conn.close()
        except Exception:
            pass

        self.done.emit(si, cn, so, pay, cust, fiscal)
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
    def _do_nav_sync_products(self):
    
        dlg = OptionsDialog(self, pos_view=self)
        dlg._do_sync_products()

    def _on_laybye(self):
        """
        Simple UI Switcher: 
        Changes the PAY F5 button to a DEPOSIT button without breaking header styles.
        """
        # Ensure references exist to prevent crashes
        if not hasattr(self, 'laybye_btn') or not hasattr(self, 'btn_pay'):
            return

        if self.laybye_btn.isChecked():
            # ── Permission check — mirrors discount PIN flow exactly ───────────
            from PySide6.QtWidgets import QInputDialog, QLineEdit
            from models.user import authenticate_by_pin

            current_user = (getattr(self, 'user', None)
                            or (getattr(self.parent_window, 'user', {})
                                if self.parent_window else {}))

            if not current_user.get('allow_laybye', True):
                pin, ok = QInputDialog.getText(
                    self, "Authorization",
                    "Manager PIN required for Laybye:",
                    QLineEdit.Password
                )
                if not ok or not pin:
                    self.laybye_btn.setChecked(False)
                    return
                manager = authenticate_by_pin(pin)
                if not manager or manager.get("role") != "admin":
                    QMessageBox.critical(self, "Access Denied", "Invalid Manager PIN.")
                    self.laybye_btn.setChecked(False)
                    return

            # 1. Clear cart if needed
            if self._collect_invoice_items():
                res = QMessageBox.question(
                    self, "Clear Cart", "Clear cart for new Laybye?", 
                    QMessageBox.Yes | QMessageBox.No
                )
                if res == QMessageBox.Yes:
                    self._new_sale(confirm=False)

            # 2. Force customer selection IMMEDIATELY - no confirmation popup
            from views.dialogs.laybye_confirm_dialog import _is_walk_in
            
            # If no customer selected OR it's walk-in, open picker immediately
            if not self._selected_customer or _is_walk_in(self._selected_customer):
                # Open customer picker directly - no warning message
                dlg = CustomerSearchPopup(self)
                if dlg.exec() == QDialog.Accepted and dlg.selected_customer:
                    # Single entry point keeps nav-bar btn + inline label +
                    # price list + grid re-price all in sync.
                    self._apply_selected_customer(dlg.selected_customer)
                else:
                    # User cancelled - turn off laybye mode
                    self.laybye_btn.setChecked(False)
                    return

            # 3. Change Main Action Button to Deposit
            self.btn_pay.setText("DEPOSIT (F5)")
            self.btn_pay.setStyleSheet(
                f"background-color: #e67e22; color: {WHITE}; font-weight: bold; "
                f"border-radius: 6px; font-size: 17px;"
            )
            
            if self.parent_window:
                self.parent_window._set_status("MODE: Laybye Active")
        
        else:
            # Reset Main Action Button (pharmacy-aware: PAY / FINALIZE QUOTE / DISPENSE)
            self._refresh_pay_button_label()
            self.btn_pay.setStyleSheet(
                f"background-color: {SUCCESS}; color: {WHITE}; font-weight: bold; "
                f"border-radius: 6px; font-size: 17px;"
            )
            
            if self.parent_window:
                self.parent_window._set_status("MODE: Standard Sale")

    def _execute_laybye_transaction(self):
        """
        Full Laybye flow logic separated for clean execution.
        Called by _open_payment if Laybye mode is active.
        DIRECT FLOW: Skips any confirmation dialogs.
        """
        if not _HAS_LAYBYE:
            QMessageBox.warning(self, "Not Available", 
                                "Laybye dialogs could not be loaded.\n"
                                "Ensure laybye_payment_dialog.py exists.")
            return

        # ── 1. Collect cart ──────────────────────────────────────────────────
        cart_items = self._collect_invoice_items()
        if not cart_items:
            QMessageBox.information(self, "Empty Cart", "Add items to the cart first.")
            return

        try:
            cart_total = float(self._lbl_total.text() or "0")
        except ValueError:
            cart_total = sum(float(it.get("total", 0)) for it in cart_items)

        if cart_total <= 0:
            QMessageBox.information(self, "Zero Total", "Cart total is zero.")
            return

        # ── 2. CUSTOMER SELECTION - Already selected in _on_laybye, but verify ──
        from views.dialogs.laybye_confirm_dialog import _is_walk_in
        
        # If somehow customer is still missing, open picker directly
        if not self._selected_customer or _is_walk_in(self._selected_customer):
            dlg = CustomerSearchPopup(self)
            if dlg.exec() != QDialog.Accepted or not dlg.selected_customer:
                return
            self._apply_selected_customer(dlg.selected_customer)

        confirmed_customer = self._selected_customer

        # ── 3. Deposit dialog (Direct jump to payment) ────────────────────────
        from views.dialogs.laybye_payment_dialog import LaybyePaymentDialog
        deposit_dlg = LaybyePaymentDialog(
            parent=self, 
            total=cart_total, 
            customer=confirmed_customer,
            cashier_id=self.cashier_id if hasattr(self, 'cashier_id') else None,
            cashier_name=self.cashier_name if hasattr(self, 'cashier_name') else "",
            subtotal=self.subtotal if hasattr(self, 'subtotal') else None,
            total_vat=self.total_vat if hasattr(self, 'total_vat') else 0,
            shift_id=self.shift_id if hasattr(self, 'shift_id') else None,
            items=cart_items,
        )
        if deposit_dlg.exec() != QDialog.Accepted:
            return

        deposit_amount = deposit_dlg.deposit_amount
        deposit_method = deposit_dlg.deposit_method
        deposit_splits = deposit_dlg.deposit_splits  # This is the dict with full details
        company_name   = deposit_dlg.accepted_company_name
        delivery_date  = deposit_dlg.delivery_date
        order_type     = deposit_dlg.order_type

        print(f"[Laybye] Deposit amount: {deposit_amount}")
        print(f"[Laybye] Deposit splits (full): {deposit_splits}")
        print(f"[Laybye] Number of splits: {len(deposit_splits) if deposit_splits else 0}")

        # ✅ Convert splits to simple {method: usd_amount} format for the service
        simple_splits = {}
        if deposit_splits:
            for method, data in deposit_splits.items():
                # If data is a dict with 'usd' key, use that
                if isinstance(data, dict) and 'usd' in data:
                    simple_splits[method] = data['usd']
                # If data is already a number, use it directly
                elif isinstance(data, (int, float)):
                    simple_splits[method] = float(data)
                else:
                    simple_splits[method] = float(data) if data else 0.0
        
        print(f"[Laybye] Simple splits for service: {simple_splits}")

        # ── 4. Save Sales Order ─────────────────────────────────────────────
        try:
            from models.sales_order import create_sales_order as _create_sales_order
        except ImportError:
            QMessageBox.critical(self, "DB Error", "models/sales_order.py not found.")
            return

        so_items = [{
            "item_code": it.get("part_no", ""), 
            "item_name": it.get("product_name", ""),
            "qty": it.get("qty", 1), 
            "rate": it.get("price", 0.0), 
            "amount": it.get("total", 0.0)
        } for it in cart_items]

        try:
            order_id = _create_sales_order(
                cart_items=so_items, 
                total=cart_total, 
                deposit_amount=deposit_amount,
                deposit_method=deposit_method, 
                deposit_splits=deposit_splits,  # Pass the full splits with details
                customer=confirmed_customer,
                company=company_name, 
                delivery_date=delivery_date, 
                order_type=order_type,
            )
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Error: {e}")
            import traceback
            traceback.print_exc()
            return



        # ── 6. Print receipt ────────────────────────────────────────────────
        if _HAS_SO_PRINT:
            try:
                from services.sales_order_print import print_laybye_deposit as _print_laybye_deposit
                _print_laybye_deposit(order_id)
            except Exception as e:
                print(f"[Laybye] Print error: {e}")

        # ── 7. Feedback & UI Reset ──────────────────────────────────────────
        self._refresh_unsynced_badge()
        self._new_sale(confirm=False)
        
        # Turn off the toggle in the header
        if hasattr(self, 'laybye_btn'):
            self.laybye_btn.setChecked(False)
            self._on_laybye() 

        if self.parent_window:
            self.parent_window._set_status(f"Laybye #{order_id} Saved Successfully")
    def _refresh_pay_button_label(self):
        # Pharmacists always dispense (Quote workflow, no payment). Everyone
        # else follows the explicit cart-mode toggle. Checking is_pharmacist
        # live on every call — not relying on the potentially-stale
        # _cart_mode — means the label is always correct for the current
        # session regardless of init-time timing.
        if not hasattr(self, "btn_pay") or self.btn_pay is None:
            return
        _user = getattr(self, "user", None)
        _role = (_user or {}).get("role") if isinstance(_user, dict) else None
        _is_p = False
        try:
            from utils.roles import is_pharmacist
            _is_p = bool(is_pharmacist(_user))
        except Exception as _re:
            print(f"[POSView] is_pharmacist import failed: {_re}", flush=True)

        if _is_p:
            # Lock pharmacists into Quote mode so _open_payment reroutes too
            self._cart_mode = "quote"
            self.btn_pay.setText("DISPENSE")
        elif getattr(self, "_cart_mode", "sales") == "quote":
            self.btn_pay.setText("FINALIZE QUOTE")
        else:
            self.btn_pay.setText("PAY  F5")
        print(f"[POSView] PAY label refresh: mode={getattr(self, '_cart_mode', '?')!r} "
              f"role={_role!r} is_pharmacist={_is_p} → {self.btn_pay.text()!r}",
              flush=True)

    def _on_quote_mode_toggle(self, checked: bool):
        # Flip cart mode and repaint the PAY button. Behavior switch happens
        # at click time inside _open_payment (which reads _cart_mode).
        self._cart_mode = "quote" if checked else "sales"
        self._refresh_pay_button_label()
        if getattr(self, "parent_window", None):
            try:
                self.parent_window._set_status(
                    f"MODE: {'Quote' if checked else 'Sales'}"
                )
            except Exception:
                pass

    def _open_payment(self):
        """
        Opens the payment dialog and processes the sale.
        Redirects to Laybye flow if toggled ON.
        In pharmacy mode, reroutes to save+print quotation (the "Dispense"
        path for pharmacists, "Finalize Quote" for everyone else).
        """
        # ── 0. SHIFT GUARD ─────────────────────────────────────────────────────────────
        if not self._require_active_shift():
            return

        # ── 0a. QUOTE MODE REROUTE ────────────────────────────────────────────
        # Pharmacists always dispense (never finalize a sale). Other users
        # follow the explicit Quote-Mode toggle. Live is_pharmacist check so
        # this is immune to _cart_mode drift.
        _reroute = False
        try:
            from utils.roles import is_pharmacist
            if is_pharmacist(getattr(self, "user", None)):
                _reroute = True
        except Exception:
            pass
        if not _reroute and getattr(self, "_cart_mode", "sales") == "quote":
            _reroute = True
        if _reroute:
            self._save_quotation()
            return

        # ── 0b. REDIRECTION LOGIC (Laybye Check) ─────────────────────────────
        # If the laybye switcher is toggled ON, execute the Laybye flow instead
        if hasattr(self, 'laybye_btn') and self.laybye_btn.isChecked():
            # This calls the full Laybye Flow (Confirmation -> Deposit -> Save)
            self._execute_laybye_transaction()
            return

        # ── 1. PERMISSION & VALIDATION ──────────────────────────────────────
        if not self._check_permission("allow_receipt", "Process Payment / Print Receipt"):
            return
            
        try:
            total = float(self._lbl_total.text() or "0")
        except ValueError:
            total = 0.0
            
        if total <= 0:
            QMessageBox.warning(self, "Empty Invoice", "Add items before payment.")
            return

        # ── 2. CUSTOMER REQUIREMENT ─────────────────────────────────────────
        # Ensure the default customer is loaded if none selected yet.
        self._ensure_default_customer()
        # If still none is selected, open the customer picker now.
        if not self._selected_customer:
            QMessageBox.information(
                self, "Select Customer",
                "Please select a customer before processing payment."
            )
            _picker = CustomerSearchPopup(self)
            if _picker.exec() != QDialog.Accepted or not _picker.selected_customer:
                return  # cashier cancelled
            # Central setter — keeps nav btn + inline label + price list +
            # grid re-price + cart-clear prompt all consistent.
            self._apply_selected_customer(_picker.selected_customer)

        # ── 3. COLLECT INVOICE ITEMS ─────────────────────────────────────────
        items = self._collect_invoice_items()
        
        if not items or len(items) == 0:
            QMessageBox.warning(self, "No Items", "No items in the invoice to save.")
            return
        
        print(f"[POSView] Collected {len(items)} items from invoice table")
        for idx, it in enumerate(items):
            print(f"   Item {idx+1}: {it.get('product_name')} - qty: {it.get('qty')} - total: {it.get('total')}")
        
        # Calculate subtotal and VAT
        subtotal = 0.0
        total_vat = 0.0
        for it in items:
            subtotal += it.get("total", 0)
            total_vat += it.get("tax_amount", 0)
        
        # Get cashier info
        cashier_id = self.user.get("id") if isinstance(self.user, dict) else None
        cashier_name = self.user.get("username", "") if isinstance(self.user, dict) else ""
        
        # Get active shift ID
        from models.shift import get_active_shift
        active_shift = get_active_shift()
        shift_id = active_shift.get("id") if active_shift else None
        discount_amount = getattr(self, "current_discount_percent", 0.0)
        
        # ── 4. OPEN PAYMENT DIALOG WITH ITEMS ──────────────────────────────────
        if _HAS_PAYMENT_DIALOG:
            dlg = _ExternalPaymentDialog(
                self,
                total=total,
                customer=self._selected_customer,
                items=items,  # PASS THE ITEMS!
                cashier_id=cashier_id,
                cashier_name=cashier_name,
                subtotal=subtotal,
                total_vat=total_vat,
                discount_amount=discount_amount,
                shift_id=shift_id,
            )
        else:
            dlg = PaymentDialog(
                self,
                total=total,
                customer=self._selected_customer,
                items=items,  # PASS THE ITEMS!
                cashier_id=cashier_id,
                cashier_name=cashier_name,
                subtotal=subtotal,
                total_vat=total_vat,
                discount_amount=discount_amount,
                shift_id=shift_id,
            )

        if dlg.exec() == QDialog.Accepted:
            # ✅ EXTRACT DATA FROM THE DIALOG (sale already created inside PaymentDialog)
            if hasattr(dlg, "accepted_tendered"):
                tendered       = dlg.accepted_tendered
                method         = dlg.accepted_method
                change_out     = getattr(dlg, "accepted_change", max(tendered - total, 0.0))
                final_customer = getattr(dlg, "accepted_customer", self._selected_customer)
                sale_id_result = getattr(dlg, "accepted_sale_id", None)
                sale           = getattr(dlg, "accepted_sale", None)  # ✅ USE THE SALE FROM DIALOG
                splits         = getattr(dlg, "accepted_splits", [])
                has_on_account = getattr(dlg, "accepted_is_credit", False)
                
                print(f"[POSView] Sale already created in PaymentDialog with ID: {sale_id_result}")
                
                # ✅ CRITICAL: DO NOT CREATE SALE AGAIN - IT ALREADY EXISTS!
                # The sale was already created in PaymentDialog._save()
                # We just need to handle UI updates and any post-sale actions
                
                if sale is None and sale_id_result is not None:
                    # If we have sale ID but not the full sale object, fetch it
                    try:
                        from models.sale import get_sale_by_id
                        sale = get_sale_by_id(sale_id_result)
                        print(f"[POSView] Fetched sale {sale_id_result} from database")
                    except Exception as e:
                        print(f"[POSView] Error fetching sale: {e}")
                
                cust_name    = final_customer.get("customer_name", "Walk-in") if final_customer else "Walk-in"
                cust_contact = final_customer.get("custom_telephone_number", "") if final_customer else ""
                company_name = getattr(dlg, "accepted_company_name", "")

                # ── Work out real vs On Account amounts ─────────────────────────
                real_splits   = [sp for sp in splits if not sp.get("on_account")]
                oa_splits     = [sp for sp in splits if sp.get("on_account")]
                real_paid_usd = sum(sp.get("base_value", sp.get("amount", 0)) for sp in real_splits) if real_splits else (
                    0.0 if has_on_account else tendered
                )
                oa_amount      = round(sum(sp.get("base_value", sp.get("amount", 0)) for sp in oa_splits), 4)

                # ── 5. POST-SALE ACTIONS (Payment entries already created in PaymentDialog) ──
                # NOTE: Payment entries are already created in PaymentDialog._save()
                # We don't need to create them again here!
                
                print(f"[POSView] Sale #{sale.get('invoice_no', 'N/A') if sale else 'N/A'} completed")
                print(f"[POSView] Total: ${total:.2f} | Paid: ${tendered:.2f} | Change: ${change_out:.2f}")
                print(f"[POSView] Payment method: {method}")
                print(f"[POSView] On Account: {has_on_account}")
                print(f"[POSView] Splits: {len(splits)}")

                # ── 6. UI FEEDBACK & CLEANUP ──────────────────────────────────
                if sale:
                    self._update_prev_txn_display(
                        paid=tendered, change=change_out,
                        invoice_no=sale.get("invoice_no", "")
                    )
                    if self.parent_window:
                        status = f"Sale #{sale.get('number', '')} saved — ${total:.2f} ({method})"
                        if cust_name and cust_name != "Walk-in":
                            status += f" — {cust_name}"
                        if has_on_account:
                            status += "  [On Account]"
                        self.parent_window._set_status(status)
                    self._refresh_unsynced_badge()
                else:
                    print(f"[POSView] WARNING: No sale object available after payment dialog")
                    QMessageBox.warning(self, "Sale Error", 
                        "The sale was processed but could not be retrieved. Please check the database.")
                    return

            else:
                # Fallback for older payment dialog that doesn't have accepted_sale
                print(f"[POSView] Using fallback - payment dialog didn't provide sale object")
                try:
                    tendered = float(dlg._amt.text() or "0")
                except (ValueError, AttributeError):
                    tendered = total
                method         = getattr(dlg, "_method", "CASH")
                change_out     = max(tendered - total, 0.0)
                final_customer = self._selected_customer
                sale_id_result = None
                splits         = []
                has_on_account = False
                
                # Fallback: Create sale here only if not already created
                from models.sale import create_sale
                from services.payment_entry_service import create_payment_entry
                
                discount_pct = getattr(self, "current_discount_percent", 0.0)
                discount_amt = round(subtotal * (discount_pct / 100.0), 4) if discount_pct > 0 else 0.0
                cust_name = final_customer.get("customer_name", "Walk-in") if final_customer else "Walk-in"
                cust_contact = final_customer.get("custom_telephone_number", "") if final_customer else ""
                company_name = ""
                
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
                    is_on_account=False,
                    skip_stock=False,
                    skip_print=False,
                    shift_id=shift_id,
                )
                
                create_payment_entry(sale)
                
                self._update_prev_txn_display(
                    paid=tendered, change=change_out,
                    invoice_no=sale.get("invoice_no", "")
                )
                if self.parent_window:
                    status = f"Sale #{sale.get('number', '')} saved — ${total:.2f} ({method})"
                    if cust_name and cust_name != "Walk-in":
                        status += f" — {cust_name}"
                    self.parent_window._set_status(status)
                self._refresh_unsynced_badge()

            # Clear invoice for next customer
            self._new_sale(confirm=False)
            
        else:
            # Dialog was cancelled or rejected
            print(f"[POSView] Payment dialog cancelled")
            pass

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
        self.current_discount_percent = 0.0   # ← Discount state
        self._quotation_mode = False           # ← Quotation mode flag

        # Active price list for the current customer — resolved from the
        # customer's default_price_list_id at selection time. Used by the
        # price-lookup helper when adding items to the cart. None means
        # "no price list configured" → any item lookup returns 0 and the
        # cashier can't add to cart. (Matches Android behaviour.)
        self._active_price_list: str | None = None

        self._build_ui()
        QTimer.singleShot(0, self._ensure_default_customer)

        # Enable global Up/Down → cart navigation. Installing POSView as an
        # event filter on QApplication lets us catch Up/Down from any focused
        # child (product grid buttons, category buttons, etc.) and route them
        # to the cart table. Text inputs still keep their own behaviour —
        # see the Up/Down branch at the top of eventFilter().
        try:
            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self)
                self._global_cart_nav_ready = True
        except Exception as _e:
            print(f"[POSView] global cart nav install failed: {_e}")

    # =========================================================================
    # QUOTATION MANAGEMENT METHODS
    # =========================================================================
    
    def _open_quotation_manager(self):
        """Open quotation management dialog."""
        try:
            from views.dialogs.quotation_dialog import QuotationDialog
            dlg = QuotationDialog(self)
            dlg.quotation_converted.connect(self._add_quotation_to_cart)
            dlg.exec()
        except ImportError as e:
            QMessageBox.warning(self, "Error", f"Could not open Quotation Manager:\n{e}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Unexpected error:\n{e}")

    def _add_quotation_to_cart(self, data):
        """Add quotation items to cart."""
        cart_items = data.get("cart_items", [])
        customer = data.get("customer", "")
        quotation_name = data.get("quotation_name", "")

        # Loading a quotation converts it into an active sale — exit any active
        # Quote mode so the PAY button finalises a sale instead of saving back
        # into the quotation.
        if getattr(self, "_quotation_mode", False):
            self._quotation_mode = False
            try:
                if hasattr(self, "quote_btn") and hasattr(self.quote_btn, "setChecked"):
                    self.quote_btn.setChecked(False)
            except Exception:
                pass

        # Check if cart has items
        if self._collect_invoice_items():
            reply = QMessageBox.question(self, "Clear Cart",
                f"Load quotation {quotation_name}? This will clear the current cart.",
                QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
            self._new_sale(confirm=False)
        
        # Add items to cart — write directly into each empty row so the exact
        # quotation qty is preserved (bypasses the +1 duplicate logic in
        # _add_product_to_invoice which would reset every line to qty=1).
        for item in cart_items:
            qty = item.get("qty", 1)
            try:
                qty = float(qty)
                if qty <= 0:
                    qty = 1.0
            except (TypeError, ValueError):
                qty = 1.0

            name       = item.get("product_name", "")
            price      = item.get("price", 0)
            part_no    = item.get("part_no", "")
            product_id = item.get("product_id", None)
            discount   = item.get("discount", 0)

            # Resolve tax display from product record
            tax_display = ""
            if product_id:
                try:
                    from models.product import get_product_by_id
                    prod = get_product_by_id(product_id)
                    if prod:
                        tax_rate = prod.get("tax_rate", 0.0)
                        tax_display = f"VAT {tax_rate}%" if tax_rate > 0 else "ZERO RATED"
                except Exception:
                    pass
            if not tax_display and part_no:
                try:
                    from database.db import get_connection
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT tax_rate, tax_type FROM products WHERE part_no = ?",
                        (part_no,)
                    )
                    row = cursor.fetchone()
                    conn.close()
                    if row:
                        tax_rate = float(row[0] or 0)
                        tax_display = f"VAT {tax_rate}%" if tax_rate > 0 else "ZERO RATED"
                except Exception:
                    pass

            r = self._find_next_empty_row()
            self._ensure_rows(r + 1)
            self._block_signals = True
            self._init_row(
                r,
                part_no=part_no,
                details=name,
                qty=f"{qty:.4g}",
                amount=f"{price:.2f}",
                disc=f"{discount:.2f}",
                tax=tax_display
            )
            row_item = self.invoice_table.item(r, 0)
            if row_item:
                row_item.setData(Qt.UserRole, product_id)
                # Pharmacy: restore dosage/batch metadata on loaded quotation rows
                if item.get("is_pharmacy"):
                    row_item.setData(self.PHARMACY_META_ROLE, {
                        "is_pharmacy": True,
                        "dosage":      item.get("dosage"),
                        "batch_no":    item.get("batch_no"),
                        "expiry_date": item.get("expiry_date"),
                        "product_id":  product_id,
                    })
                    try:
                        row_item.setIcon(qta.icon("fa5s.prescription-bottle-alt",
                                                  color="#6a1b9a"))
                    except Exception:
                        pass
            self._block_signals = False
            self._recalc_row(r)
            self._last_filled_row = r

        self._recalc_totals()

        # Set customer if provided — route through the central setter so
        # the grid reprices and the inline label stays in sync.
        if customer:
            try:
                from models.customer import search_customers
                customers = search_customers(customer)
                if customers:
                    self._apply_selected_customer(customers[0])
            except Exception as e:
                print(f"Error setting customer: {e}")
        
        if self.parent_window:
            self.parent_window._set_status(f"Loaded quotation: {len(cart_items)} items")
        
        QMessageBox.information(self, "Success", 
            f"Quotation {quotation_name} loaded with {len(cart_items)} item(s).")
    # =========================================================================
    # REST OF YOUR EXISTING POSView METHODS BELOW
    # =========================================================================
    # (Keep all your existing methods like _build_ui, _build_nav, _build_left_panel,
    #  _build_invoice_table, _init_row, _find_next_empty_row, _highlight_active_row,
    #  _recalc_row, _recalc_totals, _on_item_changed, _open_inline_search,
    #  _inline_refresh_popup, _inline_on_text_changed, _inline_on_enter,
    #  _inline_on_item_clicked, _inline_commit_query, _inline_commit_product,
    #  _fill_row_from_product, _close_inline_search, eventFilter,
    #  _on_cell_clicked, _on_cell_double_clicked, _on_product_btn_clicked,
    #  _pick_product_uom_and_price, _resolve_price_for_product, _get_price_rows_for_list,
    #  _is_template_product, _pick_variant, _check_permission, _warn_popup,
    #  _require_active_shift, _get_pos_rule, _apply_pricing_rules,
    #  _add_product_to_invoice, _build_invoice_footer, _update_prev_txn_display,
    #  _build_right_panel, _build_numpad, _numpad_press, _numpad_clear,
    #  _numpad_del_line, _numpad_enter, _open_qty_popup, _build_bottom_grid,
    #  _on_grid_resize, _render_product_page_debounced, _cat_scroll,
    #  _refresh_cat_tabs, _cat_tab_style, _on_category_tap, _load_category_products,
    #  _grid_turn_page, _render_product_page, _apply_btn_image,
    #  _product_btn_context_menu, _set_product_image, _remove_product_image,
    #  _reload_current_category, _open_day_shift, _open_shift_chooser,
    #  _refresh_shift_pill, _open_stock_file, _open_settings, _select_customer,
    #  _open_sales_list, _collect_invoice_items, _save_sale, _print_receipt,
    #  _print_receipt_for_sale, _reprint_by_invoice_no, _open_payment,
    #  _open_customer_payment_entry, _open_hold_recall, _reset_customer_btn,
    #  _refresh_customer_btn, _ensure_default_customer, _refresh_unsynced_badge,
    #  _open_credit_note_dialog, _load_credit_note_into_table, _exit_return_mode,
    #  _process_return, _print_credit_note_receipt, _new_sale, _on_discount_clicked,
    #  _quick_tender, _on_laybye, _execute_laybye_transaction, _on_quotation,
    #  _save_quotation, _send_quotation_to_printer, etc.)
    # =========================================================================
    def _clear_cart(self):
        """Clear all items from the cart/invoice table"""
        # Clear the table
        self.invoice_table.setRowCount(0)
        self._ensure_rows(1)  # Reset with 1 empty row
        self._last_filled_row = -1
        
        # Reset totals
        if hasattr(self, '_lbl_total'):
            self._lbl_total.setText("0.00")
        if hasattr(self, '_lbl_subtotal'):
            self._lbl_subtotal.setText("0.00")
        if hasattr(self, '_lbl_vat'):
            self._lbl_vat.setText("0.00")
        if hasattr(self, '_lbl_discount'):
            self._lbl_discount.setText("0.00")
        
        # Reset discount
        self.current_discount_percent = 0.0
        
        # Clear any selected items
        self._active_row = -1
        self._active_col = -1
        
        print("[POS] Cart cleared")

    def _send_quotation_to_printer(self, text: str):
        """Send quotation text to printer - COMMENTED OUT FOR NOW"""
        # TODO: Fix printing service issue
        # The error was: 'str' object has no attribute 'companyName'
        # This needs to be fixed in the printing service
        
        print("[Quotation] Printing skipped - printing service needs fix")
        print(f"[Quotation] Would have printed:\n{text}")
        
        """
        # ORIGINAL PRINTING CODE - COMMENTED OUT
        try:
            from services.printing_service import printing_service
            
            # Get company defaults for header
            from models.company_defaults import get_defaults
            company = get_defaults()
            
            # Build header with company info
            header = []
            company_name = company.get("company_name", "HAVANO POS")
            header.append("=" * 40)
            header.append(f"{company_name:^40}")
            header.append("=" * 40)
            
            # Add company address if available
            if company.get("address_1"):
                header.append(company.get("address_1"))
            if company.get("address_2"):
                header.append(company.get("address_2"))
            if company.get("phone"):
                header.append(f"Tel: {company.get('phone')}")
            if company.get("email"):
                header.append(f"Email: {company.get('email')}")
            if company.get("tin_number"):
                header.append(f"TIN: {company.get('tin_number')}")
            header.append("-" * 40)
            
            # Combine header with quotation text
            full_text = "\n".join(header) + "\n" + text
            
            # Print to configured printer
            from models.hardware_settings import get_hardware_settings
            settings = get_hardware_settings()
            printer_name = settings.get("main_printer", "")
            
            if printer_name and printer_name != "(None)":
                success = printing_service.print_text(full_text, printer_name=printer_name)
                if success:
                    print("[Quotation] ✅ Printed successfully")
                else:
                    print("[Quotation] ❌ Print failed")
            else:
                print("[Quotation] No printer configured")
                
        except Exception as e:
            print(f"[Quotation] ❌ Printing failed: {e}")
            import traceback
            traceback.print_exc()
        """

    def _save_quotation(self):
        """Save and print the current cart as a Quotation."""
        items = self._collect_invoice_items()
        if not items:
            QMessageBox.information(self, "Empty Cart", "Add items before saving a Quotation.")
            return
        if not self._selected_customer:
            QMessageBox.information(self, "No Customer", "Please select a customer first.")
            return
        
        try:
            total = float(self._lbl_total.text() or "0")
        except ValueError:
            total = sum(float(i.get("total", 0)) for i in items)

        cname = self._selected_customer.get("customer_name", "")
        from PySide6.QtCore import QDateTime, QDate
        now = QDateTime.currentDateTime().toString("dd/MM/yyyy  hh:mm")

        # Cashier / discount rules info
        current_user = (getattr(self, 'user', None)
                        or (getattr(self.parent_window, 'user', {}) if self.parent_window else {}))
        cashier_name = current_user.get("full_name") or current_user.get("username", "")
        allow_disc   = current_user.get("allow_discount", False)
        max_disc_pct = current_user.get("max_discount_percent", 0) or 0
        expiry_str   = current_user.get("discount_expiry_date", "") or ""
        disc_expired = False
        expiry_display = ""
        if expiry_str:
            try:
                ed = QDate.fromString(expiry_str, "yyyy-MM-dd")
                if not ed.isValid():
                    ed = QDate.fromString(expiry_str, "dd/MM/yyyy")
                if ed.isValid():
                    expiry_display = ed.toString("dd/MM/yyyy")
                    if QDate.currentDate() > ed:
                        disc_expired = True
            except Exception:
                pass

        # =========================================================================
        # SAVE TO DATABASE
        # =========================================================================
        from datetime import date
        from models.quotation import Quotation, QuotationItem, save_quotation, get_all_quotations
        
        # Generate quotation number
        current_year = date.today().year
        existing = get_all_quotations()
        existing_names = [q.name for q in existing]
        
        qtn_num = 1
        while True:
            qtn_name = f"SAL-QTN-{current_year}-{qtn_num:05d}"
            if qtn_name not in existing_names:
                break
            qtn_num += 1
        
        # Create quotation items with proper None handling
        quotation_items = []
        for it in items:
            # Handle None values - convert to 0 if needed
            qty = it.get("qty")
            if qty is None:
                qty = 1.0
            else:
                qty = float(qty)
            
            price = it.get("price")
            if price is None:
                price = 0.0
            else:
                price = float(price)
            
            amount = it.get("total")
            if amount is None:
                amount = qty * price
            else:
                amount = float(amount)
            
            discount = it.get("discount")
            if discount is None:
                discount = 0.0
            else:
                discount = float(discount)
            
            part_no = it.get("part_no")
            if part_no is None:
                part_no = ""
            else:
                part_no = str(part_no)
            
            product_name = it.get("product_name")
            if product_name is None:
                product_name = ""
            else:
                product_name = str(product_name)
            
            uom = it.get("uom")
            if uom is None:
                uom = "Nos"
            else:
                uom = str(uom)
            
            # Calculate discounted rate if discount applied
            if discount > 0:
                discounted_rate = price * (1 - discount / 100)
            else:
                discounted_rate = price
            
            quotation_items.append(QuotationItem(
                item_code=part_no,
                item_name=product_name,
                description=product_name,
                qty=qty,
                rate=discounted_rate,
                amount=amount,
                uom=uom,
                part_no=part_no,
                # Pharmacy fields — propagate dosage/batch from row metadata
                is_pharmacy=bool(it.get("is_pharmacy", False)),
                dosage=it.get("dosage"),
                batch_no=it.get("batch_no"),
                expiry_date=it.get("expiry_date"),
            ))
        
        # Resolve a stable cashier_name for this quote so the pharmacy label
        # preview later can show the original creator even if a different
        # user opens the quote.
        _user_ctx = (getattr(self, 'user', None) or
                     (getattr(self.parent_window, 'user', {}) if self.parent_window else {}) or
                     {})
        quote_cashier_name = (
            _user_ctx.get("username")
            or _user_ctx.get("full_name")
            or "Unknown"
        )

        # Create quotation object
        quotation = Quotation(
            name=qtn_name,
            transaction_date=date.today().isoformat(),
            grand_total=total,
            docstatus=0,  # Draft
            company=self._selected_customer.get("company_name", "APK Test"),
            status="Draft",
            customer=cname,
            items=quotation_items,
            valid_till=None,
            reference_number=None,
            synced=False,  # ← NOT SYNCED YET - local only
            cashier_name=quote_cashier_name,
        )
        
        # Save to database
        try:
            local_id = save_quotation(quotation)
            if local_id:
                print(f"[Quotation] ✅ Saved to database: {qtn_name} (ID: {local_id}, synced=False)")
                
                # =========================================================================
                # TRIGGER IMMEDIATE SYNC TO FRAPPE (with retry)
                # =========================================================================
                import threading
                from services.quotation_sync_service import sync_quotation_on_create
                
                # Start sync in background thread so it doesn't block UI
                def do_sync():
                    success = sync_quotation_on_create(local_id, max_retries=3)
                    if success:
                        print(f"[Quotation] ✅ {qtn_name} synced to Frappe")
                    else:
                        print(f"[Quotation] ⚠️ {qtn_name} will be synced later by background worker")
                
                threading.Thread(target=do_sync, daemon=True).start()
                
            else:
                print(f"[Quotation] ⚠️ Failed to save to database")
                QMessageBox.warning(self, "Save Error", "Failed to save quotation to database.")
                return
        except Exception as e:
            print(f"[Quotation] ❌ Error saving: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Save Error", f"Could not save quotation:\n{str(e)}")
            return

        # =========================================================================
        # BUILD PRINT TEXT
        # =========================================================================
        W = 40
        lines = ["=" * W,
                 f"QUOTATION",
                 "=" * W,
                 f"  QTN No:     {qtn_name}",
                 f"  Date:       {now}",
                 f"  Customer:   {cname}",
                 f"  Cashier:    {cashier_name}",
                 f"  Status:     DRAFT",
                 "-" * W]
        
        for it in items:
            name = str(it.get("product_name", ""))[:24]
            qty = it.get("qty")
            if qty is None:
                qty = 1.0
            else:
                qty = float(qty)
            
            price = it.get("price")
            if price is None:
                price = 0.0
            else:
                price = float(price)
            
            disc = it.get("discount")
            if disc is None:
                disc = 0.0
            else:
                disc = float(disc)
            
            line_tot = it.get("total")
            if line_tot is None:
                line_tot = qty * price
            else:
                line_tot = float(line_tot)
            
            qty_str = f"{int(qty)}" if qty == int(qty) else f"{qty:.2f}"
            lines.append(f"{name:<24} {qty_str:>3}x ${price:.2f}")
            if disc > 0:
                disc_amt = qty * price * (disc / 100.0)
                lines.append(f"  Disc {disc:.0f}%            -${disc_amt:.2f}")
            lines.append(f"  {'─'*20}  ${line_tot:.2f}")

        lines += ["-" * W, f"  TOTAL:             ${total:.2f}", "=" * W]

        # Discount Rules Section
        lines.append("  DISCOUNT AUTHORISATION")
        lines.append("-" * W)
        if not allow_disc:
            lines.append("  Discount: NOT PERMITTED for this cashier")
        elif disc_expired:
            lines.append(f"  Discount: EXPIRED ({expiry_display})")
            lines.append("  (Manager PIN required to override)")
        else:
            lines.append(f"  Cashier:  {cashier_name}")
            lines.append(f"  Allowed:  Up to {max_disc_pct}%")
            if expiry_display:
                lines.append(f"  Valid to: {expiry_display}")
            else:
                lines.append("  Valid to: No expiry set")

        lines += ["=" * W, "  This quotation is valid for 30 days.",
                 f"  ID: {local_id} | Synced: No",
                 "=" * W]

        # =========================================================================
        # SHOW PREVIEW DIALOG
        # =========================================================================
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle("Quotation Saved")
        dlg.setMinimumSize(450, 580)
        dlg.setStyleSheet(f"QDialog {{ background:{WHITE}; }}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)
        
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setFont(__import__("PySide6.QtGui", fromlist=["QFont"]).QFont("Courier New", 10))
        txt.setPlainText("\n".join(lines))
        txt.setStyleSheet(f"QTextEdit {{ background:{WHITE}; color:{DARK_TEXT}; border:1px solid {BORDER}; border-radius:4px; }}")
        lay.addWidget(txt, 1)
        
        br = QHBoxLayout()
        br.setSpacing(8)
        
        print_btn = QPushButton("Print")
        print_btn.setFixedHeight(36)
        print_btn.setCursor(Qt.PointingHandCursor)
        print_btn.setStyleSheet(f"QPushButton {{ background:{SUCCESS}; color:{WHITE}; border:none; border-radius:5px; font-size:13px; font-weight:bold; padding:0 20px; }} QPushButton:hover {{ background:{SUCCESS_H}; }}")
        
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(36)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"QPushButton {{ background:{NAVY}; color:{WHITE}; border:none; border-radius:5px; font-size:13px; font-weight:bold; padding:0 20px; }} QPushButton:hover {{ background:{NAVY_2}; }}")
        
        # Print fires services.quotation_print directly and closes the preview
        # silently — no "Printing is temporarily disabled" popup, no final
        # "Success" dialog. Any failure is surfaced on the parent status bar.
        def _do_print_and_close():
            try:
                from services.quotation_print import print_quotation
                ok = print_quotation({"name": qtn_name, "local_id": local_id})
            except Exception as _pe:
                ok = False
                print(f"[Quotation] print_quotation raised: {_pe}")
            if self.parent_window and hasattr(self.parent_window, "_set_status"):
                self.parent_window._set_status(
                    f"Quotation {qtn_name} sent to printer."
                    if ok else
                    f"Quotation {qtn_name} saved; print failed — check printer."
                )
            dlg.accept()

        print_btn.clicked.connect(_do_print_and_close)
        close_btn.clicked.connect(dlg.accept)

        br.addStretch()
        br.addWidget(print_btn)
        br.addWidget(close_btn)
        lay.addLayout(br)

        dlg.exec()

        # Clear cart + fully exit quotation mode (both flags + navbar pill +
        # PAY button label). No "Success" popup — status bar already carries
        # the print result.
        self._clear_cart()
        self._quotation_mode = False
        self._cart_mode = "sales"
        if hasattr(self, '_quotation_mode_btn'):
            self._quotation_mode_btn.setChecked(False)
        if hasattr(self, 'quote_mode_btn') and self.quote_mode_btn is not None:
            try:
                self.quote_mode_btn.blockSignals(True)
                self.quote_mode_btn.setChecked(False)
                self.quote_mode_btn.blockSignals(False)
            except Exception:
                pass
        try:
            self._refresh_pay_button_label()
        except Exception:
            pass

    # =========================================================================
    # NAV BAR
    # =========================================================================
    def _build_nav(self):
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet(f"background-color: {WHITE}; border-bottom: 2px solid {BORDER};")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(6)

        # ── Brand + Logo ──────────────────────────────────────────────────────
        logo = QLabel("Havano POS System")
        logo.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {NAVY}; background: transparent;")
        layout.addWidget(logo)
        layout.addSpacing(12)

        # ── Uniform nav button spec ──
        NAV_H  = 30
        NAV_FS = 11   
        NAV_R  = 4    
        NAV_PX = 12   

        def _nav_style(bg, hov, extra=""):
            return (
                f"QPushButton {{ background-color:{bg}; color:{WHITE}; border:none; "
                f"border-radius:{NAV_R}px; font-size:{NAV_FS}px; font-weight:bold; "
                f"padding:0 {NAV_PX}px; {extra}}} "
                f"QPushButton:hover {{ background-color:{hov}; }} "
                f"QPushButton:pressed {{ background-color:{NAVY_3}; color:{WHITE}; }}"
            )

        # ── Helper: uniform nav button ────────────────────────────────────────
        def _nb(text, handler, color=NAVY_2, hov=NAVY_3, min_w=None):
            b = QPushButton(text)
            b.setFixedHeight(NAV_H)
            b.setCursor(Qt.PointingHandCursor)
            if min_w:
                b.setMinimumWidth(min_w)
            b.setStyleSheet(_nav_style(color, hov))
            b.clicked.connect(handler)
            return b

        # ── Sales button ──────────────────────────────────────────────────────
        sales_menu_btn = HoverMenuButton("Sales ▾", color=ACCENT, hov=ACCENT_H, height=NAV_H)
        sales_menu_btn.addItem("Sales Invoice List", self._open_sales_list)
        sales_menu_btn.addItem("Sales Orders",        self._open_sales_order_list)
        sales_menu_btn.addSeparator()
        sales_menu_btn.addItem("Payments", self._open_customer_payment_entry)
        sales_menu_btn.addSeparator()
        sales_menu_btn.addItem("Reprint Shift Reconciliation", self._open_shift_reprint)
        layout.addWidget(sales_menu_btn)

        # ── Admin Check ───────────────────────────────────────────────────────
        is_admin_user = False
        try:
            from models.user import is_admin
            if self.user and is_admin(self.user):
                is_admin_user = True
        except Exception:
            pass

        # ── Inventory button (admin only) ─────────────────────────────────────
        if is_admin_user:
            inv_menu_btn = HoverMenuButton("Inventory ▾", color=NAVY_2, hov=NAVY_3, height=NAV_H)
            inv_menu_btn.addItem("Stock on Hand",   self._open_inventory_dashboard)
            layout.addWidget(inv_menu_btn)

        # ── Maintenance button (admin only) ───────────────────────────────────
        if is_admin_user:
            maint_btn = HoverMenuButton("Maintenance ▾", color=NAVY_2, hov=NAVY_3, height=NAV_H)

            def _sd(cls_name, *args, **kwargs):
                def _handler():
                    try:
                        import importlib
                        sd = importlib.import_module("views.dialogs.settings_dialog")
                        cls = getattr(sd, cls_name)
                        p = self.parent_window or self
                        if cls_name == "ManageUsersDialog":
                            cls(p, current_user=self.user).exec()
                        else:
                            cls(p).exec()
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Could not open {cls_name}:\n{e}")
                return _handler

            maint_btn.addItem("Users",              _sd("ManageUsersDialog"))
            maint_btn.addSeparator()
            maint_btn.addItem("Company Defaults",   self._open_company_defaults_nav)
            maint_btn.addItem("POS Rules",          _sd("POSRulesDialog"))
            maint_btn.addItem("Hardware Settings",  _sd("HardwareDialog"))
            maint_btn.addItem("Payment Modes",      self._open_payment_modes_dialog)
            maint_btn.addItem("Advanced Printing",  self._open_adv_printing_nav)
            maint_btn.addSeparator()
            maint_btn.addItem("Sync Queue",         self._open_sales_list)
            maint_btn.addItem("Stock File",         self._open_stock_file)
            maint_btn.addSeparator()
            maint_btn.addItem("Tax Settings",       lambda: coming_soon(self, "Tax Settings"))
            maint_btn.addItem("Printer Setup",      lambda: coming_soon(self, "Printer Setup"))
            maint_btn.addItem("Backup",             lambda: coming_soon(self, "Backup"))
            layout.addWidget(maint_btn)
            layout.addSpacing(10)

        # ── Customer selector ─────────────────────────────────────────────────
        self._cust_btn = QPushButton("Customer")
        self._cust_btn.setIcon(qta.icon("fa5s.user", color="white"))
        self._cust_btn.setFixedHeight(NAV_H)
        self._cust_btn.setMaximumWidth(170)
        self._cust_btn.setCursor(Qt.PointingHandCursor)
        self._cust_btn.setStyleSheet(_nav_style(NAVY_2, NAVY_3))
        self._cust_btn.clicked.connect(self._select_customer)
        layout.addWidget(self._cust_btn)
        layout.addSpacing(4)

        # ── Sync Badges ───────────────────────────────────────────────────────
        def _make_badge(label, tip, handler, color=NAVY_2, hover=NAVY_3):
            b = QPushButton(label)
            b.setFixedHeight(NAV_H)
            b.setMinimumWidth(50)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(_nav_style(color, hover))
            b.setToolTip(tip)
            b.clicked.connect(handler)
            return b

        # ── Q-badge (sync errors) ─────────────────────────────────────────────
        self._q_badge = _make_badge("Q : 0", "All records synced", lambda: UnsyncedPopup("", self).exec())
        self._q_badge.setStyleSheet(_nav_style(SUCCESS, SUCCESS_H))
        layout.addWidget(self._q_badge)
        layout.addSpacing(2)

        # ── Z-badge (fiscalization errors) ────────────────────────────────────
        self._z_badge = _make_badge("Z : 0", "All sales fiscalized", lambda: self._show_unfiscalized_popup(), color=NAVY_2, hover=NAVY_3)
        self._z_badge.setStyleSheet(_nav_style(SUCCESS, SUCCESS_H))
        layout.addWidget(self._z_badge)
        layout.addSpacing(2)

        # Keep hidden references for backward compatibility
        self._all_synced_badge = self._q_badge
        self._si_badge = self._q_badge
        self._cn_badge = self._q_badge
        self._so_badge = self._q_badge

        # ── Cart Mode (Sales vs Quote) — default by role ──────────────────────
        # Pharmacists default to Quote; everyone else to Sales. Toggleable.
        _cart_mode_user = getattr(self, "user", None)
        _is_p = False
        try:
            from utils.roles import is_pharmacist as _is_pharm
            _is_p = bool(_is_pharm(_cart_mode_user))
        except Exception as _cmerr:
            print(f"[POSView] cart_mode init — is_pharmacist import failed: {_cmerr}", flush=True)
        _role_at_init = (
            _cart_mode_user.get("role")
            if isinstance(_cart_mode_user, dict) else None
        )
        _keys_at_init = (
            list(_cart_mode_user.keys())
            if isinstance(_cart_mode_user, dict) else None
        )
        print(
            f"[POSView] cart_mode init: user_type={type(_cart_mode_user).__name__} "
            f"role={_role_at_init!r} keys={_keys_at_init} is_pharmacist={_is_p}",
            flush=True,
        )
        self._cart_mode = "quote" if _is_p else "sales"

        self.quote_mode_btn = QPushButton("Quote Mode")
        self.quote_mode_btn.setCheckable(True)
        self.quote_mode_btn.setChecked(self._cart_mode == "quote")
        self.quote_mode_btn.setFixedHeight(NAV_H)
        self.quote_mode_btn.setMinimumWidth(120)
        self.quote_mode_btn.setCursor(Qt.PointingHandCursor)
        self.quote_mode_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY_3}; color: {WHITE}; border: none;
                border-radius: {NAV_R}px; font-size: {NAV_FS}px; font-weight: bold;
                text-align: center; padding: 0px 5px; outline: none;
            }}
            QPushButton:hover   {{ background-color: {NAVY_2}; }}
            QPushButton:checked {{ background-color: #7c3aed; }}
            QPushButton:checked:hover {{ background-color: #9333ea; }}
        """)
        self.quote_mode_btn.setToolTip(
            "Toggle Quote Mode — the finalize button saves the cart as a "
            "quotation instead of opening the payment flow."
        )
        self.quote_mode_btn.toggled.connect(self._on_quote_mode_toggle)
        layout.addWidget(self.quote_mode_btn)
        layout.addSpacing(4)
        
        

        # ── Laybye Switcher ───────────────────────────────────────────────────
        self.laybye_btn = QPushButton("Laybye")
        self.laybye_btn.setCheckable(True)
        self.laybye_btn.setFixedHeight(NAV_H)
        self.laybye_btn.setMinimumWidth(110)
        self.laybye_btn.setCursor(Qt.PointingHandCursor)

        self.laybye_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AMBER};
                color: {WHITE};
                border: none;
                border-radius: {NAV_R}px;
                font-size: {NAV_FS}px;
                font-weight: bold;
                text-align: center;
                padding: 0px 5px;
                outline: none;
            }}
            QPushButton:hover {{
                background-color: {ORANGE};
            }}
            QPushButton:pressed {{
                background-color: {NAVY_3};
                color: {WHITE};
            }}
            QPushButton:checked {{
                background-color: {AMBER};
            }}
            QPushButton:checked:hover {{
                background-color: {ORANGE};
            }}
        """)

        self.laybye_btn.setToolTip("Toggle Laybye Mode")
        self.laybye_btn.clicked.connect(self._on_laybye)
        layout.addWidget(self.laybye_btn)
        layout.addSpacing(4)

        # ── Payments button ───────────────────────────────────────────────────
        layout.addWidget(_nb("Payments", self._open_customer_payment_entry, color=ACCENT, hov=ACCENT_H))
        layout.addSpacing(4)
        
        # ── Quotation button ──────────────────────────────────────────────────
        quote_btn = _nb("Quote", self._on_quotation, color=NAVY_3, hov=NAVY_2)
        quote_btn.setToolTip("Create a Quotation")
        layout.addWidget(quote_btn)
        layout.addSpacing(4)
        
        # ── Options dropdown (replaces right-panel Options button) ───────────────
        options_menu_btn = HoverMenuButton("Options ▾", color=NAVY_2, hov=NAVY_3, height=NAV_H)
        options_menu_btn.addItem("Create Credit Note  (Return)", self._open_credit_note_dialog)
        options_menu_btn.addItem("Save / Print Quotation",       self._save_quotation)
        options_menu_btn.addItem("Manage Quotations",            self._open_quotation_manager)
        options_menu_btn.addItem("Reprint Invoice",              self._reprint_by_invoice_no)
        options_menu_btn.addSeparator()
        options_menu_btn.addItem("Sync Products from Server",    self._do_nav_sync_products)
        layout.addWidget(options_menu_btn)
        layout.addSpacing(4)
        
        

        # ── Return mode indicator ─────────────────────────────────────────────
        self._return_btn = _nb("↩   Return", self._process_return, color=DANGER, hov=DANGER_H)
        self._return_btn.setVisible(False)
        layout.addWidget(self._return_btn)
        layout.addSpacing(4)

        # Refresh Sync Badges
        QTimer.singleShot(500, self._refresh_unsynced_badge)
        self._unsynced_timer = QTimer(self)
        self._unsynced_timer.setInterval(10000)
        self._unsynced_timer.timeout.connect(self._refresh_unsynced_badge)
        self._unsynced_timer.start()

        layout.addStretch(1)

        # ── Dashboard button (admin only) ─────────────────────────────────────
        if is_admin_user:
            dash_btn = _nb("Dashboard", self.parent_window.switch_to_dashboard if self.parent_window else lambda: None, color=ACCENT, hov=ACCENT_H)
            layout.addWidget(dash_btn)
            layout.addSpacing(4)

        # ── Logout ────────────────────────────────────────────────────────────
        logout = QPushButton("Logout")
        logout.setFixedHeight(NAV_H)
        logout.setCursor(Qt.PointingHandCursor)
        logout.setStyleSheet(_nav_style(DANGER, DANGER_H))
        if self.parent_window:
            logout.clicked.connect(self.parent_window._logout)
        layout.addWidget(logout)

        return bar
    
    def _show_unfiscalized_popup(self):
        """Show popup with unfiscalized sales"""
        try:
            from views.dialogs.unfiscalized_dialog import UnfiscalizedDialog
            UnfiscalizedDialog(self).exec()
        except ImportError:
            QMessageBox.information(self, "Unfiscalized Sales", 
                "Check your database for sales with fiscal_status = 'pending' or 'failed'")
    
    def _refresh_unsynced_badge(self):
        """Kick off a background thread to fetch counts — never blocks the UI."""
        if getattr(self, "_badge_worker_running", False):
            return
        self._badge_worker_running = True

        self._current_badge_worker = _BadgeWorker(self)

        def _on_done(si, cn, so, pay, cust, fiscal):
            self._badge_worker_running = False
            self._apply_badge_counts(si, cn, so, pay, cust, fiscal)
            try:
                self._current_badge_worker.deleteLater()
                self._current_badge_worker = None
            except Exception:
                pass

        self._current_badge_worker.done.connect(_on_done)
        self._current_badge_worker.start()

    def _apply_badge_counts(self, si_count, cn_count, so_count, pay_count, cust_count, fiscal_count):
        """Update the Q-badge and Z-badge UI"""
        # ── Update Q-badge (sync errors) ────────────────────────────────────────
        if hasattr(self, "_q_badge"):
            total_sync = si_count + cn_count + so_count + pay_count + cust_count
            btn = self._q_badge

            if total_sync == 0:
                btn.setText("Q : 0")
                btn.setToolTip("All records synced — click for details")
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {SUCCESS}; color: {WHITE}; border: none;
                        border-radius: 3px; font-size: 11px; font-weight: bold; padding: 0 6px;
                    }}
                    QPushButton:hover {{ background-color: {SUCCESS_H}; }}
                """)
            else:
                bg, hov = (AMBER, ORANGE) if total_sync < 5 else (DANGER, DANGER_H)
                suffix = f"{total_sync} !" if total_sync >= 5 else str(total_sync)
                btn.setText(f"Q : {suffix}")
                btn.setToolTip(
                    f"{total_sync} unsynced record(s)\n"
                    f"  SI={si_count}  CN={cn_count}  SO={so_count}\n"
                    f"  PAY={pay_count}  CUST={cust_count}"
                )
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg}; color: {WHITE}; border: none;
                        border-radius: 3px; font-size: 11px; font-weight: bold; padding: 0 6px;
                    }}
                    QPushButton:hover {{ background-color: {hov}; }}
                """)

        # ── Update Z-badge (fiscalization errors) ───────────────────────────────
        if hasattr(self, "_z_badge"):
            z_btn = self._z_badge

            if fiscal_count == 0:
                z_btn.setText("Z : 0")
                z_btn.setToolTip("All sales fiscalized — click for details")
                z_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {SUCCESS}; color: {WHITE}; border: none;
                        border-radius: 3px; font-size: 11px; font-weight: bold; padding: 0 6px;
                    }}
                    QPushButton:hover {{ background-color: {SUCCESS_H}; }}
                """)
            else:
                bg, hov = (AMBER, ORANGE) if fiscal_count < 5 else (DANGER, DANGER_H)
                suffix = f"{fiscal_count} !" if fiscal_count >= 5 else str(fiscal_count)
                z_btn.setText(f"Z : {suffix}")
                z_btn.setToolTip(
                    f"{fiscal_count} sale(s) pending fiscalization\n"
                    f"Click to view and retry failed fiscalizations"
                )
                z_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg}; color: {WHITE}; border: none;
                        border-radius: 3px; font-size: 11px; font-weight: bold; padding: 0 6px;
                    }}
                    QPushButton:hover {{ background-color: {hov}; }}
                """)
    # Pharmacy user-role key used on invoice_table cells (Qt.UserRole is already
    # used for product_id on col 0, so we stamp pharmacy meta on +1)
    PHARMACY_META_ROLE = Qt.UserRole + 1

    def _is_pharmacy_product_lookup(self, product_id, part_no: str) -> bool:
        """Fetch is_pharmacy_product from DB; returns False if unresolved."""
        try:
            if product_id:
                from models.product import get_product_by_id
                prod = get_product_by_id(int(product_id))
                if prod:
                    return bool(prod.get("is_pharmacy_product", False))
            if part_no:
                from database.db import get_connection
                conn = get_connection(); cur = conn.cursor()
                cur.execute(
                    "SELECT COALESCE(is_pharmacy_product, 0) FROM products WHERE part_no = ?",
                    (part_no,),
                )
                row = cur.fetchone(); conn.close()
                if row:
                    return bool(row[0])
        except Exception as e:
            print(f"[Pharmacy] is_pharmacy_product lookup failed: {e}")
        return False

    def _prompt_dosage_and_batch(self, product_id) -> dict:
        """Pharmacy: modal dialog that captures dosage AND batch together.
        Returns {'dosage': str|None, 'batch_no': str|None, 'expiry_date': str|None}.
        Skipping returns all-None; no-batches path still allows the dosage
        to be captured and the cart add to proceed.

        Uses QDialog (not Qt.Popup) so the QComboBox drop-down lists inside
        are actually clickable — Qt.Popup-flagged windows auto-close as soon
        as their focus is stolen by a child popup, which made the dosage
        search combobox effectively dead."""
        try:
            from models.dosage import list_dosages
            dosages = list_dosages() or []
        except Exception as e:
            print(f"[Pharmacy] list_dosages failed: {e}")
            dosages = []

        try:
            from models.product import get_batches_for_product
            batches = get_batches_for_product(int(product_id)) if product_id else []
        except Exception as e:
            print(f"[Pharmacy] get_batches_for_product failed: {e}")
            batches = []

        # Sort batches by expiry ascending so the soonest-to-expire comes first
        # (becomes the default-selected combobox item for FIFO dispensing).
        def _exp_key(b):
            e = b.get("expiry_date") or ""
            return (e == "", str(e))  # empties last
        batches = sorted(batches, key=_exp_key)

        print(f"[Pharmacy] dosage_and_batch: {len(dosages)} dosage(s), "
              f"{len(batches)} batch(es) for product_id={product_id}", flush=True)

        dlg = QDialog(self)
        dlg.setWindowTitle("Dispense Item — Dosage & Batch")
        dlg.setModal(True)
        dlg.setMinimumSize(560, 420)
        dlg.setStyleSheet(f"""
            QDialog {{ background: {WHITE}; }}
            QLabel  {{ color: {NAVY}; background: transparent; }}
            QComboBox, QLineEdit {{
                background: {WHITE}; color: {NAVY};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 4px 8px; font-size: 13px; min-height: 28px;
            }}
            QComboBox:focus, QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
        """)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        title = QLabel("Dispense Item — Dosage & Batch")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {NAVY};")
        lay.addWidget(title)

        # --- Dosage section ---
        dosage_hdr = QLabel("Dosage")
        dosage_hdr.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {NAVY}; margin-top: 6px;")
        lay.addWidget(dosage_hdr)

        lay.addWidget(QLabel("Search saved dosage (type code or description):"))
        cbo = QComboBox(dlg)
        cbo.setEditable(True)
        cbo.setInsertPolicy(QComboBox.NoInsert)
        cbo.addItem("— none —", "")
        for d in dosages:
            desc = getattr(d, "description", "") or ""
            code = getattr(d, "code", "") or ""
            label = f"{code} — {desc}" if desc else code
            cbo.addItem(label, code)
        # Contains-mode case-insensitive completer for substring search
        try:
            _cmp = cbo.completer()
            if _cmp is not None:
                from PySide6.QtWidgets import QCompleter as _QCmp
                _cmp.setCompletionMode(_QCmp.PopupCompletion)
                _cmp.setFilterMode(Qt.MatchContains)
                _cmp.setCaseSensitivity(Qt.CaseInsensitive)
        except Exception:
            pass
        lay.addWidget(cbo)

        lay.addWidget(QLabel("Or quick dosage (not saved):"))
        edit = QLineEdit(dlg)
        edit.setPlaceholderText("e.g. 1 tab TID x 5d")
        lay.addWidget(edit)

        # Track which dosage input the user touched last
        state = {"last": "combo"}
        edit.textEdited.connect(lambda _t: state.update({"last": "edit"}))
        cbo.activated.connect(lambda _i: state.update({"last": "combo"}))

        # --- Batch section ---
        batch_hdr = QLabel("Batch & Expiry")
        batch_hdr.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {NAVY}; margin-top: 8px;")
        lay.addWidget(batch_hdr)

        batch_cbo = QComboBox(dlg)
        if not batches:
            batch_cbo.addItem("— no batches registered —", None)
            batch_cbo.setEnabled(False)
        else:
            batch_cbo.setEditable(True)
            batch_cbo.setInsertPolicy(QComboBox.NoInsert)
            for b in batches:
                bn  = b.get("batch_no") or "(no batch no)"
                exp = b.get("expiry_date") or "?"
                qty = b.get("qty", 0)
                label = f"{bn}  —  expires {exp}   |   qty: {qty}"
                batch_cbo.addItem(label, b)
            # FIFO default: select the earliest-expiring batch (index 0 after sort)
            batch_cbo.setCurrentIndex(0)
            # Contains-filter completer so users can type batch number or date
            try:
                _bcmp = batch_cbo.completer()
                if _bcmp is not None:
                    from PySide6.QtWidgets import QCompleter as _QCmp
                    _bcmp.setCompletionMode(_QCmp.PopupCompletion)
                    _bcmp.setFilterMode(Qt.MatchContains)
                    _bcmp.setCaseSensitivity(Qt.CaseInsensitive)
            except Exception:
                pass
        lay.addWidget(batch_cbo)

        lay.addStretch()

        # --- Buttons ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        use_btn  = navy_btn("Use",  height=34, color=SUCCESS, hover=SUCCESS_H)
        skip_btn = navy_btn("Skip", height=34, color=NAVY_2,  hover=NAVY_3)
        btn_row.addStretch(); btn_row.addWidget(skip_btn); btn_row.addWidget(use_btn)
        lay.addLayout(btn_row)

        result = {"dosage": None, "batch_no": None, "expiry_date": None}
        def _use():
            if state["last"] == "edit" and edit.text().strip():
                result["dosage"] = edit.text().strip()
            else:
                result["dosage"] = cbo.currentData() or None
            b = batch_cbo.currentData()
            if b:
                result["batch_no"] = b.get("batch_no") or None
                result["expiry_date"] = b.get("expiry_date")
            dlg.accept()
        def _skip():
            dlg.reject()
        use_btn.clicked.connect(_use)
        skip_btn.clicked.connect(_skip)

        dlg.exec()

        return {
            "dosage":      result["dosage"],
            "batch_no":    result["batch_no"],
            "expiry_date": result["expiry_date"],
        }

    def _is_pharmacy_row_locked(self, row: int) -> bool:
        # Cashiers cannot modify or delete rows stamped as pharmacy line items.
        if row is None or row < 0:
            return False
        col0 = self.invoice_table.item(row, 0)
        if not col0 or not col0.data(self.PHARMACY_META_ROLE):
            return False
        try:
            from utils.roles import is_pharmacist
            return not is_pharmacist(getattr(self, "user", None))
        except Exception:
            return False

    def _notify_pharmacy_locked(self):
        try:
            from utils.toast import show_toast
            show_toast(self, "Pharmacy line items are locked — only a pharmacist can modify them.",
                       duration_ms=3000, kind="warn")
        except Exception:
            pass
        QApplication.beep()

    def _add_product_to_invoice(self, name, price, part_no="", product_id=None, stock=None, uom=""):
        # ── Always close any open inline search before we touch the table ─────
        self._close_inline_search()

        # ── #0 Require a running shift ───────────────────────────────────────────
        if not self._require_active_shift():
            return

        # ── Pharmacy gate + dosage/batch capture ─────────────────────────────────
        pharmacy_meta = None
        if self._is_pharmacy_product_lookup(product_id, part_no):
            from utils.roles import is_pharmacist as _is_pharm
            if not _is_pharm(self.user):
                try:
                    QApplication.beep()
                except Exception:
                    pass
                try:
                    from utils.toast import show_toast
                    show_toast(
                        self,
                        "Only pharmacists can add pharmacy products — "
                        "ask a pharmacist to create a quote.",
                        duration_ms=3500, kind="warn",
                    )
                except Exception:
                    pass
                print(f"[Pharmacy] Blocked add — user is not pharmacist: {name}")
                return
            # Pharmacist — single merged popup captures dosage + batch together
            combined = self._prompt_dosage_and_batch(product_id)
            pharmacy_meta = {
                "is_pharmacy": True,
                "dosage":      combined.get("dosage"),
                "batch_no":    combined.get("batch_no"),
                "expiry_date": combined.get("expiry_date"),
                "product_id":  product_id,
            }

        # ── #3 Block zero-price ───────────────────────────────────────────────
        if price <= 0 and self._get_pos_rule("block_zero_price", default=True):
            self._warn_popup(
                "Zero Price Blocked",
                f"<b>{name}</b> has no selling price set.<br>"
                "Update the price in the server and re-sync, or disable the "
                "'Block Zero-Price Sales' rule in Maintenance → POS Rules.",
                icon=QMessageBox.Warning,
            )
            return

        # ── #4 Block zero/negative stock ─────────────────────────────────────
        if self._get_pos_rule("block_zero_stock", default=True):
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
        if self._get_pos_rule("use_pricing_rules", default=True):
            price = self._apply_pricing_rules(product_id, part_no, price)
        
        # ── GET TAX INFORMATION FROM PRODUCT ───────────────────────────────────
        tax_rate = 0.0
        tax_type = "ZERO RATED"
        tax_display = ""
        
        if product_id:
            try:
                from models.product import get_product_by_id
                prod = get_product_by_id(product_id)
                if prod:
                    tax_rate = prod.get("tax_rate", 0.0)
                    tax_type = prod.get("tax_type", "ZERO RATED")
                    if tax_rate > 0:
                        tax_display = f"VAT {tax_rate}%"
                    else:
                        tax_display = "ZERO RATED"
                    print(f"[AddProduct] {name} - Tax Rate: {tax_rate}%, Type: {tax_type}")
            except Exception as e:
                print(f"[AddProduct] Error getting tax: {e}")
        
        # If no tax info from product, try by part_no
        if tax_rate == 0 and part_no:
            try:
                from database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT tax_rate, tax_type FROM products WHERE part_no = ?", (part_no,))
                row = cursor.fetchone()
                conn.close()
                if row:
                    tax_rate = float(row[0] or 0)
                    tax_type = str(row[1] or "ZERO RATED")
                    if tax_rate > 0:
                        tax_display = f"VAT {tax_rate}%"
                    else:
                        tax_display = "ZERO RATED"
            except Exception as e:
                print(f"[AddProduct] Error getting tax from part_no: {e}")
        
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

                saved_part_no    = _cell_text(r, self.COL_PART_NO)
                saved_pid        = _cell_data(r, self.COL_PART_NO)
                saved_name       = _cell_text(r, self.COL_NAME)
                saved_price      = _cell_text(r, self.COL_PRICE)
                saved_uom        = _cell_text(r, self.COL_UOM)
                saved_disc       = _cell_text(r, self.COL_DISC)
                # Use existing tax or new tax display
                existing_tax = _cell_text(r, self.COL_TAX)
                saved_tax = existing_tax if existing_tax else tax_display

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
                    for col in range(self.INVOICE_COL_COUNT):
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

                # ── Write to destination row with tax info ─────────────────────
                self._block_signals = True
                self._init_row(dest, part_no=saved_part_no, details=saved_name,
                               qty=f"{new_qty:.4g}", amount=saved_price,
                               uom=saved_uom,
                               disc=saved_disc or "0.00", tax=saved_tax)
                item0 = self.invoice_table.item(dest, 0)
                if item0:
                    item0.setData(Qt.UserRole, saved_pid)
                    # Pharmacy meta survives row compaction: re-stamp if we had it
                    if pharmacy_meta:
                        item0.setData(self.PHARMACY_META_ROLE, pharmacy_meta)
                        try:
                            item0.setIcon(qta.icon("fa5s.prescription-bottle-alt",
                                                   color="#6a1b9a"))
                        except Exception:
                            pass
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
                # Move to next empty row and reopen inline search
                next_r = self._find_next_empty_row()
                if next_r != dest:
                    self._active_row = next_r
                    self._active_col = 0
                    self.invoice_table.setCurrentCell(next_r, 0)
                    self._highlight_active_row(next_r)
                    QTimer.singleShot(120, lambda r=next_r: self._open_inline_search(r, 0))
                return

        # ── New row with tax info ─────────────────────────────────────────────
        r = self._find_next_empty_row()
        self._block_signals = True
        # Fall back to the product's stock UOM when the caller didn't pass one.
        # Callers going through `_pick_product_uom_and_price` always set `uom`;
        # only legacy direct invocations (e.g. from pharmacy auto-dispense)
        # may leave it blank.
        _row_uom = uom
        if not _row_uom and product_id:
            try:
                from models.product import get_product_by_id
                _p = get_product_by_id(product_id)
                if _p:
                    _row_uom = str(_p.get("uom") or "").strip()
            except Exception:
                _row_uom = ""
        # Pharmacy: surface the dosage on the cart so the cashier can see
        # what was captured in the dispense popup — appended to the details
        # cell as "<name>  ·  <dosage>". Full metadata still lives in
        # PHARMACY_META_ROLE so save_sale keeps its fields intact.
        _display_name = name
        if pharmacy_meta and pharmacy_meta.get("dosage"):
            _display_name = f"{name}  ·  {str(pharmacy_meta['dosage']).strip()}"

        self._init_row(r, part_no=part_no, details=_display_name, qty="1",
                       amount=f"{price:.2f}",
                       uom=_row_uom,
                       disc="0.00", tax=tax_display)
        item = self.invoice_table.item(r, self.COL_PART_NO)
        if item:
            item.setData(Qt.UserRole, product_id)
            # Pharmacy: stamp the row with dosage/batch metadata for save path + Phase 7
            if pharmacy_meta:
                item.setData(self.PHARMACY_META_ROLE, pharmacy_meta)
                try:
                    item.setIcon(qta.icon("fa5s.prescription-bottle-alt",
                                          color="#6a1b9a"))
                except Exception:
                    pass
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
            self.parent_window._set_status(f"Added: {name} @ ${price:.2f} (Tax: {tax_display})")
        # Move cursor to the NEXT empty row and reopen inline search.
        next_r = self._find_next_empty_row()
        self._active_row = next_r
        self._active_col = 0
        self.invoice_table.setCurrentCell(next_r, 0)
        self._highlight_active_row(next_r)
        QTimer.singleShot(120, lambda r=next_r: self._open_inline_search(r, 0))
        
    def _collect_invoice_items(self) -> list[dict]:
        """Collect items from the invoice table with tax information"""
        items = []
        import re
        
        for r in range(self.invoice_table.rowCount()):
            try:
                qty = float(self.invoice_table.item(r, self.COL_QTY).text() or "0")
            except (ValueError, AttributeError):
                qty = 0.0
            if qty <= 0:
                continue
            try:
                part_no      = self.invoice_table.item(r, self.COL_PART_NO).text()
                # Name cell may be decorated with " · <dosage>" for pharmacy rows;
                # keep product_name canonical so sale_items / Frappe see the raw name.
                _name_cell   = self.invoice_table.item(r, self.COL_NAME).text()
                product_name = _name_cell.split("  ·  ", 1)[0].strip()
                price        = float(self.invoice_table.item(r, self.COL_PRICE).text() or "0")
                disc         = float((self.invoice_table.item(r, self.COL_DISC).text() or "0").replace('%', '').strip())
                tax_text     = self.invoice_table.item(r, self.COL_TAX).text() or ""
                total        = float(self.invoice_table.item(r, self.COL_TOTAL).text() or "0")
                product_id   = self.invoice_table.item(r, self.COL_PART_NO).data(Qt.UserRole)
                _uom_item    = self.invoice_table.item(r, self.COL_UOM)
                uom_cell     = _uom_item.text().strip() if _uom_item else ""
                
                # Parse tax rate from tax column
                tax_rate = 0.0
                tax_type = "ZERO RATED"
                
                # Try to extract numeric rate from tax column (e.g., "15.5", "15.5%", "VAT 15.5%")
                numbers = re.findall(r'(\d+\.?\d*)', tax_text)
                if numbers:
                    tax_rate = float(numbers[0])
                    if tax_rate > 0:
                        tax_type = "VAT"
                else:
                    # Check text-based tax types
                    if "VAT" in tax_text.upper():
                        tax_rate = 15.5  # Default VAT rate
                        tax_type = "VAT"
                    elif "ZERO" in tax_text.upper():
                        tax_rate = 0.0
                        tax_type = "ZERO RATED"
                    elif "EXEMPT" in tax_text.upper():
                        tax_rate = 0.0
                        tax_type = "EXEMPT"
                
                # If still no tax rate, try to get from product database
                if tax_rate == 0.0 and product_id:
                    try:
                        from models.product import get_product_by_id
                        prod = get_product_by_id(product_id)
                        if prod:
                            tax_rate = prod.get("tax_rate", 0.0)
                            tax_type = prod.get("tax_type", "ZERO RATED")
                            print(f"[Tax] Product {product_name} has tax_rate={tax_rate} from DB")
                    except Exception as e:
                        print(f"[Tax] Error getting product tax: {e}")
                
                print(f"[Tax] Item: {product_name} - Rate: {tax_rate}% - Type: {tax_type}")
                
            except (ValueError, AttributeError) as e:
                print(f"[Tax] Error collecting item: {e}")
                continue
            
            # Pharmacy meta (if stamped by _add_product_to_invoice)
            pharm = None
            try:
                cell0 = self.invoice_table.item(r, 0)
                if cell0:
                    pharm = cell0.data(self.PHARMACY_META_ROLE)
            except Exception:
                pharm = None

            # UOM: prefer the cart cell (reflects the user's UOM-picker choice);
            # fall back to the product row so legacy adds still carry the stock UOM.
            uom_val = uom_cell
            if not uom_val and product_id:
                try:
                    from models.product import get_product_by_id
                    _p = get_product_by_id(product_id)
                    if _p:
                        uom_val = str(_p.get("uom") or "").strip()
                except Exception as _e:
                    print(f"[UOM] Could not resolve uom for product_id={product_id}: {_e}")

            items.append({
                "part_no": part_no,
                "product_name": product_name,
                "qty": qty,
                "price": price,
                "discount": disc,
                "tax": tax_text,
                "total": total,
                "product_id": product_id,
                "tax_rate": tax_rate,      # ADD THIS - numeric rate
                "tax_type": tax_type,      # ADD THIS - text type
                "tax_amount": total * (tax_rate / 100) if tax_rate > 0 else 0,
                # Unit of measure — populated for both sale & quotation paths.
                # Empty string when unresolvable (legacy product rows).
                "uom":         uom_val,
                # Pharmacy round-trip fields (None if not a pharmacy row)
                "is_pharmacy": bool(pharm.get("is_pharmacy")) if pharm else False,
                "dosage":      pharm.get("dosage") if pharm else None,
                "batch_no":    pharm.get("batch_no") if pharm else None,
                "expiry_date": pharm.get("expiry_date") if pharm else None,
            })

        print(f"[Tax] Total items collected: {len(items)}")
        return items

    def _save_sale(self):
        items = self._collect_invoice_items()
        if not items:
            QMessageBox.warning(self, "Empty Invoice", "Add items before saving.")
            return
        try:
            total = float(self._lbl_total.text() or "0")
        except ValueError:
            total = 0.0
        try:
            from models.sale import create_sale
            from models.shift import get_active_shift
            
            cashier_id   = self.user.get("id") if isinstance(self.user, dict) else None
            cashier_name = self.user.get("username", "") if isinstance(self.user, dict) else ""
            
            # Get active shift ID
            active_shift = get_active_shift()
            shift_id = active_shift.get("id") if active_shift else None
            
            # Calculate subtotal and total VAT
            subtotal = sum(item.get("total", 0) for item in items)
            total_vat = sum(item.get("tax_amount", 0) for item in items)
            discount_pct = getattr(self, "current_discount_percent", 0.0)
            discount_amt = subtotal * (discount_pct / 100.0) if discount_pct > 0 else 0.0
            
            sale = create_sale(
                items=items,
                total=total,
                tendered=total,
                method="CASH",
                cashier_id=cashier_id,
                cashier_name=cashier_name,
                customer_name=self._selected_customer.get("customer_name", "") if self._selected_customer else "",
                customer_contact=self._selected_customer.get("custom_telephone_number", "") if self._selected_customer else "",
                change_amount=0.0,
                discount_percent=discount_pct,
                discount_amount=discount_amt,
                subtotal=subtotal,
                total_vat=total_vat,
                shift_id=shift_id,
            )
            self._update_prev_txn_display(paid=total, change=0.0, invoice_no=sale.get("invoice_no", ""))
            if self.parent_window:
                self.parent_window._set_status(f"Sale #{sale['number']} saved — ${total:.2f}")
            # ── Increment offline sync counter ──────────────────────────────
            try:
                from services.printing_service import printing_service as _ps
                _ps.get_next_sync_number()
            except Exception:
                pass
            # ── Badge refresh: immediately after DB write, before UI reset ──
            self._refresh_unsynced_badge()
            self._new_sale(confirm=False)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", _friendly_db_error(e))
        
    
    # =========================================================================
    # OPEN SHIFT REPRINT DIALOG
    # =========================================================================
    def _open_shift_reprint(self):
        """Open the shift reconciliation reprint dialog."""
        try:
            from views.dialogs.shift_reprint_dialog import show_shift_reprint
            show_shift_reprint(self)
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"Could not open reprint dialog: {str(e)}")

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
        self.current_discount_percent = 0.0   # ← Discount state
        self._quotation_mode = False           # ← Quotation mode flag
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
        self._quotation_mode = False           # ← Quotation mode flag
        self._build_ui()
        QTimer.singleShot(0, self._ensure_default_customer)

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
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet(f"background-color: {WHITE}; border-bottom: 2px solid {BORDER};")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(6)

        # ── Brand + Logo ──────────────────────────────────────────────────────
        logo = QLabel("Havano POS System")
        logo.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {NAVY}; background: transparent;")
        layout.addWidget(logo)
        layout.addSpacing(12)

        # ── Uniform nav button spec ──
        NAV_H  = 30
        NAV_FS = 11   
        NAV_R  = 4    
        NAV_PX = 12   

        def _nav_style(bg, hov, extra=""):
            return (
                f"QPushButton {{ background-color:{bg}; color:{WHITE}; border:none; "
                f"border-radius:{NAV_R}px; font-size:{NAV_FS}px; font-weight:bold; "
                f"padding:0 {NAV_PX}px; {extra}}} "
                f"QPushButton:hover {{ background-color:{hov}; }} "
                f"QPushButton:pressed {{ background-color:{NAVY_3}; color:{WHITE}; }}"
            )

        # ── Helper: uniform nav button ────────────────────────────────────────
        def _nb(text, handler, color=NAVY_2, hov=NAVY_3, min_w=None):
            b = QPushButton(text)
            b.setFixedHeight(NAV_H)
            b.setCursor(Qt.PointingHandCursor)
            if min_w:
                b.setMinimumWidth(min_w)
            b.setStyleSheet(_nav_style(color, hov))
            b.clicked.connect(handler)
            return b

        # ── Sales button ──────────────────────────────────────────────────────
        sales_menu_btn = HoverMenuButton("Sales ▾", color=ACCENT, hov=ACCENT_H, height=NAV_H)
        sales_menu_btn.addItem("Sales Invoice List", self._open_sales_list)
        sales_menu_btn.addItem("Sales Orders",        self._open_sales_order_list)
        sales_menu_btn.addSeparator()
        sales_menu_btn.addItem("Payments", self._open_customer_payment_entry)
        sales_menu_btn.addSeparator()
        sales_menu_btn.addItem("Reprint Shift Reconciliation", self._open_shift_reprint)
        layout.addWidget(sales_menu_btn)
        

        # ── Admin Check ───────────────────────────────────────────────────────
        is_admin_user = False
        try:
            from models.user import is_admin
            if self.user and is_admin(self.user):
                is_admin_user = True
        except Exception:
            pass

        # ── Inventory button (admin only) ─────────────────────────────────────
        if is_admin_user:
            inv_menu_btn = HoverMenuButton("Inventory ▾", color=NAVY_2, hov=NAVY_3, height=NAV_H)
            inv_menu_btn.addItem("Stock on Hand",   self._open_inventory_dashboard)
            layout.addWidget(inv_menu_btn)

        # ── Maintenance button (admin only) ───────────────────────────────────
        if is_admin_user:
            maint_btn = HoverMenuButton("Maintenance ▾", color=NAVY_2, hov=NAVY_3, height=NAV_H)

            def _sd(cls_name, *args, **kwargs):
                def _handler():
                    try:
                        import importlib
                        sd = importlib.import_module("views.dialogs.settings_dialog")
                        cls = getattr(sd, cls_name)
                        p = self.parent_window or self
                        if cls_name == "ManageUsersDialog":
                            cls(p, current_user=self.user).exec()
                        else:
                            cls(p).exec()
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Could not open {cls_name}:\n{e}")
                return _handler

            maint_btn.addItem("Users",              _sd("ManageUsersDialog"))
            maint_btn.addSeparator()
            maint_btn.addItem("Company Defaults",   self._open_company_defaults_nav)
            maint_btn.addItem("POS Rules",          _sd("POSRulesDialog"))
            maint_btn.addItem("Hardware Settings",  _sd("HardwareDialog"))
            maint_btn.addItem("Payment Modes",      self._open_payment_modes_dialog)
            maint_btn.addItem("Advanced Printing",  self._open_adv_printing_nav)
            maint_btn.addSeparator()
            maint_btn.addItem("Sync Queue",         self._open_sales_list)
            maint_btn.addItem("Stock File",         self._open_stock_file)
            maint_btn.addSeparator()
            maint_btn.addItem("Tax Settings",       lambda: coming_soon(self, "Tax Settings"))
            maint_btn.addItem("Printer Setup",      lambda: coming_soon(self, "Printer Setup"))
            maint_btn.addItem("Backup",             lambda: coming_soon(self, "Backup"))
            layout.addWidget(maint_btn)
            layout.addSpacing(10)

        # ── Customer selector ─────────────────────────────────────────────────
        self._cust_btn = QPushButton("Customer")
        self._cust_btn.setIcon(qta.icon("fa5s.user", color="white"))
        self._cust_btn.setFixedHeight(NAV_H)
        self._cust_btn.setMaximumWidth(170)
        self._cust_btn.setCursor(Qt.PointingHandCursor)
        self._cust_btn.setStyleSheet(_nav_style(NAVY_2, NAVY_3))
        self._cust_btn.clicked.connect(self._select_customer)
        layout.addWidget(self._cust_btn)
        layout.addSpacing(4)

        # ── Sync Badges ───────────────────────────────────────────────────────
        def _make_badge(label, tip, handler):
            b = QPushButton(label)
            b.setFixedHeight(NAV_H)
            b.setMinimumWidth(50)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(_nav_style(NAVY_2, NAVY_3))
            b.setToolTip(tip)
            b.clicked.connect(handler)
            return b

        # ── Single unified Q-badge (replaces SI / CN / SO individual badges) ──
        self._q_badge = _make_badge("Q : 0", "All records synced", lambda: UnsyncedPopup("", self).exec())
        self._q_badge.setStyleSheet(_nav_style(SUCCESS, SUCCESS_H))
        layout.addWidget(self._q_badge)
        layout.addSpacing(2)

        # ── Z-badge (fiscalization errors) ────────────────────────────────────
        self._z_badge = _make_badge("Z : 0", "All sales fiscalized", lambda: self._show_unfiscalized_popup())
        self._z_badge.setStyleSheet(_nav_style(SUCCESS, SUCCESS_H))
        layout.addWidget(self._z_badge)
        layout.addSpacing(2)

        # Keep hidden references so legacy code that calls setVisible() on the
        # old badges doesn't crash at runtime.
        self._all_synced_badge = self._q_badge   # backward compat alias
        self._si_badge = self._q_badge
        self._cn_badge = self._q_badge
        self._so_badge = self._q_badge

        # ── Laybye Switcher ───────────────────────────────────────────────────
        self.laybye_btn = QPushButton("Laybye")
        self.laybye_btn.setCheckable(True)
        self.laybye_btn.setFixedHeight(NAV_H)
        self.laybye_btn.setMinimumWidth(110)
        self.laybye_btn.setCursor(Qt.PointingHandCursor)

        self.laybye_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AMBER}; 
                color: {WHITE}; 
                border: none;
                border-radius: {NAV_R}px; 
                font-size: {NAV_FS}px; 
                font-weight: bold;
                text-align: center;
                padding: 0px 5px; 
                outline: none;
            }}
            QPushButton:hover {{ 
                background-color: {ORANGE}; 
            }}
            /* Matches the standard nav button behavior for the click action */
            QPushButton:pressed {{ 
                background-color: {NAVY_3}; 
                color: {WHITE};
            }}
            /* Ensures that once 'Checked', it returns to the AMBER color scheme */
            QPushButton:checked {{ 
                background-color: {AMBER}; 
            }}
            QPushButton:checked:hover {{ 
                background-color: {ORANGE}; 
            }}
        """)

        self.laybye_btn.setToolTip("Toggle Laybye Mode")
        self.laybye_btn.clicked.connect(self._on_laybye)
        layout.addWidget(self.laybye_btn)
        layout.addSpacing(4)

        # ── Payments button ───────────────────────────────────────────────────
        layout.addWidget(_nb("Payments", self._open_customer_payment_entry, color=ACCENT, hov=ACCENT_H))
        layout.addSpacing(4)
        

        # ── Quotation button ──────────────────────────────────────────────────
        quote_btn = _nb("Quote", self._on_quotation, color=NAVY_3, hov=NAVY_2)
        quote_btn.setToolTip("Create a Quotation")
        layout.addWidget(quote_btn)
        layout.addSpacing(4)
        
        
        
        
# ── Options dropdown ──────────────────────────────────────────────────────
        options_menu_btn = HoverMenuButton("Options ▾", color=NAVY_2, hov=NAVY_3, height=NAV_H)
        options_menu_btn.addItem("Create Credit Note  (Return)", self._open_credit_note_dialog)
        # options_menu_btn.addItem("Save / Print Quotation",       self._save_quotation)
        options_menu_btn.addItem("Save / Print Quotation", self._save_quotation)

        
        # options_menu_btn.addItem("Manage Quotations",            self._open_quotation_manager)
        # options_menu_btn.addItem("Reprint Invoice",              self._reprint_by_invoice_no)
        options_menu_btn.addSeparator(),
        
        options_menu_btn.addItem("Sync Products from Server",    self._do_nav_sync_products)
        layout.addWidget(options_menu_btn)
        layout.addSpacing(4)
        

        # ── Return mode indicator ─────────────────────────────────────────────
        self._return_btn = _nb("↩   Return", self._process_return, color=DANGER, hov=DANGER_H)
        self._return_btn.setVisible(False)
        layout.addWidget(self._return_btn)
        layout.addSpacing(4)

        # Refresh Sync Badges — timer is already started in the first _build_nav;
        # do NOT create a second one here or counts will double.
        if not getattr(self, "_unsynced_timer", None):
            QTimer.singleShot(500, self._refresh_unsynced_badge)
            self._unsynced_timer = QTimer(self)
            self._unsynced_timer.setInterval(3000)
            self._unsynced_timer.timeout.connect(self._refresh_unsynced_badge)
            self._unsynced_timer.start()

        layout.addStretch(1)

        # ── Dashboard button (admin only) ─────────────────────────────────────
        if is_admin_user:
            dash_btn = _nb("Dashboard", self.parent_window.switch_to_dashboard if self.parent_window else lambda: None, color=ACCENT, hov=ACCENT_H)
            layout.addWidget(dash_btn)
            layout.addSpacing(4)

        # ── Logout ────────────────────────────────────────────────────────────
        logout = QPushButton("Logout")
        logout.setFixedHeight(NAV_H)
        logout.setCursor(Qt.PointingHandCursor)
        logout.setStyleSheet(_nav_style(DANGER, DANGER_H))
        if self.parent_window:
            logout.clicked.connect(self.parent_window._logout)
        layout.addWidget(logout)

        return bar
    
    def _show_options_menu(self):
        """Opens a full-size Options dialog with all available actions."""
        dlg = OptionsDialog(self, pos_view=self)
        dlg.exec()
    
    def _open_inventory_dashboard(self):
        """Open dashboard and switch to Stock on Hand tab."""
        if self.parent_window:
            # Switch to dashboard
            self.parent_window.switch_to_dashboard()
            # Access the dashboard widget and switch to stock tab
            if hasattr(self.parent_window, '_dashboard'):
                dashboard = self.parent_window._dashboard
                if hasattr(dashboard, '_tabs'):
                    # Find and select the Stock tab (index 1 in AdminDashboard)
                    dashboard._tabs.setCurrentIndex(1)
                    # Optionally refresh stock data
                    if hasattr(dashboard, '_load_stock_data'):
                        dashboard._load_stock_data()
                    # Set status message
                    self.parent_window._set_status("Inventory Dashboard - Stock on Hand")

    def _open_inventory_list_nav(self):
        """Open inventory list from nav-bar hover menu."""
        try:
            from views.dialogs.inventory_list_dialog import InventoryListDialog
            InventoryListDialog(self.parent_window or self).exec()
        except NameError as e:
            QMessageBox.warning(self, "Import Error", f"inventory_list_dialog.py is missing an import:\n{e}\n\nAdd the missing import to that file.")
        except ImportError:
            coming_soon(self, "Inventory List")

    def _open_item_groups_nav(self):
        """Open item groups dialog from nav-bar hover menu."""
        try:
            from views.dialogs.item_group_dialog import ItemGroupDialog
            ItemGroupDialog(self.parent_window or self).exec()
        except ImportError:
            coming_soon(self, "Item Groups")

    def _open_company_defaults_nav(self):
        """Open company defaults from nav-bar hover menu — full screen."""
        try:
            from views.pages.company_defaults_page import CompanyDefaultsPage
            dlg = QDialog(self.parent_window or self)
            dlg.setWindowTitle("Company Defaults")
            dlg.setStyleSheet(f"QDialog {{ background: {OFF_WHITE}; }}")
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(CompanyDefaultsPage())
            dlg.setWindowState(Qt.WindowMaximized)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open Company Defaults:\n{e}")

    def _open_adv_printing_nav(self):
        """Open Advanced Printing from settings_dialog."""
        try:
            from views.dialogs.settings_dialog import SettingsDialog as _SD
            # AdvanceSettingsDialog may live in settings_dialog or advance_settings_dialog
            try:
                from views.dialogs.advance_settings_dialog import AdvanceSettingsDialog as _ASD
                _ASD(self.parent_window or self).exec()
            except ImportError:
                _SD(self.parent_window or self).exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open Advanced Printing:\n{e}")

    # =========================================================================
    # LEFT PANEL
    # =========================================================================
    def _build_left_panel(self):
        panel = QWidget(); panel.setStyleSheet(f"background-color: {OFF_WHITE};")
        # 12 rows × 32 px + 32 header + 42 footer = 458 px min before scrolling
        panel.setMinimumHeight(290)
        layout = QVBoxLayout(panel)
        layout.setSpacing(0); layout.setContentsMargins(0, 0, 0, 0)
        # Inline customer search strip (applies in all modes; pharmacy or not)
        layout.addWidget(self._build_customer_search_strip())
        layout.addWidget(self._build_invoice_table(), 1)
        layout.addWidget(self._build_invoice_footer())
        return panel

    # =========================================================================
    # INLINE CUSTOMER SEARCH STRIP (pharmacy phase — GLOBAL, not pharmacy-only)
    # =========================================================================
    def _build_customer_search_strip(self) -> QWidget:
        """Inline customer search row above the cart — attach/replace active customer."""
        wrap = QWidget()
        wrap.setFixedHeight(46)
        wrap.setStyleSheet(f"background: {OFF_WHITE}; border-bottom: 1px solid {BORDER};")
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)

        # Leading icon
        icon_lbl = QLabel()
        try:
            icon_lbl.setPixmap(qta.icon("fa5s.user", color=NAVY).pixmap(14, 14))
        except Exception:
            icon_lbl.setText("👤")
        icon_lbl.setStyleSheet("background: transparent;")
        lay.addWidget(icon_lbl)

        # Search input
        self._cust_search_edit = QLineEdit()
        self._cust_search_edit.setPlaceholderText("Search customer by name or phone...")
        self._cust_search_edit.setClearButtonEnabled(True)
        try:
            self._cust_search_edit.addAction(
                qta.icon("fa5s.search", color=MUTED),
                QLineEdit.LeadingPosition,
            )
        except Exception:
            pass
        self._cust_search_edit.setStyleSheet(f"""
            QLineEdit {{
                background: {WHITE}; color: {DARK_TEXT};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 4px 8px; font-size: 12px;
            }}
            QLineEdit:focus {{ border: 1.5px solid {ACCENT}; }}
        """)
        self._cust_search_edit.textEdited.connect(self._on_cust_search_edited)
        self._cust_search_edit.returnPressed.connect(self._on_cust_search_enter)
        lay.addWidget(self._cust_search_edit, 1)

        # Completer (dropdown suggestions) — updated on textEdited
        self._cust_completer = QCompleter([], self._cust_search_edit)
        self._cust_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._cust_completer.setFilterMode(Qt.MatchContains)
        self._cust_completer.activated.connect(self._on_cust_completer_activated)
        self._cust_search_edit.setCompleter(self._cust_completer)
        self._cust_completer_cache: dict[str, dict] = {}

        # "+" Add-new button
        add_btn = QPushButton()
        try:
            add_btn.setIcon(qta.icon("fa5s.plus", color="white"))
        except Exception:
            add_btn.setText("+")
        add_btn.setFixedSize(32, 30)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setToolTip("Add new customer")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: {WHITE}; border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{ background: {ACCENT_H}; }}
        """)
        add_btn.clicked.connect(self._inline_add_new_customer)
        lay.addWidget(add_btn)

        # Selected customer label
        self._cust_inline_label = QLabel("No customer")
        self._cust_inline_label.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; background: transparent; padding: 0 6px;"
        )
        self._cust_inline_label.setMinimumWidth(160)
        self._cust_inline_label.setMaximumWidth(260)
        lay.addWidget(self._cust_inline_label)

        return wrap

    def _on_cust_search_edited(self, text: str):
        """Update completer suggestions as user types (name or phone)."""
        query = (text or "").strip()
        if len(query) < 2:
            return
        try:
            from models.customer import search_customers
            results = search_customers(query) or []
        except Exception as e:
            print(f"[CustSearch] search error: {e}")
            results = []
        labels = []
        cache: dict[str, dict] = {}
        for c in results[:25]:
            nm = c.get("customer_name", "") or ""
            ph = c.get("custom_telephone_number", "") or ""
            label = f"{nm}  —  {ph}" if ph else nm
            labels.append(label)
            cache[label] = c
        self._cust_completer_cache = cache
        # Rebuild completer model
        from PySide6.QtCore import QStringListModel
        self._cust_completer.setModel(QStringListModel(labels))

    def _on_cust_completer_activated(self, label: str):
        """Pick a suggested customer — attach as active customer."""
        cust = self._cust_completer_cache.get(label)
        if not cust:
            return
        self._attach_inline_customer(cust)

    def _on_cust_search_enter(self):
        """Enter with no selection — pick the top match if available."""
        text = (self._cust_search_edit.text() or "").strip()
        if not text:
            return
        # Prefer an exact match in cache, else the first entry
        exact = next((v for k, v in self._cust_completer_cache.items() if k.lower() == text.lower()), None)
        if exact:
            self._attach_inline_customer(exact)
            return
        if self._cust_completer_cache:
            first = next(iter(self._cust_completer_cache.values()))
            self._attach_inline_customer(first)

    def _attach_inline_customer(self, cust: dict):
        """
        Called when the cashier picks a customer via the inline search
        completer. Delegates to `_apply_selected_customer` so the
        nav-bar button, inline label, cart-clear prompt, status bar, AND
        the product-grid re-price all happen in one place. Keeping this
        alias so legacy callers (QuickAddCustomerDialog signal etc.)
        don't have to change.
        """
        self._apply_selected_customer(cust)

    def _inline_add_new_customer(self):
        """Open the existing QuickAddCustomerDialog and auto-attach on success."""
        try:
            from views.dialogs.customer_dialog import QuickAddCustomerDialog
        except Exception as e:
            QMessageBox.warning(self, "Error",
                                f"Customer dialog not available:\n{e}")
            return
        dlg = QuickAddCustomerDialog(self)
        try:
            dlg.customer_created.connect(self._attach_inline_customer)
        except Exception:
            pass
        dlg.exec()

    # ── Invoice table ─────────────────────────────────────────────────────────
    # Column indices — change here only, every lookup uses these constants.
    # UOM sits next to Qty, between Qty and Disc.
    COL_PART_NO  = 0
    COL_NAME     = 1
    COL_PRICE    = 2
    COL_QTY      = 3
    COL_UOM      = 4
    COL_DISC     = 5
    COL_TAX      = 6
    COL_TOTAL    = 7
    INVOICE_COL_COUNT = 8

    # ── Invoice column labels — edit here to rename ──────────────────────────
    INVOICE_COL_LABELS = ["Item No.", "Item Details", "Amount $", "Qty", "UOM", "Disc", "TAX", "Total $"]

    def _build_invoice_table(self):
        self.invoice_table = QTableWidget()
        self.invoice_table.setColumnCount(self.INVOICE_COL_COUNT)
        self.invoice_table.setHorizontalHeaderLabels(self.INVOICE_COL_LABELS)
        hh = self.invoice_table.horizontalHeader()
        hh.setSectionResizeMode(self.COL_PART_NO, QHeaderView.Fixed);  self.invoice_table.setColumnWidth(self.COL_PART_NO, 95)
        hh.setSectionResizeMode(self.COL_NAME,    QHeaderView.Stretch)
        hh.setSectionResizeMode(self.COL_PRICE,   QHeaderView.Fixed);  self.invoice_table.setColumnWidth(self.COL_PRICE, 90)
        hh.setSectionResizeMode(self.COL_QTY,     QHeaderView.Fixed);  self.invoice_table.setColumnWidth(self.COL_QTY, 90)
        hh.setSectionResizeMode(self.COL_UOM,     QHeaderView.Fixed);  self.invoice_table.setColumnWidth(self.COL_UOM, 60)
        hh.setSectionResizeMode(self.COL_DISC,    QHeaderView.Fixed);  self.invoice_table.setColumnWidth(self.COL_DISC, 65)
        hh.setSectionResizeMode(self.COL_TAX,     QHeaderView.Fixed);  self.invoice_table.setColumnWidth(self.COL_TAX, 45)
        hh.setSectionResizeMode(self.COL_TOTAL,   QHeaderView.Fixed);  self.invoice_table.setColumnWidth(self.COL_TOTAL, 90)

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
                  amount="", uom="", disc="", tax="", total=""):
        # vals order must match COL_* constants (Part, Name, Price, Qty, UOM, Disc, TAX, Total)
        vals = [part_no, details, amount, qty, uom, disc, tax, total]
        for c, val in enumerate(vals):
            item = QTableWidgetItem(str(val))
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter if c == self.COL_NAME else Qt.AlignCenter)
            if c in (self.COL_PRICE, self.COL_TOTAL):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setForeground(QColor(ACCENT) if c == self.COL_TOTAL else QColor(NAVY))
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
            for c in range(self.INVOICE_COL_COUNT):
                item = self.invoice_table.item(r, c)
                if not item:
                    continue
                if is_active:
                    item.setBackground(ACTIVE_BG)
                    item.setForeground(ACTIVE_FG if c != self.COL_TOTAL else QColor(ACCENT))
                else:
                    bg = FILLED_BG if r % 2 == 0 else ALT_BG
                    item.setBackground(bg)
                    item.setForeground(FILLED_FG if c != self.COL_TOTAL else QColor(ACCENT))

    # ── Calculation engine ────────────────────────────────────────────────────
    def _recalc_row(self, r):
        if self._block_signals:
            return
        try:
            amount      = float(self.invoice_table.item(r, self.COL_PRICE).text() or "0")
            qty         = float(self.invoice_table.item(r, self.COL_QTY).text() or "0")
            disc_amount = float((self.invoice_table.item(r, self.COL_DISC).text() or "0").replace('%', '').strip())
            total       = max(qty * amount - disc_amount, 0.0)
        except (ValueError, AttributeError):
            total = 0.0
        self._block_signals = True
        item = self.invoice_table.item(r, self.COL_TOTAL)
        if item:
            # Only show a value when the row has an actual product entry
            details = self.invoice_table.item(r, self.COL_NAME)
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
                subtotal  += float(self.invoice_table.item(r, self.COL_TOTAL).text() or "0")
                qty_total += float(self.invoice_table.item(r, self.COL_QTY).text() or "0")
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
        # Pharmacy lock: cashiers cannot replace/edit the product on a pharmacy row
        if self._is_pharmacy_row_locked(row):
            self._notify_pharmacy_locked()
            return

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
            picked = self._pick_product_uom_and_price(product)
            if picked is None:
                return   # cancelled / blocked
            product, uom, price = picked
            self._add_product_to_invoice(
                name=product["name"],
                price=price,
                part_no=product.get("part_no", ""),
                product_id=product.get("id"),
                uom=uom,
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
            # After OK — move to the next empty row so user can continue scanning
            next_row = self._find_next_empty_row()
            self._ensure_rows(next_row + 1)
            self._highlight_active_row(next_row)
            self.invoice_table.setCurrentCell(next_row, 0)
            self._active_row = next_row
            self._active_col = 0
            self._open_inline_search(next_row, 0)

    def _inline_commit_product(self, product):
        self._close_inline_search()
        if not product:
            return
        picked = self._pick_product_uom_and_price(product)
        if picked is None:
            return   # cancelled / blocked
        product, uom, price = picked
        self._add_product_to_invoice(
            name=product["name"],
            price=price,
            part_no=product.get("part_no", ""),
            product_id=product.get("id"),
            stock=product.get("stock"),
            uom=uom,
        )

    def _fill_row_from_product(self, row, product):
        """Write a product into a specific row — only used when the product is
        NOT already on the invoice (called from _add_product_to_invoice new-row path)."""
        self._block_signals = True
        self._init_row(row, part_no=product["part_no"], details=product["name"],
                       qty="1", amount=f"{product['price']:.2f}",
                       uom=(product.get("uom") or ""),
                       disc="0.00", tax="")
        item0 = self.invoice_table.item(row, self.COL_PART_NO)
        if item0: item0.setData(Qt.UserRole, product.get("id"))
        self._block_signals = False
        self._recalc_row(row)
        self.invoice_table.setCurrentCell(row, self.COL_QTY)
        self._active_row      = row
        self._active_col      = self.COL_QTY
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

        # ── Global Up/Down → cart navigation ─────────────────────────────────
        # When the cashier is on the POS screen but focus is on a button / the
        # product grid / anywhere that isn't a text input, Up/Down should move
        # through the cart rows. The per-widget branches below still own the
        # specific behaviours (inline-search popup, table's own edit triggers).
        if event.type() == QEvent.KeyPress and getattr(self, "_global_cart_nav_ready", False):
            _k = event.key()
            if _k in (Qt.Key_Up, Qt.Key_Down):
                from PySide6.QtWidgets import QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox
                fw = QApplication.focusWidget()
                # Skip if the invoice_table or inline search already handle Up/Down
                # (their own branches below fire with the correct context).
                if fw is self.invoice_table or fw is getattr(self, "_inline_edit", None):
                    pass  # fall through to specific branches
                elif isinstance(fw, (QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox)):
                    pass  # let text inputs handle Up/Down themselves
                elif hasattr(self, "invoice_table") and self.invoice_table is not None:
                    delta = -1 if _k == Qt.Key_Up else 1
                    cur_r = getattr(self, "_active_row", 0)
                    cur_r = cur_r if cur_r >= 0 else 0
                    target = max(0, min(cur_r + delta, self.invoice_table.rowCount() - 1))
                    self._active_row = target
                    col = getattr(self, "_active_col", self.COL_PART_NO)
                    col = col if col >= 0 else self.COL_PART_NO
                    self.invoice_table.setCurrentCell(target, col)
                    self._highlight_active_row(target)
                    try:
                        self.invoice_table.scrollToItem(
                            self.invoice_table.item(target, col),
                            QAbstractItemView.EnsureVisible)
                    except Exception:
                        pass
                    self.invoice_table.setFocus()
                    return True

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

            # #36 Up arrow — move to row above.
            # Inline search only re-opens when the destination row is empty —
            # navigating across filled rows shouldn't spawn a search popup.
            if key == Qt.Key_Up:
                self._close_inline_search()
                target = max(0, self._active_row - 1)
                self._active_row = target
                self.invoice_table.setCurrentCell(target, self._active_col)
                self._highlight_active_row(target)
                self.invoice_table.scrollToItem(
                    self.invoice_table.item(target, self._active_col),
                    QAbstractItemView.EnsureVisible)
                if self._active_col in (self.COL_PART_NO, self.COL_NAME):
                    _n = self.invoice_table.item(target, self.COL_NAME)
                    if not (_n and _n.text().strip()):
                        self._open_inline_search(target, self._active_col)
                return True

            # #36 Down arrow — move to row below. Same skip-on-filled rule.
            if key == Qt.Key_Down:
                self._close_inline_search()
                target = min(self._active_row + 1, self.invoice_table.rowCount() - 1)
                self._active_row = target
                self.invoice_table.setCurrentCell(target, self._active_col)
                self._highlight_active_row(target)
                self.invoice_table.scrollToItem(
                    self.invoice_table.item(target, self._active_col),
                    QAbstractItemView.EnsureVisible)
                if self._active_col in (self.COL_PART_NO, self.COL_NAME):
                    _n = self.invoice_table.item(target, self.COL_NAME)
                    if not (_n and _n.text().strip()):
                        self._open_inline_search(target, self._active_col)
                return True

            # #36 Tab — cycle Code→Qty→Disc, wrap to next/prev row
            if key == Qt.Key_Tab:
                self._close_inline_search()
                _TAB = [self.COL_PART_NO, self.COL_QTY, self.COL_DISC]
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
            # To this:
            if key == Qt.Key_F6: self._open_quotation_manager(); return True
            if key == Qt.Key_F5:        self._open_payment();     return True
            if key == Qt.Key_F7:        self._open_sales_list();  return True
            if key == Qt.Key_Q:         UnsyncedPopup("PAY", self).exec(); return True
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
        if col == self.COL_TAX:
            item = self.invoice_table.item(row, col)
            if item: item.setText("" if item.text() == "T" else "T")
        elif col in (self.COL_PART_NO, self.COL_NAME):
            # Open inline search ONLY on empty rows. Clicking an existing
            # cart line should just move the active row (so Up/Down arrow
            # navigation keeps working) — the search popup stole focus before.
            name_item = self.invoice_table.item(row, self.COL_NAME)
            is_filled = bool(name_item and name_item.text().strip())
            if is_filled:
                self._close_inline_search()
                self._highlight_active_row(row)
                self.invoice_table.setFocus()
            else:
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
            picked = self._pick_product_uom_and_price(dlg.selected_product)
            if picked is None:
                return   # cancelled / blocked
            p, uom, price = picked
            self._block_signals = True
            self._init_row(row, part_no=p["part_no"], details=p["name"],
                           qty="1", amount=f"{price:.2f}",
                           uom=(uom or ""),
                           disc="0.00", tax="")
            item0 = self.invoice_table.item(row, self.COL_PART_NO)
            if item0: item0.setData(Qt.UserRole, p.get("id"))
            self._block_signals = False
            self._recalc_row(row)
            self.invoice_table.setCurrentCell(row, self.COL_QTY)
            self._active_row = row; self._active_col = self.COL_QTY; self._numpad_buffer = ""

    def _on_product_btn_clicked(self, product: dict):
        """Product tile tapped — debounce, then route through the shared
        template/variant/uom/price pipeline."""
        self._close_inline_search()

        import time as _time
        now  = _time.monotonic()
        last = getattr(self, "_last_grid_tap", 0)
        if now - last < 0.20:
            return
        self._last_grid_tap = now

        picked = self._pick_product_uom_and_price(product)
        if picked is None:
            return
        product, uom, price = picked

        self._add_product_to_invoice(
            name       = product.get("name", ""),
            price      = price,
            part_no    = product.get("part_no", ""),
            product_id = product.get("id"),
            stock      = product.get("stock"),
            uom        = uom,
        )

    def _pick_product_uom_and_price(
        self, product: dict,
    ) -> tuple[dict, str, float] | None:
        """
        Shared pre-add pipeline used by every "add this product to cart"
        path (grid tile tap, inline search commit, double-click cell
        picker, barcode lookup, etc.).

        Steps:
          1. If the tapped product is a *template*, open the variant
             picker and swap in the selected variant.
          2. Resolve a (uom, price) pair against the active customer's
             price list. `_resolve_price_for_product` opens
             `UomPickerDialog` when the item has more than one UOM row
             in that price list — so multi-UOM items still get the
             picker, just read from `item_prices` instead of the legacy
             `product_uom_prices` table.
          3. Returns (product_actually_used, uom, price), or None if the
             cashier cancelled or anything was rejected (no customer /
             no price list / zero-priced item — each case shows its own
             explainer before returning None).
        """
        if not product:
            return None

        if self._is_template_product(product):
            product = self._pick_variant(product) or {}
            if not product:
                return None  # user cancelled the variant picker

        picked = self._resolve_price_for_product(product)
        if picked is None:
            return None
        uom, price = picked
        return (product, uom, price)

    # -----------------------------------------------------------------------
    # Price-list resolution (task 1e)
    # -----------------------------------------------------------------------

    def _get_active_price_list(self) -> str | None:
        """Active customer's price list name (e.g. 'Standard Selling')."""
        cust = self._selected_customer or {}
        name = (cust.get("price_list_name") or "").strip()
        return name or None

    def _get_price_rows_for_list(self, part_no: str, price_list: str) -> list[dict]:
        """
        All (uom, price) rows for an item under the given price list, from the
        `item_prices` cache populated by product sync.
        """
        try:
            from database.db import get_connection
            conn = get_connection()
            cur  = conn.cursor()
            cur.execute("""
                SELECT uom, price FROM item_prices
                WHERE  part_no = ? AND price_list = ? AND price_type = 'selling'
                ORDER  BY CASE WHEN uom = 'nos' THEN 0 ELSE 1 END, price
            """, (part_no, price_list))
            rows = cur.fetchall(); conn.close()
            return [{"uom": r[0], "price": float(r[1] or 0)} for r in rows]
        except Exception as e:
            print(f"[pos] _get_price_rows_for_list failed ({part_no}/{price_list}): {e}")
            return []

    def _resolve_price_for_product(self, product: dict) -> tuple[str, float] | None:
        """
        Returns (uom, price) or None.

        None means "don't add to cart" — we've already shown an explanation to
        the cashier (no customer / no price list / item not priced / zero).
        """
        part_no  = product.get("part_no", "")
        base_uom = str(product.get("uom", "Nos") or "Nos")
        name     = product.get("name", part_no)

        if not self._selected_customer:
            self._warn_popup(
                "No customer selected",
                f"Pick a customer before adding <b>{name}</b> — the price "
                f"depends on the customer's price list.",
            )
            return None

        price_list = self._get_active_price_list()
        if not price_list:
            self._warn_popup(
                "No price list",
                f"The current customer has no default price list. "
                f"<b>{name}</b> can't be sold until one is assigned.",
            )
            return None

        rows = self._get_price_rows_for_list(part_no, price_list)
        if not rows:
            self._warn_popup(
                "Item not priced",
                f"<b>{name}</b> has no price in the <b>{price_list}</b> "
                f"price list. Add a rate on the server and re-sync.",
            )
            return None

        # Single UOM → use it directly.
        if len(rows) == 1:
            picked = rows[0]
        else:
            dlg = UomPickerDialog(
                product_name=name,
                uom_prices=rows,
                parent=self,
            )
            if dlg.exec() != QDialog.Accepted or not dlg.selected_uom:
                return None
            picked = {"uom": dlg.selected_uom, "price": dlg.selected_price}

        if float(picked["price"] or 0) <= 0:
            self._warn_popup(
                "Zero-priced item",
                f"<b>{name}</b> is priced at 0 in <b>{price_list}</b>. "
                f"The POS won't sell zero-priced items — update the price "
                f"on the server and re-sync.",
            )
            return None

        return (picked.get("uom") or base_uom, float(picked["price"]))

    # -----------------------------------------------------------------------
    # Variants (task 3c) — picker placeholder wired in the dialog step
    # -----------------------------------------------------------------------

    def _is_template_product(self, product: dict) -> bool:
        """True for items flagged as variant templates by the sync."""
        return bool(product.get("is_template") or product.get("has_variants"))

    def _pick_variant(self, template: dict) -> dict | None:
        """
        Open the variant picker (built in task 3c). Import kept local so a
        missing module doesn't break POS startup.
        """
        try:
            from views.dialogs.variant_picker_dialog import VariantPickerDialog
        except Exception as e:
            print(f"[pos] variant picker unavailable: {e}")
            self._warn_popup(
                "Variants not available",
                "This item has variants but the picker dialog is not "
                "installed yet. Please update the POS.",
            )
            return None

        dlg = VariantPickerDialog(template=template, parent=self)
        if dlg.exec() != QDialog.Accepted or not dlg.selected_variant:
            return None
        return dlg.selected_variant

    # =========================================================================
    # PERMISSION CHECK HELPER  (#23)
    # =========================================================================
    def _check_permission(self, flag: str, action_label: str = "This action") -> bool:
        """
        Return True if the current user has the given permission flag.
        If denied, prompts for an admin PIN — grants access if PIN is valid.
        Falls back to True for admins; defaults to True if column not present yet.
        """
        from PySide6.QtWidgets import QInputDialog
        user = self.user or {}
        # Admins always have all permissions
        if (user.get("role") or "").lower() == "admin":
            return True
        # Check flag — default True if not set (backward compat)
        allowed = bool(user.get(flag, True))
        if not allowed:
            # Offer admin PIN bypass
            pin, ok = QInputDialog.getText(
                self,
                "Authorization Required",
                f"<b>{action_label}</b> requires admin authorization.\n\nEnter Admin PIN:",
                __import__("PySide6.QtWidgets", fromlist=["QLineEdit"]).QLineEdit.Password,
            )
            if not ok or not pin:
                return False
            try:
                from models.user import authenticate_by_pin
                manager = authenticate_by_pin(pin)
                if manager and (manager.get("role") or "").lower() == "admin":
                    return True
            except Exception:
                pass
            self._warn_popup(
                "Access Denied",
                f"<b>{action_label}</b> — invalid admin PIN.",
                icon=QMessageBox.Critical,
            )
            return False
        return True

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
        # Return focus to the invoice table — only reopen inline search if NOT from grid
        QTimer.singleShot(0, lambda: (
            self.invoice_table.setFocus(),
            self._open_inline_search(self._active_row, 0)
        ))

    # =========================================================================
    # =========================================================================
    # SHIFT GUARD  — called before any transaction action
    # =========================================================================
    def _prompt_open_shift_if_missing(self):
        """Called once after MainWindow is shown. If no shift is active, goes
        straight into the open-shift flow so the cashier can start selling
        without chasing down a button. No-op when a shift is already open."""
        try:
            from models.shift import get_active_shift
            if get_active_shift():
                return
        except Exception:
            return
        try:
            self._open_shift_chooser()
        except Exception as e:
            print(f"[MainWindow] auto-prompt open-shift failed: {e}")

    def _require_active_shift(self) -> bool:
        """
        Returns True immediately when a shift is running (zero UI overhead).
        If no shift is active, opens the shift chooser directly — the old
        intermediate "No Shift Running" modal was one click of pure friction
        before every POS session. The caller still aborts (returns False)
        after the chooser closes; the next user action triggers a re-check.
        """
        try:
            from models.shift import get_active_shift
            if get_active_shift():
                return True
        except Exception:
            return True   # can't check → fail open, don't block

        # No active shift — jump straight into the chooser/open-shift dialog.
        try:
            self._open_shift_chooser()
        except Exception as e:
            print(f"[_require_active_shift] open-shift launch failed: {e}")
        # Re-check: if user completed opening a shift inside the chooser,
        # let the caller proceed instead of bouncing them out.
        try:
            from models.shift import get_active_shift
            return bool(get_active_shift())
        except Exception:
            return False

    # POS RULES HELPERS  (#3 #4 #7)
    # =========================================================================
    def _get_pos_rule(self, key: str, default: bool = True) -> bool:
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
        """#7 — fetch pricing rule discount and return adjusted price."""
        try:
            from services.frappe_api import get_pricing_rule_discount
            disc_pct = get_pricing_rule_discount(part_no) or 0.0
            if disc_pct > 0:
                return round(price * (1.0 - disc_pct / 100.0), 2)
        except Exception:
            pass
        return price

    
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
    # =========================================================================
    # RIGHT PANEL
    # =========================================================================
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

        # --- Top Row: Utility Buttons ---
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

        # ── DYNAMIC SHIFT LOGIC ──────────────────────────────────────────────
        from models.shift import get_active_shift

        def _refresh_shift_button():
            active_shift = None
            try:
                active_shift = get_active_shift()
            except:
                pass

            if active_shift:
                label = f"CLOSE\nSHIFT #{active_shift.get('shift_number', '')}"
                bg    = ORANGE
                hov   = AMBER
            else:
                label = "START\nSHIFT (F2)"
                bg    = SUCCESS
                hov   = SUCCESS_H

            self.btn_shift_action.setText(label)
            self.btn_shift_action.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg}; color: {WHITE}; border: none;
                    border-radius: 6px; font-size: 11px; font-weight: bold;
                }}
                QPushButton:hover   {{ background-color: {hov}; }}
                QPushButton:pressed {{ background-color: {NAVY_3}; }}
            """)

        def handle_shift():
            active_shift = None
            try:
                active_shift = get_active_shift()
            except:
                pass

            if active_shift:
                self._open_day_shift()       # Trigger Reconcile/Close
            else:
                self._open_shift_chooser()   # Trigger Start
            
            _refresh_shift_button()          # Instantly update state

        # Initialize the button with dummy values; _refresh_shift_button sets the real ones
        self.btn_shift_action = _top_btn("", SUCCESS, SUCCESS_H, handle_shift)
        top_row.addWidget(self.btn_shift_action)
        _refresh_shift_button() 
        # ─────────────────────────────────────────────────────────────────────

        top_row.addWidget(_top_btn("Reprint\nF3", NAVY, NAVY_2, self._reprint_by_invoice_no))
        top_row.addWidget(_top_btn("Discount\nF4 (%)", "#e67e22", "#d35400", self._on_discount_clicked))
        top_row.addWidget(_top_btn("Hold/\nRecall", NAVY_2, NAVY_3, self._open_hold_recall))

        # Options Button
        # REPLACE with this:
        qtn_btn = _top_btn("Quotation\nF6", NAVY_3, NAVY_2, self._open_quotation_manager)
        top_row.addWidget(qtn_btn)

        layout.addLayout(top_row)

        # --- Middle: Numpad ---
        layout.addWidget(self._build_numpad(), 1)

        # --- Bottom Row: New Transaction + PAY ---
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(4)

        # 1. New Transaction
        new_txn_btn = QPushButton("New\nTransaction")
        new_txn_btn.setFixedHeight(52)
        new_txn_btn.setFixedWidth(110)
        new_txn_btn.setCursor(Qt.PointingHandCursor)
        new_txn_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY_2}; color: {WHITE}; border: none;
                border-radius: 6px; font-size: 10px; font-weight: bold;
            }}
            QPushButton:hover   {{ background-color: {NAVY_3}; }}
            QPushButton:pressed {{ background-color: {NAVY}; }}
        """)
        new_txn_btn.clicked.connect(lambda: self._new_sale(confirm=False))
        bottom_row.addWidget(new_txn_btn)

        # 2. PAY Button
        self.btn_pay = QPushButton("PAY  F5")
        self.btn_pay.setFixedHeight(52)
        self.btn_pay.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_pay.setCursor(Qt.PointingHandCursor)
        self.btn_pay.setStyleSheet(f"""
            QPushButton {{
                background-color: {SUCCESS}; color: {WHITE}; border: none;
                border-radius: 6px; font-size: 17px; font-weight: bold; letter-spacing: 1px;
            }}
            QPushButton:hover   {{ background-color: {SUCCESS_H}; }}
            QPushButton:pressed {{ background-color: {NAVY_3}; }}
        """)
        self.btn_pay.clicked.connect(self._open_payment)
        # Pharmacy-aware label: PAY → FINALIZE QUOTE / DISPENSE when pharmacy mode on
        self._refresh_pay_button_label()
        bottom_row.addWidget(self.btn_pay)

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
        # Pharmacy lock: cashiers cannot modify qty/discount on pharmacy rows
        if self._active_col in (3, 4) and self._is_pharmacy_row_locked(self._active_row):
            self._notify_pharmacy_locked()
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
        # Pharmacy lock: cashiers cannot clear qty/discount on pharmacy rows
        if self._active_col in (3, 4) and self._is_pharmacy_row_locked(self._active_row):
            self._notify_pharmacy_locked()
            return
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

        # Pharmacy lock: cashiers cannot delete pharmacy rows
        if self._is_pharmacy_row_locked(row):
            self._notify_pharmacy_locked()
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
            for col in range(self.INVOICE_COL_COUNT):
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

        # Pharmacy lock: cashiers cannot change qty on pharmacy rows
        if self._is_pharmacy_row_locked(row):
            self._notify_pharmacy_locked()
            return

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
        
        # Add debounce timer for resize events
        self._resize_debounce_timer = QTimer()
        self._resize_debounce_timer.setSingleShot(True)
        self._resize_debounce_timer.timeout.connect(self._render_product_page_debounced)

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
        
        # Disable touch events to prevent glitching
        self._product_grid_widget.setAttribute(Qt.WA_AcceptTouchEvents, False)
        
        self._product_grid = QGridLayout(self._product_grid_widget)
        self._product_grid.setSpacing(2); self._product_grid.setContentsMargins(2, 2, 2, 2)
        outer.addWidget(self._product_grid_widget, 1)

        # REMOVED: resize event filter that was causing constant re-renders
        # Instead, override resizeEvent for debounced rendering
        self._product_grid_widget.resizeEvent = self._on_grid_resize

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
    
    def _on_grid_resize(self, event):
        """Debounced resize handler to prevent excessive re-renders"""
        # Restart the timer on each resize - only render after resizing stops
        self._resize_debounce_timer.start(100)  # 100ms debounce delay
        event.accept()
    
    def _render_product_page_debounced(self):
        """Debounced version that ensures layout is ready before rendering"""
        # Small delay to ensure layout is fully processed
        QTimer.singleShot(10, self._render_product_page)

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
        """
        Load products for a category, overlay the active customer's
        price-list prices, and stash variant metadata for tap-time lookup.
        """
        try:
            from models.product import get_products_by_category, get_all_products
            if name == "All":
                db_products = get_all_products()
            else:
                db_products = get_products_by_category(name)
                # If a category is empty, fall back to everything
                if not db_products:
                    db_products = get_all_products()

            # ── Overlay price-list prices ────────────────────────────────
            # Price comes *only* from the active customer's price list.
            # No fallback to products.price — the rule is: no price list
            # (or no rate in that list for this item) → show 0. Cart add
            # will also refuse zero-priced items. Matches the Android
            # client minus its "try Standard Selling" fallback (which the
            # user explicitly rejected — no silent price substitutions).
            active_list = self._get_active_price_list()
            price_map: dict[str, float] = {}
            if active_list:
                try:
                    from models.item_price import get_prices_map
                    price_map = get_prices_map(active_list)
                except Exception as e:
                    print(f"[grid] price map load failed ({active_list}): {e}")
                    price_map = {}
            else:
                print("[grid] ⚠ no active price list — grid will show 0.00 "
                      "everywhere (cart add will block)")

            # ── Build tuple list + per-part meta map for tap handler ─────
            tuples:  list[tuple] = []
            meta:    dict[str, dict] = {}
            hidden_no_price = 0
            for p in db_products:
                part_no = (p.get("part_no") or "").upper()
                # Single source of truth: price_map[part_no] or 0. No
                # fallback to products.price under any condition.
                price = float(price_map.get(part_no, 0) or 0)

                tuples.append((
                    p["name"], p["part_no"], price, p["id"],
                    p.get("image_path", ""),
                ))
                meta[part_no] = {
                    "is_template":  bool(p.get("is_template")),
                    "has_variants": bool(p.get("has_variants")),
                    "variant_of":   p.get("variant_of"),
                    "attributes":   p.get("attributes") or "",
                    "uom":          p.get("uom") or "Nos",
                    "stock":        p.get("stock"),
                }
                if active_list and price <= 0 and not p.get("is_template"):
                    hidden_no_price += 1

            self._current_products    = tuples
            self._product_meta_by_pn  = meta
            if hidden_no_price:
                print(f"[grid] {hidden_no_price} item(s) show 0 — no rate in "
                      f"price list '{active_list}'")
        except Exception as e:
            print(f"[grid] Error loading products: {e}")
            self._current_products   = []
            self._product_meta_by_pn = {}

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

        # Uniform fixed cell size — computed from widget dimensions with safe fallbacks
        GAP  = 2
        gw   = max(600, self._product_grid_widget.width())
        gh   = max(300, self._product_grid_widget.height())
        
        # Width same always; height = width (square) when images, fills rows otherwise
        cell_w = max(60, (gw - (COLS + 1) * GAP) // COLS)
        cell_h = max(40, min(cell_w, 100) if any_image else (gh - (ROWS + 1) * GAP) // ROWS)

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
                    # Pull variant metadata stashed by _load_category_products
                    # so the tap handler knows if this is a template tile.
                    _pn_key = (part_no or "").upper()
                    _meta   = (getattr(self, "_product_meta_by_pn", {}) or {}).get(_pn_key, {})
                    btn.clicked.connect(
                        lambda _, prod=dict(
                            name         = pname,
                            price        = price,
                            part_no      = part_no,
                            id           = product_id,
                            uom          = _meta.get("uom") or "Nos",
                            stock        = _meta.get("stock"),
                            is_template  = _meta.get("is_template", False),
                            has_variants = _meta.get("has_variants", False),
                            variant_of   = _meta.get("variant_of"),
                            attributes   = _meta.get("attributes") or "",
                        ): self._on_product_btn_clicked(prod)
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
        act_set    = menu.addAction(qta.icon("fa5s.image"), "Set Image…")
        act_remove = menu.addAction(qta.icon("fa5s.trash"), "Remove Image")
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
        from views.dialogs.shift_reconciliation_dialog import ShiftReconciliationDialog
        cashier_id = self.user.get("id") if isinstance(self.user, dict) else None
        dlg = ShiftReconciliationDialog(self, cashier_id=cashier_id)
        if dlg.exec() == QDialog.Accepted:
            if self.parent_window:
                self.parent_window._logout()

    def _open_shift_chooser(self):
        """Nav-bar SHIFT pill → opens ShiftChooserDialog."""
        try:
            from views.dialogs.day_shift_dialog import ShiftChooserDialog
        except ImportError:
            from views.dialogs.day_shift_dialog import DayShiftDialog as ShiftChooserDialog
        dlg = ShiftChooserDialog(self, user=self.user)
        dlg.exec()
        # Refresh pill after dialog closes
        self._refresh_shift_pill()

    def _refresh_shift_pill(self):
        """Update the shift status pill in the nav bar."""
        if not hasattr(self, "_shift_pill"):
            return
        try:
            from models.shift import get_active_shift
            s = get_active_shift()
            if s:
                self._shift_pill.setText(f"Shift #{s.get('shift_number', '')}")
                self._shift_pill.setIcon(qta.icon("fa5s.circle", color="#2ecc71"))
                self._shift_pill.setStyleSheet(f"""
                    QPushButton {{
                        background-color:{SUCCESS}; color:{WHITE}; border:none;
                        border-radius:15px; font-size:11px; font-weight:bold;
                        padding:0 12px; min-width:90px;
                    }}
                    QPushButton:hover {{ background-color:{SUCCESS_H}; }}
                    QPushButton:pressed {{ background-color:{NAVY_3}; color:{WHITE}; }}
                """)
                self._shift_pill.setToolTip("Shift is running — click to view details")
            else:
                self._shift_pill.setText("No Shift")
                self._shift_pill.setIcon(qta.icon("fa5s.circle", color="#333333"))
                self._shift_pill.setStyleSheet(f"""
                    QPushButton {{
                        background-color:{MUTED}; color:{WHITE}; border:none;
                        border-radius:15px; font-size:11px; font-weight:bold;
                        padding:0 12px; min-width:90px;
                    }}
                    QPushButton:hover {{ background-color:{NAVY_2}; }}
                    QPushButton:pressed {{ background-color:{NAVY_3}; color:{WHITE}; }}
                """)
                self._shift_pill.setToolTip("Click to start a shift")
        except Exception:
            pass

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
        """Nav-bar Customer button → full picker dialog."""
        dlg = CustomerSearchPopup(self)
        if dlg.exec() != QDialog.Accepted:
            return
        picked = dlg.selected_customer
        if picked:
            # Central setter keeps nav btn + inline label + price list +
            # grid re-price + cart-clear prompt all consistent.
            self._apply_selected_customer(picked)
        else:
            self._reset_customer_btn()

    def _open_sales_list(self):
        if _HAS_SALES_LIST:
            dlg = SalesListDialog(self)
            dlg.show()
        else:
            coming_soon(self, "Sales List — add views/dialogs/sales_list_dialog.py")

    def _open_sales_order_list(self):
        """Open the Sales Orders list (laybyes + any pulled SO from Frappe).
        Cashiers can convert fully-paid orders into invoices here."""
        try:
            from views.dialogs.sales_order_list_dialog import SalesOrderListDialog
            dlg = SalesOrderListDialog(self, user=getattr(self, "user", None))
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Sales Orders",
                f"Could not open Sales Orders list:\n{e}")

    def _open_payment_modes_dialog(self):
        """Maintenance → Payment Modes. Reorder MOPs, set exchange rates."""
        try:
            from views.dialogs.payment_modes_dialog import PaymentModesDialog
            PaymentModesDialog(self).exec()
        except Exception as e:
            QMessageBox.warning(self, "Payment Modes",
                f"Could not open Payment Modes dialog:\n{e}")
    
    

    def _print_receipt(self):
        items = self._collect_invoice_items()
        if not items:
            QMessageBox.information(self, "Nothing to Print", "Invoice is empty."); return
        try:
            total = float(self._lbl_total.text() or "0")
        except ValueError:
            total = 0.0

        from PySide6.QtCore import QDateTime, QDate
        now        = QDateTime.currentDateTime().toString("dd/MM/yyyy  hh:mm")
        cust_name  = self._selected_customer.get("customer_name", "") if self._selected_customer else "Walk-in"
        cust_phone = self._selected_customer.get("custom_telephone_number", "") if self._selected_customer else ""

        # Cashier / discount rules info
        current_user = (getattr(self, 'user', None)
                        or (getattr(self.parent_window, 'user', {}) if self.parent_window else {}))
        cashier_name    = current_user.get("full_name") or current_user.get("username", "")
        allow_disc      = current_user.get("allow_discount", False)
        max_disc_pct    = current_user.get("max_discount_percent", 0) or 0
        expiry_str      = current_user.get("discount_expiry_date", "") or ""

        # Check if discount authorisation is expired
        disc_expired = False
        expiry_display = ""
        if expiry_str:
            try:
                ed = QDate.fromString(expiry_str, "yyyy-MM-dd")
                if not ed.isValid():
                    ed = QDate.fromString(expiry_str, "dd/MM/yyyy")
                if ed.isValid():
                    expiry_display = ed.toString("dd/MM/yyyy")
                    if QDate.currentDate() > ed:
                        disc_expired = True
            except Exception:
                pass

        W = 40
        lines = ["=" * W, "          HAVANO POS", f"  {now}", f"  Customer:  {cust_name}"]
        if cust_phone:
            lines.append(f"  Phone:     {cust_phone}")
        if cashier_name:
            lines.append(f"  Cashier:   {cashier_name}")
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
        lines += [f"  TOTAL:             ${total:.2f}", "=" * W]

        # ── Discount Rules Section ────────────────────────────────────────────
        lines.append("  DISCOUNT AUTHORISATION")
        lines.append("-" * W)
        if not allow_disc:
            lines.append("  Discount: NOT PERMITTED for this cashier")
        elif disc_expired:
            lines.append(f"  Discount: EXPIRED ({expiry_display})")
            lines.append("  (Manager PIN required to override)")
        else:
            lines.append(f"  Cashier:  {cashier_name}")
            lines.append(f"  Allowed:  Up to {max_disc_pct}%")
            if expiry_display:
                lines.append(f"  Valid to: {expiry_display}")
            else:
                lines.append("  Valid to: No expiry set")
        lines += ["=" * W, "      Thank you for your purchase!", "=" * W]

        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
        dlg = QDialog(self); dlg.setWindowTitle("Receipt Preview  —  F3"); dlg.setMinimumSize(400, 560)
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
                receiptHeader   = co.get("receipt_header", ""),
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

   

    def _open_customer_payment_entry(self):
        """
        Open the customer payment entry dialog.
        Logic mirrored exactly from _on_laybye: 
        1. ALWAYS force customer selection (picker opens immediately).
        2. Update UI button styling and text (Success Green).
        3. Open Payment Dialog.
        """
        # 1. Force customer selection every time (mirrored from Lay-by flow)
        dlg_search = CustomerSearchPopup(self)
        if dlg_search.exec() != QDialog.Accepted or not dlg_search.selected_customer:
            QMessageBox.information(self, "Customer Required", 
                                    "Please select a customer before recording a payment.")
            return
        
        # Central setter — keeps nav btn / inline label / price list /
        # grid re-price / cart-clear prompt all consistent.
        self._apply_selected_customer(dlg_search.selected_customer)

        # 2. Proceed to Payment Entry
        customer = self._selected_customer
        
        
        dlg = CustomerPaymentDialog(self, customer=customer)
        if dlg.exec() == QDialog.Accepted:
            cname = customer.get("customer_name", "Customer")
            status_msg = f"Payment recorded for {cname}."
            
            if self.parent_window:
                if hasattr(self.parent_window, '_set_status'):
                    self.parent_window._set_status(status_msg)
                else:
                    self.parent_window.statusBar().showMessage(status_msg, 3000)

    def _open_hold_recall(self):
        HoldRecallDialog(self).exec()

    def _reset_customer_btn(self):
        self._selected_customer = None
        self._cust_btn.setText("Customer")
        self._cust_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY_2}; color: {MID}; border: 1px solid {NAVY_3};
                border-radius: 3px; font-size: 11px; padding: 0 8px;
            }}
            QPushButton:hover {{ background-color: {NAVY_3}; color: {WHITE}; }}
        """)
        # Re-apply the default customer so the button always shows one
        self._ensure_default_customer()

    def _refresh_customer_btn(self):
        """Update the customer button label without clearing the selection."""
        if self._selected_customer:
            name = self._selected_customer.get("customer_name", "")
            self._cust_btn.setText(f"{name[:22]}")
            self._cust_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ACCENT}; color: {WHITE};
                    border: none; border-radius: 3px;
                    font-size: 11px; font-weight: bold; padding: 0 8px;
                }}
                QPushButton:hover {{ background-color: {ACCENT_H}; }}
            """)
            # Keep inline strip label in sync (if the strip has been built)
            if hasattr(self, "_cust_inline_label") and self._cust_inline_label is not None:
                self._cust_inline_label.setText(f"Customer: {name}")
                self._cust_inline_label.setStyleSheet(
                    f"color: {NAVY}; font-size: 11px; font-weight: bold; "
                    f"background: transparent; padding: 0 6px;"
                )
        else:
            self._cust_btn.setText("Customer")
            self._cust_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {NAVY_2}; color: {MID}; border: 1px solid {NAVY_3};
                    border-radius: 3px; font-size: 11px; padding: 0 8px;
                }}
                QPushButton:hover {{ background-color: {NAVY_3}; color: {WHITE}; }}
            """)
            if hasattr(self, "_cust_inline_label") and self._cust_inline_label is not None:
                self._cust_inline_label.setText("No customer")
                self._cust_inline_label.setStyleSheet(
                    f"color: {MUTED}; font-size: 11px; background: transparent; padding: 0 6px;"
                )

    # =========================================================================
    # DEFAULT CUSTOMER — auto-selected on startup / payment
    # =========================================================================
    def _ensure_default_customer(self):
        """
        Pick the active customer at POS startup.

        Priority (matches Android):
          1. Customer whose name == login response's `default_customer`
             (saved to company_defaults.server_default_customer by
             services/auth_service.py — sourced from ERPNext's
             User Permission with is_default=1).
          2. The generic "Default" customer (created post-login by
             models/default_customer.create_default_customer).

        Once resolved, we also seed the active price list from the
        customer's default_price_list_id, so pricing applies on the very
        first cart add.

        Never overwrites a selection the cashier has already made.
        """
        # Cashier already picked someone — don't clobber it.
        if self._selected_customer:
            return

        try:
            from models.customer import get_customer_by_name, get_all_customers
        except Exception as e:
            print(f"[pos] _ensure_default_customer import failed: {e}")
            return

        picked = self._pick_login_default_customer(get_customer_by_name)
        if picked is None:
            picked = self._pick_generic_default_customer(get_all_customers)
        if picked is None:
            return   # nothing usable — bail silently

        self._apply_selected_customer(picked)

    # ---- helpers used by _ensure_default_customer -------------------------

    def _pick_login_default_customer(self, getter):
        """Resolve the login-bound default customer by name. None if missing."""
        try:
            from models.company_defaults import get_defaults
            name = (get_defaults() or {}).get("server_default_customer") or ""
            name = str(name).strip()
        except Exception:
            name = ""
        if not name:
            return None
        try:
            cust = getter(name)
            if cust:
                print(f"[pos] 🎯 Login default customer resolved: {name}")
                return cust
            print(f"[pos] ⚠ Login default customer '{name}' not in local DB")
        except Exception as e:
            print(f"[pos] login-default lookup failed ({name}): {e}")
        return None

    def _pick_generic_default_customer(self, getter_all):
        """Fallback: the generic 'Default' customer (created post-login)."""
        try:
            for c in (getter_all() or []):
                if (c.get("customer_name") or "").strip().lower() == "default":
                    return c
        except Exception as e:
            print(f"[pos] generic-default lookup failed: {e}")
        return None

    def _apply_selected_customer(self, cust: dict) -> bool:
        """Single entry point for 'a customer was chosen'.

        Keeps *everything* consistent after a customer change:
          • `_selected_customer` + active price list
          • the nav-bar Customer button (`_cust_btn`)
          • the inline search-strip label next to the search box
            (`_cust_inline_label`)
          • the search input itself (cleared so the next search is fresh)
          • the status bar
          • re-prices the product grid against the new customer's list
          • **clears the cart** if the customer's price list differs from
            the currently active one and the cart has items — stale per-row
            prices against the old list would be misleading.

        Returns True when applied, False when the user cancelled a
        cart-clear confirmation. Callers that care can branch on this to
        undo UI state (e.g. re-tick the previous customer selection).
        """
        if not cust:
            return False

        new_price_list = cust.get("price_list_name") or None

        # Ask before wiping a populated cart for a price-list change.
        if not self._confirm_cart_clear_on_price_list_change(new_price_list):
            return False

        self._selected_customer = cust
        self._active_price_list = new_price_list
        name = cust.get("customer_name", "") or ""

        print(f"[pos] 👤 customer='{name}' "
              f"price_list='{self._active_price_list or '(none)'}'")

        # Nav-bar button (also updates _cust_inline_label via _refresh_customer_btn)
        try:
            self._refresh_customer_btn()
        except Exception:
            pass

        # Inline label — _refresh_customer_btn already touches it, but we
        # set it here too so callers that fire before the strip is built
        # still render correctly on the next show.
        if hasattr(self, "_cust_inline_label") and self._cust_inline_label is not None:
            try:
                self._cust_inline_label.setText(f"Customer: {name}")
                self._cust_inline_label.setStyleSheet(
                    f"color: {NAVY}; font-size: 11px; font-weight: bold; "
                    f"background: transparent; padding: 0 6px;"
                )
            except Exception:
                pass

        # Clear the inline search box so the cashier can type a new query
        # without backspacing the previous one. Block signals so textEdited
        # doesn't fire the completer with an empty string.
        if hasattr(self, "_cust_search_edit") and self._cust_search_edit is not None:
            try:
                self._cust_search_edit.blockSignals(True)
                self._cust_search_edit.clear()
                self._cust_search_edit.blockSignals(False)
            except Exception:
                pass

        if self.parent_window:
            try:
                self.parent_window._set_status(f"Customer: {name or 'Default'}")
            except Exception:
                pass

        # Re-render the current category so prices reflect the new price list.
        try:
            self._reload_current_category()
        except Exception as e:
            print(f"[pos] grid re-price failed: {e}")
        return True

    def _confirm_cart_clear_on_price_list_change(self, new_price_list: str | None) -> bool:
        """
        Ask the cashier before wiping a populated cart because the incoming
        customer's price list differs from the active one.

        Returns True when it's safe to continue with the customer change:
          • cart is empty, or
          • price list is unchanged, or
          • user confirmed the wipe (cart gets cleared here).
        Returns False when the user cancels — caller should NOT change
        customer.

        Startup / first-time selection (no existing selected customer)
        never prompts because there's nothing to lose.
        """
        # Startup / first pick — nothing to protect.
        if self._selected_customer is None:
            return True

        # Same price list → no price recomputation needed, keep the cart.
        current_pl = self._active_price_list or None
        if (current_pl or "") == (new_price_list or ""):
            return True

        # Empty cart → safe to switch silently.
        try:
            if not self._collect_invoice_items():
                return True
        except Exception:
            pass

        answer = QMessageBox.question(
            self,
            "Clear cart?",
            (
                f"The new customer uses price list "
                f"<b>{new_price_list or '(none)'}</b> (current: "
                f"<b>{current_pl or '(none)'}</b>).\n\n"
                "Cart items were priced at the previous list. They will be "
                "cleared so new rates apply.\n\nContinue?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return False

        try:
            self._clear_cart()
        except Exception as e:
            print(f"[pos] cart clear on customer change failed: {e}")
        return True
    
    # def _refresh_unsynced_badge(self):
    #     """Refresh sync badges.

    #     When all three counts are zero   → show a single green "✓ All Synced" badge.
    #     When any count is non-zero       → hide the unified badge and show only the
    #                                        individual SI / CN / SO badges that have errors,
    #                                        coloured amber (< 5) or red (≥ 5).
    #     """

    #     def _apply_badge(badge, count, label):
    #         if not hasattr(self, badge):
    #             return
    #         btn = getattr(self, badge)
    #         if count == 0:
    #             btn.setVisible(False)
    #             return
    #         bg, hov = (AMBER, ORANGE) if count < 5 else (DANGER, DANGER_H)
    #         suffix = f"{count}" if count < 5 else f"{count} !"
    #         prefix = "⚠ " if count >= 5 else ""
    #         btn.setText(f"{label} {suffix}")
    #         btn.setToolTip(f"{prefix}{count} unsynced {label}(s) — click to view errors")
    #         btn.setStyleSheet(f"""
    #             QPushButton {{
    #                 background-color: {bg}; color: {WHITE}; border: none;
    #                 border-radius: 3px; font-size: 11px; font-weight: bold; padding: 0 6px;
    #             }}
    #             QPushButton:hover {{ background-color: {hov}; }}
    #         """)
    #         btn.setVisible(True)

    #     # SI — Sales Invoices (count from sync_errors table, fallback to models.sale)
    #     si_count = 0
    #     try:
    #         from services.sync_errors_service import count_unresolved
    #         si_count = count_unresolved("SI")
    #     except Exception:
    #         pass
    #     if si_count == 0:
    #         try:
    #             from models.sale import get_all_sales
    #             si_count = sum(1 for s in get_all_sales() if not s.get("synced"))
    #         except Exception:
    #             pass
    #     _apply_badge("_si_badge", si_count, "SI")

    #     # CN — Credit Notes
    #     cn_count = 0
    #     try:
    #         from database.db import get_connection
    #         conn = get_connection(); cur = conn.cursor()
    #         cur.execute(
    #             "SELECT COUNT(*) FROM credit_notes "
    #             "WHERE cn_status IN ('ready','pending_sync')")
    #         row = cur.fetchone(); conn.close()
    #         cn_count = int(row[0] or 0) if row else 0
    #     except Exception:
    #         pass
    #     _apply_badge("_cn_badge", cn_count, "CN")

    #     # SO — Sales Orders / Laybyes (errors from sync_errors, count from model)
    #     so_count = 0
    #     try:
    #         from services.sync_errors_service import count_unresolved
    #         so_count = count_unresolved("SO")
    #     except Exception:
    #         pass
    #     if so_count == 0 and _HAS_SALES_ORDER:
    #         try:
    #             so_count = len(_get_unsynced_so())
    #         except Exception:
    #             pass
    #     _apply_badge("_so_badge", so_count, "SO")

    #     # Unified badge — visible only when everything is clean
    #     if hasattr(self, "_all_synced_badge"):
    #         self._all_synced_badge.setVisible(
    #             si_count == 0 and cn_count == 0 and so_count == 0)

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
                part_no  = self.invoice_table.item(r, self.COL_PART_NO).text()
                name     = self.invoice_table.item(r, self.COL_NAME).text()
                price    = float(self.invoice_table.item(r, self.COL_PRICE).text() or "0")
                total_ln = float(self.invoice_table.item(r, self.COL_TOTAL).text() or "0")
                product_id = self.invoice_table.item(r, self.COL_PART_NO).data(Qt.UserRole)
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
            cn_result = create_credit_note(
                original_sale_id=cn["id"],
                items_to_return=items,
                currency=cn.get("currency", "USD"),
                customer_name=cn.get("customer_name", ""),
                cashier_name=cashier_name,
            )
        except Exception as e:
            QMessageBox.warning(self, "Credit Note Error", str(e))
            return

        # ── Step 2: Create Refund Payment Entry (Pay to Customer) ─────────────
        try:
            from services.cn_payment_entry_service import create_cn_payment_entry
            create_cn_payment_entry(cn_result)
        except Exception as pe_err:
            print(f"Refund creation failed (non-blocking): {pe_err}")

        # ── Fiscalize synchronously so QR is ready before printing ───────────
        fiscal_qr   = ""
        fiscal_vc   = ""
        try:
            from services.fiscalization_service import get_fiscalization_service
            _fs = get_fiscalization_service()
            if _fs.is_fiscalization_enabled():
                _fs.process_credit_note_fiscalization(cn_result["id"])
                # Read the QR/VC back from DB now that it's committed
                from models.credit_note import get_credit_note_by_id
                _saved = get_credit_note_by_id(cn_result["id"])
                if _saved:
                    fiscal_qr = _saved.get("fiscal_qr_code", "") or ""
                    fiscal_vc = _saved.get("fiscal_verification_code", "") or ""
        except Exception as _fe:
            print(f"[CN Print] Synchronous fiscalization failed for CN "
                  f"{cn_result.get('cn_number', '')}: {_fe}")

        if self.parent_window:
            self.parent_window._set_status(
                f"Return processed  ·  {cn.get('invoice_no', '')}  ·  ${total:.2f}")

        # ── Print credit note receipt ─────────────────────────────────────────
        self._print_credit_note_receipt(cn, items, total, cashier_name,
                                        fiscal_qr=fiscal_qr, fiscal_vc=fiscal_vc)

        # ── Badge refresh: immediately after DB write, before UI reset ──
        self._refresh_unsynced_badge()
        self._new_sale(confirm=False)

    def _print_credit_note_receipt(self, cn: dict, items: list, total: float, cashier_name: str,
                                   fiscal_qr: str = "", fiscal_vc: str = ""):
        """Build a proper ReceiptData credit note and send it to printing_service."""
        import json
        from pathlib import Path
        from models.receipt import ReceiptData, Item
        from models.company_defaults import get_defaults
        from services.printing_service import printing_service

        co = get_defaults() or {}

        # ── Resolve printer ──────────────────────────────────────────────────
        hw_file  = Path("app_data/hardware_settings.json")
        printers = []
        try:
            with open(hw_file, "r", encoding="utf-8") as f:
                hw = json.load(f)
            if hw.get("main_printer") and hw["main_printer"] != "(None)":
                printers.append(hw["main_printer"])
        except Exception:
            pass

        if not printers:
            QMessageBox.warning(
                self, "No Printer",
                "No active printer configured in hardware settings.\n"
                "Go to Settings → Hardware to configure a printer."
            )
            return

        # ── Build ReceiptData ────────────────────────────────────────────────
        subtotal = sum(float(it.get("total", 0)) for it in items)

        receipt = ReceiptData(
            doc_type            = "credit_note",
            companyName         = co.get("company_name", ""),
            companyAddress      = co.get("address_1", ""),
            companyAddressLine1 = co.get("address_2", ""),
            companyEmail        = co.get("email", ""),
            tel                 = co.get("phone", ""),
            tin                 = co.get("tin_number", ""),
            vatNo               = co.get("vat_number", ""),
            invoiceNo           = cn.get("cn_number", cn.get("id", "")),
            invoiceDate         = cn.get("date", ""),
            cashierName         = cashier_name,
            customerName        = cn.get("customer_name", "Walk-in") or "Walk-in",
            customerContact     = cn.get("customer_contact", ""),
            grandTotal          = total,
            subtotal            = subtotal,
            totalVat            = 0.0,
            amountTendered      = 0.0,
            change              = 0.0,
            currency            = cn.get("currency", "USD"),
            footer              = co.get("footer_text", "Credit note issued. Thank you."),
        )
        # Extra attributes read via getattr() in printing_service — set after construction
        receipt.originalInvoiceNo = cn.get("invoice_no", "")
        receipt.creditNoteReason  = cn.get("reason", "")
        # Pre-resolved fiscal data — printing_service will use these directly
        receipt.fiscal_qr_code           = fiscal_qr
        receipt.fiscal_verification_code = fiscal_vc

        for it in items:
            qty   = float(it.get("qty", 0))
            price = float(it.get("price", 0))
            amt   = float(it.get("total", qty * price))
            receipt.items.append(Item(
                productName = it.get("product_name", ""),
                productid   = it.get("part_no", "") or it.get("product_id", ""),
                qty         = qty,
                price       = price,
                amount      = amt,
            ))
        receipt.itemlist = receipt.items

        # ── Print ────────────────────────────────────────────────────────────
        ok = False
        for p in printers:
            if printing_service.print_credit_note(receipt, printer_name=p):
                ok = True

        if ok:
            QMessageBox.information(self, "Credit Note Printed",
                                    "Credit note receipt sent to printer.")
        else:
            QMessageBox.warning(self, "Print Failed",
                                "Credit note could not be sent to printer.\n"
                                "Check printer connection and try again.")

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
        # Keep the selected customer across sales so the cashier does not have
        # to re-select the same customer every transaction.  The cashier can
        # tap the customer button at any time to switch to a different customer.
        self._refresh_customer_btn()
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
        from PySide6.QtCore import QDate

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

        # ── 3b. Check discount expiry date ────────────────────────────────────
        expiry_str = current_user.get("discount_expiry_date", "") or ""
        if expiry_str and can_disc:
            expiry_date = QDate.fromString(expiry_str, "yyyy-MM-dd")
            if not expiry_date.isValid():
                expiry_date = QDate.fromString(expiry_str, "dd/MM/yyyy")
            if expiry_date.isValid() and QDate.currentDate() > expiry_date:
                # Discount privilege has expired — require manager override
                can_disc = False
                _expired_msg = (
                    f"Discount authorisation for <b>{current_user.get('full_name') or current_user.get('username','this user')}</b> "
                    f"expired on <b>{expiry_date.toString('dd/MM/yyyy')}</b>.<br><br>"
                    f"A Manager PIN is required to proceed."
                )
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Discount Expired")
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setText(_expired_msg)
                msg_box.setTextFormat(Qt.RichText)
                msg_box.setStandardButtons(QMessageBox.Ok)
                msg_box.setStyleSheet(f"QMessageBox {{ background:{WHITE}; }} QLabel {{ color:{DARK_TEXT}; }}")
                msg_box.exec()

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
            # Manager override — use manager's limit (100 = full access)
            limit = manager.get("max_discount_percent", 100) or 100

        # ── 5. Read existing value to pre-fill ───────────────────────────────
        existing = self.invoice_table.item(row, self.COL_DISC)
        current_val = 0.0
        if existing and existing.text().strip():
            try:
                current_val = float(existing.text().replace('%', '').strip())
            except (ValueError, AttributeError):
                current_val = 0.0

        print(f"[discount] can_disc={can_disc}  limit={limit}  current_val={current_val}")

        # ── 6. Get line total for conversion ─────────────────────────────────
        try:
            line_price = float(self.invoice_table.item(row, self.COL_PRICE).text() or "0")
            line_qty   = float(self.invoice_table.item(row, self.COL_QTY).text() or "1")
            line_total = line_price * line_qty
        except (ValueError, AttributeError):
            line_total = 0.0

        # ── 7. Custom discount dialog ─────────────────────────────────────────
        disc_dlg = QDialog(self)
        disc_dlg.setWindowTitle("Apply Discount")
        disc_dlg.setFixedSize(420, 300)
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

        title_lbl = QLabel("Apply Discount")
        title_lbl.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {NAVY};")
        dlg_lay.addWidget(title_lbl)

        # ── Rules banner ─────────────────────────────────────────────────────
        cashier_name = current_user.get("full_name") or current_user.get("username", "")
        from PySide6.QtCore import QDateTime
        now_str = QDateTime.currentDateTime().toString("dd/MM/yyyy  hh:mm")
        expiry_display = ""
        if expiry_str:
            try:
                ed = QDate.fromString(expiry_str, "yyyy-MM-dd")
                if not ed.isValid():
                    ed = QDate.fromString(expiry_str, "dd/MM/yyyy")
                if ed.isValid():
                    expiry_display = f"  |  Expires: {ed.toString('dd/MM/yyyy')}"
            except Exception:
                pass
        rules_lbl = QLabel(
            f"Cashier: <b>{cashier_name}</b>  |  Max allowed: <b>{limit}%</b>"
            f"{expiry_display}<br>"
            f"<span style='color:{MUTED};font-size:10px;'>{now_str}</span>"
        )
        rules_lbl.setTextFormat(Qt.RichText)
        rules_lbl.setWordWrap(True)
        rules_lbl.setStyleSheet(
            f"font-size:11px; color:{NAVY}; background:{LIGHT}; "
            f"border:1px solid {BORDER}; border-radius:5px; padding:6px 10px;"
        )
        dlg_lay.addWidget(rules_lbl)
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
            _update_hint()

        def _pick_pct():
            btn_pct.setChecked(True); btn_amt.setChecked(False); _style_toggle()
            _update_hint()

        btn_amt.clicked.connect(_pick_amt)
        btn_pct.clicked.connect(_pick_pct)
        toggle_row.addWidget(btn_amt)
        toggle_row.addWidget(btn_pct)
        dlg_lay.addLayout(toggle_row)

        disc_input = QLineEdit()
        disc_input.setPlaceholderText("")
        disc_input.setText(f"{current_val:.2f}" if current_val else "")
        disc_input.selectAll()
        dlg_lay.addWidget(disc_input)

        # Pre-calculate allowed amounts so cashier sees them before typing
        max_allowed_amt = round(line_total * (float(limit) / 100.0), 2) if line_total > 0 else 0.0

        hint_lbl = QLabel()
        hint_lbl.setWordWrap(True)

        def _update_hint():
            """Refresh the hint label live as the user types."""
            raw_text = disc_input.text().strip()
            if btn_pct.isChecked():
                # Show allowed range in both % and dollar amount
                hint_lbl.setText(
                    f"Allowed: 0% – <b>{limit}%</b>  "
                    f"(max <b>${max_allowed_amt:.2f}</b> off a ${line_total:.2f} line)"
                )
                try:
                    entered = float(raw_text)
                    entered_amt = line_total * (entered / 100.0)
                    if entered > limit:
                        hint_lbl.setText(
                            f"{entered:.1f}% exceeds your limit of <b>{limit}%</b>  "
                            f"(= ${line_total * entered / 100:.2f}).  "
                            f"Max you can give: <b>${max_allowed_amt:.2f}</b>"
                        )
                        hint_lbl.setStyleSheet(f"font-size:11px; color:{DANGER};")
                    elif entered > 0:
                        hint_lbl.setText(
                            f"{entered:.1f}% = <b>${entered_amt:.2f}</b> off  "
                            f"(limit: {limit}% = ${max_allowed_amt:.2f})"
                        )
                        hint_lbl.setStyleSheet(f"font-size:11px; color:{SUCCESS};")
                    else:
                        hint_lbl.setText(
                            f"Allowed: 0% – <b>{limit}%</b>  "
                            f"(max <b>${max_allowed_amt:.2f}</b> off a ${line_total:.2f} line)"
                        )
                        hint_lbl.setStyleSheet(f"font-size:11px; color:{MUTED};")
                except ValueError:
                    hint_lbl.setStyleSheet(f"font-size:11px; color:{MUTED};")
            else:
                # Fixed amount mode
                hint_lbl.setText(
                    f"Allowed: $0.00 – <b>${max_allowed_amt:.2f}</b>  "
                    f"({limit}% of ${line_total:.2f})"
                )
                hint_lbl.setStyleSheet(f"font-size:11px; color:{MUTED};")
                try:
                    entered = float(raw_text)
                    if line_total > 0 and limit < 100 and entered > max_allowed_amt:
                        implied = (entered / line_total) * 100
                        hint_lbl.setText(
                            f"${entered:.2f} ({implied:.1f}%) exceeds your limit.  "
                            f"Max allowed: <b>${max_allowed_amt:.2f}</b>"
                        )
                        hint_lbl.setStyleSheet(f"font-size:11px; color:{DANGER};")
                    elif entered > 0:
                        implied = (entered / line_total) * 100 if line_total > 0 else 0
                        hint_lbl.setText(
                            f"${entered:.2f} ({implied:.1f}% off)  "
                            f"(limit: ${max_allowed_amt:.2f})"
                        )
                        hint_lbl.setStyleSheet(f"font-size:11px; color:{SUCCESS};")
                except ValueError:
                    pass

        hint_lbl.setTextFormat(Qt.RichText)
        hint_lbl.setStyleSheet(f"font-size:11px; color:{MUTED};")
        dlg_lay.addWidget(hint_lbl)

        # Wire live update
        disc_input.textChanged.connect(lambda _: _update_hint())

        # Call once to show the initial state
        _update_hint()

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
            # ── HARD ENFORCE the user's max_discount_percent ──────────────────
            if raw < 0 or raw > float(limit):
                QMessageBox.warning(
                    self, "Discount Exceeds Limit",
                    f"{raw:.1f}% exceeds the maximum allowed discount of {limit}% "
                    f"for cashier '{cashier_name}'.\n\n"
                    f"Please enter a value between 0% and {limit}%.\n\n"
                    f"A Manager PIN override is required to apply a higher discount."
                )
                return
            disc_amount = line_total * (raw / 100.0)
            msg = f"Discount {raw:.2f}% (${disc_amount:.2f}) applied to row {row+1}." if raw > 0 else "Discount cleared."
        else:
            disc_amount = raw
            if disc_amount < 0 or (line_total > 0 and disc_amount > line_total):
                QMessageBox.warning(self, "Out of Range", f"Amount must be 0 – ${line_total:.2f}.")
                return
            # Also enforce max % cap when entering as fixed amount
            if line_total > 0 and limit < 100:
                max_allowed_amt = line_total * (float(limit) / 100.0)
                if disc_amount > max_allowed_amt:
                    implied_pct = (disc_amount / line_total) * 100
                    QMessageBox.warning(
                        self, "Discount Exceeds Limit",
                        f"${disc_amount:.2f} ({implied_pct:.1f}%) exceeds the maximum allowed "
                        f"discount of {limit}% (${max_allowed_amt:.2f}) "
                        f"for cashier '{cashier_name}'.\n\n"
                        f"A Manager PIN override is required for a higher discount."
                    )
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

        self.invoice_table.setItem(row, self.COL_DISC, disc_item)
        self._recalc_row(row)
        self._recalc_totals()

        print(f"[discount] {msg}")
        if self.parent_window:
            self.parent_window._set_status(msg)

    def _quick_tender(self, _amount):
        pass  # no-op

    

    # =========================================================================
    # QUOTATION FLOW
    # =========================================================================
    def _on_quotation(self):
        """
        Quotation flow:
          1. Permission check — allow_quote required (or admin PIN).
          2. Clear the cart (with confirmation if items exist).
          3. Force customer selection.
          4. User adds items to the cart normally.
          5. When ready, open QuotationDialog to print/save.
        """
        # ── Permission check ─────────────────────────────────────────────────
        if not self._check_permission("allow_quote", "Create Quotation"):
            return

        # ── Step 1: Clear the cart ────────────────────────────────────────────
        existing_items = self._collect_invoice_items()
        if existing_items:
            reply = QMessageBox.question(
                self, "Create Quotation",
                "Creating a Quotation will clear the current cart.\n\n"
                "Continue and clear the cart?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        self._new_sale(confirm=False)

        # ── Step 2: Force customer selection ─────────────────────────────────
        dlg = CustomerSearchPopup(self)
        if dlg.exec() != QDialog.Accepted or not dlg.selected_customer:
            QMessageBox.information(self, "Customer Required",
                                    "Please select a customer before creating a Quotation.")
            return
        # Route through the central setter so the grid re-prices, the
        # inline label updates, and a cart-clear is offered if the price
        # list differs from what was previously active.
        self._apply_selected_customer(dlg.selected_customer)
        cname = (dlg.selected_customer or {}).get("customer_name", "")
        if self.parent_window:
            self.parent_window._set_status(
                f"Quotation mode — Customer: {cname}  — Add items then use Options › Save Quotation")

        # ── Step 3: Set quotation mode flag and flip the PAY button label ────
        # _quotation_mode is the legacy flag; _cart_mode is what
        # _refresh_pay_button_label reads, so both get set. The Quote Mode
        # toggle pill in the navbar is kept in sync (blockSignals prevents
        # _on_quote_mode_toggle from firing and looping).
        self._quotation_mode = True
        self._cart_mode = "quote"
        try:
            if hasattr(self, "quote_mode_btn") and self.quote_mode_btn is not None:
                self.quote_mode_btn.blockSignals(True)
                self.quote_mode_btn.setChecked(True)
                self.quote_mode_btn.blockSignals(False)
        except Exception:
            pass
        try:
            self._refresh_pay_button_label()
        except Exception as _e:
            print(f"[_on_quotation] pay button refresh failed: {_e}")

        # No confirmation popup — PAY now reads "FINALIZE QUOTE" and the
        # status bar already shows "Quotation mode — Customer: <name>".

    

    def _send_quotation_to_printer(self, text: str):
        """Send quotation text to the thermal printer."""
        try:
            from services.printing_service import printing_service
            # Support multiple method names for compatibility
            if hasattr(printing_service, 'print_raw_text'):
                printing_service.print_raw_text(text)
            elif hasattr(printing_service, 'print_text'):
                printing_service.print_text(text)
            elif hasattr(printing_service, 'print_receipt'):
                printing_service.print_receipt(text)
            else:
                # Direct win32 fallback
                import win32print, json as _json
                from pathlib import Path as _Path
                hw = _json.loads(_Path("app_data/hardware_settings.json").read_text()) if _Path("app_data/hardware_settings.json").exists() else {}
                printer_name = hw.get("main_printer", "")
                if not printer_name or printer_name == "(None)": raise Exception("No main printer configured.")
                hp = win32print.OpenPrinter(printer_name)
                try:
                    win32print.StartDocPrinter(hp, 1, ("Quotation", None, "RAW"))
                    win32print.StartPagePrinter(hp)
                    win32print.WritePrinter(hp, text.encode("utf-8", errors="replace"))
                    win32print.EndPagePrinter(hp)
                    win32print.EndDocPrinter(hp)
                finally:
                    win32print.ClosePrinter(hp)
        except Exception as e:
            QMessageBox.warning(self, "Print Error", f"Could not print quotation:\n{e}")
# =============================================================================
# CASHIER POS VIEW
# 
# =============================================================================
 #=============================================================================
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
        
        self.quotation_sync_thread = start_quotation_sync_thread()

        self._stack = QStackedWidget()
        self._pos_view = POSView(parent_window=self, user=self.user)
        self._stack.addWidget(self._pos_view)

        from models.user import is_admin
        if is_admin(self.user):
            self._dashboard = AdminDashboard(parent_window=self, user=self.user)
            self._stack.addWidget(self._dashboard)

        self.setCentralWidget(self._stack)
        self._build_menubar()
        self.menuBar().setVisible(False)

        self._status_bar = QStatusBar()
        self._status_bar.setSizeGripEnabled(False)
        self._status_bar.showMessage("  Ready")
        self.setStatusBar(self._status_bar)

        # #37 — logged-in user in footer
        _uname = self.user.get("username", "")
        _urole = self.user.get("role", "cashier")
        _user_w = QWidget(); _user_w.setStyleSheet("background: transparent;")
        _user_h = QHBoxLayout(_user_w); _user_h.setContentsMargins(6, 0, 6, 0); _user_h.setSpacing(4)
        _user_ic = QLabel(); _user_ic.setPixmap(qta.icon("fa5s.user", color=MID).pixmap(12, 12))
        _user_ic.setStyleSheet("background: transparent;")
        _user_lbl = QLabel(f"{_uname} [{_urole.upper()}]")
        _user_lbl.setStyleSheet(f"color: {MID}; font-size: 11px; background: transparent;")
        _user_h.addWidget(_user_ic); _user_h.addWidget(_user_lbl)
        self._status_bar.addPermanentWidget(_user_w)

        _sep1 = QLabel("|")
        _sep1.setStyleSheet(f"color: {NAVY_2}; background: transparent;")
        self._status_bar.addPermanentWidget(_sep1)

        # #38 — server URL in footer
        try:
            from services.site_config import get_host_label as _ghl
            _srv = _ghl()
        except Exception:
            _srv = "—"
        _srv_w = QWidget(); _srv_w.setStyleSheet("background: transparent;")
        _srv_h = QHBoxLayout(_srv_w); _srv_h.setContentsMargins(6, 0, 6, 0); _srv_h.setSpacing(4)
        _srv_ic = QLabel(); _srv_ic.setPixmap(qta.icon("fa5s.globe", color=MID).pixmap(12, 12))
        _srv_ic.setStyleSheet("background: transparent;")
        _srv_lbl = QLabel(f"{_srv}")
        _srv_lbl.setStyleSheet(f"color: {MID}; font-size: 11px; background: transparent;")
        _srv_h.addWidget(_srv_ic); _srv_h.addWidget(_srv_lbl)
        self._status_bar.addPermanentWidget(_srv_w)

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
        _sql_w = QWidget(); _sql_w.setStyleSheet("background: transparent;")
        _sql_h = QHBoxLayout(_sql_w); _sql_h.setContentsMargins(6, 0, 6, 0); _sql_h.setSpacing(4)
        _sql_ic = QLabel(); _sql_ic.setPixmap(qta.icon("fa5s.database", color=MID).pixmap(12, 12))
        _sql_ic.setStyleSheet("background: transparent;")
        _sql_lbl = QLabel(f"{_sql}")
        _sql_lbl.setStyleSheet(f"color: {MID}; font-size: 11px; background: transparent;")
        _sql_h.addWidget(_sql_ic); _sql_h.addWidget(_sql_lbl)
        self._status_bar.addPermanentWidget(_sql_w)

        # #18 — everyone lands on POS first, always.
        # POSView picks its initial cart mode (Sales vs Quote) based on the
        # user's role; pharmacists default to Quote, everyone else to Sales.
        # The mode is toggleable from the POS navbar at any time.
        self._stack.setCurrentIndex(0)

        # Proactively prompt for a shift right after login if none is running.
        # Deferred via singleShot so the main window finishes painting first;
        # the chooser then opens immediately without an intermediate popup.
        # The method lives on POSView — MainWindow doesn't own the shift UI.
        QTimer.singleShot(0, self._pos_view._prompt_open_shift_if_missing)

        # ── Background sync services ──────────────────────────────────────────
        # Product sync (every 15 s) — keeps local product list up to date
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

        # POS upload (every 60 s) — pushes local unsynced sales to server
        try:
            from services.pos_upload_service import start_upload_thread
            self._upload_worker = start_upload_thread()
        except Exception as _e:
            import logging
            logging.getLogger("MainWindow").warning(
                "POS upload service could not start: %s", _e)

        # Payment entry sync — pushes local payment entries → Server
        try:
            from services.payment_entry_service import start_payment_sync_daemon
            self._payment_sync = start_payment_sync_daemon()
        except Exception as _e:
            import logging
            logging.getLogger("MainWindow").warning(
                "Payment entry sync could not start: %s", _e)
                
        # Customer payment sync — pushes account payments → Server
        try:
            from services.payment_upload_service import start_payment_sync_daemon as start_customer_payment_sync
            self._customer_payment_sync = start_customer_payment_sync()
        except Exception as _e:
            import logging
            logging.getLogger("MainWindow").warning(
                "Customer payment sync could not start: %s", _e)

        # Accounts + exchange rates sync (hourly)
        try:
            from services.accounts_sync_service import start_accounts_sync_daemon
            self._accounts_sync = start_accounts_sync_daemon()
        except Exception as _e:
            import logging
            logging.getLogger("MainWindow").warning(
                "Accounts sync could not start: %s", _e)

        # Sales Order pull — pulls Frappe Sales Orders → local DB every 5 min
        # so cashiers can finalise fully-paid laybyes into invoices offline.
        try:
            from services.sales_order_pull_service import start_sales_order_pull_daemon
            self._sales_order_pull = start_sales_order_pull_daemon()
        except Exception as _e:
            import logging
            logging.getLogger("MainWindow").warning(
                "Sales Order pull could not start: %s", _e)

        # Credit note sync (every 60s) -- pushes ready CNs to server
        try:
            from services.credit_note_sync_service import start_credit_note_sync_daemon
            self._cn_sync = start_credit_note_sync_daemon()
        except Exception as _e:
            import logging
            logging.getLogger("MainWindow").warning(
                "Credit note sync could not start: %s", _e)

        # Sales Order (Laybye) sync — pushes unsynced SOs to server
        try:
            from services.sales_order_upload_service import start_so_upload_thread
            self._so_upload_thread = start_so_upload_thread()
        except Exception as _e:
            import logging
            logging.getLogger("MainWindow").warning(
                "Sales Order upload service could not start: %s", _e)

        # Laybye Payment Entry sync — pushes local laybye deposits → Server
        try:
            from services.laybye_payment_entry_service import start_laybye_pe_sync_daemon
            self._laybye_payment_sync = start_laybye_pe_sync_daemon()
        except Exception as _e:
            import logging
            logging.getLogger("MainWindow").warning(
                "Laybye payment entry sync could not start: %s", _e)

        # ── Ensure sync_errors table exists ────────────────────────────────────
        try:
            from services.sync_errors_service import ensure_table as _set
            _set()
        except Exception:
            pass

        # ── Sync error bus — route background sync errors to the GUI ─────────────
        try:
            sync_error_bus.error_posted.connect(
                self._on_sync_error,
                Qt.QueuedConnection)
        except Exception:
            pass

        # ── One-shot startup sync (runs immediately in background on login) ──
        # Fires once right after MainWindow opens so products, customers,
        # users, accounts and exchange rates are all refreshed without the
        # cashier having to click anything manually.
        QTimer.singleShot(2000, self._run_startup_sync)   # 2 s delay lets the
        # UI finish rendering before the network calls start.

    # =========================================================================
    # PHARMACIST LANDING — open the Quotations list dialog right after login
    # for users whose role == "Pharmacist".  Follows the same invocation style
    # as _open_quotation_manager() in POSView (modal dlg.exec()).
    # =========================================================================
    def _open_quotations_for_pharmacist(self):
        try:
            from views.dialogs.quotation_dialog import QuotationDialog
            dlg = QuotationDialog(self)
            dlg.exec()
        except Exception as e:
            print(f"[main_window] Could not open Quotations for pharmacist: {e}")

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

    # =========================================================================
    # OPEN SHIFT REPRINT DIALOG
    # =========================================================================
    def _open_shift_reprint(self):
        """Open the shift reconciliation reprint dialog."""
        try:
            from views.dialogs.shift_reprint_dialog import show_shift_reprint
            show_shift_reprint(self)
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"Could not open reprint dialog: {str(e)}")

    # =========================================================================
    # BUILD MENUBAR
    # =========================================================================
    def _build_menubar(self):
        mb = self.menuBar()
        mb.setVisible(False)  # hidden by default, but we still build it for toggle

        # ── Sales ─────────────────────────────────────────────────────────────
        sales_menu = mb.addMenu("Sales")
        for label, fn in [
            ("Sales Invoice List", self._pos_view._open_sales_list),
            ("Sales Orders",       self._pos_view._open_sales_order_list),
            (None, None),
            ("Payments",           self._pos_view._open_customer_payment_entry),
            (None, None),
            ("Reprint Shift Reconciliation", self._open_shift_reprint),
        ]:
            if label is None:
                sales_menu.addSeparator()
            else:
                a = QAction(label, self)
                a.triggered.connect(fn)
                sales_menu.addAction(a)

        # ── Admin / Other menus would go here ─────────────────────────────────
        # ... rest of your menu code ...

    # =========================================================================
    # SYNC ERROR HANDLER
    # =========================================================================
    def _on_sync_error(self, error_msg: str):
        """Show sync errors in the status bar."""
        self._status_bar.showMessage(f"{error_msg}", 5000)
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
        
        
    def enter_laybye_mode(self):
        """
        Triggered by the Laybye button in the header.
        Checks cart state and toggles the UI mode.
        """
        # 1. Check if the cart has items (assuming self.results or self.cart_table)
        if self.results.rowCount() > 0:
            confirm = QMessageBox.question(
                self, 
                "Switch to Laybye?", 
                "The current cart must be cleared to start a Laybye. Proceed?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if confirm == QMessageBox.Yes:
                self.results.setRowCount(0) # Clear the cart
                self._update_totals()       # Refresh your total labels
            else:
                return # User cancelled, stay in normal mode

        # 2. Update the Payment Button to 'Deposit' Mode
        self._set_pay_button_mode(is_laybye=True)
        
        # 3. Visual Feedback
        self.statusBar().showMessage("MODE: LAYBYE ACTIVE (Deposit Required)", 0)
        self.statusBar().setStyleSheet(f"background-color: {ORANGE}; color: {WHITE};")
    
    # =========================================================================
    # SYNC ERROR HANDLER  (receives signals from SyncErrorBus)
    # =========================================================================
    def _on_sync_error(self, service: str, order_ref: str, message: str):
        """
        Called on the GUI thread whenever a background sync fails.
        Updates badges and shows a non-blocking toast popup.
        """
        import logging as _lg
        _lg.getLogger("SyncError").warning("[%s] %s — %s", service, order_ref, message)

        # Refresh badge counts
        if hasattr(self, "_pos_view"):
            self._pos_view._refresh_unsynced_badge()

        # Show toast (non-modal, auto-hides after 10 s)
        self._show_sync_toast(service, order_ref, message)

    def _show_sync_toast(self, service: str, order_ref: str, message: str):
        """
        Shows a small styled error panel anchored to the bottom-right of the
        main window.  Auto-hides after 10 seconds.
        A 'Details' button opens the relevant UnsyncedPopup.
        """
        # Map service name → badge kind
        kind = "SI"
        for key, val in (("SalesOrder", "SO"), ("sales_order", "SO"),
                         ("CreditNote", "CN"), ("credit_note",  "CN")):
            if key.lower() in service.lower():
                kind = val
                break

        toast = QWidget(self)
        toast.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        toast.setAttribute(Qt.WA_ShowWithoutActivating, True)
        toast.setStyleSheet(f"""
            QWidget {{
                background:{NAVY};
                border:2px solid {DANGER};
                border-radius:8px;
            }}
            QLabel {{ background:transparent; }}
        """)

        tl = QVBoxLayout(toast)
        tl.setContentsMargins(14, 10, 14, 10)
        tl.setSpacing(6)

        # Row 1: icon + title + close
        hrow = QHBoxLayout(); hrow.setSpacing(8)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon("fa5s.times-circle", color=DANGER).pixmap(16, 16))
        icon_lbl.setStyleSheet("background:transparent;")
        _svc_map = {
            "SalesOrderUpload": "Sales Order Sync",
            "pos_upload":       "Invoice Sync",
            "CreditNoteSync":   "Credit Note Sync",
            "laybye_payment":   "Deposit Sync",
        }
        svc_short = next(
            (v for k, v in _svc_map.items() if k.lower() in service.lower()),
            service.replace("Upload","").replace("Service","").replace("Sync"," Sync")
        )
        title_lbl = QLabel(f"Sync Error — {svc_short}")
        title_lbl.setStyleSheet(
            f"font-size:12px; font-weight:bold; color:{WHITE};")
        close_btn = QPushButton(); close_btn.setIcon(qta.icon("fa5s.times", color=MID))
        close_btn.setFixedSize(22, 22); close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent;color:{MID};border:none;font-size:12px; }}
            QPushButton:hover {{ color:{WHITE}; }}
        """)
        close_btn.clicked.connect(toast.hide)
        hrow.addWidget(icon_lbl); hrow.addWidget(title_lbl, 1); hrow.addWidget(close_btn)
        tl.addLayout(hrow)

        # Row 2: order ref
        if order_ref:
            ref_lbl = QLabel(f"Order: {order_ref}")
            ref_lbl.setStyleSheet(f"font-size:11px; color:{MID};")
            tl.addWidget(ref_lbl)

        # Row 3: clean error message
        short_msg = _clean_frappe_error(message)[:160]
        if short_msg:
            msg_lbl = QLabel(short_msg)
            msg_lbl.setWordWrap(True)
            msg_lbl.setStyleSheet(f"font-size:11px; color:{DANGER};")
            tl.addWidget(msg_lbl)

        # Row 4: admin hint
        hint_lbl = QLabel(
            "Contact your administrator if this keeps happening.\n"
            "Check: Stock Settings → Stock Reservation,\n"
            "Company Defaults → Warehouse / Cash Account."
        )
        hint_lbl.setWordWrap(True)
        hint_lbl.setStyleSheet(f"font-size:10px; color:{MUTED};")
        tl.addWidget(hint_lbl)

        # Row 5: details button
        details_btn = QPushButton(f"View unsynced {kind}s")
        details_btn.setIcon(qta.icon("fa5s.search", color="white"))
        details_btn.setFixedHeight(28); details_btn.setCursor(Qt.PointingHandCursor)
        details_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT};color:{WHITE};border:none;
                           border-radius:4px;font-size:11px;font-weight:bold; }}
            QPushButton:hover {{ background:{ACCENT_H}; }}
        """)
        details_btn.clicked.connect(
            lambda _k=kind: (toast.hide(), UnsyncedPopup(_k, self).exec()))
        tl.addWidget(details_btn)

        toast.adjustSize()
        # Position: bottom-right of main window
        mg = self.geometry()
        toast.move(mg.right() - toast.width() - 24,
                   mg.bottom() - toast.height() - 52)
        toast.show()
        toast.raise_()
        QTimer.singleShot(10000, toast.hide)

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
        from models.user import is_admin

        # ── POS ───────────────────────────────────────────────────────────────
        pos_menu = mb.addMenu("POS")
        for label, fn in [
            ("New Sale",           lambda: (self.switch_to_pos(), self._pos_view._new_sale())),
            (None, None),
            ("Create Credit Note", lambda: CreditNoteDialog(self).exec()),
            ("Credit Note Sync",   lambda: CreditNoteManagerDialog(self).exec()),
            (None, None),
            ("X-Report",           self._open_pos_reports),
        ]:
            if label is None:
                pos_menu.addSeparator()
            else:
                a = QAction(label, self); a.triggered.connect(fn); pos_menu.addAction(a)

        # ── Sales ─────────────────────────────────────────────────────────────
        sales_menu = mb.addMenu("Sales")
        for label, fn in [
            ("Sales Invoice List", self._pos_view._open_sales_list),
            ("Sales Orders",       self._pos_view._open_sales_order_list),
            (None, None),
            ("Payments",           self._pos_view._open_customer_payment_entry),
            (None, None),
            ("Reprint Shift Reconciliation", self._open_shift_reprint),
        ]:  
            if label is None:
                sales_menu.addSeparator()
            else:
                a = QAction(label, self); a.triggered.connect(fn); sales_menu.addAction(a)

        # ── Inventory (admin only) ─────────────────────────────────────────────
        if is_admin(self.user):
            inv_menu = mb.addMenu("Inventory")
            for label, fn in [
                ("Inventory List", self._open_inventory_list),
                ("Item Groups",    self._open_item_groups),
            ]:
                a = QAction(label, self); a.triggered.connect(fn); inv_menu.addAction(a)

        # ── Maintenance ────────────────────────────────────────────────────────
        maint = mb.addMenu("Maintenance")

        def _sd_action(cls_name):
            """Return a handler that opens a class from settings_dialog."""
            def _h():
                try:
                    import importlib
                    sd = importlib.import_module("views.dialogs.settings_dialog")
                    cls = getattr(sd, cls_name)
                    if cls_name == "ManageUsersDialog":
                        cls(self, current_user=self.user).exec()
                    else:
                        cls(self).exec()
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not open {cls_name}:\n{e}")
            return _h

        for label, fn in [
            ("Companies",         _sd_action("CompanyDialog")),
            ("Customer Groups",   _sd_action("CustomerGroupDialog")),
            ("Warehouses",        _sd_action("WarehouseDialog")),
            ("Cost Centers",      _sd_action("CostCenterDialog")),
            ("Price Lists",       _sd_action("PriceListDialog")),
            ("Customers",         _sd_action("CustomerDialog")),
            ("Users",             _sd_action("ManageUsersDialog")),
            (None, None),
            ("Company Defaults",  self._open_company_defaults),
            ("POS Rules",         _sd_action("POSRulesDialog")),
            ("Hardware Settings", _sd_action("HardwareDialog")),
            # ("Advanced Printing", lambda: AdvanceSettingsDialog(self).exec()),
            (None, None),
            ("Day Shift",         self._pos_view._open_day_shift),
            ("Sync Queue",        self._pos_view._open_sales_list),
            (None, None),
            ("Stock File",        self._pos_view._open_stock_file),
            (None, None),
            ("Products",          lambda: coming_soon(self, "Products")),
            ("Tax Settings",      lambda: coming_soon(self, "Tax Settings")),
            ("Printer Setup",     lambda: coming_soon(self, "Printer Setup")),
            ("Backup",            lambda: coming_soon(self, "Backup")),
        ]:
            if label is None:
                maint.addSeparator()
            else:
                a = QAction(label, self); a.triggered.connect(fn); maint.addAction(a)

    # ── Menubar action helpers ─────────────────────────────────────────────────
    def _open_inventory_list(self):
        try:
            from views.dialogs.inventory_list_dialog import InventoryListDialog
            InventoryListDialog(self).exec()
        except NameError as e:
            QMessageBox.warning(self, "Import Error",
                f"inventory_list_dialog.py is missing an import:\n{e}\n\n"
                "Add the missing widget import (e.g. QDialog) to that file.")
        except ImportError:
            coming_soon(self, "Inventory List")

    def _open_item_groups(self):
        try:
            from views.dialogs.item_group_dialog import ItemGroupDialog
            ItemGroupDialog(self).exec()
        except ImportError:
            coming_soon(self, "Item Groups")

    def _open_company_defaults(self):
        try:
            from views.pages.company_defaults_page import CompanyDefaultsPage
            dlg = QDialog(self)
            dlg.setWindowTitle("Company Defaults")
            dlg.setStyleSheet(f"QDialog {{ background: {OFF_WHITE}; }}")
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(CompanyDefaultsPage())
            dlg.setWindowState(Qt.WindowMaximized)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open Company Defaults:\n{e}")
    
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
            self._do_logout()

    def _logout_after_shift_close(self):
        """Shift was just reconciled — skip the "Logout?" confirmation and
        return straight to the login screen so the next cashier can open
        a new shift without the old one lingering."""
        self._do_logout()

    def _do_logout(self):
        """Hide the current main window, show LoginDialog, on success launch
        a fresh MainWindow. Shared by the user-initiated Logout button and
        the automatic post-shift-close flow."""
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
# CUSTOMER PAYMENT ENTRY DIALOG
# Clean version - No confirmations, just save and close

from PySide6.QtWidgets import (
    QDialog, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QFrame, QSizePolicy, QMessageBox,
    QScrollArea, QDateEdit
)
from PySide6.QtCore import Qt, QLocale, QDate
from PySide6.QtGui import QDoubleValidator
import hashlib
import json
import time


class CustomerPaymentDialog(QDialog):
    """
    Clean customer payment dialog using MOP structure.
    No confirmations - saves payment and closes immediately.
    """
    
    _NAVY      = "#0d1f3c"
    _NAVY_2    = "#162d52"
    _NAVY_3    = "#1e3d6e"
    _ACCENT    = "#1a5fb4"
    _ACCENT_H  = "#1c6dd0"
    _WHITE     = "#ffffff"
    _OFF_WHITE = "#f0f4f9"
    _LIGHT     = "#e4eaf4"
    _MID       = "#8fa8c8"
    _MUTED     = "#5a7a9a"
    _BORDER    = "#c8d8ec"
    _SUCCESS   = "#1a7a3c"
    _SUCCESS_H = "#1f9447"
    _DANGER    = "#b02020"
    _ORANGE    = "#c05a00"

    def __init__(self, parent=None, customer=None):
        super().__init__(parent)
        self._customer = customer
        self._methods: list[dict] = []
        self._active_method: str = ""
        self._method_rows: dict = {}
        self._payment_type: str = "outstanding"
        self._processing_save = False
        
        self.setWindowTitle("Customer Payment")
        self.setMinimumSize(860, 560)
        self.setModal(True)
        self.setWindowState(Qt.WindowMaximized)
        
        self._load_payment_methods()
        self._build_ui()
        self._refresh_balances()
        
        if self._methods:
            self._active_method = self._methods[0]["label"]
            self._activate_method(self._active_method)

    # =========================================================================
    # Data Loading
    # =========================================================================
    
    def _load_payment_methods(self):
        """Load payment methods from modes_of_payment table."""
        result = []
        seen = set()
        
        try:
            from database.db import get_connection, fetchall_dicts
            conn = get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT
                    m.name            AS mop_name,
                    m.gl_account      AS gl_account,
                    m.account_currency AS currency
                FROM modes_of_payment m
                WHERE m.gl_account IS NOT NULL
                  AND m.gl_account <> ''
                  AND m.enabled = 1
                ORDER BY m.name
            """)
            rows = fetchall_dicts(cur)
            conn.close()
            
            for row in rows:
                mop_name = (row.get("mop_name") or "").strip()
                gl_account = (row.get("gl_account") or "").strip()
                curr = (row.get("currency") or "USD").upper()
                
                if not mop_name or not gl_account:
                    continue
                
                key = mop_name.lower()
                if key in seen:
                    continue
                seen.add(key)
                
                rate = self._get_rate(curr, "USD")
                
                result.append({
                    "label": mop_name,
                    "mop_name": mop_name,
                    "gl_account": gl_account,
                    "currency": curr,
                    "rate_to_usd": rate,
                })
                
        except Exception as e:
            print(f"Error loading payment methods: {e}")
        
        if not result:
            result = [
                {"label": "Cash", "mop_name": "Cash", "gl_account": "", "currency": "USD", "rate_to_usd": 1.0},
                {"label": "Card", "mop_name": "Card", "gl_account": "", "currency": "USD", "rate_to_usd": 1.0},
            ]
        
        self._methods = result

    def _get_rate(self, from_currency: str, to_currency: str = "USD") -> float:
        if from_currency.upper() == to_currency.upper():
            return 1.0
        try:
            from models.exchange_rate import get_rate
            r = get_rate(from_currency, to_currency)
            if r:
                return float(r)
            inv = get_rate(to_currency, from_currency)
            if inv and float(inv) > 0:
                return 1.0 / float(inv)
        except Exception:
            pass
        return 1.0

    def _refresh_balances(self):
        if not self._customer:
            return
        try:
            from models.customer import get_customer_by_id
            updated = get_customer_by_id(self._customer["id"])
            if updated:
                self._customer = updated
            
            outstanding = float(self._customer.get("outstanding_amount", 0))
            laybye = float(self._customer.get("laybye_balance", 0))
            
            self._lbl_outstanding_bal.setText(f"USD  {outstanding:,.2f}")
            self._lbl_laybye_bal.setText(f"USD  {laybye:,.2f}")
            self._update_due_amounts()
        except Exception as e:
            print(f"Error refreshing balances: {e}")

    # =========================================================================
    # UI Building
    # =========================================================================
    
    def _build_ui(self):
        self.setStyleSheet(f"""
            QDialog  {{ background:{self._OFF_WHITE}; font-family:'Segoe UI',sans-serif; }}
            QLabel   {{ background:transparent; color:{self._NAVY}; }}
            QWidget  {{ background:{self._OFF_WHITE}; }}
        """)
        
        outer = QVBoxLayout(self)
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)
        
        outer.addWidget(self._build_header())
        outer.addWidget(self._build_top_bar())
        
        body_w = QWidget()
        body_l = QHBoxLayout(body_w)
        body_l.setContentsMargins(24, 18, 24, 18)
        body_l.setSpacing(20)
        body_l.addLayout(self._build_left(), stretch=5)
        
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet(f"background:{self._BORDER}; border:none;")
        sep.setFixedWidth(1)
        body_l.addWidget(sep)
        
        body_l.addLayout(self._build_right(), stretch=4)
        outer.addWidget(body_w, stretch=1)

    def _build_header(self):
        hdr = QWidget()
        hdr.setFixedHeight(44)
        hdr.setStyleSheet(f"background:{self._NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 0, 24, 0)
        hl.setSpacing(12)
        
        name = (self._customer or {}).get("customer_name", "Unknown")
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"color:{self._WHITE}; font-size:14px; font-weight:700;")
        hl.addWidget(name_lbl)
        
        phone = (self._customer or {}).get("mobile", "") or (self._customer or {}).get("custom_telephone_number", "")
        if phone:
            detail = QLabel(phone)
            detail.setStyleSheet("color:rgba(255,255,255,0.45); font-size:11px;")
            hl.addWidget(detail)
        
        hl.addStretch()
        
        badge = QLabel("CUSTOMER PAYMENT")
        badge.setStyleSheet(
            f"background:rgba(255,255,255,0.10); color:rgba(255,255,255,0.65);"
            f" border:1px solid rgba(255,255,255,0.18); border-radius:4px;"
            f" font-size:8px; font-weight:700; padding:3px 9px;"
        )
        hl.addWidget(badge)
        return hdr

    def _build_top_bar(self):
        bar = QWidget()
        bar.setFixedHeight(90)
        bar.setStyleSheet(f"background:{self._WHITE};")
        bl = QVBoxLayout(bar)
        bl.setContentsMargins(24, 10, 24, 10)
        bl.setSpacing(8)
        
        row1 = QHBoxLayout()
        row1.setSpacing(0)
        
        self._btn_outstanding = QPushButton("Outstanding")
        self._btn_outstanding.setFixedHeight(28)
        self._btn_outstanding.setCursor(Qt.PointingHandCursor)
        self._btn_outstanding.setFocusPolicy(Qt.NoFocus)
        self._btn_outstanding.clicked.connect(lambda: self._set_payment_type("outstanding"))
        
        self._btn_laybye = QPushButton("Laybye")
        self._btn_laybye.setFixedHeight(28)
        self._btn_laybye.setCursor(Qt.PointingHandCursor)
        self._btn_laybye.setFocusPolicy(Qt.NoFocus)
        self._btn_laybye.clicked.connect(lambda: self._set_payment_type("laybye"))
        
        row1.addWidget(self._btn_outstanding)
        row1.addWidget(self._btn_laybye)
        row1.addSpacing(24)
        
        outstanding_lbl = QLabel("Outstanding:")
        outstanding_lbl.setStyleSheet(f"font-size:12px; color:{self._MUTED};")
        self._lbl_outstanding_bal = QLabel("USD  0.00")
        self._lbl_outstanding_bal.setStyleSheet(f"font-size:13px; font-weight:700; color:{self._NAVY}; font-family:'Courier New',monospace;")
        row1.addWidget(outstanding_lbl)
        row1.addWidget(self._lbl_outstanding_bal)
        row1.addSpacing(20)
        
        laybye_lbl = QLabel("Laybye:")
        laybye_lbl.setStyleSheet(f"font-size:12px; color:{self._MUTED};")
        self._lbl_laybye_bal = QLabel("USD  0.00")
        self._lbl_laybye_bal.setStyleSheet(f"font-size:13px; font-weight:700; color:{self._NAVY}; font-family:'Courier New',monospace;")
        row1.addWidget(laybye_lbl)
        row1.addWidget(self._lbl_laybye_bal)
        row1.addStretch()
        bl.addLayout(row1)
        
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        
        self._date_edit = QDateEdit(QDate.currentDate())
        self._date_edit.setFixedHeight(28)
        self._date_edit.setFixedWidth(120)
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("dd/MM/yyyy")
        self._date_edit.setStyleSheet(self._input_style())
        
        self._ref_input = QLineEdit()
        self._ref_input.setFixedHeight(28)
        self._ref_input.setFixedWidth(200)
        self._ref_input.setPlaceholderText("Reference / Note")
        self._ref_input.setStyleSheet(self._input_style())
        
        row2.addWidget(QLabel("Date:"))
        row2.addWidget(self._date_edit)
        row2.addSpacing(20)
        row2.addWidget(QLabel("Ref:"))
        row2.addWidget(self._ref_input)
        row2.addStretch()
        bl.addLayout(row2)
        
        self._refresh_tab_styles()
        return bar

    def _input_style(self) -> str:
        return (
            f"background:{self._WHITE}; color:{self._NAVY};"
            f" border:1px solid {self._BORDER}; border-radius:5px;"
            f" font-size:12px; padding:0 9px;"
        )

    def _refresh_tab_styles(self):
        active_style = (
            f"QPushButton {{ background:{self._NAVY}; color:{self._WHITE}; border:none;"
            f" border-radius:5px; font-size:12px; font-weight:700; padding:0 14px; }}"
        )
        inactive_style = (
            f"QPushButton {{ background:transparent; color:{self._MUTED}; border:none;"
            f" border-radius:5px; font-size:12px; font-weight:500; padding:0 14px; }}"
            f"QPushButton:hover {{ color:{self._NAVY}; }}"
        )
        self._btn_outstanding.setStyleSheet(active_style if self._payment_type == "outstanding" else inactive_style)
        self._btn_laybye.setStyleSheet(active_style if self._payment_type == "laybye" else inactive_style)

    def _set_payment_type(self, ptype: str):
        self._payment_type = ptype
        self._refresh_tab_styles()
        self._update_due_amounts()

    def _build_left(self):
        vbox = QVBoxLayout()
        vbox.setSpacing(6)
        
        amt_card = QFrame()
        amt_card.setFixedHeight(70)
        amt_card.setStyleSheet(f"QFrame {{ background:{self._WHITE}; border:2px solid {self._BORDER}; border-radius:8px; }}")
        acl = QVBoxLayout(amt_card)
        acl.setContentsMargins(16, 8, 16, 8)
        acl.setSpacing(2)
        cap = QLabel("TOTAL PAYMENT (USD)")
        cap.setAlignment(Qt.AlignCenter)
        cap.setStyleSheet(f"color:{self._MUTED}; font-size:9px; font-weight:700; letter-spacing:1px;")
        self._total_lbl = QLabel("0.00")
        self._total_lbl.setAlignment(Qt.AlignCenter)
        self._total_lbl.setStyleSheet(f"color:{self._NAVY}; font-size:24px; font-weight:800; font-family:'Courier New',monospace;")
        acl.addWidget(cap)
        acl.addWidget(self._total_lbl)
        vbox.addWidget(amt_card)
        vbox.addSpacing(8)
        
        ch = QWidget()
        ch.setFixedHeight(20)
        chl = QHBoxLayout(ch)
        chl.setContentsMargins(4, 0, 4, 0)
        for txt, st, al in [
            ("MODE OF PAYMENT", 4, Qt.AlignLeft),
            ("CCY", 1, Qt.AlignCenter),
            ("AMOUNT", 3, Qt.AlignRight),
            ("BALANCE DUE", 4, Qt.AlignRight),
        ]:
            lh = QLabel(txt)
            lh.setStyleSheet(f"color:{self._MUTED}; font-size:8px; font-weight:700; letter-spacing:0.8px;")
            lh.setAlignment(al)
            chl.addWidget(lh, st)
        vbox.addWidget(ch)
        vbox.addSpacing(2)
        
        validator = QDoubleValidator(0.0, 999999.99, 2)
        validator.setLocale(QLocale(QLocale.English))
        
        for method in self._methods:
            row_widget = self._create_method_row(method, validator)
            vbox.addWidget(row_widget)
        
        vbox.addStretch(1)
        return vbox

    def _create_method_row(self, method: dict, validator):
        label = method["label"]
        curr = method["currency"]
        
        row = QWidget()
        row.setFixedHeight(34)
        row.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)
        
        btn = QPushButton(f"  {label}")
        btn.setFixedHeight(28)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setStyleSheet(self._method_btn_style(False))
        btn.clicked.connect(lambda _, m=label: self._activate_method(m))
        
        curr_label = QLabel(curr)
        curr_label.setFixedHeight(28)
        curr_label.setFixedWidth(50)
        curr_label.setAlignment(Qt.AlignCenter)
        curr_label.setStyleSheet(
            f"background:{self._LIGHT}; color:{self._ACCENT}; border:1px solid {self._BORDER};"
            f" border-radius:5px; font-size:10px; font-weight:bold;"
        )
        
        amount_entry = QLineEdit()
        amount_entry.setFixedHeight(28)
        amount_entry.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        amount_entry.setValidator(validator)
        amount_entry.setStyleSheet(self._field_style(False))
        amount_entry.focusInEvent = lambda e, m=label, orig=amount_entry.focusInEvent: (
            self._activate_method(m, focus_field=False), orig(e))
        amount_entry.textChanged.connect(lambda: self._on_amount_changed())
        
        due_label = QLabel("—")
        due_label.setFixedHeight(28)
        due_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        due_label.setStyleSheet(
            f"color:{self._NAVY}; font-size:11px; font-weight:bold;"
            f" background:{self._WHITE}; border:1px solid {self._BORDER};"
            f" border-radius:5px; padding:0 8px;"
        )
        
        layout.addWidget(btn, 4)
        layout.addWidget(curr_label, 1)
        layout.addWidget(amount_entry, 3)
        layout.addWidget(due_label, 4)
        
        self._method_rows[label] = (btn, amount_entry, due_label)
        return row

    def _method_btn_style(self, active: bool) -> str:
        if active:
            return (f"QPushButton {{ background:{self._NAVY}; color:{self._WHITE}; border:none;"
                    f" border-radius:5px; font-size:12px; font-weight:bold;"
                    f" text-align:left; padding:0 12px; }}"
                    f"QPushButton:hover {{ background:{self._NAVY_2}; }}")
        return (f"QPushButton {{ background:{self._WHITE}; color:{self._NAVY};"
                f" border:1px solid {self._BORDER}; border-radius:5px;"
                f" font-size:12px; text-align:left; padding:0 12px; }}"
                f"QPushButton:hover {{ background:{self._LIGHT}; }}")

    def _field_style(self, active: bool) -> str:
        if active:
            return (f"QLineEdit {{ background:{self._WHITE}; color:{self._NAVY};"
                    f" border:2px solid {self._NAVY}; border-radius:5px;"
                    f" font-size:14px; font-weight:bold; padding:0 10px; }}")
        return (f"QLineEdit {{ background:{self._WHITE}; color:{self._NAVY};"
                f" border:1px solid {self._BORDER}; border-radius:5px;"
                f" font-size:14px; padding:0 10px; }}"
                f"QLineEdit:focus {{ border:2px solid {self._NAVY}; }}")

    def _activate_method(self, label: str, focus_field: bool = True):
        self._active_method = label
        for lbl, (btn, ae, _) in self._method_rows.items():
            active = lbl == label
            btn.setStyleSheet(self._method_btn_style(active))
            ae.setStyleSheet(self._field_style(active))
        if focus_field and label in self._method_rows:
            ae = self._method_rows[label][1]
            ae.setFocus()
            ae.selectAll()

    def _active_field(self) -> QLineEdit:
        if self._active_method in self._method_rows:
            return self._method_rows[self._active_method][1]
        return next(iter(self._method_rows.values()))[1]

    def _method_info(self, label: str):
        for m in self._methods:
            if m["label"] == label:
                return m["currency"], m.get("rate_to_usd", 1.0), m.get("gl_account", "")
        return "USD", 1.0, ""

    # =========================================================================
    # Amount Calculations
    # =========================================================================
    
    def _get_paid_amount_native(self, label: str) -> float:
        if label not in self._method_rows:
            return 0.0
        _, ae, _ = self._method_rows[label]
        try:
            return float(ae.text() or "0")
        except ValueError:
            return 0.0

    def _get_paid_amount_usd(self, label: str) -> float:
        native = self._get_paid_amount_native(label)
        _, rate, _ = self._method_info(label)
        return native * rate

    def _get_total_paid_usd(self) -> float:
        return sum(self._get_paid_amount_usd(m["label"]) for m in self._methods)

    def _get_remaining_due_usd(self) -> float:
        if not self._customer:
            return 0.0
        if self._payment_type == "laybye":
            total_due = float(self._customer.get("laybye_balance", 0))
        else:
            total_due = float(self._customer.get("outstanding_amount", 0))
        paid = self._get_total_paid_usd()
        return max(total_due - paid, 0.0)

    def _on_amount_changed(self):
        self._update_total_display()
        self._update_due_amounts()

    def _update_total_display(self):
        total_usd = self._get_total_paid_usd()
        self._total_lbl.setText(f"{total_usd:,.2f}")

    def _update_due_amounts(self):
        remaining_usd = self._get_remaining_due_usd()
        is_settled = remaining_usd <= 0.005
        
        for label in self._method_rows:
            _, _, due_label = self._method_rows[label]
            curr, rate, _ = self._method_info(label)
            
            if curr.upper() == "USD":
                due_text = f"USD  {remaining_usd:.2f}"
            else:
                if rate > 0:
                    native_due = remaining_usd / rate
                else:
                    native_due = remaining_usd
                due_text = f"{curr}  {native_due:,.2f}"
            
            due_label.setText(due_text)
            fg_color = self._SUCCESS if is_settled else self._NAVY
            due_label.setStyleSheet(
                f"color:{fg_color}; font-size:11px; font-weight:bold;"
                f" background:{self._WHITE}; border:1px solid {self._BORDER};"
                f" border-radius:5px; padding:0 8px;"
            )

    # =========================================================================
    # Right Panel - Numpad
    # =========================================================================
    
    def _build_right(self):
        vbox = QVBoxLayout()
        vbox.setSpacing(8)
        
        grid = QGridLayout()
        grid.setSpacing(6)
        
        def _numpad_btn(text, kind="digit"):
            btn = QPushButton(text)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            styles = {
                "digit": (self._WHITE, self._LIGHT, self._NAVY),
                "quick": (self._NAVY_3, self._NAVY_2, self._WHITE),
                "del": (self._NAVY_2, self._NAVY_3, self._WHITE),
                "clear": (self._DANGER, "#cc2828", self._WHITE),
            }
            bg, hov, fg = styles.get(kind, styles["digit"])
            btn.setStyleSheet(
                f"QPushButton {{ background:{bg}; color:{fg}; border:1px solid {self._BORDER};"
                f" border-radius:6px; font-size:15px; font-weight:bold; }}"
                f"QPushButton:hover {{ background:{hov}; }}"
                f"QPushButton:pressed {{ background:{self._NAVY_3}; color:{self._WHITE}; }}"
            )
            return btn
        
        bback = _numpad_btn("", "del")
        bback.setIcon(qta.icon("fa5s.backspace", color="white"))
        bback.clicked.connect(self._numpad_back)
        grid.addWidget(bback, 0, 0)
        
        bclr = _numpad_btn("Clear", "clear")
        bclr.clicked.connect(self._numpad_clear)
        grid.addWidget(bclr, 0, 1)
        
        bcan = _numpad_btn("Cancel", "clear")
        bcan.clicked.connect(self.reject)
        grid.addWidget(bcan, 0, 2, 1, 2)
        
        digit_rows = [["7","8","9"], ["4","5","6"], ["1","2","3"]]
        quick_amts = [10, 20, 50, 100]
        
        for ri, digs in enumerate(digit_rows, 1):
            for ci, d in enumerate(digs):
                b = _numpad_btn(d, "digit")
                b.clicked.connect(lambda _, x=d: self._numpad_press(x))
                grid.addWidget(b, ri, ci)
            qa = quick_amts[ri - 1]
            qb = _numpad_btn(str(qa), "quick")
            qb.clicked.connect(lambda _, a=qa: self._numpad_quick(a))
            grid.addWidget(qb, ri, 3)
        
        b0 = _numpad_btn("0", "digit")
        b0.clicked.connect(lambda: self._numpad_press("0"))
        grid.addWidget(b0, 4, 0)
        
        b00 = _numpad_btn("00", "digit")
        b00.clicked.connect(lambda: self._numpad_press_multi("00"))
        grid.addWidget(b00, 4, 1)
        
        bdot = _numpad_btn(".", "digit")
        bdot.clicked.connect(lambda: self._numpad_press("."))
        grid.addWidget(bdot, 4, 2)
        
        qb100 = _numpad_btn("100", "quick")
        qb100.clicked.connect(lambda: self._numpad_quick(100))
        grid.addWidget(qb100, 4, 3)
        
        b000 = _numpad_btn("000", "digit")
        b000.clicked.connect(lambda: self._numpad_press_multi("000"))
        grid.addWidget(b000, 5, 0, 1, 3)
        
        for r in range(6):
            grid.setRowMinimumHeight(r, 42)
            grid.setRowStretch(r, 0)
        for c in range(4):
            grid.setColumnStretch(c, 1)
        
        vbox.addLayout(grid, stretch=0)
        vbox.addSpacing(8)
        
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{self._BORDER}; border:none;")
        sep.setFixedHeight(1)
        vbox.addWidget(sep)
        vbox.addSpacing(8)
        
        bsave = QPushButton("Post Payment")
        bsave.setFixedHeight(52)
        bsave.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bsave.setCursor(Qt.PointingHandCursor)
        bsave.setStyleSheet(
            f"QPushButton {{ background:{self._SUCCESS}; color:{self._WHITE}; border:none;"
            f" border-radius:6px; font-size:14px; font-weight:bold; }}"
            f"QPushButton:hover {{ background:{self._SUCCESS_H}; }}"
        )
        bsave.clicked.connect(self._save)
        vbox.addWidget(bsave, stretch=1)
        
        return vbox

    def _numpad_press(self, key: str):
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

    def _numpad_press_multi(self, digits: str):
        for d in digits:
            self._numpad_press(d)

    def _numpad_back(self):
        f = self._active_field()
        f.setText(f.text()[:-1])

    def _numpad_clear(self):
        self._active_field().clear()

    def _numpad_quick(self, amt: int):
        curr, rate, _ = self._method_info(self._active_method)
        if curr.upper() != "USD" and rate > 0:
            native = amt / rate
            self._active_field().setText(f"{native:.2f}")
        else:
            self._active_field().setText(f"{amt:.2f}")

    # =========================================================================
    # Save Payment - NO CONFIRMATIONS
    # =========================================================================
    
    def _save(self):
        """Save payment - no confirmations, just save and close."""
        if self._processing_save:
            return
        
        if not self._customer:
            QMessageBox.warning(self, "No Customer", "Please select a customer.")
            return
        
        total_usd = self._get_total_paid_usd()
        if total_usd <= 0:
            QMessageBox.warning(self, "No Amount", "Please enter a payment amount.")
            self._active_field().setFocus()
            return
        
        self._processing_save = True
        
        try:
            from models.payment import create_customer_payment
            from database.db import get_connection

            saved_ledger_ids = []
            
            # Save each method with > 0 amount as its own record
            for method in self._methods:
                native_amt = self._get_paid_amount_native(method["label"])
                if native_amt > 0.005:
                    curr, rate, gl_account = self._method_info(method["label"])
                    
                    # Create payment record for this leg
                    payment_rec = create_customer_payment(
                        customer_id=self._customer["id"],
                        amount=native_amt,
                        method=method["label"],
                        currency=curr,
                        reference=self._ref_input.text().strip(),
                        cashier_id=self._get_cashier_id(),
                        payment_date=self._date_edit.date().toString("yyyy-MM-dd"),
                        payment_type=self._payment_type,
                        account_name=gl_account
                    )
                    if payment_rec and payment_rec.get("id"):
                        saved_ledger_ids.append(payment_rec["id"])
            
            if saved_ledger_ids:
                # Try to sync each to Frappe (non-blocking)
                try:
                    from services.payment_upload_service import post_payment_entry_to_frappe
                    import threading
                    for pid in saved_ledger_ids:
                        threading.Thread(target=post_payment_entry_to_frappe, args=(pid,)).start()
                except Exception as e:
                    print(f"Sync trigger error: {e}")
                
                # Print receipt (separately per leg for now, clean and accurate)
                try:
                    from models.payment import print_customer_payment
                    for pid in saved_ledger_ids:
                        print_customer_payment(pid)
                except Exception as e:
                    print(f"Print error: {e}")
                
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Failed to create payment record.")
                
        except Exception as e:
            print(f"Error saving payment: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save payment: {e}")
        finally:
            self._processing_save = False

    def _get_cashier_id(self):
        try:
            p = self.parent()
            while p:
                if hasattr(p, "user") and p.user:
                    return p.user.get("id")
                p = p.parent()
        except Exception:
            pass
        return None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self._get_total_paid_usd() > 0:
                self._save()
        else:
            super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_balances()
        if self._active_method:
            self._activate_method(self._active_method)
# # =============================================================================
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
        title = QLabel("Reprint")
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
        self._tabs.addTab(self._build_invoice_tab(), "  Sales Invoice")
        self._tabs.addTab(self._build_order_tab(),   "  Sales Order")
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
        self._inv_btn = QPushButton("Reprint Invoice")
        self._inv_btn.setIcon(qta.icon("fa5s.print", color="white"))
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
        self._so_btn = QPushButton("Reprint Sales Order")
        self._so_btn.setIcon(qta.icon("fa5s.print", color="white"))
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
        if not sale:
            return

        # ── Load full item list from DB ───────────────────────────────────────
        try:
            from models.sale import get_sale_items, get_sale_by_id
            full = get_sale_by_id(sale["id"])
            if full:
                sale = full
            items = get_sale_items(sale["id"])
            sale["items"] = items if items else []
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load items:\n{e}")
            return

        if not sale.get("items"):
            QMessageBox.warning(self, "No Items",
                                "No line items found for this invoice.\n"
                                "The receipt cannot be printed.")
            return

        # ── Build ReceiptData and send via printing_service.reprint ──────────
        try:
            import json
            from pathlib import Path
            from models.receipt import ReceiptData, Item
            from models.company_defaults import get_defaults
            from services.printing_service import printing_service

            co = get_defaults() or {}

            receipt = ReceiptData(
                doc_type            = "receipt",
                receiptType         = sale.get("receipt_type", "Invoice"),
                companyName         = co.get("company_name", ""),
                companyAddress      = co.get("address_1", ""),
                companyAddressLine1 = co.get("address_2", ""),
                companyEmail        = co.get("email", ""),
                tel                 = co.get("phone", ""),
                tin                 = co.get("tin_number", ""),
                vatNo               = co.get("vat_number", ""),
                deviceSerial        = co.get("zimra_serial_no", ""),
                deviceId            = co.get("zimra_device_id", ""),
                invoiceNo           = sale.get("invoice_no", ""),
                invoiceDate         = sale.get("invoice_date", "") or sale.get("date", ""),
                cashierName         = sale.get("cashier_name", ""),
                customerName        = sale.get("customer_name", "") or "Walk-in",
                customerContact     = sale.get("customer_contact", ""),
                grandTotal          = float(sale.get("total", 0)),
                subtotal            = float(sale.get("subtotal", 0) or sale.get("total", 0)),
                totalVat            = float(sale.get("total_vat", 0)),
                amountTendered      = float(sale.get("tendered", 0) or sale.get("total", 0)),
                change              = float(sale.get("change_amount", 0)),
                discAmt             = float(sale.get("discount_amount", 0)),
                paymentMode         = sale.get("method", "CASH"),
                currency            = sale.get("currency", "USD"),
                receiptHeader       = co.get("receipt_header", ""),
                footer              = co.get("footer_text", "Thank you for your purchase!"),
            )

            for it in sale["items"]:
                qty   = float(it.get("qty", 1))
                price = float(it.get("price", 0))
                amt   = float(it.get("total", 0) or qty * price)
                receipt.items.append(Item(
                    productName = it.get("product_name", "") or it.get("item_name", ""),
                    productid   = it.get("part_no", "") or it.get("item_code", ""),
                    qty         = qty,
                    price       = price,
                    amount      = amt,
                    tax_amount  = float(it.get("tax_amount", 0)),
                ))
            receipt.itemlist = receipt.items

            # Resolve printer from hardware settings
            hw_file  = Path("app_data/hardware_settings.json")
            printers = []
            try:
                with open(hw_file, "r", encoding="utf-8") as f:
                    hw = json.load(f)
                if hw.get("main_printer") and hw["main_printer"] != "(None)":
                    printers.append(hw["main_printer"])
            except Exception:
                pass

            if not printers:
                QMessageBox.warning(self, "No Printer",
                                    "No active printer configured in hardware settings.")
                return

            # Use printing_service.reprint so the REPRINT banner is stamped
            ok = False
            for p in printers:
                if printing_service.reprint(receipt, printer_name=p):
                    ok = True

            if ok:
                QMessageBox.information(self, "Reprint",
                                        f"Invoice {sale.get('invoice_no', '')} sent to printer.")
                self.accept()
            else:
                QMessageBox.warning(self, "Print Failed",
                                    "Could not send to printer. Check the printer connection.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not reprint:\n{e}")

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
    """Simple return dialog - click invoice → loads into cart for return."""

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
        self._existing_cns = set()  # Track which sales already have credit notes
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
            self._load_existing_credit_notes()
        except Exception:
            self._all_sales = []

    def _load_existing_credit_notes(self):
        """Load all sale IDs that already have credit notes."""
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT original_sale_id FROM credit_notes")
            rows = cur.fetchall()
            self._existing_cns = {row[0] for row in rows}
            conn.close()
        except Exception as e:
            print(f"Error loading existing credit notes: {e}")
            self._existing_cns = set()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 14)
        root.setSpacing(10)
        title = QLabel("Credit Note / Return")
        title.setStyleSheet(
            f"color:{NAVY}; font-size:15px; font-weight:bold; background:transparent;"
        )
        root.addWidget(title)
        row = QHBoxLayout()
        row.setSpacing(8)
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
        row.addWidget(lbl)
        row.addWidget(self._search, 1)
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
        
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        bc = QPushButton("Cancel")
        bc.setFixedHeight(32)
        bc.setFixedWidth(80)
        bc.setCursor(Qt.PointingHandCursor)
        bc.setFocusPolicy(Qt.NoFocus)
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
            self._ac.setFixedHeight(0)
            self.setFixedSize(600, 170)
            return
        
        ql = q.lower()
        matches = [
            s for s in self._all_sales
            if ql in (s.get("invoice_no") or "").lower()
            or ql in (s.get("frappe_ref") or "").lower()
            or ql in (s.get("customer_name") or "").lower()
        ][:15]
        
        if not matches:
            self._ac.setFixedHeight(0)
            self.setFixedSize(600, 170)
            return
        
        # Check for exact match - load immediately
        exact = [
            s for s in matches
            if (s.get("invoice_no") or "").lower() == ql
            or (s.get("frappe_ref") or "").lower() == ql
        ]
        if exact:
            self._load_and_close(exact[0])
            return
        
        if len(matches) == 1:
            self._load_and_close(matches[0])
            return
        
        # Show list for multiple matches
        for s in matches:
            # Check if already has credit note
            has_cn = s.get("id") in self._existing_cns
            frappe = s.get("frappe_ref") or ""
            label = (
                f"{s.get('invoice_no', '?')}"
                + (f"  [{frappe}]" if frappe else "")
                + f"   ·   {s.get('customer_name') or 'Walk-in'}"
                + f"   ·   ${float(s.get('total', 0)):.2f}"
                + f"   ·   {s.get('invoice_date', '')}"
            )
            if has_cn:
                label += "   RETURN ALREADY PROCESSED"

            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, s)
            if has_cn:
                it.setIcon(qta.icon("fa5s.exclamation-triangle", color="#e67e22"))
                it.setForeground(QColor(MUTED))
                it.setFlags(it.flags() & ~Qt.ItemIsSelectable)  # Disable selection
            self._ac.addItem(it)
        
        h = min(len(matches), 6) * 42
        self._ac.setFixedHeight(h)
        self.setFixedSize(600, 170 + h)

    def _pick(self, item: QListWidgetItem):
        sale = item.data(Qt.UserRole)
        if sale.get("id") in self._existing_cns:
            QMessageBox.warning(self, "Already Returned", 
                f"Invoice {sale.get('invoice_no', '')} already has a credit note.\n"
                "Cannot process another return for this invoice.")
            return
        self._load_and_close(sale)

    def _load_and_close(self, sale_stub: dict):
        sid = sale_stub["id"]
        
        # Double-check if already has credit note
        if sid in self._existing_cns:
            QMessageBox.warning(self, "Already Returned", 
                f"Invoice {sale_stub.get('invoice_no', '')} already has a credit note.\n"
                "Cannot process another return for this invoice.")
            return
        
        try:
            from models.sale import get_sale_by_id, get_sale_items
            full = get_sale_by_id(sid)
            if full and not full.get("items"):
                full["items"] = get_sale_items(sid)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load sale:\n{e}")
            return
        
        if not full:
            QMessageBox.warning(self, "Not Found", "Sale not found.")
            return
        
        if not full.get("items"):
            QMessageBox.warning(
                self, "No Items",
                f"No items found for {full.get('invoice_no', '')}."
            )
            return
        
        # Build items for return
        items_to_return = []
        for item in full.get("items", []):
            items_to_return.append({
                "part_no": item.get("part_no", ""),
                "product_name": item.get("product_name", ""),
                "qty": float(item.get("qty", 1)),
                "price": float(item.get("price", 0)),
                "total": float(item.get("total", 0)),
                "tax_amount": float(item.get("tax_amount", 0)),
                "tax_rate": float(item.get("tax_rate", 0)),
                "tax_type": item.get("tax_type", ""),
                "reason": "Customer Return"
            })
        
        try:
            self._existing_cns.add(sid)
            self.credit_note_ready.emit(full)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load items for return:\n{str(e)}")
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
        self.setWindowTitle("Advanced Printing & Receipt Settings")
        self.setWindowIcon(qta.icon("fa5s.print"))
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

        save_btn = navy_btn("Save & Apply", height=40, color=SUCCESS, hover=SUCCESS_H)
        save_btn.setIcon(qta.icon("fa5s.save", color="white"))
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
            size_sb = QSpinBox(); size_sb.setRange(6, 30); size_sb.setValue(max(6, int(size_val or 0)))
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
        self.sb_content_size.setValue(max(6, int(default.contentFontSize or 8)))
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
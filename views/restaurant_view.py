"""
views/restaurant_view.py
========================
Restaurant Order View — ERP style.
Dense, structured, data-first. Matches Havano POS system aesthetic.
"""

from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QLineEdit, QSizePolicy,
    QGraphicsDropShadowEffect, QDialog, QLayout
)
from PySide6.QtCore import Qt, Signal, QSize, QPoint, QRect
from PySide6.QtGui import QFont, QColor, QCursor

# ── ERP Palette ──────────────────────────────────────────────────────────────
BG          = "#ffffff"
WHITE       = "#ffffff"
SURFACE     = "#f4f5f7"          # page / panel fill
CARD_BG     = "#ffffff"
BORDER      = "#d1d5db"          # structural border
BORDER_LT   = "#e5e7eb"          # light separator
HDR_BG      = "#1e293b"          # dark navy header
HDR_TEXT    = "#f1f5f9"
ACCENT      = "#2563eb"          # blue accent
ACCENT_DIM  = "#1d4ed8"
ACCENT_SOFT = "#eff6ff"
TEXT        = "#111827"
TEXT_SEC    = "#6b7280"
TEXT_MUTED  = "#9ca3af"
SUCCESS     = "#16a34a"
SUCCESS_BG  = "#f0fdf4"
DANGER      = "#dc2626"
DANGER_BG   = "#fef2f2"
WARNING     = "#d97706"
ROW_ALT     = "#f9fafb"          # alternating table row
TAG_OPEN_BG = "#dbeafe"
TAG_OPEN_FG = "#1d4ed8"
TAG_PAID_BG = "#f3f4f6"
TAG_PAID_FG = "#6b7280"
# ─────────────────────────────────────────────────────────────────────────────


_GLOBAL_STYLE = f"""
    * {{
        font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
    }}
    QWidget {{
        background: {SURFACE};
        color: {TEXT};
    }}
    QScrollArea  {{ background: transparent; border: none; }}
    QScrollBar:vertical {{
        background: {SURFACE};
        width: 5px;
        border-radius: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER};
        border-radius: 2px;
        min-height: 24px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ height: 0; }}
    QLineEdit {{
        background: {BG};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 3px;
        padding: 6px 10px;
        font-size: 12px;
        selection-background-color: {ACCENT};
    }}
    QLineEdit:focus {{ border: 1.5px solid {ACCENT}; }}
    QLineEdit:hover {{ border-color: #93c5fd; }}
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _tag(text: str, bg: str, fg: str, bold: bool = True) -> QLabel:
    lbl = QLabel(text)
    weight = "700" if bold else "600"
    lbl.setStyleSheet(f"""
        background: {bg};
        color: {fg};
        font-size: 10px;
        font-weight: {weight};
        border-radius: 2px;
        padding: 2px 7px;
        letter-spacing: 0.4px;
    """)
    lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return lbl


def _divider(horizontal: bool = True) -> QFrame:
    d = QFrame()
    d.setFrameShape(QFrame.HLine if horizontal else QFrame.VLine)
    d.setStyleSheet(f"border: none; border-top: 1px solid {BORDER_LT};")
    d.setFixedHeight(1)
    return d


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(f"""
        font-size: 9px;
        font-weight: 700;
        color: {TEXT_MUTED};
        letter-spacing: 1px;
        padding: 0;
        margin-bottom: 2px;
    """)
    return lbl


# ── Flow Layout ──────────────────────────────────────────────────────────────

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, hSpacing=10, vSpacing=10):
        super().__init__(parent)
        self._items = []
        self._hSpace = hSpacing
        self._vSpace = vSpacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, index): return self._items[index] if 0 <= index < len(self._items) else None
    def takeAt(self, index): return self._items.pop(index) if 0 <= index < len(self._items) else None
    def expandingDirections(self): return Qt.Orientations()
    def hasHeightForWidth(self): return True
    def heightForWidth(self, width): return self.doLayout(QRect(0, 0, width, 0), True)
    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)
    def sizeHint(self): return self.minimumSize()
    def minimumSize(self):
        size = QSize()
        for item in self._items: size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size
    def doLayout(self, rect, testOnly):
        x, y, lineHeight = rect.x(), rect.y(), 0
        for item in self._items:
            nextX = x + item.sizeHint().width() + self._hSpace
            if nextX - self._hSpace > rect.right() and lineHeight > 0:
                x, y = rect.x(), y + lineHeight + self._vSpace
                nextX = x + item.sizeHint().width() + self._hSpace
                lineHeight = 0
            if not testOnly: item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x, lineHeight = nextX, max(lineHeight, item.sizeHint().height())
        return y + lineHeight - rect.y()

class FlowContainer(QWidget):
    """A container that dynamically updates its height for FlowLayout inside a QScrollArea."""
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.layout():
            self.setMinimumHeight(self.layout().heightForWidth(self.width()))

# ── Table Card ────────────────────────────────────────────────────────────────

class TableCard(QFrame):
    clicked = Signal(dict)

    def __init__(self, table_data: dict, parent=None):
        super().__init__(parent)
        self.data = table_data
        self.setFixedSize(176, 130)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("TableCard")

        occupied   = table_data.get("status") == "Occupied"
        accent_clr = DANGER  if occupied else SUCCESS
        accent_bg  = DANGER_BG if occupied else SUCCESS_BG
        status_txt = "OCCUPIED" if occupied else "AVAILABLE"
        left_strip = DANGER if occupied else "#d1d5db"

        self.setStyleSheet(f"""
            QFrame#TableCard {{
                background: {CARD_BG};
                border: 1px solid {BORDER};
                border-left: 3px solid {left_strip};
                border-radius: 0px;
            }}
            QFrame#TableCard:hover {{
                border: 1px solid {ACCENT};
                border-left: 3px solid {ACCENT};
                background: {ACCENT_SOFT};
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(0)

        # Status tag and current total
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        
        tag = _tag(status_txt, accent_bg, accent_clr)
        top_row.addWidget(tag)
        top_row.addStretch()
        
        if occupied and table_data.get("current_total", 0) > 0:
            amt_lbl = QLabel(f"${float(table_data['current_total']):.2f}")
            amt_lbl.setStyleSheet(f"""
                font-size: 13px;
                font-weight: 700;
                color: {DANGER};
            """)
            top_row.addWidget(amt_lbl)
            
        lay.addLayout(top_row)
        lay.addSpacing(7)

        # Table name
        name_lbl = QLabel(table_data["name"])
        name_lbl.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 700;
            color: {TEXT};
        """)
        name_lbl.setWordWrap(True)
        lay.addWidget(name_lbl)

        lay.addSpacing(2)

        # Table # · seats
        meta_lbl = QLabel(f"No. {table_data['table_number']}  ·  {table_data['capacity']} seats")
        meta_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_SEC};")
        lay.addWidget(meta_lbl)

        lay.addSpacing(6)

        # Floor label
        floor_lbl = QLabel(table_data["floor"])
        floor_lbl.setStyleSheet(f"""
            font-size: 10px;
            font-weight: 600;
            color: {TEXT_MUTED};
        """)
        lay.addWidget(floor_lbl, alignment=Qt.AlignLeft)
        lay.addStretch()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.data)
        super().mousePressEvent(event)


# ── Table Action Dialog ───────────────────────────────────────────────────────

class TableActionDialog(QDialog):
    def __init__(self, table_data: dict, parent=None):
        super().__init__(parent)
        self.table_data = table_data
        self.action = None  # 'add', 'pay', 'view', 'pay_all'
        
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setModal(True)
        self.setFixedSize(240, 310)
        
        # Apply shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

        self.setStyleSheet(f"""
            QDialog {{
                background: #ffffff;
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
            QPushButton {{
                background: transparent;
                color: {TEXT};
                border: none;
                border-radius: 6px;
                padding: 12px 16px;
                text-align: left;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {ACCENT_SOFT};
                color: {ACCENT};
            }}
            QLabel#Title {{
                font-size: 14px;
                font-weight: 800;
                color: {TEXT};
                padding: 12px 16px 4px 16px;
            }}
            QLabel#Subtitle {{
                font-size: 11px;
                color: {TEXT_MUTED};
                padding: 0 16px 8px 16px;
            }}
        """)
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(2)
        
        title = QLabel(f"Table {table_data['table_number']}")
        title.setObjectName("Title")
        lay.addWidget(title)
        
        subtitle = QLabel(table_data.get("name", "Restaurant Table"))
        subtitle.setObjectName("Subtitle")
        lay.addWidget(subtitle)
        
        lay.addWidget(_divider())
        lay.addSpacing(4)
        
        btn_add = QPushButton("ADD ORDER")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(f"background: {ACCENT}; color: white; font-weight: 700;")
        btn_add.clicked.connect(lambda: self._set_action('add'))
        lay.addWidget(btn_add)

        btn_pay = QPushButton("CLOSE TABLE")
        btn_pay.setCursor(Qt.PointingHandCursor)
        btn_pay.setStyleSheet(f"background: {SUCCESS}; color: white; font-weight: 700;")
        btn_pay.clicked.connect(lambda: self._set_action('pay_all'))
        lay.addWidget(btn_pay)

        btn_view = QPushButton("VIEW ALL ORDERS")
        btn_view.setCursor(Qt.PointingHandCursor)
        btn_view.clicked.connect(lambda: self._set_action('view'))
        lay.addWidget(btn_view)

        lay.addSpacing(4)
        lay.addWidget(_divider())
        lay.addSpacing(4)

        btn_prebill = QPushButton("PRE-BILL")
        btn_prebill.setCursor(Qt.PointingHandCursor)
        btn_prebill.setStyleSheet(f"color: {TEXT_SEC}; font-weight: 500;")
        btn_prebill.clicked.connect(lambda: self._set_action('prebill'))
        lay.addWidget(btn_prebill)
        
        lay.addSpacing(4)
        lay.addWidget(_divider())
        lay.addSpacing(4)
        
        btn_cancel = QPushButton("Dismiss")
        btn_cancel.setStyleSheet(f"color: {TEXT_SEC}; font-weight: 500;")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        lay.addWidget(btn_cancel)

    def _set_action(self, action: str):
        self.action = action
        self.accept()


# ── KOT Action Dialog ─────────────────────────────────────────────────────────

class KOTActionDialog(QDialog):
    def __init__(self, order_data: dict, parent=None):
        super().__init__(parent)
        self.order_data = order_data
        self.action = None  # 'edit', 'cancel', 'pay'
        
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setModal(True)
        self.setFixedSize(250, 320)
        
        # Apply shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

        self.setStyleSheet(f"""
            QDialog {{
                background: #ffffff;
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
            QPushButton {{
                background: transparent;
                color: {TEXT};
                border: none;
                border-radius: 8px;
                padding: 12px 16px;
                text-align: center;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton#btnEdit {{
                background: {ACCENT};
                color: white;
            }}
            QPushButton#btnEdit:hover {{
                background: {ACCENT_DIM};
            }}
            QPushButton#btnCancel {{
                background: transparent;
                color: {DANGER};
                border: 1px solid {DANGER};
            }}
            QPushButton#btnCancel:hover {{
                background: {DANGER_BG};
            }}
            QPushButton#btnPay {{
                background: {SUCCESS};
                color: white;
            }}
            QPushButton#btnPay:hover {{
                background: #15803d;
            }}
            QPushButton#btnClose {{
                color: {TEXT_SEC};
                font-weight: 600;
            }}
            QPushButton#btnClose:hover {{
                background: {ROW_ALT};
                color: {TEXT};
            }}
            QLabel#Title {{
                font-size: 16px;
                font-weight: 800;
                color: {TEXT};
                padding: 14px 16px 2px 16px;
            }}
            QLabel#Subtitle {{
                font-size: 12px;
                color: {TEXT_MUTED};
                padding: 0 16px 10px 16px;
            }}
        """)
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(6)
        
        title = QLabel(f"Order #ORD-{order_data['id']}")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)
        
        subtitle = QLabel(f"{order_data.get('table_name', 'Table')} · {order_data.get('customer_name', 'Guest')}")
        subtitle.setObjectName("Subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        lay.addWidget(subtitle)
        
        lay.addWidget(_divider())
        lay.addSpacing(6)
        
        # Touch-friendly buttons
        btn_edit = QPushButton("EDIT KOT")
        btn_edit.setObjectName("btnEdit")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.clicked.connect(lambda: self._set_action('edit'))
        lay.addWidget(btn_edit)

        btn_pay_kot = QPushButton("PAY KOT")
        btn_pay_kot.setObjectName("btnPay")
        btn_pay_kot.setCursor(Qt.PointingHandCursor)
        btn_pay_kot.clicked.connect(lambda: self._set_action('pay'))
        lay.addWidget(btn_pay_kot)

        btn_cancel = QPushButton("CANCEL KOT")
        btn_cancel.setObjectName("btnCancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(lambda: self._set_action('cancel'))
        lay.addWidget(btn_cancel)

        lay.addSpacing(4)
        
        btn_close = QPushButton("Dismiss")
        btn_close.setObjectName("btnClose")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        lay.addWidget(btn_close)

    def _set_action(self, action: str):
        self.action = action
        self.accept()


# ── Floor Legend ──────────────────────────────────────────────────────────────

class _Legend(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: transparent;")
        hl = QHBoxLayout(self)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(16)

        for clr, label in [(SUCCESS, "Available"), (DANGER, "Occupied"), (ACCENT, "Selected")]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {clr}; font-size: 12px;")
            txt = QLabel(label)
            txt.setStyleSheet(f"font-size: 11px; color: {TEXT_SEC};")
            hl.addWidget(dot)
            hl.addWidget(txt)

        hl.addStretch()


# ── Orders Sidebar ────────────────────────────────────────────────────────────

class _OrdersPanel(QFrame):
    order_action = Signal(str, dict) # action_name, order_data

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_table_filter: dict | None = None
        self.setFixedWidth(320)
        self.setObjectName("OrdersPanel")
        self.setStyleSheet(f"""
            QFrame#OrdersPanel {{
                background: {CARD_BG};
                border: 1px solid {BORDER};
                border-radius: 4px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Panel header ─────────────────────────────────────────────────
        phdr = QFrame()
        phdr.setFixedHeight(40)
        phdr.setStyleSheet(f"""
            background: {SURFACE};
            border-bottom: 1px solid {BORDER};
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        """)
        phdr_lay = QHBoxLayout(phdr)
        phdr_lay.setContentsMargins(14, 0, 14, 0)

        title = QLabel("Order History")
        title.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {TEXT}; background: transparent;")
        phdr_lay.addWidget(title)
        phdr_lay.addStretch()
        root.addWidget(phdr)

        # ── Filter strip ─────────────────────────────────────────────────
        fstrip = QFrame()
        fstrip.setStyleSheet(f"background: {BG}; border-bottom: 1px solid {BORDER_LT};")
        fs_lay = QVBoxLayout(fstrip)
        fs_lay.setContentsMargins(12, 10, 12, 10)
        fs_lay.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search table or guest…")
        self.search.textChanged.connect(self._apply_filter)
        fs_lay.addWidget(self.search)

        tab_row = QHBoxLayout()
        tab_row.setSpacing(4)
        self._current_filter = "All"
        self._filter_btns: dict[str, QPushButton] = {}

        for lbl in ("All", "Open", "Paid"):
            btn = QPushButton(lbl)
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {SURFACE};
                    color: {TEXT_SEC};
                    border: 1px solid {BORDER};
                    border-radius: 0px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0 14px;
                }}
                QPushButton:checked {{
                    background: {ACCENT};
                    color: #ffffff;
                    border-color: {ACCENT_DIM};
                }}
                QPushButton:hover:!checked {{
                    background: {ACCENT_SOFT};
                    border-color: {ACCENT};
                    color: {ACCENT};
                }}
            """)
            btn.clicked.connect(lambda _, l=lbl: self._set_filter(l))
            tab_row.addWidget(btn)
            self._filter_btns[lbl] = btn

        self._filter_btns["All"].setChecked(True)
        tab_row.addStretch()
        fs_lay.addLayout(tab_row)
        root.addWidget(fstrip)

        # ── Scrollable orders list ────────────────────────────────────────
        self._all_orders: list[dict] = []
        self._orders_container = QWidget()
        self._orders_container.setStyleSheet("background: transparent;")
        self._orders_layout = QVBoxLayout(self._orders_container)
        self._orders_layout.setContentsMargins(0, 0, 0, 0)
        self._orders_layout.setSpacing(0)
        self._orders_layout.setAlignment(Qt.AlignTop)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self._orders_container)
        root.addWidget(scroll, 1)

    # ── Public ────────────────────────────────────────────────────────────

    def load(self, orders: list[dict]):
        self._all_orders = orders
        self._apply_filter()

    # ── Internal ──────────────────────────────────────────────────────────

    def _set_filter(self, text: str):
        self._current_filter = text
        for lbl, btn in self._filter_btns.items():
            btn.setChecked(lbl == text)
        self._apply_filter()

    def view_table_orders(self, table_data: dict | None):
        if self._active_table_filter == table_data:
            # Toggle off if clicked again
            self._active_table_filter = None
            self.search.setPlaceholderText("Search table or guest…")
        else:
            self._active_table_filter = table_data
            if table_data:
                self.search.setPlaceholderText(f"Filtered to Table {table_data.get('table_number')} ({table_data.get('floor')})")
        self.search.clear()
        self._apply_filter()

    def _apply_filter(self):
        while self._orders_layout.count():
            child = self._orders_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        query = self.search.text().lower()
        filtered: list[dict] = []

        for o in self._all_orders:
            eff = "Open" if o["status"] in ("Open", "Ordered") else o["status"]
            if self._current_filter == "Open"  and eff != "Open":  continue
            if self._current_filter == "Paid"  and eff != "Paid":  continue
            
            # Substring match if set
            if query and query not in f"{o.get('table_name','')} {o.get('table_number','')} {o.get('customer_name','')}".lower():
                continue
                
            # Exact Floor+Number match if active table filter is applied
            if self._active_table_filter:
                ft = self._active_table_filter
                # The incoming dictionaries might have integers or strings, so cast to string safely 
                if (str(o.get('table_number', '')) != str(ft.get('table_number', '')) or
                    str(o.get('floor', '')).lower() != str(ft.get('floor', '')).lower()):
                    continue
            
            o["_eff"] = eff
            filtered.append(o)

        if not filtered:
            empty = QLabel("No orders found.\nClear filters or view all.")
            empty.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; font-style: italic; padding: 24px;")
            empty.setAlignment(Qt.AlignCenter)
            self._orders_layout.addWidget(empty)
            return

        for idx, o in enumerate(filtered):
            is_open = o.get("_eff") == "Open"
            row = self._make_order_row(o, is_open, idx)
            self._orders_layout.addWidget(row)
            self._orders_layout.addWidget(_divider())

    def _make_order_row(self, o: dict, is_open: bool, idx: int) -> QFrame:
        row_bg = BG if idx % 2 == 0 else ROW_ALT
        card   = QFrame()
        card.setObjectName("ORow")
        card.setStyleSheet(f"""
            QFrame#ORow {{
                background: {row_bg};
                border: none;
                border-left: 3px solid {"" + (ACCENT if is_open else BORDER_LT)};
            }}
            QFrame#ORow:hover {{
                background: {ACCENT_SOFT};
                border-left-color: {ACCENT};
            }}
        """)
        card.setCursor(Qt.PointingHandCursor)
        card.mousePressEvent = lambda e: self._on_row_clicked(e, o)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)

        # Row 1: table name + status tag
        r1 = QHBoxLayout()
        r1.setSpacing(6)

        ord_id_lbl = QLabel(f"#ORD-{o['id']}")
        ord_id_lbl.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {HDR_BG}; background: transparent;")
        r1.addWidget(ord_id_lbl)
        r1.addStretch()

        tag = _tag(
            "OPEN" if is_open else "PAID",
            TAG_OPEN_BG if is_open else TAG_PAID_BG,
            TAG_OPEN_FG if is_open else TAG_PAID_FG,
        )
        r1.addWidget(tag)
        lay.addLayout(r1)

        # Row 2: table info
        r2 = QLabel(f"{o['table_name']}  ({o['table_number']})")
        r2.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {TEXT_SEC}; background: transparent;")
        lay.addWidget(r2)

        # Row 3: guest
        r3 = QLabel(f"Guest: {o['customer_name']}")
        r3.setStyleSheet(f"font-size: 11px; color: {TEXT_SEC}; background: transparent;")
        lay.addWidget(r3)

        # Row 3: timestamp
        time_str = (
            o["created_at"].strftime("%d/%m/%Y  %H:%M")
            if hasattr(o["created_at"], "strftime")
            else str(o["created_at"])[:16]
        )
        r3 = QLabel(time_str)
        r3.setStyleSheet(f"font-size: 10px; color: {TEXT_MUTED}; background: transparent;")
        lay.addWidget(r3)

        # Order items block
        try:
            from models.restaurant_order import get_order_items
            items = get_order_items(o["id"])
            if items:
                lay.addWidget(_divider())

                total = 0.0
                for oi in items:
                    qty   = float(oi.get("qty", 1))
                    price = float(oi.get("price", 0))
                    line  = qty * price
                    total += line

                    ir = QHBoxLayout()
                    ir.setSpacing(0)
                    il = QLabel(f"{oi['item_name']} × {qty:.4g}")
                    il.setStyleSheet(f"font-size: 11px; color: {TEXT}; background: transparent;")
                    ip = QLabel(f"${line:.2f}")
                    ip.setStyleSheet(f"font-size: 11px; color: {TEXT}; background: transparent;")
                    ip.setAlignment(Qt.AlignRight)
                    ir.addWidget(il)
                    ir.addWidget(ip)
                    lay.addLayout(ir)

                # Total
                tr = QHBoxLayout()
                tl = QLabel("Total")
                tl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {ACCENT}; background: transparent;")
                tv = QLabel(f"${total:.2f}")
                tv.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {ACCENT}; background: transparent;")
                tv.setAlignment(Qt.AlignRight)
                tr.addWidget(tl)
                tr.addWidget(tv)
                lay.addLayout(tr)
        except Exception:
            pass

        return card

    def _on_row_clicked(self, event, order_data: dict):
        if event.button() == Qt.LeftButton:
            dlg = KOTActionDialog(order_data, self)
            dlg.move(QCursor.pos().x() - 110, QCursor.pos().y() - 100)
            if dlg.exec() == QDialog.Accepted:
                self.order_action.emit(dlg.action, order_data)


# ── Main View ─────────────────────────────────────────────────────────────────

class OrderView(QWidget):
    back_to_pos      = Signal()
    table_selected   = Signal(dict)  # Legacy/Available tables
    action_add_order = Signal(dict)  # Append mode
    action_pay_order = Signal(dict)  # Pay mode (All or Single)
    action_edit_kot  = Signal(dict)  # Edit specific order
    action_cancel_kot = Signal(int)  # Cancel specific order ID
    action_pay_all   = Signal(dict)  # Pay combined orders

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_GLOBAL_STYLE)
        self._status_filter = "All"
        self._build()

    def showEvent(self, event):
        super().showEvent(event)
        self._current_floor = "All"
        self._status_filter = "All"
        if hasattr(self, "_panel"):
            self._panel._current_filter = "All"
            self._panel.search.clear()
        if hasattr(self, "table_search"):
            self.table_search.clear()
        self.refresh()

    def _handle_table_click(self, td: dict):
        if td.get("status") == "Occupied":
            dlg = TableActionDialog(td, self)
            
            # Position smartly near center of the card
            from PySide6.QtCore import QPoint
            widget = self.sender()
            if isinstance(widget, QWidget):
                g_pos = widget.mapToGlobal(QPoint(0, 0))
                # Center the dialog on the table card
                dlg.move(
                    g_pos.x() + (widget.width() - dlg.width()) // 2,
                    g_pos.y() + (widget.height() - dlg.height()) // 2
                )
            else:
                from PySide6.QtGui import QCursor
                cursor_pos = QCursor.pos()
                dlg.move(cursor_pos.x() - 110, cursor_pos.y() - 10)
            
            dlg.exec()
            if dlg.action == "add":
                self.action_add_order.emit(td)
            elif dlg.action == "pay_all":
                self.action_pay_all.emit(td)
            elif dlg.action == "view":
                self._panel.view_table_orders(td)
            elif dlg.action == "prebill":
                self._print_prebill(td)
        else:
            self.table_selected.emit(td)
    def _print_prebill(self, table_data: dict):
        """Aggregate all open KOTs for the table and print a pre-bill."""
        from models.restaurant_order import get_orders_for_table, get_order_items
        from PySide6.QtWidgets import QMessageBox
        from datetime import datetime
        
        table_id = table_data.get("id")
        orders = get_orders_for_table(table_id)
        
        if not orders:
            QMessageBox.information(self, "Pre-Bill", "No open orders found for this table.")
            return

        all_items = []
        for o in orders:
            items = get_order_items(o["id"])
            all_items.extend(items)

        if not all_items:
            QMessageBox.information(self, "Pre-Bill", "No items found in the current orders.")
            return

        # Prepare receipt data
        from models.receipt import ReceiptData, Item
        from models.company_defaults import get_defaults
        
        co = get_defaults() or {}
        
        receipt = ReceiptData()
        receipt.companyName = co.get("company_name", "Havano POS")
        receipt.companyLogoPath = co.get("logo_path", "")
        receipt.companyAddress = co.get("address", "")
        receipt.tel = co.get("phone", "")
        receipt.tin = co.get("tin", "")
        receipt.vatNo = co.get("vat_no", "")
        
        receipt.receiptHeader = "*** PRE-BILL ***"
        receipt.invoiceNo = f"Table {table_data.get('table_number')}"
        receipt.invoiceDate = datetime.now().strftime("%Y-%m-%d")
        receipt.customerName = orders[0].get("customer_name") if orders else "Guest"
        
        # Aggregate items by product_id/item_code to consolidate duplicates
        aggregated = {}
        for it in all_items:
            key = it.get("product_id") or it.get("item_code")
            if key in aggregated:
                aggregated[key].qty += it.get("qty", 0)
                aggregated[key].amount = aggregated[key].qty * aggregated[key].price
            else:
                aggregated[key] = Item(
                    productName=it.get("item_name", ""),
                    productid=str(it.get("product_id", "")),
                    qty=it.get("qty", 0),
                    price=it.get("price", 0),
                    amount=it.get("qty", 0) * it.get("price", 0)
                )
        
        receipt.items = list(aggregated.values())
        receipt.grandTotal = sum(i.amount for i in receipt.items)
        receipt.footer = "This is a pre-bill, not a tax invoice."

        # Print using the printing service
        try:
            from services.printing_service import PrintingService
            ps = PrintingService()
            # Get default printer from settings if possible, or use None
            from models.advance_settings import AdvanceSettings
            settings = AdvanceSettings.load_from_file()
            printer_name = getattr(settings, "invoicePrinter", None)
            
            if ps.print_invoice_receipt(receipt, printer_name=printer_name):
                QMessageBox.information(self, "Pre-Bill", "Pre-bill sent to printer.")
            else:
                QMessageBox.warning(self, "Print Failed", "Could not print the pre-bill.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to print pre-bill: {e}")

    def _handle_order_action(self, action: str, order_data: dict):
        if action == "edit":
            self.action_edit_kot.emit(order_data)
        elif action == "pay":
            self.action_pay_order.emit(order_data)
        elif action == "cancel":
            self.action_cancel_kot.emit(order_data["id"])

    # ── Construction ─────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_toolbar())
        root.addWidget(self._build_body(), 1)

    def _build_header(self) -> QFrame:
        hdr = QFrame()
        hdr.setFixedHeight(52)
        hdr.setObjectName("MainHeader")
        hdr.setStyleSheet(f"""
            QFrame#MainHeader {{
                background: {HDR_BG};
                border-bottom: 1px solid #334155;
            }}
        """)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 0, 24, 0)
        hl.setSpacing(12)

        # # Module label
        # mod_lbl = QLabel("RESTAURANT")
        # mod_lbl.setStyleSheet(f"""
        #     font-size: 10px;
        #     font-weight: 700;
        #     color: #64748b;
        #     letter-spacing: 1.5px;
        #     background: transparent;
        # """)
        # hl.addWidget(mod_lbl)

        # sep = QLabel("|")
        # sep.setStyleSheet(f"color: #334155; font-size: 14px; background: transparent;")
        # hl.addWidget(sep)

        title = QLabel("Floor Management")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {HDR_TEXT}; background: transparent;")
        hl.addWidget(title)
        
        # Move floor layout toggle buttons into this header
        hl.addSpacing(24)
        self._floor_btns_lay = QHBoxLayout()
        self._floor_btns_lay.setSpacing(4)
        hl.addLayout(self._floor_btns_lay)
        
        hl.addStretch()

        back_btn = QPushButton("← Back to POS")
        back_btn.setFixedHeight(30)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 3px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background: #334155;
                color: {HDR_TEXT};
                border-color: #475569;
            }}
            QPushButton:pressed {{
                background: #1e293b;
            }}
        """)
        back_btn.clicked.connect(self.back_to_pos.emit)
        hl.addWidget(back_btn)

        return hdr

    def _build_toolbar(self) -> QFrame:
        tb = QFrame()
        tb.setFixedHeight(44)
        tb.setStyleSheet(f"""
            background: {BG};
            border-bottom: 1px solid {BORDER};
        """)
        hl = QHBoxLayout(tb)
        hl.setContentsMargins(24, 0, 24, 0)
        hl.setSpacing(20)

        # Stats chips
        self._stat_total   = self._stat_chip("Total Tables", "—", action=lambda: self._set_status_filter("All"))
        self._stat_avail   = self._stat_chip("Available",    "—", SUCCESS, action=lambda: self._set_status_filter("Available"))
        self._stat_occup   = self._stat_chip("Occupied",     "—", DANGER,  action=lambda: self._set_status_filter("Occupied"))
        for chip in (self._stat_total, self._stat_avail, self._stat_occup):
            hl.addWidget(chip)

        vd = QFrame(); vd.setFrameShape(QFrame.VLine)
        vd.setStyleSheet(f"border: none; border-left: 1px solid {BORDER_LT}; margin: 8px 0;")
        vd.setFixedWidth(1); hl.addWidget(vd)

        vd2 = QFrame(); vd2.setFrameShape(QFrame.VLine)
        vd2.setStyleSheet(f"border: none; border-left: 1px solid {BORDER_LT}; margin: 8px 0;")
        vd2.setFixedWidth(1); hl.addWidget(vd2)

        # Legend inline
        for clr, lbl in ((SUCCESS, "Available"), (DANGER, "Occupied")):
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {clr}; font-size: 11px; background: transparent;")
            txt = QLabel(lbl)
            txt.setStyleSheet(f"font-size: 11px; color: {TEXT_SEC}; background: transparent;")
            hl.addWidget(dot)
            hl.addWidget(txt)

        hl.addStretch()

        # Table Search
        self.table_search = QLineEdit()
        self.table_search.setPlaceholderText("🔍  Search tables...")
        self.table_search.setFixedWidth(220)
        self.table_search.setFixedHeight(28)
        self.table_search.setStyleSheet(f"""
            QLineEdit {{
                background: {WHITE};
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 0 10px;
                font-size: 11px;
                color: {TEXT};
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        self.table_search.textChanged.connect(lambda: self.refresh())
        hl.addWidget(self.table_search)

        hl.addSpacing(10)

        refresh_btn = QPushButton("↻  Refresh")
        refresh_btn.setFixedHeight(28)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT_SOFT};
                color: {ACCENT};
                border: 1px solid #bfdbfe;
                border-radius: 3px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 14px;
            }}
            QPushButton:hover  {{ background: #dbeafe; border-color: {ACCENT}; }}
            QPushButton:pressed {{ background: #bfdbfe; }}
        """)
        refresh_btn.clicked.connect(self.refresh)
        hl.addWidget(refresh_btn)

        return tb

    def _stat_chip(self, label: str, value: str, clr: str = TEXT_SEC, action=None) -> QPushButton:
        btn = QPushButton()
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(32)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 0px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: {ACCENT_SOFT};
                border-color: {ACCENT};
            }}
        """)
        
        hl = QHBoxLayout(btn)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(6)

        lbl = QLabel(label + ":")
        lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;")
        val = QLabel(value)
        val.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {clr}; background: transparent;")
        val.setObjectName(f"stat_{label.replace(' ', '_')}")

        hl.addWidget(lbl)
        hl.addWidget(val)
        
        if action:
            btn.clicked.connect(action)
            
        return btn

    def _set_status_filter(self, filter_name: str):
        self._status_filter = filter_name
        
        # Highlight active chip
        for chip, name in [
            (self._stat_total, "All"),
            (self._stat_avail, "Available"),
            (self._stat_occup, "Occupied")
        ]:
            is_active = (self._status_filter == name)
            chip.setStyleSheet(f"""
                QPushButton {{
                    background: {ACCENT_SOFT if is_active else "transparent"};
                    border: 1px solid {ACCENT if is_active else "transparent"};
                    border-radius: 0px;
                    padding: 0 12px;
                }}
                QPushButton:hover {{
                    background: {ACCENT_SOFT};
                    border-color: {ACCENT};
                }}
            """)
            
        self.refresh()

    def _build_body(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet(f"background: {SURFACE};")
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Main Content
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(24, 20, 24, 20); body_lay.setSpacing(20)

        grid_panel = QFrame(); grid_panel.setObjectName("GridPanel")
        grid_panel.setStyleSheet(f"QFrame#GridPanel {{ background:{CARD_BG}; border:1px solid {BORDER}; border-radius:0px; }}")
        gp_lay = QVBoxLayout(grid_panel); gp_lay.setContentsMargins(0,0,0,0); gp_lay.setSpacing(0)
        
        grid_container = FlowContainer()
        grid_container.setStyleSheet("background: transparent;")
        self.grid = FlowLayout(grid_container, margin=16, hSpacing=12, vSpacing=12)
        
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame); scroll.setWidget(grid_container)
        gp_lay.addWidget(scroll, 1)
        body_lay.addWidget(grid_panel, 3)

        self._panel = _OrdersPanel(); self._panel.order_action.connect(self._handle_order_action)
        body_lay.addWidget(self._panel, 0)
        root.addWidget(body, 1)
        return container

    # -- Public API --

    def refresh(self):
        """Reload tables and orders from the model layer."""
        while self.grid.count():
            child = self.grid.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        from models.restaurant_order import get_all_tables, get_recent_orders, get_all_floors
        tables = get_all_tables()

        if not hasattr(self, "_current_floor"): self._current_floor = "All"
        try:
            db_floors = get_all_floors()
            floors = ["All"] + [f["name"] for f in db_floors]
        except Exception:
            floors = sorted(list(set(t.get("floor", "Main") for t in tables)))
            floors = ["All"] + floors
            
        while self._floor_btns_lay.count():
            child = self._floor_btns_lay.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        for fl in floors:
            is_active = (fl == self._current_floor)
            btn = QPushButton(fl.upper())
            btn.setCheckable(True); btn.setChecked(is_active)
            btn.setFixedHeight(42); btn.setCursor(Qt.PointingHandCursor)
            bg  = ACCENT   if is_active else SURFACE
            fg  = WHITE    if is_active else TEXT_SEC
            brd = ACCENT   if is_active else BORDER
            btn.setStyleSheet(f"QPushButton {{ background:{bg}; color:{fg}; border:1px solid {brd}; border-radius:6px; font-size:12px; font-weight:800; padding:0 24px; }}")
            btn.clicked.connect(lambda _, f=fl: self._set_floor_filter(f))
            self._floor_btns_lay.addWidget(btn)

        occupied = sum(1 for t in tables if t.get("status") == "Occupied")
        avail    = len(tables) - occupied
        for chip, val, clr in [(self._stat_total, str(len(tables)), TEXT_SEC), (self._stat_avail, str(avail), SUCCESS), (self._stat_occup, str(occupied), DANGER)]:
            for w in chip.findChildren(QLabel):
                if not w.text().endswith(":"):
                    w.setText(val); w.setStyleSheet(f"font-size:12px; font-weight:700; color:{clr}; background:transparent;")
                    break

        query = self.table_search.text().lower() if hasattr(self, "table_search") else ""
        st_f = getattr(self, "_status_filter", "All")
        fl_f = self._current_floor
        filtered = []
        for t in tables:
            if fl_f != "All" and t.get("floor") != fl_f: continue
            ts = t.get("status", "Available")
            if st_f == "Available" and ts != "Available": continue
            if st_f == "Occupied" and ts != "Occupied": continue
            if query and query not in f"{t['name']} {t['table_number']}".lower(): continue
            filtered.append(t)
        for t in filtered:
            card = TableCard(t); card.clicked.connect(self._handle_table_click)
            self.grid.addWidget(card)
        self._panel.load(get_recent_orders())

    def _set_floor_filter(self, floor_name: str):
        self._current_floor = floor_name
        self.refresh()

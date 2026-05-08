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
    QGraphicsDropShadowEffect, QDialog, QLayout, QMessageBox,
    QDoubleSpinBox, QComboBox
)
from PySide6.QtCore import Qt, Signal, QSize, QPoint, QRect, QTimer
from PySide6.QtGui import QFont, QColor, QCursor, QDoubleValidator

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
ORANGE      = "#c05a00"
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


def _format_elapsed(opened_at) -> str:
    """Return human-readable elapsed time: Xm / Xh Ym / Xd Yh"""
    if not opened_at:
        return ""
    try:
        from datetime import datetime
        if isinstance(opened_at, str):
            opened_at = datetime.fromisoformat(opened_at)
        delta = datetime.now() - opened_at
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            return ""
        minutes = total_seconds // 60
        hours   = minutes // 60
        days    = hours   // 24
        if days >= 1:
            return f"{days}d {hours % 24}h"
        if hours >= 1:
            return f"{hours}h {minutes % 60}m"
        return f"{minutes}m"
    except Exception:
        return ""


def _aging_color(opened_at) -> str:
    """
    Return a color string based on how long the table has been open:
      < 30 min  → green  (fresh)
      30–60 min → amber  (getting old)
      > 60 min  → red    (overdue)
    Returns empty string if opened_at is None/invalid.
    """
    if not opened_at:
        return ""
    try:
        from datetime import datetime
        if isinstance(opened_at, str):
            opened_at = datetime.fromisoformat(opened_at)
        delta   = datetime.now() - opened_at
        minutes = int(delta.total_seconds()) // 60
        if minutes < 0:
            return ""
        if minutes < 30:
            return SUCCESS        # green  — fresh
        if minutes < 60:
            return WARNING        # amber  — getting long
        return DANGER             # red    — overdue
    except Exception:
        return ""


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

        # Row 1: status tag (left) + aging time (right, admin only)
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        tag_widget = _tag(
            "OCCUPIED" if occupied else "AVAILABLE",
            "#fef2f2" if occupied else "#f0fdf4",
            "#dc2626" if occupied else "#16a34a",
        )
        top_row.addWidget(tag_widget)
        top_row.addStretch()

        if occupied:
            age_ts    = table_data.get("last_order_at") or table_data.get("opened_at")
            elapsed   = _format_elapsed(age_ts)
            aging_clr = _aging_color(age_ts)
            if elapsed and aging_clr:
                t_lbl = QLabel(elapsed)
                t_lbl.setStyleSheet(
                    f"font-size: 10px; font-weight: 700; color: {aging_clr}; background: transparent;"
                )
                top_row.addWidget(t_lbl)

        lay.addLayout(top_row)
        lay.addSpacing(5)

        name_lbl = QLabel(table_data["name"])
        name_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #111827;")
        name_lbl.setWordWrap(True)
        lay.addWidget(name_lbl)
        lay.addSpacing(2)

        meta_lbl = QLabel(f"No. {table_data['table_number']}  ·  {table_data['capacity']} seats")
        meta_lbl.setStyleSheet("font-size: 11px; color: #6b7280;")
        lay.addWidget(meta_lbl)
        lay.addSpacing(4)

        # Waiter row: name left, amount right
        if occupied:
            waiter_name = table_data.get("_waiter_name", "")
            if not waiter_name and table_data.get("active_waiter_id"):
                try:
                    from models.restaurant_order import get_waiter_name
                    waiter_name = get_waiter_name(table_data.get("active_waiter_id"))
                except Exception:
                    pass
            waiter_row = QHBoxLayout()
            waiter_row.setContentsMargins(0, 0, 0, 0)
            if waiter_name:
                w_lbl = QLabel(waiter_name)
                w_lbl.setStyleSheet("font-size: 10px; color: #2563eb; font-weight: 600; background: transparent;")
                waiter_row.addWidget(w_lbl)
            waiter_row.addStretch()
            if table_data.get("current_total", 0) > 0:
                amt_lbl = QLabel(f"${float(table_data['current_total']):.2f}")
                amt_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #dc2626; background: transparent;")
                waiter_row.addWidget(amt_lbl)
            lay.addLayout(waiter_row)

        lay.addSpacing(3)
        floor_lbl = QLabel(table_data["floor"])
        floor_lbl.setStyleSheet("font-size: 10px; font-weight: 600; color: #9ca3af;")
        lay.addWidget(floor_lbl, alignment=Qt.AlignLeft)
        lay.addStretch()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            # Check if we are still alive before emitting
            try:
                self.clicked.emit(self.data)
            except RuntimeError:
                pass


# ── Bill Collect Dialog ───────────────────────────────────────────────────────

class BillCollectDialog(QDialog):
    """
    Small popup to record each person's share (MOP + amount) against a table.
    Saves to restaurant_bill_splits. No payment is triggered here at all.
    When CLOSE TABLE is used later, the saved splits auto-populate PaymentDialog.
    """

    def __init__(self, table_data: dict, bill_total: float, parent=None):
        super().__init__(parent)
        self.table_data  = table_data
        self.table_id    = table_data["id"]
        self.bill_total  = bill_total

        self.setWindowTitle("Collect Shares")
        self.setMinimumWidth(520)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog   {{ background: {BG}; font-family: 'Segoe UI', sans-serif; }}
            QLabel    {{ background: transparent; color: {TEXT}; }}
            QLineEdit {{ background: {BG}; border: 1px solid {BORDER};
                        border-radius: 4px; padding: 4px 8px;
                        font-size: 13px; color: {TEXT}; }}
            QLineEdit:focus {{ border: 1.5px solid {ACCENT}; }}
            QPushButton {{ border-radius: 6px; font-size: 12px;
                           font-weight: 700; padding: 0 14px; }}
        """)

        # Load MOPs
        self._methods: list[dict] = []
        try:
            from views.dialogs.payment_dialog import _load_payment_methods
            from models.company_defaults import get_defaults
            co = (get_defaults() or {}).get("company_name", "")
            self._methods = _load_payment_methods(co)
        except Exception as e:
            print(f"[BillCollect] Could not load MOPs: {e}")

        # Load existing splits from DB
        self._splits: list[dict] = []
        try:
            from models.restaurant_order import get_bill_splits
            self._splits = get_bill_splits(self.table_id)
        except Exception:
            pass

        self._build()
        self._refresh_summary()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        tbl_lbl = QLabel(
            f"Table {self.table_data.get('table_number')}  ·  "
            f"{self.table_data.get('name', '')}"
        )
        tbl_lbl.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {TEXT};")
        hdr.addWidget(tbl_lbl)
        hdr.addStretch()
        bill_lbl = QLabel(f"Bill Total:  ${self.bill_total:,.2f}")
        bill_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {DANGER}; "
            f"background: {DANGER_BG}; border-radius: 4px; padding: 2px 10px;")
        hdr.addWidget(bill_lbl)
        root.addLayout(hdr)

        # ── Entry area ────────────────────────────────────────────────────────
        entry_frame = QFrame()
        entry_frame.setStyleSheet(
            f"QFrame {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 6px; }}")
        ef_lay = QVBoxLayout(entry_frame)
        ef_lay.setContentsMargins(12, 10, 12, 10)
        ef_lay.setSpacing(8)

        # Column headers
        ch = QHBoxLayout()
        for txt, stretch in [("METHOD", 3), ("CCY", 1), ("AMOUNT", 2), ("LABEL (opt.)", 2), ("", 1)]:
            l = QLabel(txt)
            l.setStyleSheet(
                f"font-size: 9px; font-weight: 700; color: {TEXT_MUTED}; letter-spacing: 0.8px;")
            ch.addWidget(l, stretch)
        ef_lay.addLayout(ch)

        # MOP selector
        row = QHBoxLayout(); row.setSpacing(6)

        self._mop_combo = QComboBox()
        self._mop_combo.setFixedHeight(32)
        self._mop_combo.setStyleSheet(
            f"QComboBox {{ background:{BG}; border:1px solid {BORDER}; "
            f"border-radius:4px; padding:0 8px; font-size:12px; font-weight:600; }}"
            f"QComboBox::drop-down {{ border:none; }}")
        for m in self._methods:
            self._mop_combo.addItem(f"  {m['label']}", userData=m)
        self._mop_combo.currentIndexChanged.connect(self._on_mop_changed)
        row.addWidget(self._mop_combo, 3)

        self._ccy_lbl = QLabel("USD")
        self._ccy_lbl.setFixedHeight(32)
        self._ccy_lbl.setFixedWidth(44)
        self._ccy_lbl.setAlignment(Qt.AlignCenter)
        self._ccy_lbl.setStyleSheet(
            f"background:{ACCENT_SOFT}; color:{ACCENT}; border:1px solid {BORDER}; "
            f"border-radius:4px; font-size:10px; font-weight:700;")
        row.addWidget(self._ccy_lbl, 1)

        self._amount_edit = QLineEdit()
        self._amount_edit.setFixedHeight(32)
        self._amount_edit.setPlaceholderText("0.00")
        self._amount_edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        validator = QDoubleValidator(0.0, 999999.99, 2)
        self._amount_edit.setValidator(validator)
        row.addWidget(self._amount_edit, 2)

        self._label_edit = QLineEdit()
        self._label_edit.setFixedHeight(32)
        self._label_edit.setPlaceholderText("Person 1…")
        row.addWidget(self._label_edit, 2)

        add_btn = QPushButton("+ Add")
        add_btn.setFixedHeight(32)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet(
            f"QPushButton {{ background:{ACCENT}; color:white; }}"
            f"QPushButton:hover {{ background:{ACCENT_DIM}; }}")
        add_btn.clicked.connect(self._on_add)
        row.addWidget(add_btn, 1)

        ef_lay.addLayout(row)
        root.addWidget(entry_frame)

        # ── Collected list ────────────────────────────────────────────────────
        list_frame = QFrame()
        list_frame.setStyleSheet(
            f"QFrame {{ background:{BG}; border:1px solid {BORDER}; border-radius:6px; }}")
        lf_outer = QVBoxLayout(list_frame)
        lf_outer.setContentsMargins(0, 0, 0, 0)

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background:transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(12, 8, 12, 8)
        self._list_layout.setSpacing(4)
        self._list_layout.setAlignment(Qt.AlignTop)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setFixedHeight(160)
        scroll.setWidget(self._list_widget)
        lf_outer.addWidget(scroll)
        root.addWidget(list_frame)

        # ── Summary bar ───────────────────────────────────────────────────────
        summ = QFrame()
        summ.setStyleSheet(
            f"QFrame {{ background:{ACCENT_SOFT}; border:1px solid {ACCENT}; border-radius:6px; }}")
        sl = QHBoxLayout(summ)
        sl.setContentsMargins(14, 8, 14, 8)

        self._collected_lbl = QLabel("Collected: $0.00")
        self._collected_lbl.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{ACCENT};")
        self._remaining_lbl = QLabel(f"Remaining: ${self.bill_total:,.2f}")
        self._remaining_lbl.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{DANGER};")
        sl.addWidget(self._collected_lbl)
        sl.addStretch()
        sl.addWidget(self._remaining_lbl)
        root.addWidget(summ)

        # ── Action buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)

        done_btn = QPushButton("Done")
        done_btn.setFixedHeight(38)
        done_btn.setCursor(Qt.PointingHandCursor)
        done_btn.setStyleSheet(
            f"QPushButton {{ background:{ACCENT}; color:white; border:none; }}"
            f"QPushButton:hover {{ background:{ACCENT_DIM}; }}")
        done_btn.clicked.connect(self.accept)
        btn_row.addWidget(done_btn)

        root.addLayout(btn_row)

        # Seed from DB
        self._on_mop_changed()
        self._rebuild_list()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _on_mop_changed(self):
        m = self._mop_combo.currentData()
        if m:
            self._ccy_lbl.setText(m.get("currency", "USD"))

    def _on_add(self):
        m = self._mop_combo.currentData()
        if not m:
            QMessageBox.warning(self, "No MOP", "Please select a payment method.")
            return
        try:
            raw = float(self._amount_edit.text() or "0")
        except ValueError:
            raw = 0.0
        if raw <= 0:
            QMessageBox.warning(self, "Invalid Amount", "Please enter an amount greater than 0.")
            return

        currency = m.get("currency", "USD")
        rate     = m.get("rate_to_usd", 1.0) or 1.0
        usd      = round(raw * rate, 4)
        label    = self._label_edit.text().strip()

        from models.restaurant_order import add_bill_split, get_bill_splits
        ok = add_bill_split(
            table_id=self.table_id,
            mop_label=m["label"],
            currency=currency,
            amount_raw=raw,
            amount_usd=usd,
            label=label,
        )
        if ok:
            self._splits = get_bill_splits(self.table_id)
            self._amount_edit.clear()
            self._label_edit.clear()
            self._rebuild_list()
            self._refresh_summary()
        else:
            QMessageBox.warning(self, "Error", "Could not save share. Check logs.")

    def _on_delete(self, split_id: int):
        from models.restaurant_order import delete_bill_split, get_bill_splits
        delete_bill_split(split_id)
        self._splits = get_bill_splits(self.table_id)
        self._rebuild_list()
        self._refresh_summary()

    def _rebuild_list(self):
        while self._list_layout.count():
            child = self._list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self._splits:
            empty = QLabel("No shares collected yet.")
            empty.setStyleSheet(
                f"color:{TEXT_MUTED}; font-size:11px; font-style:italic; padding:8px;")
            empty.setAlignment(Qt.AlignCenter)
            self._list_layout.addWidget(empty)
            return

        for sp in self._splits:
            row = QFrame()
            row.setStyleSheet(
                f"QFrame {{ background:{ACCENT_SOFT}; border-radius:4px; }}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 4, 8, 4)
            rl.setSpacing(8)

            lbl = sp.get("label") or ""
            mop = sp.get("mop_label", "")
            ccy = sp.get("currency", "USD")
            raw = float(sp.get("amount_raw", 0))
            usd = float(sp.get("amount_usd", 0))

            display = f"{mop}  ·  {ccy} {raw:,.2f}"
            if lbl:
                display = f"{lbl}  —  " + display
            if ccy.upper() != "USD":
                display += f"  (≈ ${usd:.2f})"

            txt = QLabel(display)
            txt.setStyleSheet(f"font-size:12px; font-weight:600; color:{TEXT};")
            rl.addWidget(txt, 1)

            del_btn = QPushButton("✕")
            del_btn.setFixedSize(22, 22)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setStyleSheet(
                f"QPushButton {{ background:transparent; color:{DANGER}; "
                f"font-weight:700; border:none; font-size:12px; }}"
                f"QPushButton:hover {{ color:#991b1b; }}")
            del_btn.clicked.connect(lambda _, sid=sp["id"]: self._on_delete(sid))
            rl.addWidget(del_btn)

            self._list_layout.addWidget(row)

    def _refresh_summary(self):
        collected_usd = sum(float(s.get("amount_usd", 0)) for s in self._splits)
        remaining_usd = max(self.bill_total - collected_usd, 0.0)
        self._collected_lbl.setText(f"Collected: ${collected_usd:,.2f}")
        self._remaining_lbl.setText(f"Remaining: ${remaining_usd:,.2f}")


# ── Table Action Dialog ───────────────────────────────────────────────────────

class TableActionDialog(QDialog):
    def __init__(self, table_data: dict, parent=None, settings: dict | None = None):
        super().__init__(parent)
        self.table_data = table_data
        self.settings = settings or {}
        self.action = None  # 'add', 'pay', 'view', 'pay_all', 'split', 'collect_shares'
        
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setModal(True)
        h = 310
        if self.settings.get("allow_split_bill"):
            h += 45
        if self.settings.get("allow_partial_payment"):
            h += 45
        self.setFixedSize(240, h)
        
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

        # Fetch current user for TableActionDialog gating
        self.user = getattr(parent, "user", {}) or {}
        from models.user import is_admin
        _is_admin = is_admin(self.user)
        self._pay_restricted = not _is_admin and not bool(self.user.get("allow_pay_kot", True))

        btn_pay = QPushButton("CLOSE TABLE [ADMIN]" if self._pay_restricted else "CLOSE TABLE")
        btn_pay.setCursor(Qt.PointingHandCursor)
        btn_pay.setStyleSheet(f"background: {SUCCESS}; color: white; font-weight: 700;")
        btn_pay.clicked.connect(lambda: self._gated_action('pay_all', self._pay_restricted))
        lay.addWidget(btn_pay)

        if self.settings.get("allow_split_bill"):
            btn_split = QPushButton("SPLIT BILL")
            btn_split.setCursor(Qt.PointingHandCursor)
            btn_split.setStyleSheet(f"background: {ORANGE}; color: white; font-weight: 700;")
            btn_split.clicked.connect(lambda: self._set_action('split'))
            lay.addWidget(btn_split)

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

        if self.settings.get("allow_partial_payment"):
            btn_collect = QPushButton("COLLECT SHARES")
            btn_collect.setCursor(Qt.PointingHandCursor)
            btn_collect.setStyleSheet(f"color: {TEXT_SEC}; font-weight: 500;")
            btn_collect.clicked.connect(lambda: self._set_action('collect_shares'))
            lay.addWidget(btn_collect)
        
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

    def _gated_action(self, action: str, requires_admin: bool):
        if not requires_admin:
            self._set_action(action)
            return
        # Admin PIN prompt
        from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox
        pin, ok = QInputDialog.getText(
            self, "Admin Required", "Enter admin PIN:",
            QLineEdit.Password
        )
        if not ok: return
        try:
            from models.user import authenticate_by_pin, is_admin
            u = authenticate_by_pin(pin)
            if u and is_admin(u):
                self._set_action(action)
            else:
                QMessageBox.warning(self, "Access Denied", "Incorrect or non-admin PIN.")
        except Exception:
            if pin: self._set_action(action)


# ── KOT Action Dialog ─────────────────────────────────────────────────────────

class KOTActionDialog(QDialog):
    def __init__(self, order_data: dict, parent=None, settings: dict | None = None):
        super().__init__(parent)
        self.order_data = order_data
        self.action     = None  # 'edit', 'cancel', 'pay'

        s = settings or {}
        # Fetch current user from parent
        self.user = getattr(parent, "user", {}) or {}
        if not self.user and hasattr(parent, "parent"):
            # Try grandparent (OrderView)
            p = parent.parent()
            self.user = getattr(p, "user", {}) or {}

        from models.user import is_admin
        _is_admin = is_admin(self.user)

        # Permissions: restricted if NOT admin AND permission bit is OFF
        self._pay_restricted    = not _is_admin and not bool(self.user.get("allow_pay_kot", True))
        self._cancel_restricted = not _is_admin and not bool(self.user.get("allow_cancel_kot", False))
        # Modify reason setting (global)
        self._modify_restricted = not bool(s.get("require_modify_reason", True)) if s else False

        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setModal(True)
        self.setFixedSize(250, 360) # Increased height for Print button

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20); shadow.setXOffset(0); shadow.setYOffset(4)
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
                padding: 11px 16px;
                text-align: center;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton#btnEdit {{
                background: {ACCENT};
                color: white;
            }}
            QPushButton#btnEdit:hover {{ background: {ACCENT_DIM}; }}
            QPushButton#btnCancel {{
                color: {DANGER};
                border: 1px solid {DANGER};
            }}
            QPushButton#btnCancel:hover {{ background: {DANGER_BG}; }}
            QPushButton#btnPay {{
                background: {SUCCESS};
                color: white;
            }}
            QPushButton#btnPay:hover {{ background: #15803d; }}
            QPushButton#btnClose {{
                color: {TEXT_SEC};
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton#btnClose:hover {{ background: {ROW_ALT}; color: {TEXT}; }}
            QPushButton#btnPrint {{
                background: {HDR_BG};
                color: white;
            }}
            QPushButton#btnPrint:hover {{ background: #2c3e50; }}
            QLabel#Title {{
                font-size: 15px;
                font-weight: 800;
                color: {TEXT};
                padding: 12px 16px 2px 16px;
            }}
            QLabel#Subtitle {{
                font-size: 11px;
                color: {TEXT_MUTED};
                padding: 0 16px 6px 16px;
            }}
            QLabel#TimeLabel {{
                font-size: 11px;
                font-weight: 700;
                padding: 0 16px 8px 16px;
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(5)

        title = QLabel(f"Order #ORD-{order_data['id']}")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        subtitle = QLabel(f"{order_data.get('table_name', 'Table')}  ·  {order_data.get('customer_name', 'Guest')}")
        subtitle.setObjectName("Subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        lay.addWidget(subtitle)

        # Elapsed since order placed — no emoji
        created_at = order_data.get("created_at") or order_data.get("opened_at")
        elapsed    = _format_elapsed(created_at)
        aging_clr  = _aging_color(created_at) or TEXT_MUTED
        if elapsed:
            time_lbl = QLabel(f"{elapsed} ago")
            time_lbl.setObjectName("TimeLabel")
            time_lbl.setAlignment(Qt.AlignCenter)
            time_lbl.setStyleSheet(
                f"font-size: 11px; font-weight: 700; color: {aging_clr}; "
                f"background: transparent; padding: 0 16px 6px 16px;"
            )
            lay.addWidget(time_lbl)

        lay.addWidget(_divider())
        lay.addSpacing(4)

        # EDIT KOT — admin PIN if restricted
        lbl_edit = "EDIT KOT  [ADMIN]" if self._modify_restricted else "EDIT KOT"
        btn_edit = QPushButton(lbl_edit)
        btn_edit.setObjectName("btnEdit")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.clicked.connect(lambda: self._gated_action('edit', self._modify_restricted))
        lay.addWidget(btn_edit)

        # PAY KOT — admin PIN if restricted
        lbl_pay = "PAY KOT  [ADMIN]" if self._pay_restricted else "PAY KOT"
        btn_pay = QPushButton(lbl_pay)
        btn_pay.setObjectName("btnPay")
        btn_pay.setCursor(Qt.PointingHandCursor)
        btn_pay.clicked.connect(lambda: self._gated_action('pay', self._pay_restricted))
        lay.addWidget(btn_pay)

        # CANCEL KOT — admin PIN if restricted
        lbl_cancel = "CANCEL KOT  [ADMIN]" if self._cancel_restricted else "CANCEL KOT"
        btn_cancel = QPushButton(lbl_cancel)
        btn_cancel.setObjectName("btnCancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(lambda: self._gated_action('cancel', self._cancel_restricted))
        lay.addWidget(btn_cancel)

        # PRINT PRE-BILL
        btn_print = QPushButton("PRINT PRE-BILL")
        btn_print.setObjectName("btnPrint")
        btn_print.setCursor(Qt.PointingHandCursor)
        btn_print.clicked.connect(lambda: self._set_action('print'))
        lay.addWidget(btn_print)

        lay.addSpacing(4)
        btn_close = QPushButton("Dismiss")
        btn_close.setObjectName("btnClose")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        lay.addWidget(btn_close)

    def _gated_action(self, action: str, requires_admin: bool):
        if not requires_admin:
            self._set_action(action)
            return
        # Admin PIN prompt
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        pin, ok = QInputDialog.getText(
            self, "Admin Required", "Enter admin PIN:",
            QLineEdit.Password
        )
        if not ok:
            return
        try:
            from models.user import authenticate_by_pin, is_admin
            u = authenticate_by_pin(pin)
            if u and is_admin(u):
                self._set_action(action)
            else:
                QMessageBox.warning(self, "Access Denied", "Incorrect or non-admin PIN.")
        except Exception:
            # Fallback: accept any non-empty PIN if model not available
            if pin:
                self._set_action(action)

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
        self._current_waiter_id: int | None = None   # set by OrderView.refresh()
        self._is_admin: bool = True                   # set by OrderView.refresh()
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

        for lbl in ("All", "Open", "Paid", "Cancelled"):
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
            status = o.get("status", "")
            if status in ("Open", "Ordered"):
                eff = "Open"
            elif status == "Cancelled":
                eff = "Cancelled"
            else:
                eff = "Paid"

            if self._current_filter == "Open"      and eff != "Open":      continue
            if self._current_filter == "Paid"      and eff != "Paid":      continue
            if self._current_filter == "Cancelled" and eff != "Cancelled": continue

            # Waiter isolation: non-admin users only see their own orders
            if not self._is_admin and self._current_waiter_id is not None:
                if o.get("waiter_id") != self._current_waiter_id:
                    continue

            if query and query not in f"{o.get('table_name','')} {o.get('table_number','')} {o.get('customer_name','')}".lower():
                continue

            if self._active_table_filter:
                ft = self._active_table_filter
                if (str(o.get('table_number', '')) != str(ft.get('table_number', '')) or
                    str(o.get('floor', '')).lower() != str(ft.get('floor', '')).lower()):
                    continue

            o["_eff"] = eff
            filtered.append(o)

        if not filtered:
            empty = QLabel("No orders found.")
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
        eff    = o.get("_eff", "Paid")
        row_bg = BG if idx % 2 == 0 else ROW_ALT

        if eff == "Open":
            left_clr = ACCENT
            tag_bg, tag_fg, tag_txt = TAG_OPEN_BG, TAG_OPEN_FG, "OPEN"
        elif eff == "Cancelled":
            left_clr = WARNING
            tag_bg, tag_fg, tag_txt = "#fef3c7", "#92400e", "CANCELLED"
        else:
            left_clr = BORDER_LT
            tag_bg, tag_fg, tag_txt = TAG_PAID_BG, TAG_PAID_FG, "PAID"

        card = QFrame()
        card.setObjectName("ORow")
        card.setStyleSheet(f"""
            QFrame#ORow {{
                background: {row_bg};
                border: none;
                border-left: 3px solid {left_clr};
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

        # Row 1: order ID + status tag
        r1 = QHBoxLayout(); r1.setSpacing(6)
        ord_id_lbl = QLabel(f"#ORD-{o['id']}")
        ord_id_lbl.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {HDR_BG}; background: transparent;")
        r1.addWidget(ord_id_lbl)
        r1.addStretch()
        r1.addWidget(_tag(tag_txt, tag_bg, tag_fg))
        lay.addLayout(r1)

        # Row 2: table
        r2 = QLabel(f"{o['table_name']}  ({o['table_number']})")
        r2.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {TEXT_SEC}; background: transparent;")
        lay.addWidget(r2)

        # Row 3: guest
        guest = o.get('customer_name') or 'Guest'
        r3 = QLabel(guest)
        r3.setStyleSheet(f"font-size: 11px; color: {TEXT_SEC}; background: transparent;")
        lay.addWidget(r3)

        # Row 4: timestamp + elapsed (open orders only, no emoji)
        time_str = (
            o["created_at"].strftime("%d/%m/%Y  %H:%M")
            if hasattr(o.get("created_at"), "strftime")
            else str(o.get("created_at", ""))[:16]
        )
        time_row = QHBoxLayout(); time_row.setSpacing(8)
        ts_lbl = QLabel(time_str)
        ts_lbl.setStyleSheet(f"font-size: 10px; color: {TEXT_MUTED}; background: transparent;")
        time_row.addWidget(ts_lbl)
        if is_open:
            elapsed   = _format_elapsed(o.get("created_at") or o.get("opened_at"))
            aging_clr = _aging_color(o.get("created_at") or o.get("opened_at"))
            if elapsed:
                age_lbl = QLabel(elapsed)
                age_lbl.setStyleSheet(
                    f"font-size: 10px; font-weight: 700; color: {aging_clr}; background: transparent;"
                )
                time_row.addWidget(age_lbl)
        time_row.addStretch()
        lay.addLayout(time_row)

        # Items block
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
                    ir = QHBoxLayout(); ir.setSpacing(0)
                    il = QLabel(f"{oi['item_name']} x{qty:.4g}")
                    il.setStyleSheet(f"font-size: 11px; color: {TEXT}; background: transparent;")
                    ip = QLabel(f"${line:.2f}")
                    ip.setStyleSheet(f"font-size: 11px; color: {TEXT}; background: transparent;")
                    ip.setAlignment(Qt.AlignRight)
                    ir.addWidget(il); ir.addWidget(ip)
                    lay.addLayout(ir)
                tr = QHBoxLayout()
                tl = QLabel("Total")
                tl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {ACCENT}; background: transparent;")
                tv = QLabel(f"${total:.2f}")
                tv.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {ACCENT}; background: transparent;")
                tv.setAlignment(Qt.AlignRight)
                tr.addWidget(tl); tr.addWidget(tv)
                lay.addLayout(tr)
        except Exception:
            pass

        return card

    def _on_row_clicked(self, event, order_data: dict):
        if event.button() == Qt.LeftButton:
            # Load settings so KOTActionDialog can enforce Pay/Cancel locks
            rs = {}
            try:
                from models.restaurant_order import get_restaurant_settings
                rs = get_restaurant_settings()
            except Exception:
                pass
            dlg = KOTActionDialog(order_data, self, settings=rs)
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
        
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(60000)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start()

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
            rs = {}
            try:
                from models.restaurant_order import get_restaurant_settings
                rs = get_restaurant_settings()
            except Exception:
                pass
            dlg = TableActionDialog(td, self, settings=rs)
            
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
                td_no_reason = dict(td)
                td_no_reason["skip_reason"] = True
                self.action_add_order.emit(td_no_reason)
            elif dlg.action == "pay_all":
                self.action_pay_all.emit(td)
            elif dlg.action == "split":
                # For now, splitting from the table card level will also 
                # load all orders for the table but trigger the split UI.
                # We can handle this in MainWindow.
                self.action_pay_all.emit(td) 
            elif dlg.action == "view":
                self._panel.view_table_orders(td)
            elif dlg.action == "prebill":
                self._print_prebill(td)
            elif dlg.action == "collect_shares":
                self._open_bill_collect(td)
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
            
            if not ps.print_invoice_receipt(receipt, printer_name=printer_name):
                QMessageBox.warning(self, "Print Failed", "Could not print the pre-bill.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to print pre-bill: {e}")

    def _open_bill_collect(self, table_data: dict):
        """Open BillCollectDialog — pure collect/save popup, no payment triggered."""
        from models.restaurant_order import get_orders_for_table, get_order_items
        table_id = table_data.get("id")
        orders   = get_orders_for_table(table_id)
        bill_total = 0.0
        for o in orders:
            for it in get_order_items(o["id"]):
                bill_total += float(it.get("qty", 0)) * float(it.get("price", 0))

        if bill_total <= 0:
            QMessageBox.information(self, "Collect Shares", "No open bill found for this table.")
            return

        dlg = BillCollectDialog(table_data, bill_total, parent=self)
        dlg.exec()  # always just opens — Done button closes it, no payment fired

    def _handle_order_action(self, action: str, order_data: dict):
        if action == "edit":
            self.action_edit_kot.emit(order_data)
        elif action == "pay":
            self.action_pay_order.emit(order_data)
        elif action == 'print':
            self._print_order_directly(order_data)
        elif action == "cancel":
            self.action_cancel_kot.emit(order_data["id"])

    def _print_order_directly(self, order_data):
        """Aggregate this specific KOT and print as a pre-bill."""
        try:
            from models.restaurant_order import get_order_items, get_waiter_name
            items = get_order_items(order_data["id"])
            if not items: return
            
            # Prepare receipt data
            from models.receipt import ReceiptData, Item
            from models.company_defaults import get_defaults
            from datetime import datetime
            
            co = get_defaults() or {}
            
            receipt = ReceiptData()
            receipt.companyName = co.get("company_name", "Havano POS")
            receipt.companyLogoPath = co.get("logo_path", "")
            receipt.companyAddress = co.get("address", "")
            receipt.tel = co.get("phone", "")
            receipt.tin = co.get("tin", "")
            receipt.vatNo = co.get("vat_no", "")
            
            receipt.receiptHeader = "*** PRE-BILL ***"
            table_lbl = order_data.get("table_name", f"Table {order_data.get('table_number', '')}")
            receipt.invoiceNo = f"{table_lbl} / ORD-{order_data['id']}"
            receipt.invoiceDate = datetime.now().strftime("%Y-%m-%d")
            receipt.customerName = order_data.get("customer_name") or "Guest"
            
            # Get waiter name
            waiter_id = order_data.get("waiter_id")
            receipt.cashierName = get_waiter_name(waiter_id) or "Waiter"
            
            for it in items:
                receipt.items.append(Item(
                    productName=it.get("item_name", ""),
                    productid=str(it.get("product_id", "")),
                    qty=float(it.get("qty", 0)),
                    price=float(it.get("price", 0)),
                    amount=float(it.get("qty", 0)) * float(it.get("price", 0))
                ))
            
            receipt.grandTotal = sum(i.amount for i in receipt.items)
            receipt.footer = "This is a pre-bill, not a tax invoice."

            # Print using the printing service
            from services.printing_service import PrintingService
            ps = PrintingService()
            from models.advance_settings import AdvanceSettings
            settings = AdvanceSettings.load_from_file()
            printer_name = getattr(settings, "invoicePrinter", None)
            
            if not ps.print_invoice_receipt(receipt, printer_name=printer_name):
                QMessageBox.warning(self, "Print Failed", "Could not print the pre-bill.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to print pre-bill: {e}")

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

        # Monitors Dropdown
        from PySide6.QtWidgets import QMenu
        self.mon_btn = QPushButton("Monitors")
        self.mon_btn.setFixedWidth(100); self.mon_btn.setFixedHeight(28)
        self.mon_btn.setCursor(Qt.PointingHandCursor)
        self.mon_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: {WHITE}; 
                border-radius: 6px; font-weight: bold; font-size: 11px;
                border: none;
            }}
            QPushButton::menu-indicator {{ image: none; }}
            QPushButton:hover {{ background: {ACCENT_DIM}; }}
        """)
        mon_menu = QMenu(self)
        mon_menu.setStyleSheet(f"background: {WHITE}; color: {TEXT}; border: 1px solid {BORDER};")
        def _launch(m):
            from views.restaurant_kds import KitchenWindow, ReadyBoardWindow, UnifiedMonitorWindow
            if m == "k": self._kw = KitchenWindow(); self._kw.show()
            elif m == "d": self._db = ReadyBoardWindow(); self._db.show()
            elif m == "u": self._um = UnifiedMonitorWindow(); self._um.show()
        mon_menu.addAction("Kitchen Display (KDS)", lambda: _launch("k"))
        mon_menu.addAction("Ready Board (Dispatch)", lambda: _launch("d"))
        mon_menu.addAction("Unified Monitor", lambda: _launch("u"))
        self.mon_btn.setMenu(mon_menu)
        hl.addWidget(self.mon_btn)

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
        
        self._log_btn = QPushButton("📋  KOT Log")
        self._log_btn.setFixedHeight(28)
        self._log_btn.setCursor(Qt.PointingHandCursor)
        self._log_btn.setStyleSheet(f"""
            QPushButton {{
                background: {SURFACE};
                color: {TEXT_SEC};
                border: 1px solid {BORDER};
                border-radius: 3px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 14px;
            }}
            QPushButton:hover  {{ background: {WHITE}; border-color: {ACCENT}; color: {ACCENT}; }}
        """)
        self._log_btn.clicked.connect(self._show_kot_log)
        hl.addWidget(self._log_btn)

        return tb

    def _show_kot_log(self):
        from views.dialogs.restaurant_log_dialog import RestaurantLogDialog
        dlg = RestaurantLogDialog(self)
        dlg.exec()

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

        from models.restaurant_order import (
            get_all_tables, get_recent_orders, get_all_floors,
            get_restaurant_settings, get_waiter_name
        )
        from PySide6.QtWidgets import QPushButton, QLabel

        waiter_id        = getattr(self, "_current_user_id", None)
        is_admin         = getattr(self, "_is_admin", False)
        waiter_isolation = False
        rs               = {}
        try:
            rs               = get_restaurant_settings()
            waiter_isolation = bool(rs.get("waiter_isolation"))
        except Exception:
            pass

        # Admin always sees all tables; waiter isolation applies to non-admins only
        effective_isolation = waiter_isolation and not is_admin
        tables = get_all_tables(waiter_id=waiter_id, waiter_isolation=effective_isolation)

        for t in tables:
            wid = t.get("active_waiter_id")
            t["_waiter_name"] = get_waiter_name(wid) if wid else ""

        if not hasattr(self, "_current_floor"): self._current_floor = "All"
        try:
            db_floors = get_all_floors()
            floors = ["All"] + [f["name"] for f in db_floors]
        except Exception:
            floors = ["All"] + sorted(set(t.get("floor", "Main") for t in tables))

        while self._floor_btns_lay.count():
            child = self._floor_btns_lay.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        for fl in floors:
            is_active = (fl == self._current_floor)
            btn = QPushButton(fl.upper())
            btn.setCheckable(True); btn.setChecked(is_active)
            btn.setFixedHeight(42); btn.setCursor(Qt.PointingHandCursor)
            bg  = ACCENT if is_active else SURFACE
            fg  = WHITE  if is_active else TEXT_SEC
            brd = ACCENT if is_active else BORDER
            btn.setStyleSheet(
                f"QPushButton {{ background:{bg}; color:{fg}; border:1px solid {brd}; "
                f"border-radius:6px; font-size:12px; font-weight:800; padding:0 24px; }}"
            )
            btn.clicked.connect(lambda _, f=fl: self._set_floor_filter(f))
            self._floor_btns_lay.addWidget(btn)

        occupied = sum(1 for t in tables if t.get("status") == "Occupied")
        avail    = len(tables) - occupied
        for chip, val, clr in [
            (self._stat_total, str(len(tables)), TEXT_SEC),
            (self._stat_avail, str(avail),       SUCCESS),
            (self._stat_occup, str(occupied),    DANGER),
        ]:
            for w in chip.findChildren(QLabel):
                if not w.text().endswith(":"):
                    w.setText(val)
                    w.setStyleSheet(f"font-size:12px; font-weight:700; color:{clr}; background:transparent;")
                    break

        query = self.table_search.text().lower() if hasattr(self, "table_search") else ""
        st_f  = getattr(self, "_status_filter", "All")
        fl_f  = self._current_floor
        filtered = []
        for t in tables:
            if fl_f != "All" and t.get("floor") != fl_f: continue
            ts = t.get("status", "Available")
            if st_f == "Available" and ts != "Available": continue
            if st_f == "Occupied"  and ts != "Occupied":  continue
            if query and query not in f"{t['name']} {t['table_number']}".lower(): continue
            filtered.append(t)

        for t in filtered:
            card = TableCard(t)
            card.clicked.connect(self._handle_table_click)
            self.grid.addWidget(card)

        # Show log button only for admins
        if hasattr(self, "_log_btn"):
            self._log_btn.setVisible(is_admin)

        # Pass waiter/admin context to panel so it can isolate sidebar orders too
        self._panel._current_waiter_id = waiter_id
        self._panel._is_admin          = is_admin
        self._panel.load(get_recent_orders(limit=200))

    def _set_floor_filter(self, floor_name: str):
        self._current_floor = floor_name
        self.refresh()
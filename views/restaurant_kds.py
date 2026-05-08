"""
Havano POS — Kitchen Display System
Next-gen, compact, unified card design. No white/colored column backgrounds.
Tick buttons are large, clear, and impossible to miss.
"""

import json
import asyncio
import weakref
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QLayout, QApplication
)
from PySide6.QtCore import (
    Qt, Signal, QThread, QTimer, QSize, QRect, QPoint
)
from PySide6.QtGui import QColor, QPainter

# ── Design Tokens ─────────────────────────────────────────────────────────────
BG_ROOT         = "#f4f6f9"
BG_CARD         = "#ffffff"
BG_HEADER       = "#ffffff"
BG_CHIP         = "#f1f5f9"
BORDER          = "#e8ecf1"
BORDER_MED      = "#d1d9e0"
TEXT_DARK       = "#111827"
TEXT_MID        = "#4b5563"
TEXT_MUTED      = "#9ca3af"

ACCENT          = "#2563eb"
ACCENT_SOFT     = "#eff6ff"
ACCENT_BORDER   = "#bfdbfe"

SUCCESS         = "#16a34a"
SUCCESS_BG      = "#f0fdf4"
SUCCESS_BORDER  = "#86efac"
SUCCESS_TEXT    = "#15803d"

WARNING         = "#d97706"
WARNING_BG      = "#fffbeb"
WARNING_BORDER  = "#fcd34d"
WARNING_TEXT    = "#92400e"

DANGER          = "#dc2626"
DANGER_BG       = "#fef2f2"
DANGER_BORDER   = "#fca5a5"
DANGER_TEXT     = "#991b1b"

AGE_FRESH  = "#16a34a"
AGE_WARM   = "#d97706"
AGE_URGENT = "#dc2626"


def age_color(s: int) -> str:
    return AGE_URGENT if s >= 900 else (AGE_WARM if s >= 480 else AGE_FRESH)


# ── WebSocket Client ──────────────────────────────────────────────────────────
class KDSClientThread(QThread):
    message_received   = Signal(dict)
    connection_changed = Signal(bool)

    def __init__(self, url="ws://localhost:8765"):
        super().__init__()
        self.url        = url
        self._running   = True
        self._connected = False

    def run(self):
        asyncio.run(self._listen())

    async def _listen(self):
        import websockets
        while self._running:
            try:
                async with websockets.connect(
                    self.url, ping_interval=20, ping_timeout=10
                ) as ws:
                    self._connected = True
                    self.connection_changed.emit(True)
                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            self.message_received.emit(json.loads(raw))
                        except json.JSONDecodeError:
                            pass
            except Exception:
                if self._connected:
                    self._connected = False
                    self.connection_changed.emit(False)
                await asyncio.sleep(3)

    def stop(self):
        self._running = False
        self.quit()
        if not self.wait(3000):
            self.terminate()
            self.wait(1000)


# ── Flow Layout ───────────────────────────────────────────────────────────────
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, h=12, v=12):
        super().__init__(parent)
        self._items = []
        self._h, self._v = h, v
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):       self._items.append(item)
    def count(self):               return len(self._items)
    def itemAt(self, i):           return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i):           return self._items.pop(i) if 0 <= i < len(self._items) else None
    def expandingDirections(self): return Qt.Orientations()
    def hasHeightForWidth(self):   return True
    def heightForWidth(self, w):   return self._do(QRect(0, 0, w, 0), True)
    def setGeometry(self, r):
        super().setGeometry(r)
        self._do(r, False)
    def sizeHint(self):    return self.minimumSize()
    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return s + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do(self, rect, test):
        x, y, lh = rect.x(), rect.y(), 0
        for it in self._items:
            w, h = it.sizeHint().width(), it.sizeHint().height()
            nx = x + w + self._h
            if nx - self._h > rect.right() and lh > 0:
                x, y, nx = rect.x(), y + lh + self._v, rect.x() + w + self._h
                lh = 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), it.sizeHint()))
            x, lh = nx, max(lh, h)
        return y + lh - rect.y()


class FlowContainer(QWidget):
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.layout():
            self.setMinimumHeight(self.layout().heightForWidth(self.width()))


# ── Pulsing Dot ───────────────────────────────────────────────────────────────
class PulseDot(QWidget):
    def __init__(self, color=SUCCESS, size=7, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._alpha = 1.0
        self._size  = size
        self._ph    = 0.0
        self.setFixedSize(size + 10, size + 10)
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(40)

    def _tick(self):
        import math
        self._ph += 0.07
        self._alpha = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(self._ph))
        self.update()

    def set_color(self, c: str):
        self._color = QColor(c)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        halo = QColor(self._color)
        halo.setAlphaF(self._alpha * 0.18)
        p.setBrush(halo)
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, self._size + 10, self._size + 10)
        core = QColor(self._color)
        core.setAlphaF(self._alpha)
        p.setBrush(core)
        p.drawEllipse(5, 5, self._size, self._size)


# ── Elapsed Timer Label ───────────────────────────────────────────────────────
class ElapsedLabel(QLabel):
    def __init__(self, created_at, parent=None):
        super().__init__(parent)
        self._t   = self._parse(created_at)
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(1000)
        self._tick()

    def _parse(self, v):
        if isinstance(v, datetime):
            return v
        for fmt in ("%Y-%m-%d %H:%M:%S", "%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(str(v or "")[:19], fmt)
            except ValueError:
                pass
        return datetime.now()

    def seconds(self):
        return max(0, int((datetime.now() - self._t).total_seconds()))

    def _tick(self):
        s = self.seconds()
        m, sec = divmod(s, 60)
        c   = age_color(s)
        txt = f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m:02d}:{sec:02d}"
        self.setText(txt)
        self.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {c}; "
            "font-family: 'Courier New', monospace;"
        )

    def stop(self):
        self._tmr.stop()


# ── Order Card ────────────────────────────────────────────────────────────────
class OrderCard(QFrame):
    status_changed = Signal(int, str, str)

    def __init__(self, order_data, mode="kitchen",
                 local_ticks=None, is_new=False, parent=None):
        super().__init__(parent)
        self.order_id    = order_data["id"]
        self.data        = order_data
        self.mode        = mode
        self.local_ticks = set(local_ticks) if local_ticks else set()
        self._elapsed    = None
        self._alive      = True
        self.destroyed.connect(lambda: setattr(self, "_alive", False))
        self._build()
        if is_new:
            QTimer.singleShot(60, self._flash_new)

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self):
        self.setMinimumWidth(260)
        self.setMaximumWidth(400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        status = self.data.get("prep_status", "Preparing")
        items  = self.data.get("items", [])
        ticked = {
            i["item_name"] for i in items
            if i.get("item_status") == "Ready" or i["item_name"] in self.local_ticks
        }
        all_ticked = bool(items) and ticked >= {i["item_name"] for i in items}
        age = self._age()

        top = (DANGER  if status == "Cancelled"
               else SUCCESS if status == "Ready"
               else age_color(age))

        # Card: single clean border + coloured top accent only
        self.setStyleSheet(f"""
            OrderCard {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-top: 3px solid {top};
                border-radius: 12px;
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(0)

        # ── Header row ────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setSpacing(8)

        num = QLabel(f"#{self.order_id:04d}")
        num.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {TEXT_DARK}; "
            "font-family: 'Courier New', monospace;"
        )
        hdr.addWidget(num)
        hdr.addStretch()

        tbl = QLabel(f"T{self.data.get('table_number', '?')}")
        tbl.setStyleSheet(f"""
            background: {ACCENT_SOFT}; color: {ACCENT};
            font-size: 10px; font-weight: 700;
            padding: 2px 9px; border-radius: 20px;
            border: 1px solid {ACCENT_BORDER};
        """)
        hdr.addWidget(tbl)
        lay.addLayout(hdr)
        lay.addSpacing(6)

        # ── Sub-header ────────────────────────────────────────────────────────
        if self.mode != "public":
            sub = QHBoxLayout()
            sub.setSpacing(8)
            w  = (self.data.get("waiter_name") or "System").title()
            wl = QLabel(f"▸ {w}")
            wl.setStyleSheet(f"font-size: 10px; color: {TEXT_MUTED};")
            sub.addWidget(wl)
            sub.addStretch()
            self._elapsed = ElapsedLabel(self.data.get("created_at"))
            sub.addWidget(self._elapsed)
            lay.addLayout(sub)
        else:
            sc  = SUCCESS_TEXT  if status == "Ready" else WARNING_TEXT
            sb  = SUCCESS_BG    if status == "Ready" else WARNING_BG
            sbd = SUCCESS_BORDER if status == "Ready" else WARNING_BORDER
            pill = QLabel("Ready" if status == "Ready" else "Preparing")
            pill.setStyleSheet(f"""
                background: {sb}; color: {sc};
                font-size: 9px; font-weight: 700;
                padding: 2px 8px; border-radius: 20px;
                border: 1px solid {sbd};
            """)
            lay.addWidget(pill)

        lay.addSpacing(10)

        # ── Divider ───────────────────────────────────────────────────────────
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {BORDER};")
        lay.addWidget(div)
        lay.addSpacing(8)

        # ── Items ─────────────────────────────────────────────────────────────
        for item in items:
            done = item["item_name"] in ticked
            self._add_item(lay, item, done)

        lay.addSpacing(10)

        # ── Footer ────────────────────────────────────────────────────────────
        if status == "Cancelled":
            self._action_btn(
                lay, "Dismiss", DANGER, DANGER_BG, DANGER_BORDER,
                lambda: self.status_changed.emit(self.order_id, "ALL", "Closed")
            )
        elif self.mode == "kitchen":
            if all_ticked:
                oid = self.order_id
                QTimer.singleShot(450, lambda: self._safe(oid, "ALL", "Ready"))
                lbl = QLabel("✓  All done — dispatching")
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setStyleSheet(f"""
                    background: {SUCCESS_BG}; color: {SUCCESS_TEXT};
                    font-size: 10px; font-weight: 700;
                    padding: 7px; border-radius: 7px;
                    border: 1px solid {SUCCESS_BORDER};
                """)
                lay.addWidget(lbl)
            else:
                self._action_btn(
                    lay, "Mark all ready", ACCENT, ACCENT_SOFT, ACCENT_BORDER,
                    lambda: self.status_changed.emit(self.order_id, "ALL", "Ready")
                )
        elif self.mode == "dispatch":
            self._action_btn(
                lay, "Deliver to table", SUCCESS, SUCCESS_BG, SUCCESS_BORDER,
                lambda: self.status_changed.emit(self.order_id, "ALL", "Delivered")
            )
        elif self.mode == "public" and status == "Ready":
            banner = QLabel("READY FOR PICKUP")
            banner.setAlignment(Qt.AlignCenter)
            banner.setStyleSheet(f"""
                background: {SUCCESS_BG}; color: {SUCCESS_TEXT};
                font-size: 10px; font-weight: 800;
                padding: 8px; border-radius: 7px;
                letter-spacing: 1.5px; border: 1px solid {SUCCESS_BORDER};
            """)
            lay.addWidget(banner)

    # ── Item row ──────────────────────────────────────────────────────────────
    def _add_item(self, lay, item, done: bool):
        row = QWidget()
        rl  = QHBoxLayout(row)
        rl.setContentsMargins(0, 2, 0, 2)
        rl.setSpacing(8)

        qty = QLabel(str(int(item["qty"])))
        qty.setFixedSize(22, 22)
        qty.setAlignment(Qt.AlignCenter)
        qty.setStyleSheet(f"""
            background: {BG_CHIP}; color: {TEXT_MID};
            font-size: 10px; font-weight: 700;
            border-radius: 6px;
        """)
        rl.addWidget(qty)

        nl = QLabel(item["item_name"])
        nl.setWordWrap(True)
        if done:
            nl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 12px; font-weight: 400; "
                "text-decoration: line-through;"
            )
        else:
            nl.setStyleSheet(f"color: {TEXT_DARK}; font-size: 12px; font-weight: 600;")
        rl.addWidget(nl, 1)

        if self.mode == "kitchen":
            tb = QPushButton("✓")
            tb.setFixedSize(34, 34)
            tb.setCursor(Qt.PointingHandCursor)
            if done:
                tb.setEnabled(False)
                tb.setStyleSheet(f"""
                    QPushButton {{
                        background: {SUCCESS};
                        color: white;
                        border-radius: 8px;
                        border: none;
                        font-size: 14px;
                        font-weight: 900;
                    }}
                """)
            else:
                tb.setStyleSheet(f"""
                    QPushButton {{
                        background: {BG_CHIP};
                        color: {BORDER_MED};
                        border: 1.5px solid {BORDER_MED};
                        border-radius: 8px;
                        font-size: 14px;
                        font-weight: 900;
                    }}
                    QPushButton:hover {{
                        background: {SUCCESS_BG};
                        color: {SUCCESS};
                        border-color: {SUCCESS_BORDER};
                    }}
                    QPushButton:pressed {{
                        background: {SUCCESS};
                        color: white;
                        border-color: {SUCCESS};
                    }}
                """)
                n = item["item_name"]
                tb.clicked.connect(
                    lambda _, nm=n: self.status_changed.emit(self.order_id, nm, "Ready")
                )
            rl.addWidget(tb)

        lay.addWidget(row)

        if item.get("item_notes"):
            note = QLabel(f"↳  {item['item_notes']}")
            note.setStyleSheet(
                f"font-size: 10px; color: {DANGER}; font-style: italic; "
                f"padding-left: 30px; padding-bottom: 1px;"
            )
            lay.addWidget(note)

    # ── Action button ─────────────────────────────────────────────────────────
    def _action_btn(self, lay, text, color, bg, border_color, cb):
        b = QPushButton(text)
        b.setFixedHeight(34)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: {color};
                border: 1px solid {border_color};
                border-radius: 8px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {color};
                color: white;
                border-color: {color};
            }}
            QPushButton:pressed {{
                background: {color};
                color: white;
            }}
        """)
        b.clicked.connect(cb)
        lay.addWidget(b)

    def _safe(self, oid, item_name, status):
        if self._alive:
            self.status_changed.emit(oid, item_name, status)

    def _flash_new(self):
        if not self._alive:
            return
        orig  = self.styleSheet()
        flash = orig.replace(f"background: {BG_CARD};", f"background: {SUCCESS_BG};")
        self.setStyleSheet(flash)
        ref = weakref.ref(self)
        QTimer.singleShot(800, lambda: (
            ref() is not None
            and getattr(ref(), "_alive", False)
            and ref().setStyleSheet(orig)
        ))

    def _age(self) -> int:
        try:
            ct = self.data.get("created_at")
            if not isinstance(ct, datetime):
                ct = datetime.strptime(str(ct or "")[:19], "%Y-%m-%d %H:%M:%S")
            return max(0, int((datetime.now() - ct).total_seconds()))
        except Exception:
            return 0


# ── Header Bar ────────────────────────────────────────────────────────────────
class HeaderBar(QWidget):
    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setStyleSheet(f"""
            HeaderBar {{
                background: {BG_HEADER};
                border-bottom: 1px solid {BORDER};
            }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.setSpacing(12)

        stripe_color = {
            "kitchen": ACCENT, "dispatch": SUCCESS, "unified": WARNING
        }.get(mode, ACCENT)

        stripe = QFrame()
        stripe.setFixedSize(3, 22)
        stripe.setStyleSheet(f"background: {stripe_color}; border-radius: 2px;")
        lay.addWidget(stripe)

        title = QLabel({
            "kitchen": "Kitchen Display",
            "dispatch": "Dispatch Board",
            "unified":  "Order Monitor",
        }.get(mode, "KDS"))
        title.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {TEXT_DARK};"
        )
        lay.addWidget(title)
        lay.addStretch()

        self.count_badge = QLabel("0 orders")
        self.count_badge.setStyleSheet(f"""
            background: {BG_CHIP}; color: {TEXT_MUTED};
            font-size: 11px; font-weight: 600;
            padding: 3px 12px; border-radius: 20px;
            border: 1px solid {BORDER};
        """)
        lay.addWidget(self.count_badge)

        sep = QFrame(); sep.setFixedSize(1, 20)
        sep.setStyleSheet(f"background: {BORDER_MED};")
        lay.addWidget(sep)

        self.dot = PulseDot(SUCCESS, 7)
        lay.addWidget(self.dot)
        self.conn_lbl = QLabel("Live")
        self.conn_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {SUCCESS};"
        )
        lay.addWidget(self.conn_lbl)

        sep2 = QFrame(); sep2.setFixedSize(1, 20)
        sep2.setStyleSheet(f"background: {BORDER_MED};")
        lay.addWidget(sep2)

        self.clock = QLabel()
        self.clock.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {TEXT_MID}; "
            "font-family: 'Courier New', monospace;"
        )
        lay.addWidget(self.clock)
        self._ck()
        ct = QTimer(self)
        ct.timeout.connect(self._ck)
        ct.start(1000)

    def _ck(self):
        self.clock.setText(datetime.now().strftime("%H:%M:%S"))

    def set_connected(self, ok: bool):
        if ok:
            self.dot.set_color(SUCCESS)
            self.conn_lbl.setText("Live")
            self.conn_lbl.setStyleSheet(
                f"font-size: 11px; font-weight: 600; color: {SUCCESS};"
            )
        else:
            self.dot.set_color(DANGER)
            self.conn_lbl.setText("Offline")
            self.conn_lbl.setStyleSheet(
                f"font-size: 11px; font-weight: 600; color: {DANGER};"
            )

    def set_count(self, n: int):
        if n >= 10:  bg, c = DANGER_BG,  DANGER_TEXT
        elif n >= 5: bg, c = WARNING_BG, WARNING_TEXT
        else:        bg, c = BG_CHIP,    TEXT_MUTED
        self.count_badge.setText(f"{n} order{'s' if n != 1 else ''}")
        self.count_badge.setStyleSheet(f"""
            background: {bg}; color: {c};
            font-size: 11px; font-weight: 600;
            padding: 3px 12px; border-radius: 20px;
            border: 1px solid {BORDER};
        """)


# ── Column Header (unified mode only) ────────────────────────────────────────
class ColHeader(QWidget):
    def __init__(self, title: str, color: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(8)

        stripe = QFrame()
        stripe.setFixedSize(3, 16)
        stripe.setStyleSheet(f"background: {color}; border-radius: 1px;")
        lay.addWidget(stripe)

        lbl = QLabel(title.upper())
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {TEXT_MUTED}; letter-spacing: 1.2px;"
        )
        lay.addWidget(lbl)
        lay.addStretch()

        self.count_lbl = QLabel("0")
        self.count_lbl.setStyleSheet(f"""
            background: {BG_CHIP}; color: {TEXT_MUTED};
            font-size: 10px; font-weight: 600;
            padding: 1px 8px; border-radius: 20px;
            border: 1px solid {BORDER};
        """)
        lay.addWidget(self.count_lbl)

    def set_count(self, n: int):
        self.count_lbl.setText(str(n))


# ── Empty State ───────────────────────────────────────────────────────────────
class EmptyState(QWidget):
    def __init__(self, message="No active orders", parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(6)
        for txt, style in [
            ("○", f"font-size: 32px; color: {BORDER_MED};"),
            (message, f"font-size: 13px; font-weight: 600; color: {TEXT_MUTED};"),
            ("Waiting for new orders", f"font-size: 11px; color: {BORDER_MED};"),
        ]:
            l = QLabel(txt)
            l.setAlignment(Qt.AlignCenter)
            l.setStyleSheet(style)
            lay.addWidget(l)


# ── KDS Window ────────────────────────────────────────────────────────────────
class KDSWindow(QWidget):
    def __init__(self, mode="kitchen"):
        super().__init__()
        self.mode = mode
        self.setWindowTitle(f"Havano POS — {mode.title()}")
        self.setMinimumSize(1280, 800)
        self.setStyleSheet(f"QWidget {{ background: {BG_ROOT}; }}")

        self._known_ids:   set  = set()
        self._local_ticks: dict = {}
        self._last_count:  int  = 0

        self._resize_tmr = QTimer(self)
        self._resize_tmr.setSingleShot(True)
        self._resize_tmr.timeout.connect(self._refresh)

        self._build_ui()
        self._start_ws()
        self._refresh()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = HeaderBar(self.mode)
        root.addWidget(self.header)

        body = QWidget()
        body.setStyleSheet(f"background: {BG_ROOT};")
        self._body_lay = QVBoxLayout(body)
        self._body_lay.setContentsMargins(20, 16, 20, 16)
        self._body_lay.setSpacing(0)
        root.addWidget(body, 1)

        if self.mode == "unified":
            self._build_unified()
        else:
            self._build_single()

    def _build_single(self):
        scroll_style = (
            f"QScrollArea {{ background: transparent; border: none; }}"
            f"QScrollBar:vertical {{ background: {BG_CHIP}; width: 4px; border-radius: 2px; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER_MED}; border-radius: 2px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}"
        )
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet(scroll_style)

        self.board = FlowContainer()
        self.board.setStyleSheet("background: transparent;")
        self.grid = FlowLayout(self.board, margin=0, h=12, v=12)
        self.scroll.setWidget(self.board)
        self._body_lay.addWidget(self.scroll, 1)

        self.empty = EmptyState(
            "No active orders" if self.mode == "kitchen" else "Nothing ready to dispatch"
        )
        self.empty.hide()
        self._body_lay.addWidget(self.empty, 1)

    def _build_unified(self):
        scroll_style = (
            "QScrollArea { background: transparent; border: none; }"
            f"QScrollBar:vertical {{ background: {BG_CHIP}; width: 4px; border-radius: 2px; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER_MED}; border-radius: 2px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}"
        )

        cw = QWidget()
        cw.setStyleSheet("background: transparent;")
        cl = QHBoxLayout(cw)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(16)

        def make_col(title, color):
            wrap = QWidget()
            wrap.setStyleSheet("background: transparent;")
            wl = QVBoxLayout(wrap)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.setSpacing(8)

            # Minimal column header — no background, just label + stripe
            ch = ColHeader(title, color)
            wl.addWidget(ch)

            sc = QScrollArea()
            sc.setWidgetResizable(True)
            sc.setFrameShape(QFrame.NoFrame)
            sc.setStyleSheet(scroll_style)

            cont = FlowContainer()
            cont.setStyleSheet("background: transparent;")
            grid = FlowLayout(cont, margin=0, h=10, v=10)
            sc.setWidget(cont)
            wl.addWidget(sc, 1)

            emp = EmptyState()
            emp.hide()
            wl.addWidget(emp, 1)

            return wrap, ch, grid, emp

        self.prep_wrap,  self.prep_ch,  self.prep_grid,  self.prep_empty  = make_col("Preparing", WARNING)
        self.ready_wrap, self.ready_ch, self.ready_grid, self.ready_empty = make_col("Ready",     SUCCESS)

        cl.addWidget(self.prep_wrap, 1)
        cl.addWidget(self.ready_wrap, 1)
        self._body_lay.addWidget(cw, 1)

    # ── WebSocket ─────────────────────────────────────────────────────────────
    def _start_ws(self):
        self.ws = KDSClientThread()
        self.ws.message_received.connect(lambda _: QTimer.singleShot(0, self._refresh))
        self.ws.connection_changed.connect(self.header.set_connected)
        self.ws.start()

    # ── Data ──────────────────────────────────────────────────────────────────
    def _refresh(self):
        try:
            from models.restaurant_order import get_kds_orders, get_waiter_name
            orders = get_kds_orders()
            for o in orders:
                o["waiter_name"] = get_waiter_name(o.get("waiter_id"))
            self._populate(orders)
        except Exception as e:
            print(f"[KDS] Refresh error: {e}")

    def _populate(self, orders):
        cur = {o["id"] for o in orders}
        new = cur - self._known_ids
        self._known_ids  = cur
        if new and self._last_count > 0:
            self._alert()
        self._last_count = len(orders)
        if self.mode == "unified":
            self._pop_unified(orders, new)
        else:
            self._pop_single(orders, new)

    def _pop_single(self, orders, new_ids):
        filtered = [
            o for o in orders if (
                (self.mode == "kitchen"  and o["prep_status"] in ("Preparing", "Cancelled")) or
                (self.mode == "dispatch" and o["prep_status"] == "Ready")
            )
        ]

        def sk(o):
            if o["prep_status"] == "Cancelled":
                return (0, 0)
            return (1, -self._age(o))

        filtered.sort(key=sk)

        while self.grid.count():
            it = self.grid.takeAt(0)
            if it and it.widget():
                it.widget().deleteLater()

        self.header.set_count(len(filtered))

        if not filtered:
            self.scroll.hide()
            self.empty.show()
            return

        self.empty.hide()
        self.scroll.show()
        for o in filtered:
            ticks = self._local_ticks.get(o["id"], set())
            card  = OrderCard(o, mode=self.mode, local_ticks=ticks, is_new=o["id"] in new_ids)
            card.status_changed.connect(self._on_status)
            self.grid.addWidget(card)

    def _pop_unified(self, orders, new_ids):
        for g in (self.prep_grid, self.ready_grid):
            while g.count():
                it = g.takeAt(0)
                if it and it.widget():
                    it.widget().deleteLater()

        prep  = [o for o in orders if o["prep_status"] in ("Preparing", "Cancelled")]
        ready = [o for o in orders if o["prep_status"] == "Ready"]
        self.header.set_count(len(prep) + len(ready))

        self.prep_ch.set_count(len(prep))
        self.ready_ch.set_count(len(ready))

        if prep:
            self.prep_empty.hide()
            for o in prep:
                card = OrderCard(o, mode="public", is_new=o["id"] in new_ids)
                self.prep_grid.addWidget(card)
        else:
            self.prep_empty.show()

        if ready:
            self.ready_empty.hide()
            for o in ready:
                card = OrderCard(o, mode="public", is_new=o["id"] in new_ids)
                self.ready_grid.addWidget(card)
        else:
            self.ready_empty.show()

    # ── Status ────────────────────────────────────────────────────────────────
    def _on_status(self, order_id: int, item_name: str, status: str):
        try:
            from models.restaurant_order import (
                update_order_prep_status, update_item_prep_status
            )
            from services.kds_service import kds_service

            if status == "Closed":
                update_order_prep_status(order_id, "Closed")
                self._local_ticks.pop(order_id, None)
            elif item_name == "ALL":
                update_order_prep_status(order_id, status)
                self._local_ticks.pop(order_id, None)
            else:
                self._local_ticks.setdefault(order_id, set()).add(item_name)
                update_item_prep_status(order_id, item_name, status)

            kds_service.broadcast_sync({"type": "refresh", "order_id": order_id})
        except Exception as e:
            print(f"[KDS] Update error: {e}")
        finally:
            self._refresh()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _age(self, o) -> int:
        try:
            ct = o.get("created_at")
            if not isinstance(ct, datetime):
                ct = datetime.strptime(str(ct or "")[:19], "%Y-%m-%d %H:%M:%S")
            return max(0, int((datetime.now() - ct).total_seconds()))
        except Exception:
            return 0

    def _alert(self):
        orig = self.windowTitle()
        def flash(n=0):
            if n >= 6:
                self.setWindowTitle(orig)
                return
            self.setWindowTitle("🔔  NEW ORDER!" if n % 2 == 0 else orig)
            QTimer.singleShot(300, lambda: flash(n + 1))
        flash()
        try:
            QApplication.beep()
        except Exception:
            pass

    # ── Events ────────────────────────────────────────────────────────────────
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._resize_tmr.start(180)

    def closeEvent(self, e):
        self.ws.stop()
        super().closeEvent(e)


# ── Convenience Subclasses ────────────────────────────────────────────────────
class KitchenWindow(KDSWindow):
    def __init__(self): super().__init__(mode="kitchen")

class ReadyBoardWindow(KDSWindow):
    def __init__(self): super().__init__(mode="dispatch")

class UnifiedMonitorWindow(KDSWindow):
    def __init__(self): super().__init__(mode="unified")
# =============================================================================
# views/dialogs/users_dialog.py
# Clean Frappe-style table layout - matches CompanyDefaultsPage aesthetic
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QScrollArea, QFrame, QMessageBox, QCheckBox,
    QSpinBox, QAbstractItemView, QSizePolicy,
    QApplication, QDateEdit, QInputDialog, QGridLayout,
)
from PySide6.QtCore import QDate
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QColor, QFont
import qtawesome as qta
from PySide6.QtCore  import QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui   import QPainter, QLinearGradient, QRadialGradient

# ── Palette (mirrors CompanyDefaultsPage exactly) ──────────────────────────────
from theme import *

FIELD_H   = 36
LBL_W     = 120
ROW_SP    = 12


# ── Shared widget helpers (same pattern as company_defaults) ──────────────────

def _sec(text):
    l = QLabel(text.upper())
    l.setStyleSheet(
        f"color:{MUTED};font-size:10px;font-weight:bold;"
        f"background:transparent;letter-spacing:1.5px;"
    )
    l.setFixedHeight(20)
    return l


def _hr():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{BORDER};border:none;")
    return f


def _lbl(text, w=LBL_W):
    l = QLabel(text)
    l.setFixedWidth(w)
    l.setFixedHeight(FIELD_H)
    l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    l.setStyleSheet(
        f"color:{MUTED};font-size:12px;font-weight:bold;background:transparent;"
    )
    return l


def _inp(placeholder="", password=False, read_only=False):
    w = QLineEdit()
    w.setFixedHeight(FIELD_H)
    w.setPlaceholderText(placeholder)
    if password:
        w.setEchoMode(QLineEdit.Password)
    if read_only:
        w.setReadOnly(True)
    bg = LIGHT if read_only else WHITE
    w.setStyleSheet(f"""
        QLineEdit {{
            background:{bg}; color:{DARK_TEXT};
            border:1px solid {BORDER}; border-radius:6px;
            padding:0 12px; font-size:13px;
        }}
        QLineEdit:focus {{ border:2px solid {ACCENT}; }}
        QLineEdit:hover {{ border:1px solid {MID}; }}
        QLineEdit:read-only {{ color:{MUTED}; }}
    """)
    return w


def _combo(options, editable=False):
    w = QComboBox()
    w.addItems(options)
    w.setFixedHeight(FIELD_H)
    w.setEditable(editable)
    if editable:
        w.completer().setFilterMode(Qt.MatchContains)
        w.completer().setCaseSensitivity(Qt.CaseInsensitive)
    w.setStyleSheet(f"""
        QComboBox {{
            background:{WHITE}; color:{DARK_TEXT};
            border:1px solid {BORDER}; border-radius:6px;
            padding:0 12px; font-size:13px;
        }}
        QComboBox:focus {{ border:2px solid {ACCENT}; }}
        QComboBox QAbstractItemView {{
            background:{WHITE}; border:1px solid {BORDER};
            selection-background-color:{ACCENT}; selection-color:{WHITE};
        }}
    """)
    return w


def _get_default_store_name() -> str:
    """
    Returns configured default store/warehouse name from company_defaults or database.
    Auto-seeds and defaults to 'Main Store' if blank or in offline mode.
    """
    try:
        from models.company_defaults import get_defaults
        defs = get_defaults() or {}
        wh = (defs.get("server_warehouse") or defs.get("company_name") or "").strip()
        if wh:
            return wh
    except Exception:
        pass

    try:
        from database.db import get_connection, fetchone_dict
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT TOP 1 name FROM warehouses WHERE active=1 ORDER BY id")
        row = fetchone_dict(cur)
        conn.close()
        if row and row.get("name") and str(row["name"]).strip():
            return str(row["name"]).strip()
    except Exception:
        pass

    return "Main Store"


def _field_row(label_text, content, lw=LBL_W):
    row = QHBoxLayout()
    row.setSpacing(16)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(_lbl(label_text, lw))
    if isinstance(content, QHBoxLayout) or isinstance(content, QVBoxLayout):
        row.addLayout(content, 1)
    else:
        row.addWidget(content, 1)
    return row


def _add_btn_sm(callback):
    b = QPushButton()
    b.setIcon(qta.icon("fa5s.plus", color=WHITE))
    b.setFixedSize(36, 36)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"""
        QPushButton {{
            background:{ACCENT}; border:none; border-radius:6px;
        }}
        QPushButton:hover {{ background:{ACCENT}dd; }}
    """)
    b.clicked.connect(callback)
    return b


def _section_header(layout, title, top_margin=8):
    layout.addSpacing(top_margin)
    layout.addWidget(_sec(title))
    layout.addSpacing(6)
    layout.addWidget(_hr())
    layout.addSpacing(10)


def _combo_set(combo: QComboBox, value: str):
    idx = combo.findText(value, Qt.MatchFixedString)
    if idx >= 0:
        combo.setCurrentIndex(idx)


def _combo_get(combo: QComboBox) -> str:
    return (combo.currentText() or "").strip()


def _action_btn(text, color=ACCENT, hover=None, text_color=WHITE, border=None):
    hover = hover or color
    border_css = f"border:1.5px solid {border};" if border else "border:none;"
    w = QPushButton(text)
    w.setFixedHeight(34)
    w.setCursor(Qt.PointingHandCursor)
    w.setStyleSheet(f"""
        QPushButton {{
            background:{color}; color:{text_color};
            {border_css}
            border-radius:6px; font-size:12px;
            font-weight:600; padding:0 16px;
        }}
        QPushButton:hover {{ background:{hover}; }}
        QPushButton:disabled {{ background:{LIGHT}; color:{MUTED}; border:1px solid {BORDER}; }}
    """)
    return w


# =============================================================================
# TogglePill - faithful PySide6 port of CSS checkbox-wrapper-5
#
# Visuals matched to the original:
#   • Track  : linear gradient pill (#f19af3 -> #974962ff) when ON,
#              flat #d7d7d7 when OFF  - animates with QPropertyAnimation
#   • Knob   : smaller circle with gradient (#dedede -> #ffffff) +
#              drop-shadow (rgba 0,0,0,0.3) sliding left ↔ right
#   • Size   : driven by a single --size variable (default 22 px, same ratio)
#
# Public API mirrors QCheckBox:
#   toggle.isChecked()    -> bool
#   toggle.setChecked(b)  -> None
# =============================================================================

from PySide6.QtCore  import QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui   import QPainter, QLinearGradient, QColor, QPen, QRadialGradient


class _TogglePill(QWidget):
    """
    The actual pill widget - drawn entirely with QPainter so every CSS
    detail (gradient track, floating knob, smooth slide) is reproduced.
    """

    def __init__(self, size=22, parent=None):
        super().__init__(parent)
        self._size     = size
        self._checked  = True
        # _knob_x goes from 0.0 (OFF, knob left) to 1.0 (ON, knob right)
        self._knob_pos = 1.0

        w = int(2.2 * size)
        h = size
        self.setFixedSize(w, h)
        self.setCursor(Qt.PointingHandCursor)

        self._anim = QPropertyAnimation(self, b"knob_pos", self)
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

    # ── animation property ────────────────────────────────────────────────────
    def _get_knob_pos(self):
        return self._knob_pos

    def _set_knob_pos(self, v):
        self._knob_pos = v
        self.update()

    knob_pos = Property(float, _get_knob_pos, _set_knob_pos)

    # ── state ─────────────────────────────────────────────────────────────────
    def isChecked(self):
        return self._checked

    def setChecked(self, value: bool, animated=False):
        self._checked  = bool(value)
        target         = 1.0 if self._checked else 0.0
        if animated:
            self._anim.stop()
            self._anim.setStartValue(self._knob_pos)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._knob_pos = target
            self.update()

    def mousePressEvent(self, _ev):
        self.setChecked(not self._checked, animated=True)

    # ── painting ──────────────────────────────────────────────────────────────
    def paintEvent(self, _ev):
        p   = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s   = self._size
        w   = self.width()
        h   = self.height()
        r   = h / 2          # pill corner radius

        # ── track ─────────────────────────────────────────────────────────────
        # Blend between grey (OFF) and gradient-pink (ON) using knob_pos
        t = self._knob_pos   # 0.0 -> OFF, 1.0 -> ON

        if t < 0.01:
            # fully OFF - flat grey
            p.setBrush(QColor("#d7d7d7"))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(0, 0, w, h, r, r)
        else:
            # gradient track (fades in as knob moves right)
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0, QColor("#f19af3"))
            grad.setColorAt(1, QColor("#f099b5"))

            if t > 0.99:
                p.setBrush(grad)
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(0, 0, w, h, r, r)
            else:
                # blend: draw grey then overlay gradient at opacity=t
                p.setBrush(QColor("#d7d7d7"))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(0, 0, w, h, r, r)

                p.setOpacity(t)
                p.setBrush(grad)
                p.drawRoundedRect(0, 0, w, h, r, r)
                p.setOpacity(1.0)

        # ── knob shadow ───────────────────────────────────────────────────────
        knob_d   = 0.8 * s
        knob_r   = knob_d / 2
        off_x    = 0.1 * s
        on_x     = 1.3 * s
        knob_x   = off_x + self._knob_pos * (on_x - off_x)
        knob_y   = 0.1 * s
        cx       = knob_x + knob_r
        cy       = knob_y + knob_r

        shadow = QRadialGradient(cx, cy + 4, knob_r * 1.1)
        shadow.setColorAt(0,   QColor(0, 0, 0, 55))
        shadow.setColorAt(0.6, QColor(0, 0, 0, 30))
        shadow.setColorAt(1,   QColor(0, 0, 0, 0))
        p.setBrush(shadow)
        p.setPen(Qt.NoPen)
        p.drawEllipse(
            int(knob_x - knob_r * 0.15),
            int(knob_y + knob_r * 0.5),
            int(knob_d * 1.3),
            int(knob_d * 0.9),
        )

        # ── knob face ─────────────────────────────────────────────────────────
        knob_grad = QLinearGradient(cx, knob_y, cx, knob_y + knob_d)
        knob_grad.setColorAt(0, QColor("#dedede"))
        knob_grad.setColorAt(1, QColor("#ffffff"))
        p.setBrush(knob_grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(int(knob_x), int(knob_y), int(knob_d), int(knob_d))

        p.end()


class ToggleSwitch(QWidget):
    """
    Full row widget: pill toggle + label + hint line.
    Drop-in replacement for QCheckBox - same isChecked() / setChecked() API.
    """
    def __init__(self, label: str, hint: str = "", size: int = 22, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(14)

        self._pill = _TogglePill(size=size, parent=self)
        layout.addWidget(self._pill)

        txt = QVBoxLayout()
        txt.setSpacing(1)
        txt.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"font-size:12px;font-weight:600;color:{DARK_TEXT};background:transparent;"
        )
        txt.addWidget(lbl)

        if hint:
            hl = QLabel(hint)
            hl.setStyleSheet(
                f"font-size:10px;color:{MUTED};background:transparent;"
            )
            txt.addWidget(hl)

        layout.addLayout(txt)
        layout.addStretch()

    def isChecked(self) -> bool:
        return self._pill.isChecked()

    def setChecked(self, value: bool):
        self._pill.setChecked(value, animated=False)


# =============================================================================
# Add / Edit User - clean side-panel form matching CompanyDefaults layout
# =============================================================================

class _UserFormDialog(QDialog):
    def __init__(self, parent=None, user: dict = None):
        super().__init__(parent)
        self._user = user
        self.saved_user = None

        title = "New User" if not user else \
            f"Edit - {user.get('full_name') or user.get('username', '')}"
        self.setWindowTitle(title)
        self.setMinimumWidth(540)
        self.resize(600, 700)
        self.setMinimumHeight(600)
        self.setModal(True)
        self.setWindowState(Qt.WindowMaximized)
        self.setStyleSheet(f"QDialog {{ background:{OFF_WHITE}; font-family:'Segoe UI',sans-serif; }}")

        try:
            from models.company_defaults import get_defaults
            self._defs = get_defaults()
        except Exception:
            self._defs = {}

        self._build()
        
        if user:
            self._populate(user)
        else:
            self._autofill_defaults()

    # -------------------------------------------------------------------------
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar
        hdr = QWidget()
        hdr.setFixedHeight(56)
        hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 0, 20, 0)
        
        title_lbl = QLabel(self.windowTitle())
        title_lbl.setStyleSheet(f"color:{WHITE};font-size:15px;font-weight:bold;background:transparent;")
        hl.addWidget(title_lbl)
        
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("font-size:11px;color:white;background:transparent;margin-left:15px;")
        hl.addWidget(self._status_lbl, 1)

        cancel_btn = _action_btn("Cancel", color=WHITE, hover=LIGHT, text_color=DARK_TEXT, border=BORDER)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setFixedHeight(30)
        
        self._save_btn = _action_btn("Save User", color=SUCCESS, hover=SUCCESS_H)
        self._save_btn.clicked.connect(self._save)
        self._save_btn.setFixedHeight(30)

        hl.addWidget(cancel_btn)
        hl.addSpacing(10)
        hl.addWidget(self._save_btn)
        
        root.addWidget(hdr)

        # Accent line
        bar = QFrame(); bar.setFixedHeight(3)
        bar.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {NAVY},stop:0.5 {ACCENT},stop:1 {NAVY_3});
        """)
        root.addWidget(bar)

        # Scrollable form body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border:none; background:{OFF_WHITE}; }}
            QScrollBar:vertical {{
                background:{LIGHT}; width:8px; border-radius:4px;
            }}
            QScrollBar::handle:vertical {{
                background:#b0c4de; border-radius:4px; min-height:32px;
            }}
        """)

        form = QWidget()
        form.setStyleSheet(f"background:{OFF_WHITE};")
        fl = QVBoxLayout(form)
        fl.setContentsMargins(32, 20, 32, 24)
        fl.setSpacing(ROW_SP)

        # ── User Fields (2-column layout) ──────────────────────────────────────
        self._f_fullname = _inp("Full Name")
        self._f_pin      = _inp("PIN", password=True)
        self._f_pin.setMaxLength(4)
        
        row1 = QHBoxLayout()
        row1.setSpacing(32)
        row1.addLayout(_field_row("Full Name", self._f_fullname, lw=80))
        row1.addLayout(_field_row("PIN", self._f_pin, lw=60))
        fl.addLayout(row1)

        self._f_role   = _combo(["cashier", "admin", "pharmacist"])
        self._f_active = _combo(["Active", "Inactive"])
        
        row2 = QHBoxLayout()
        row2.setSpacing(32)
        row2.addLayout(_field_row("Role", self._f_role, lw=80))
        row2.addLayout(_field_row("Status", self._f_active, lw=60))
        fl.addLayout(row2)

        self._f_store = _inp("Default Store")
        self._f_allowed_stores = _inp("Allowed Stores")

        row3 = QHBoxLayout()
        row3.setSpacing(32)
        row3.addLayout(_field_row("Default Store", self._f_store, lw=80))
        row3.addLayout(_field_row("Allowed Stores", self._f_allowed_stores, lw=80))
        fl.addLayout(row3)

        # ── END OF TAB 1 ────────────────────────────────────────────────────────
        fl.addStretch()
        scroll.setWidget(form)

        # ── TAB 2: Settings ───────────────────────────────────────────────────
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setFrameShape(QFrame.NoFrame)
        settings_scroll.setStyleSheet(scroll.styleSheet())
        
        settings_form = QWidget()
        settings_form.setStyleSheet(f"background:{OFF_WHITE};")
        settings_fl = QVBoxLayout(settings_form)
        settings_fl.setContentsMargins(32, 20, 32, 24)
        settings_fl.setSpacing(ROW_SP)

        # ── Permissions ───────────────────────────────────────────────────────
        _section_header(settings_fl, "Permissions", top_margin=0)



        # ── Toggle switches ──────────────────────────────────────────────────
        toggles_row = QHBoxLayout()
        toggles_row.setContentsMargins(0, 0, 0, 0)
        toggles_row.setSpacing(16)

        toggles_grid = QGridLayout()
        toggles_grid.setSpacing(10)
        toggles_grid.setContentsMargins(0, 0, 0, 0)

        self._p_discount = ToggleSwitch("Allow discounts",      "Cashier can apply a discount at checkout")
        self._p_receipt  = ToggleSwitch("Process payments",     "Cashier can complete and tender sales")
        self._p_cn       = ToggleSwitch("Issue credit notes",   "Cashier can process returns and refunds")
        self._p_reprint  = ToggleSwitch("Reprint receipts",     "Cashier can reprint a past receipt")
        self._p_laybye   = ToggleSwitch("Allow laybye",         "Cashier can create and manage laybyes")
        self._p_quote    = ToggleSwitch("Allow quotation",      "Cashier can create and print quotations")
        self._p_reconcile = ToggleSwitch("Allow Shift Reconcile", "Permission to close whole shift and modify reconciliations")
        self._p_view_expected = ToggleSwitch("View Expected Cash", "Can see the expected amount when closing shift")
        self._p_pharmacist_pay = ToggleSwitch("Allow Pharmacist Pay", "Pharmacist can process payment for loaded orders")
        self._p_backoffice = ToggleSwitch("Allow Backoffice Access", "User can access the management dashboard")
        self._p_pos = ToggleSwitch("Allow POS Access", "User can access the POS interface")
        self._p_pharmacist_pay.setVisible(False)

        r, c = 0, 0
        for toggle in [self._p_discount, self._p_receipt, self._p_cn,
                       self._p_reprint, self._p_laybye, self._p_quote, self._p_reconcile, self._p_view_expected, self._p_pharmacist_pay, self._p_backoffice, self._p_pos]:
            toggles_grid.addWidget(toggle, r, c)
            c += 1
            if c == 4:
                c = 0
                r += 1

        toggles_row.addLayout(toggles_grid)
        settings_fl.addLayout(toggles_row)

        # ── Restaurant Permissions ─────────────────────────────────────────────
        _section_header(settings_fl, "Restaurant Permissions", top_margin=10)
        
        rest_row = QHBoxLayout()
        rest_row.setContentsMargins(0, 0, 0, 0)
        rest_row.setSpacing(16)

        rest_grid = QGridLayout()
        rest_grid.setSpacing(10)
        rest_grid.setContentsMargins(0, 0, 0, 0)

        self._p_close_table = ToggleSwitch("Allow Close Table", "Permission to finalize and close restaurant tables")
        self._p_prebill     = ToggleSwitch("Allow Pre-bill",    "Permission to print pre-bill/proforma receipts")
        self._p_pay_kot     = ToggleSwitch("Allow Pay KOT",     "Permission to process payments for KOT orders")
        self._p_edit_kot    = ToggleSwitch("Allow Edit KOT",    "Permission to modify or add items to active orders")
        self._p_cancel_kot  = ToggleSwitch("Allow Cancel Order","Permission to cancel or remove restaurant orders")
        self._p_auto_logout = ToggleSwitch("Auto Logout",       "Automatically log out after completing an order")
        self._p_assign_waiter = ToggleSwitch("Assign Waiters",  "Permission to assign waiters to available tables")

        r_row, r_col = 0, 0
        for toggle in [self._p_close_table, self._p_prebill, self._p_pay_kot,
                       self._p_edit_kot, self._p_cancel_kot, self._p_auto_logout, self._p_assign_waiter]:
            rest_grid.addWidget(toggle, r_row, r_col)
            r_col += 1
            if r_col == 4:
                r_col = 0
                r_row += 1

        rest_row.addLayout(rest_grid)
        settings_fl.addLayout(rest_row)
        _section_header(settings_fl, "Discount Limits", top_margin=10)

        # Max discount
        self._f_max_disc = QSpinBox()
        self._f_max_disc.setRange(0, 100)
        self._f_max_disc.setSuffix(" %")
        self._f_max_disc.setFixedHeight(FIELD_H)
        self._f_max_disc.setStyleSheet(f"""
            QSpinBox {{
                background:{WHITE}; color:{DARK_TEXT};
                border:1px solid {BORDER}; border-radius:6px;
                padding:0 12px; font-size:13px;
            }}
            QSpinBox:focus {{ border:2px solid {ACCENT}; }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width:22px; border:none; background:{LIGHT}; border-radius:3px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background:{BORDER};
            }}
        """)
        settings_fl.addLayout(_field_row("Max Discount", self._f_max_disc))



        settings_fl.addStretch()
        settings_scroll.setWidget(settings_form)
        
        from PySide6.QtWidgets import QTabWidget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: {OFF_WHITE}; }}
            QTabBar::tab {{ background: {LIGHT}; padding: 8px 16px; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; color: {MUTED}; font-weight: bold; }}
            QTabBar::tab:selected {{ background: {OFF_WHITE}; color: {DARK_TEXT}; }}
        """)
        self.tabs.addTab(scroll, "Detail/Information")
        self.tabs.addTab(settings_scroll, "Settings")

        # Payment Methods Tab
        pm_scroll = QScrollArea()
        pm_scroll.setWidgetResizable(True)
        pm_scroll.setFrameShape(QFrame.NoFrame)
        pm_scroll.setStyleSheet(scroll.styleSheet())
        
        pm_form = QWidget()
        pm_form.setStyleSheet(f"background:{OFF_WHITE};")
        pm_fl = QVBoxLayout(pm_form)
        pm_fl.setContentsMargins(32, 20, 32, 24)
        pm_fl.setSpacing(ROW_SP)
        
        _section_header(pm_fl, "Allowed Payment Methods", top_margin=0)
        
        self.payment_toggles = {}
        try:
            from database.db import get_connection, fetchall_dicts
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT name FROM modes_of_payment WHERE enabled=1 ORDER BY display_order")
            modes = fetchall_dicts(cur)
            conn.close()
            pm_col = QVBoxLayout()
            pm_col.setSpacing(10)
            pm_col.setContentsMargins(0, 0, 0, 0)
            for mode in modes:
                m_name = mode['name']
                t = ToggleSwitch(m_name, f"Allow {m_name} for this user")
                t.setChecked(True)
                pm_col.addWidget(t)
                self.payment_toggles[m_name] = t
            pm_fl.addLayout(pm_col)
        except Exception:
            pass
            
        pm_fl.addStretch()
        
        tab3_container = QWidget()
        tab3_container.setStyleSheet("background: transparent;")
        tab3_layout = QHBoxLayout(tab3_container)
        tab3_layout.setContentsMargins(0, 0, 0, 0)
        tab3_layout.addWidget(pm_form)
        tab3_layout.addStretch()
        
        pm_scroll.setWidget(tab3_container)
        self.tabs.addTab(pm_scroll, "Payment Methods")
        
        root.addWidget(self.tabs, 1)

        # Auto-generate username logic removed
        self._f_role.currentTextChanged.connect(self._toggle_pharmacist_pay)
        self._f_role.currentTextChanged.connect(self._apply_role_defaults)

    # -------------------------------------------------------------------------
    def _toggle_pharmacist_pay(self, role_text):
        if role_text.lower() == "pharmacist":
            self._p_pharmacist_pay.setVisible(True)
        else:
            self._p_pharmacist_pay.setVisible(False)

    # -------------------------------------------------------------------------

    def _add_new_warehouse(self):
        name, ok = QInputDialog.getText(self, "Add Warehouse", "Warehouse Name:")
        if ok and name.strip():
            try:
                from models.warehouse import create_warehouse
                create_warehouse(name.strip(), self._defs.get("company_id", 1))
                self._reload_assignments()
                self._f_whouse.setCurrentText(name.strip())
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create warehouse: {e}")

    def _add_new_cost_center(self):
        name, ok = QInputDialog.getText(self, "Add Cost Center", "Cost Center Name:")
        if ok and name.strip():
            try:
                from models.cost_center import create_cost_center
                create_cost_center(name.strip(), self._defs.get("company_id", 1))
                self._reload_assignments()
                self._f_cost.setCurrentText(name.strip())
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create cost center: {e}")

    # -------------------------------------------------------------------------
    def _auto_username(self):
        pass

    def _autofill_defaults(self):
        self._apply_role_defaults(self._f_role.currentText())
        def_store = _get_default_store_name()
        self._f_store.setText(def_store)
        self._f_allowed_stores.setText(def_store)

    def _apply_role_defaults(self, role_text: str):
        # We only auto-apply if we are not populating an existing user
        # or if they explicitly change the role combo box.
        role = role_text.strip().lower()
        is_admin = (role == "admin")
        
        self._p_discount.setChecked(is_admin)
        self._p_receipt.setChecked(True)
        self._p_cn.setChecked(is_admin)
        self._p_reprint.setChecked(is_admin)
        self._p_laybye.setChecked(is_admin)
        self._p_quote.setChecked(is_admin)
        self._p_reconcile.setChecked(True)
        self._p_view_expected.setChecked(is_admin)
        self._p_pharmacist_pay.setChecked(role == "pharmacist")
        self._p_backoffice.setChecked(is_admin)
        self._p_pos.setChecked(True)
        
        self._p_close_table.setChecked(True)
        self._p_prebill.setChecked(True)
        self._p_pay_kot.setChecked(True)
        self._p_edit_kot.setChecked(True)
        self._p_cancel_kot.setChecked(True)
        self._p_auto_logout.setChecked(not is_admin)
        self._p_assign_waiter.setChecked(True)

    def _populate(self, u: dict):
        fn = u.get("first_name") or ""
        ln = u.get("last_name") or ""
        full = u.get("full_name") or f"{fn} {ln}".strip()
        if not full:
            full = u.get("username", "")
        self._f_fullname.setText(full)
        if u.get("pin"):
            self._f_pin.setText("****")
        else:
            self._f_pin.setText("")
            self._f_pin.setPlaceholderText("pin")
        self._f_max_disc.setValue(int(u.get("max_discount_percent", 0)))

        _combo_set(self._f_role,   u.get("role", "cashier"))
        self._f_active.setCurrentIndex(0 if u.get("active", True) else 1)
        
        def_store = u.get("warehouse") or u.get("default_store") or u.get("company") or _get_default_store_name()
        allowed_store = u.get("allowed_stores") or u.get("warehouse") or u.get("company") or _get_default_store_name()
        self._f_store.setText(def_store)
        self._f_allowed_stores.setText(allowed_store)
        self._p_discount.setChecked(u.get("allow_discount",   False))
        self._p_receipt.setChecked(u.get("allow_receipt",     True))
        self._p_cn.setChecked(u.get("allow_credit_note",      False))
        self._p_reprint.setChecked(u.get("allow_reprint",     False))
        self._p_laybye.setChecked(u.get("allow_laybye",       False))
        self._p_quote.setChecked(u.get("allow_quote",         False))
        self._p_reconcile.setChecked(u.get("allow_shift_reconciliation", True))
        self._p_view_expected.setChecked(u.get("allow_view_expected", False))
        self._p_pharmacist_pay.setChecked(u.get("allow_pharmacist_pay", False))
        self._p_backoffice.setChecked(u.get("allow_backoffice", False))
        self._p_pos.setChecked(u.get("allow_pos", True))

        # Payment Methods
        pm_str = u.get("allowed_payment_methods", "ALL")
        if pm_str == "ALL" or not pm_str:
            for t in getattr(self, "payment_toggles", {}).values():
                t.setChecked(True)
        else:
            allowed = [x.strip() for x in pm_str.split(",")]
            for name, t in getattr(self, "payment_toggles", {}).items():
                t.setChecked(name in allowed)

        # Restaurant permissions
        self._p_close_table.setChecked(u.get("allow_close_table", True))
        self._p_prebill.setChecked(u.get("allow_prebill",         True))
        self._p_pay_kot.setChecked(u.get("allow_pay_kot",         True))
        self._p_edit_kot.setChecked(u.get("allow_edit_kot",       True))
        self._p_cancel_kot.setChecked(u.get("allow_cancel_kot",   True))
        self._p_auto_logout.setChecked(u.get("auto_logout",       True))
        self._p_assign_waiter.setChecked(u.get("allow_assign_waiter", True))

    def _set_status(self, msg, error=False):
        color = DANGER if error else SUCCESS
        self._status_lbl.setStyleSheet(f"font-size:11px;color:{color};background:transparent;")
        self._status_lbl.setText(msg)
        if not error:
            QTimer.singleShot(3000, lambda: self._status_lbl.setText(""))

    def _save(self):
        full_name = self._f_fullname.text().strip()
        
        if not full_name:
            self._set_status("Full Name is required.", True)
            self._f_fullname.setFocus()
            return

        parts = full_name.split(" ", 1)
        first = parts[0]
        last = parts[1] if len(parts) > 1 else ""
        
        # Auto-generate a username
        import re
        username = re.sub(r'[^a-z0-9]', '', full_name.lower().replace(" ", ""))
        if not username:
            username = "user"

        self._save_btn.setEnabled(False)

        try:
            from database.db import get_connection
            import hashlib

            pin = self._f_pin.text().strip() or None
            if pin == "****":
                pin = None

            store_val = self._f_store.text().strip() or _get_default_store_name()
            allowed_val = self._f_allowed_stores.text().strip() or store_val

            data = {
                "username":              username,
                "full_name":             full_name,
                "first_name":            first,
                "last_name":             last,
                "email":                 "",
                "role":                  _combo_get(self._f_role),
                "active":                1 if self._f_active.currentIndex() == 0 else 0,
                "company":               store_val,
                "cost_center":           "Main Cost Center",
                "warehouse":             store_val,
                "default_store":         store_val,
                "allowed_stores":        allowed_val,
                "cost_center_id":        None,
                "warehouse_id":          None,
                "max_discount_percent":  self._f_max_disc.value(),
                "discount_expiry_date":  "",
                "allow_discount":        int(self._p_discount.isChecked()),
                "allow_receipt":         int(self._p_receipt.isChecked()),
                "allow_credit_note":     int(self._p_cn.isChecked()),
                "allow_reprint":         int(self._p_reprint.isChecked()),
                "allow_laybye":          int(self._p_laybye.isChecked()),
                "allow_quote":           int(self._p_quote.isChecked()),
                "allow_shift_reconciliation": int(self._p_reconcile.isChecked()),
                "allow_view_expected":   int(self._p_view_expected.isChecked()),
                "allow_pharmacist_pay":  int(self._p_pharmacist_pay.isChecked()),
                "allow_backoffice": int(self._p_backoffice.isChecked()),
                "allow_pos": int(self._p_pos.isChecked()),
                # Restaurant
                "allow_close_table":     int(self._p_close_table.isChecked()),
                "allow_prebill":         int(self._p_prebill.isChecked()),
                "allow_pay_kot":         int(self._p_pay_kot.isChecked()),
                "allow_edit_kot":        int(self._p_edit_kot.isChecked()),
                "allow_cancel_kot":      int(self._p_cancel_kot.isChecked()),
                "auto_logout":           int(self._p_auto_logout.isChecked()),
                "allow_assign_waiter":   int(self._p_assign_waiter.isChecked()),
            }
            
            allowed_pms = [name for name, t in getattr(self, "payment_toggles", {}).items() if t.isChecked()]
            if len(allowed_pms) == len(getattr(self, "payment_toggles", {})):
                data["allowed_payment_methods"] = "ALL"
            else:
                data["allowed_payment_methods"] = ",".join(allowed_pms)

            conn = get_connection()
            cur  = conn.cursor()

            # Ensure default_store and allowed_stores columns exist in users table
            for col in ["default_store", "allowed_stores"]:
                try:
                    cur.execute(f"""
                        IF NOT EXISTS (
                            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                            WHERE TABLE_NAME='users' AND COLUMN_NAME='{col}'
                        )
                        ALTER TABLE users ADD {col} NVARCHAR(255) NULL
                    """)
                    conn.commit()
                except Exception:
                    pass

            # Columns with DEFAULT 1 (Allowed by default)
            for col in ["allow_discount", "allow_receipt",
                        "allow_laybye", "allow_quote", 
                        "allow_pay_kot", "allow_close_table", 
                        "allow_prebill", "allow_edit_kot", "allow_shift_reconciliation", "allow_view_expected"]:
                try:
                    cur.execute(f"""
                        IF NOT EXISTS (
                            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                            WHERE TABLE_NAME='users' AND COLUMN_NAME='{col}'
                        )
                        ALTER TABLE users ADD {col} BIT NOT NULL DEFAULT 1
                    """)
                    conn.commit()
                except Exception: pass

            # Columns with DEFAULT 0 (Restricted by default)
            for col in ["allow_cancel_kot", "auto_logout", "allow_pharmacist_pay", "allow_assign_waiter", "allow_credit_note", "allow_reprint"]:
                try:
                    cur.execute(f"""
                        IF NOT EXISTS (
                            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                            WHERE TABLE_NAME='users' AND COLUMN_NAME='{col}'
                        )
                        ALTER TABLE users ADD {col} BIT NOT NULL DEFAULT 0
                    """)
                    conn.commit()
                except Exception: pass

            # Ensure discount_expiry_date column exists
            try:
                cur.execute("""
                    IF NOT EXISTS (
                        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_NAME='users' AND COLUMN_NAME='discount_expiry_date'
                    )
                    ALTER TABLE users ADD discount_expiry_date NVARCHAR(20) NULL
                """)
                conn.commit()
            except Exception:
                pass

            if self._user:
                if pin is not None:
                    data["pin"] = pin
                sets   = ", ".join(f"{k}=?" for k in data)
                values = list(data.values()) + [self._user["id"]]
                cur.execute(f"UPDATE users SET {sets} WHERE id=?", values)
                conn.commit()
                from models.user import get_user_by_id
                self.saved_user = get_user_by_id(self._user["id"])
            else:
                password = "changeme"
                data["password"] = hashlib.sha256(password.encode()).hexdigest()
                if pin:
                    data["pin"] = pin
                cols = ", ".join(data.keys())
                ph   = ", ".join("?" * len(data))
                cur.execute(
                    f"INSERT INTO users ({cols}) OUTPUT INSERTED.id VALUES ({ph})",
                    list(data.values())
                )
                new_id = cur.fetchone()[0]
                conn.commit()
                from models.user import get_user_by_id
                self.saved_user = get_user_by_id(new_id)

            conn.close()
            self.accept()

        except Exception as e:
            self._set_status(f"Error: {e}", True)
            self._save_btn.setEnabled(True)


# =============================================================================
# Main Users Page - clean Frappe-style table
# =============================================================================

# Column proportions  [Name, Email, Username, Role, Store, Status, PIN, Discount]
_COLS = [
    ("Name",       200, Qt.AlignLeft),
    ("Email",      190, Qt.AlignLeft),
    ("Username",   130, Qt.AlignLeft),
    ("Role",        80, Qt.AlignCenter),
    ("Store",      140, Qt.AlignLeft),
    ("Status",      70, Qt.AlignCenter),
    ("PIN",         50, Qt.AlignCenter),
    ("Max Disc.",   60, Qt.AlignCenter),
]


class ManageUsersDialog(QDialog):
    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.current_user = current_user or {}
        from PySide6.QtCore import Qt
        self.setWindowTitle("User Accounts")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setMinimumSize(1024, 600)
        self.showMaximized()
        self.setObjectName("ManageUsersDialog")
        self.setStyleSheet(f"#ManageUsersDialog {{ background-color:{OFF_WHITE}; }}")
        
        self._all_users = []
        self._build()
        self._reload()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        from views.reports.report_template import ReportTemplate
        self.report = ReportTemplate("User Accounts", is_report=False, show_date_filter=True, parent=self)
        self.report.set_headers([c[0] for c in _COLS])

        from services.credentials import get_system_mode
        if get_system_mode() == "saas":
            self.report.btn_add.hide()
        else:
            self.report.btn_add.setText("New User")
            self.report.btn_add.clicked.connect(self._add_user)
            self.report.btn_add.show()
        
        self.report.table.doubleClicked.connect(self._edit_selected)

        root.addWidget(self.report)

    def _get_selected_user(self):
        rows = self.report.table.selectionModel().selectedRows()
        if not rows: return None
        row = rows[0].row()
        item = self.report.table.item(row, 2)
        if not item: return None
        
        username = item.text()
        if username.startswith("@"):
            username = username[1:]
            
        return next((u for u in self._all_users if u.get("username") == username), None)

    def _reload(self):
        try:
            from models.user import get_all_users
            self._all_users = get_all_users()
        except Exception as e:
            self._all_users = []
            
        data = []
        for u in self._all_users:
            name = u.get("full_name") or u.get("username") or "-"
            email = u.get("email", "") or "-"
            username = f"@{u.get('username', '')}"
            role = (u.get("role") or "cashier").upper()
            store = u.get("warehouse") or u.get("default_store") or u.get("company") or "-"
            active = "Active" if u.get("active", True) else "Inactive"
            pin = "****" if u.get("pin", "") else "-"
            disc = f"{u.get('max_discount_percent', 0)}%"
            
            data.append([name, email, username, role, store, active, pin, disc])
            
        self.report.set_data(data)
        
        # Apply formatting
        for r in range(self.report.table.rowCount()):
            role_item = self.report.table.item(r, 3)
            if role_item:
                role_item.setForeground(QColor(ACCENT if role_item.text() == "ADMIN" else SUCCESS))
                f = role_item.font(); f.setBold(True); role_item.setFont(f)
                
            active_item = self.report.table.item(r, 5)
            if active_item:
                active_item.setForeground(QColor(SUCCESS if active_item.text() == "Active" else MUTED))

            pin_item = self.report.table.item(r, 6)
            if pin_item:
                pin_item.setForeground(QColor(AMBER if pin_item.text() == "****" else MUTED))

    def _add_user(self):
        dlg = _UserFormDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._reload()

    def _edit_selected(self):
        u = self._get_selected_user()
        if u:
            dlg = _UserFormDialog(self, user=u)
            if dlg.exec() == QDialog.Accepted:
                self._reload()

    def _delete_selected(self):
        u = self._get_selected_user()
        if not u: return
        if u.get("id") == self.current_user.get("id"):
            QMessageBox.warning(self, "Cannot Delete", "You cannot delete your own account.")
            return

        name = u.get("full_name") or u.get("username")
        reply = QMessageBox.question(self, "Delete User", f"Permanently delete '{name}'?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                from models.user import delete_user
                delete_user(u["id"])
                self._reload()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete user: {e}")


# Backward compatibility
UsersDialog = ManageUsersDialog
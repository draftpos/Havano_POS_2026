# =============================================================================
# views/dialogs/users_dialog.py
# Clean Frappe-style table layout — matches CompanyDefaultsPage aesthetic
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QScrollArea, QFrame, QMessageBox, QCheckBox,
    QSpinBox, QAbstractItemView, QSizePolicy,
    QApplication,
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore  import QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui   import QPainter, QLinearGradient, QRadialGradient

# ── Palette (mirrors CompanyDefaultsPage exactly) ──────────────────────────────
NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
NAVY_3    = "#1e3d6e"
ACCENT    = "#1a5fb4"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
LIGHT     = "#e4eaf4"
BORDER    = "#c8d8ec"
MID       = "#8fa8c8"
MUTED     = "#5a7a9a"
DARK_TEXT = "#0d1f3c"
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"
AMBER     = "#b7770d"

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


def _combo(options):
    w = QComboBox()
    w.addItems(options)
    w.setFixedHeight(FIELD_H)
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


def _field_row(label_text, widget, lw=LBL_W):
    row = QHBoxLayout()
    row.setSpacing(16)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(_lbl(label_text, lw))
    row.addWidget(widget, 1)
    return row


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
# TogglePill — faithful PySide6 port of CSS checkbox-wrapper-5
#
# Visuals matched to the original:
#   • Track  : linear gradient pill (#f19af3 → #f099b5) when ON,
#              flat #d7d7d7 when OFF  — animates with QPropertyAnimation
#   • Knob   : smaller circle with gradient (#dedede → #ffffff) +
#              drop-shadow (rgba 0,0,0,0.3) sliding left ↔ right
#   • Size   : driven by a single --size variable (default 22 px, same ratio)
#
# Public API mirrors QCheckBox:
#   toggle.isChecked()    → bool
#   toggle.setChecked(b)  → None
# =============================================================================

from PySide6.QtCore  import QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui   import QPainter, QLinearGradient, QColor, QPen, QRadialGradient


class _TogglePill(QWidget):
    """
    The actual pill widget — drawn entirely with QPainter so every CSS
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
        t = self._knob_pos   # 0.0 → OFF, 1.0 → ON

        if t < 0.01:
            # fully OFF — flat grey
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
    Drop-in replacement for QCheckBox — same isChecked() / setChecked() API.
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
# Add / Edit User — clean side-panel form matching CompanyDefaults layout
# =============================================================================

class _UserFormDialog(QDialog):
    def __init__(self, parent=None, user: dict = None):
        super().__init__(parent)
        self._user = user
        self.saved_user = None

        title = "New User" if not user else \
            f"Edit — {user.get('full_name') or user.get('username', '')}"
        self.setWindowTitle(title)
        self.setFixedWidth(540)
        self.setMinimumHeight(600)
        self.setModal(True)
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
        title_lbl.setStyleSheet(
            f"color:{WHITE};font-size:15px;font-weight:bold;background:transparent;"
        )
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background:rgba(255,255,255,0.15);
                color:{WHITE}; border:none; border-radius:14px; font-size:13px;
            }}
            QPushButton:hover {{ background:rgba(255,255,255,0.25); }}
        """)
        close_btn.clicked.connect(self.reject)
        hl.addWidget(title_lbl)
        hl.addStretch()
        hl.addWidget(close_btn)
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

        # ── Identity ──────────────────────────────────────────────────────────
        _section_header(fl, "Identity", top_margin=0)

        self._f_first = _inp("First name")
        self._f_last  = _inp("Last name")
        self._f_email = _inp("email@example.com")

        fl.addLayout(_field_row("First Name", self._f_first))
        fl.addLayout(_field_row("Last Name",  self._f_last))
        fl.addLayout(_field_row("Email",      self._f_email))

        # ── Security ─────────────────────────────────────────────────────────
        _section_header(fl, "Security", top_margin=4)

        self._f_username = _inp("username")
        self._f_password = _inp("Leave blank to keep current", password=True)
        self._f_pin      = _inp("Leave blank to keep current", password=True)
        self._f_pin.setMaxLength(4)

        fl.addLayout(_field_row("Username", self._f_username))
        fl.addLayout(_field_row("Password", self._f_password))
        fl.addLayout(_field_row("PIN",      self._f_pin))

        pin_note = QLabel("Admin cannot view the current PIN — enter a new value to change it.")
        pin_note.setStyleSheet(
            f"font-size:10px;color:{MUTED};font-style:italic;background:transparent;"
        )
        pin_note.setWordWrap(True)
        fl.addWidget(pin_note)

        # ── Role & Status ─────────────────────────────────────────────────────
        _section_header(fl, "Role & Status", top_margin=4)

        self._f_role   = _combo(["cashier", "admin"])
        self._f_active = _combo(["Active", "Inactive"])

        fl.addLayout(_field_row("Role",   self._f_role))
        fl.addLayout(_field_row("Status", self._f_active))

        # ── Assignment ────────────────────────────────────────────────────────
        _section_header(fl, "Assignment", top_margin=4)

        self._f_company = _inp()
        self._f_cost    = _inp()
        self._f_whouse  = _inp()

        fl.addLayout(_field_row("Company",     self._f_company))
        fl.addLayout(_field_row("Cost Center", self._f_cost))
        fl.addLayout(_field_row("Warehouse",   self._f_whouse))

        # ── Permissions ───────────────────────────────────────────────────────
        _section_header(fl, "Permissions", top_margin=4)

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
        fl.addLayout(_field_row("Max Discount", self._f_max_disc))

        fl.addSpacing(4)

        # ── Toggle switches — indented to align with field inputs ─────────────
        toggles_row = QHBoxLayout()
        toggles_row.setContentsMargins(0, 0, 0, 0)
        toggles_row.setSpacing(16)

        spacer = QWidget()
        spacer.setFixedWidth(LBL_W)
        toggles_row.addWidget(spacer)

        toggles_col = QVBoxLayout()
        toggles_col.setSpacing(10)
        toggles_col.setContentsMargins(0, 0, 0, 0)

        self._p_discount = ToggleSwitch("Allow discounts",      "Cashier can apply a discount at checkout")
        self._p_receipt  = ToggleSwitch("Process payments",     "Cashier can complete and tender sales")
        self._p_cn       = ToggleSwitch("Issue credit notes",   "Cashier can process returns and refunds")
        self._p_reprint  = ToggleSwitch("Reprint receipts",     "Cashier can reprint a past receipt")
        self._p_laybye   = ToggleSwitch("Allow laybye",         "Cashier can create and manage laybyes")

        for toggle in [self._p_discount, self._p_receipt, self._p_cn,
                       self._p_reprint, self._p_laybye]:
            toggles_col.addWidget(toggle)

        toggles_row.addLayout(toggles_col)
        fl.addLayout(toggles_row)

        fl.addStretch()
        scroll.setWidget(form)
        root.addWidget(scroll, 1)

        # Footer bar
        foot = QWidget()
        foot.setStyleSheet(f"background:{WHITE};border-top:1px solid {BORDER};")
        foot.setFixedHeight(62)
        ftl = QHBoxLayout(foot)
        ftl.setContentsMargins(24, 12, 24, 14)
        ftl.setSpacing(10)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("font-size:11px;background:transparent;")
        ftl.addWidget(self._status_lbl, 1)

        cancel_btn = _action_btn(
            "Cancel", color=WHITE, hover=LIGHT,
            text_color=DARK_TEXT, border=BORDER
        )
        cancel_btn.clicked.connect(self.reject)

        self._save_btn = _action_btn("Save User", color=SUCCESS, hover=SUCCESS_H)
        self._save_btn.clicked.connect(self._save)

        ftl.addWidget(cancel_btn)
        ftl.addWidget(self._save_btn)
        root.addWidget(foot)

        # Auto-generate username
        self._f_first.textChanged.connect(self._auto_username)
        self._f_last.textChanged.connect(self._auto_username)

    # -------------------------------------------------------------------------
    def _auto_username(self):
        if not self._user:
            first = self._f_first.text().strip().lower().replace(" ", "")
            last  = self._f_last.text().strip().lower().replace(" ", "")
            if first or last:
                self._f_username.setText(f"{first}.{last}" if last else first)

    def _autofill_defaults(self):
        self._f_company.setText(self._defs.get("server_company", ""))
        self._f_cost.setText(self._defs.get("server_cost_center", ""))
        self._f_whouse.setText(self._defs.get("server_warehouse", ""))

    def _populate(self, u: dict):
        fn = u.get("first_name") or (u.get("full_name", "").split(" ")[0] if u.get("full_name") else "")
        ln = u.get("last_name")  or (" ".join(u.get("full_name", "").split(" ")[1:]) if u.get("full_name") else "")
        self._f_first.setText(fn)
        self._f_last.setText(ln)
        self._f_email.setText(u.get("email", ""))
        self._f_username.setText(u.get("username", ""))
        self._f_pin.setPlaceholderText("Leave blank to keep current")
        self._f_max_disc.setValue(int(u.get("max_discount_percent", 0)))
        _combo_set(self._f_role,   u.get("role", "cashier"))
        self._f_active.setCurrentIndex(0 if u.get("active", True) else 1)
        self._f_company.setText(u.get("company", "")     or self._defs.get("server_company", ""))
        self._f_cost.setText(u.get("cost_center", "")    or self._defs.get("server_cost_center", ""))
        self._f_whouse.setText(u.get("warehouse", "")    or self._defs.get("server_warehouse", ""))
        self._p_discount.setChecked(u.get("allow_discount",   True))
        self._p_receipt.setChecked(u.get("allow_receipt",     True))
        self._p_cn.setChecked(u.get("allow_credit_note",      True))
        self._p_reprint.setChecked(u.get("allow_reprint",     True))
        self._p_laybye.setChecked(u.get("allow_laybye",       True))

    def _set_status(self, msg, error=False):
        color = DANGER if error else SUCCESS
        self._status_lbl.setStyleSheet(f"font-size:11px;color:{color};background:transparent;")
        self._status_lbl.setText(msg)
        if not error:
            QTimer.singleShot(3000, lambda: self._status_lbl.setText(""))

    def _save(self):
        first    = self._f_first.text().strip()
        username = self._f_username.text().strip()

        if not first:
            self._set_status("First name is required.", True)
            self._f_first.setFocus()
            return
        if not username:
            self._set_status("Username is required.", True)
            self._f_username.setFocus()
            return

        self._save_btn.setEnabled(False)

        try:
            from database.db import get_connection
            import hashlib

            full_name = f"{first} {self._f_last.text().strip()}".strip()
            pin       = self._f_pin.text().strip() or None

            data = {
                "username":              username,
                "full_name":             full_name,
                "first_name":            first,
                "last_name":             self._f_last.text().strip(),
                "email":                 self._f_email.text().strip(),
                "role":                  _combo_get(self._f_role),
                "active":                1 if self._f_active.currentIndex() == 0 else 0,
                "company":               self._f_company.text().strip(),
                "cost_center":           self._f_cost.text().strip(),
                "warehouse":             self._f_whouse.text().strip(),
                "max_discount_percent":  self._f_max_disc.value(),
                "allow_discount":        int(self._p_discount.isChecked()),
                "allow_receipt":         int(self._p_receipt.isChecked()),
                "allow_credit_note":     int(self._p_cn.isChecked()),
                "allow_reprint":         int(self._p_reprint.isChecked()),
                "allow_laybye":          int(self._p_laybye.isChecked()),
            }

            conn = get_connection()
            cur  = conn.cursor()

            for col in ["allow_discount", "allow_receipt", "allow_credit_note",
                        "allow_reprint", "allow_laybye"]:
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

            if self._user:
                if pin is not None:
                    data["pin"] = pin
                sets   = ", ".join(f"{k}=?" for k in data)
                values = list(data.values()) + [self._user["id"]]
                cur.execute(f"UPDATE users SET {sets} WHERE id=?", values)

                password = self._f_password.text().strip()
                if password:
                    cur.execute(
                        "UPDATE users SET password=? WHERE id=?",
                        (hashlib.sha256(password.encode()).hexdigest(), self._user["id"])
                    )
                conn.commit()
                from models.user import get_user_by_id
                self.saved_user = get_user_by_id(self._user["id"])
            else:
                password      = self._f_password.text().strip() or "changeme"
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
# Main Users Page — clean Frappe-style table
# =============================================================================

# Column proportions  [Name, Email, Username, Role, Status, PIN, Discount]
_COLS = [
    ("Name",       220, Qt.AlignLeft),
    ("Email",      200, Qt.AlignLeft),
    ("Username",   140, Qt.AlignLeft),
    ("Role",        90, Qt.AlignCenter),
    ("Status",      80, Qt.AlignCenter),
    ("PIN",         60, Qt.AlignCenter),
    ("Max Disc.",   70, Qt.AlignCenter),
]


class ManageUsersDialog(QDialog):
    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.current_user = current_user or {}
        self.setWindowTitle("User Accounts")
        self.setMinimumSize(960, 580)
        self.setStyleSheet(
            f"QDialog {{ background:{OFF_WHITE}; font-family:'Segoe UI',sans-serif; }}"
        )
        self._all_users: list = []
        self._selected: dict  = {}
        self._build()
        self._reload()

    # -------------------------------------------------------------------------
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(60)
        hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(28, 0, 20, 0)
        hl.setSpacing(12)

        title = QLabel("User Accounts")
        title.setStyleSheet(
            f"color:{WHITE};font-size:18px;font-weight:bold;background:transparent;"
        )

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"font-size:12px;background:transparent;color:#2ecc71;"
        )

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background:rgba(255,255,255,0.15); color:{WHITE};
                border:none; border-radius:15px; font-size:14px;
            }}
            QPushButton:hover {{ background:rgba(255,255,255,0.25); }}
        """)
        close_btn.clicked.connect(self.accept)

        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(self._status_lbl)
        hl.addWidget(close_btn)
        root.addWidget(hdr)

        # Accent gradient line
        bar = QFrame(); bar.setFixedHeight(3)
        bar.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {NAVY},stop:0.5 {ACCENT},stop:1 {NAVY_3});
        """)
        root.addWidget(bar)

        # ── Toolbar ───────────────────────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setFixedHeight(54)
        toolbar.setStyleSheet(f"background:{WHITE};border-bottom:1px solid {BORDER};")
        tbl = QHBoxLayout(toolbar)
        tbl.setContentsMargins(20, 0, 20, 0)
        tbl.setSpacing(10)

        # Search input
        self._search = QLineEdit()
        self._search.setFixedHeight(34)
        self._search.setPlaceholderText("Search by name, email, username or role…")
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background:{OFF_WHITE}; color:{DARK_TEXT};
                border:1px solid {BORDER}; border-radius:6px;
                padding:0 12px; font-size:12px;
            }}
            QLineEdit:focus {{ border:2px solid {ACCENT}; background:{WHITE}; }}
        """)
        self._search.setFixedWidth(280)
        self._search.textChanged.connect(self._filter)

        tbl.addWidget(self._search)
        tbl.addStretch()

        self._edit_btn   = _action_btn(
            "Edit", color=WHITE, hover=LIGHT,
            text_color=DARK_TEXT, border=BORDER
        )
        self._delete_btn = _action_btn(
            "Delete", color=WHITE, hover="#fde8e8",
            text_color=DANGER, border="#f5c0c0"
        )
        self._add_btn    = _action_btn("+ New User", color=ACCENT, hover="#1c6dd0")

        self._edit_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)

        self._edit_btn.clicked.connect(self._edit_selected)
        self._delete_btn.clicked.connect(self._delete_selected)
        self._add_btn.clicked.connect(self._add_user)

        tbl.addWidget(self._edit_btn)
        tbl.addWidget(self._delete_btn)
        tbl.addSpacing(6)
        tbl.addWidget(self._add_btn)
        root.addWidget(toolbar)

        # ── Column header ─────────────────────────────────────────────────────
        col_hdr = QWidget()
        col_hdr.setFixedHeight(34)
        col_hdr.setStyleSheet(
            f"background:{LIGHT};border-bottom:1px solid {BORDER};"
        )
        chl = QHBoxLayout(col_hdr)
        chl.setContentsMargins(20, 0, 20, 0)
        chl.setSpacing(0)

        for name, width, align in _COLS:
            lbl = QLabel(name.upper())
            lbl.setFixedWidth(width)
            lbl.setAlignment(align | Qt.AlignVCenter)
            lbl.setStyleSheet(
                f"color:{MUTED};font-size:10px;font-weight:bold;"
                f"letter-spacing:1px;background:transparent;"
            )
            chl.addWidget(lbl)

        chl.addStretch()
        root.addWidget(col_hdr)

        # ── Scrollable rows ───────────────────────────────────────────────────
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

        self._rows_widget = QWidget()
        self._rows_widget.setStyleSheet(f"background:{OFF_WHITE};")
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)
        self._rows_layout.addStretch()

        scroll.setWidget(self._rows_widget)
        root.addWidget(scroll, 1)

        # ── Count footer ──────────────────────────────────────────────────────
        foot = QWidget()
        foot.setFixedHeight(32)
        foot.setStyleSheet(f"background:{WHITE};border-top:1px solid {BORDER};")
        fll = QHBoxLayout(foot)
        fll.setContentsMargins(20, 0, 20, 0)
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(
            f"font-size:11px;color:{MUTED};background:transparent;"
        )
        fll.addWidget(self._count_lbl)
        fll.addStretch()
        root.addWidget(foot)

    # ── Table rendering ───────────────────────────────────────────────────────

    def _clear_rows(self):
        layout = self._rows_layout
        while layout.count() > 1:          # keep the trailing stretch
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render(self, users: list):
        self._clear_rows()
        self._selected = {}
        self._edit_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)

        for i, u in enumerate(users):
            row = self._make_row(u, i)
            self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)

        total = len(self._all_users)
        shown = len(users)
        self._count_lbl.setText(
            f"{total} user{'s' if total != 1 else ''}" if shown == total
            else f"Showing {shown} of {total} users"
        )

    def _make_row(self, u: dict, idx: int) -> QWidget:
        bg = WHITE if idx % 2 == 0 else OFF_WHITE
        row = QWidget()
        row.setObjectName(f"row_{u.get('id', idx)}")
        row.setFixedHeight(44)
        row.setStyleSheet(f"""
            QWidget#row_{u.get('id', idx)} {{
                background:{bg};
                border-bottom:1px solid {BORDER};
            }}
            QWidget#row_{u.get('id', idx)}:hover {{
                background:{LIGHT};
            }}
        """)
        row.setCursor(Qt.PointingHandCursor)

        rl = QHBoxLayout(row)
        rl.setContentsMargins(20, 0, 20, 0)
        rl.setSpacing(0)

        def _cell(text, width, align=Qt.AlignLeft, style=""):
            l = QLabel(text)
            l.setFixedWidth(width)
            l.setAlignment(align | Qt.AlignVCenter)
            base = (
                f"font-size:12px;color:{DARK_TEXT};"
                f"background:transparent;padding:0;"
            )
            l.setStyleSheet(base + style)
            return l

        # Name (with avatar dot)
        name  = u.get("full_name") or u.get("username") or "—"
        is_admin = u.get("role", "") == "admin"
        dot_color = ACCENT if is_admin else SUCCESS
        name_lbl = QLabel()
        name_lbl.setFixedWidth(_COLS[0][1])
        name_lbl.setFixedHeight(44)
        name_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        name_lbl.setText(
            f'<span style="color:{dot_color};font-size:9px;">●</span>'
            f'&nbsp;&nbsp;<span style="font-size:13px;font-weight:600;color:{DARK_TEXT};">{name}</span>'
        )
        name_lbl.setStyleSheet("background:transparent;")
        rl.addWidget(name_lbl)

        # Email
        email = u.get("email", "") or "—"
        rl.addWidget(_cell(email, _COLS[1][1], Qt.AlignLeft,
                           f"color:{MUTED};font-size:12px;"))

        # Username
        rl.addWidget(_cell(
            f"@{u.get('username', '')}", _COLS[2][1],
            Qt.AlignLeft, f"color:{MUTED};"
        ))

        # Role badge
        role  = (u.get("role") or "cashier").upper()
        r_col = ACCENT if role == "ADMIN" else SUCCESS
        role_lbl = QLabel(role)
        role_lbl.setFixedWidth(_COLS[3][1])
        role_lbl.setAlignment(Qt.AlignCenter)
        role_lbl.setStyleSheet(f"""
            font-size:10px; font-weight:700; color:{r_col};
            background:transparent; letter-spacing:0.5px;
        """)
        rl.addWidget(role_lbl)

        # Status
        active  = u.get("active", True)
        s_text  = "Active"   if active else "Inactive"
        s_color = SUCCESS if active else MUTED
        rl.addWidget(_cell(s_text, _COLS[4][1], Qt.AlignCenter,
                           f"color:{s_color};font-weight:600;font-size:11px;"))

        # PIN masked
        pin_text = "••••" if u.get("pin", "") else "—"
        pin_col  = AMBER if u.get("pin", "") else MUTED
        rl.addWidget(_cell(pin_text, _COLS[5][1], Qt.AlignCenter,
                           f"color:{pin_col};font-size:13px;letter-spacing:2px;"))

        # Max discount
        disc = u.get("max_discount_percent", 0)
        rl.addWidget(_cell(f"{disc}%", _COLS[6][1], Qt.AlignCenter,
                           f"color:{DARK_TEXT};"))

        rl.addStretch()

        # Click to select
        row.mousePressEvent = lambda _ev, _u=u, _r=row: self._select_row(_u, _r)
        row.mouseDoubleClickEvent = lambda _ev, _u=u: self._edit_user(_u)

        return row

    def _select_row(self, u: dict, row: QWidget):
        # Deselect previous
        prev = getattr(self, "_selected_row_widget", None)
        if prev:
            idx_in_all = next(
                (i for i, x in enumerate(self._all_users) if x.get("id") == self._selected.get("id")),
                None
            )
            if idx_in_all is not None:
                bg = WHITE if idx_in_all % 2 == 0 else OFF_WHITE
                uid = self._selected.get("id", "")
                prev.setStyleSheet(f"""
                    QWidget#row_{uid} {{
                        background:{bg}; border-bottom:1px solid {BORDER};
                    }}
                    QWidget#row_{uid}:hover {{ background:{LIGHT}; }}
                """)

        self._selected = u
        self._selected_row_widget = row
        uid = u.get("id", "")
        row.setStyleSheet(f"""
            QWidget#row_{uid} {{
                background:{LIGHT}; border-bottom:1px solid {BORDER};
                border-left:3px solid {ACCENT};
            }}
        """)
        self._edit_btn.setEnabled(True)
        self._delete_btn.setEnabled(True)

    # ── Data ops ──────────────────────────────────────────────────────────────

    def _reload(self):
        try:
            from models.user import get_all_users
            self._all_users = get_all_users()
        except Exception as e:
            self._all_users = []
            print(f"[UsersDialog] load error: {e}")
        self._render(self._all_users)

    def _filter(self, text: str):
        q = text.lower().strip()
        users = (
            self._all_users if not q else [
                u for u in self._all_users
                if q in (u.get("full_name", "") or "").lower()
                or q in (u.get("email", "")     or "").lower()
                or q in (u.get("username", "")  or "").lower()
                or q in (u.get("role", "")       or "").lower()
            ]
        )
        self._render(users)

    def _add_user(self):
        dlg = _UserFormDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._reload()

    def _edit_user(self, u: dict):
        dlg = _UserFormDialog(self, user=u)
        if dlg.exec() == QDialog.Accepted:
            self._reload()

    def _edit_selected(self):
        if self._selected:
            self._edit_user(self._selected)

    def _delete_selected(self):
        u = self._selected
        if not u:
            return
        if u.get("id") == self.current_user.get("id"):
            QMessageBox.warning(self, "Cannot Delete", "You cannot delete your own account.")
            return

        name = u.get("full_name") or u.get("username")
        reply = QMessageBox.question(
            self, "Delete User",
            f"Permanently delete '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                from models.user import delete_user
                delete_user(u["id"])
                self._selected = {}
                self._reload()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete user: {e}")

    def _show_status(self, msg, error=False):
        color = DANGER if error else "#2ecc71"
        self._status_lbl.setStyleSheet(
            f"font-size:12px;background:transparent;color:{color};"
        )
        self._status_lbl.setText(msg)
        QTimer.singleShot(3000, lambda: self._status_lbl.setText(""))


# Backward compatibility
UsersDialog = ManageUsersDialog
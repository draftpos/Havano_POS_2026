# =============================================================================
# views/pages/company_defaults_page.py
#
#  ┌─────────────────────────────────────────────────┐
#  │  Company Defaults          [Save]  [✅ saved]   │  ← fixed header/action bar
#  ├─────────────────────────────────────────────────┤
#  │  ↕  SCROLLABLE BODY                             │
#  │  Receipt Details (left)  │  (blank right)       │  ← top half
#  ├──────────────┬────────────┬─────────────────────┤
#  │  Footer Text │  ZIMRA     │  User               │  ← bottom half
#  └──────────────┴────────────┴─────────────────────┘
# =============================================================================

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QFrame, QSizePolicy, QScrollArea,
)
from PySide6.QtCore import Qt, QTimer

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


# ── Shared widget builders ────────────────────────────────────────────────────

def _sec(text):
    l = QLabel(text.upper())
    l.setStyleSheet(
        f"color:{MUTED};font-size:10px;font-weight:bold;"
        f"background:transparent;letter-spacing:1.2px;"
    )
    return l


def _hr():
    f = QFrame(); f.setFrameShape(QFrame.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{BORDER};border:none;")
    return f


def _lbl(text, w=120):
    l = QLabel(text)
    l.setFixedWidth(w)
    l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    l.setStyleSheet(
        f"color:{MUTED};font-size:11px;font-weight:bold;background:transparent;"
    )
    return l


def _inp(pwd=False):
    i = QLineEdit()
    i.setFixedHeight(36)
    if pwd:
        i.setEchoMode(QLineEdit.Password)
    i.setStyleSheet(f"""
        QLineEdit {{
            background:{WHITE}; color:{DARK_TEXT};
            border:1px solid {BORDER}; border-radius:6px;
            padding:0 10px; font-size:13px;
        }}
        QLineEdit:focus {{
            border:1.5px solid {ACCENT};
            background:{WHITE};
        }}
        QLineEdit:hover {{
            border:1px solid {MID};
        }}
    """)
    return i


def _ro():
    """Read-only box — same look as input but grey background."""
    l = QLabel("—")
    l.setFixedHeight(36)
    l.setStyleSheet(
        f"color:{DARK_TEXT};font-size:13px;"
        f"background:{LIGHT};"
        f"border:1px solid {BORDER};border-radius:6px;"
        f"padding:0 10px;"
    )
    return l


def _field(label, widget, lw=120):
    h = QHBoxLayout(); h.setSpacing(12)
    h.addWidget(_lbl(label, lw))
    h.addWidget(widget, 1)
    return h


def _panel(bg=WHITE, border_right=False):
    w = QWidget()
    br = f"border-right:1px solid {BORDER};" if border_right else ""
    w.setStyleSheet(f"background:{bg};{br}")
    return w


# =============================================================================
class CompanyDefaultsPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"QWidget{{background:{OFF_WHITE};}}")
        self._inputs    = {}
        self._ro_labels = {}
        self._build()
        self._load()

    def _build(self):
        # Outer layout: fixed header on top, scroll area fills the rest
        outer = QVBoxLayout(self)
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)

        # ── Fixed header / action bar ─────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(60)
        hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 0, 24, 0)
        hl.setSpacing(16)

        title = QLabel("Company Defaults")
        title.setStyleSheet(
            f"font-size:17px;font-weight:bold;color:{WHITE};background:transparent;"
        )

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"font-size:12px;background:transparent;color:#2ecc71;"
        )

        save_btn = QPushButton("  Save  ")
        save_btn.setFixedHeight(36)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background:{SUCCESS}; color:{WHITE}; border:none;
                border-radius:6px; font-size:13px; font-weight:bold;
                padding:0 20px;
            }}
            QPushButton:hover   {{ background:{SUCCESS_H}; }}
            QPushButton:pressed {{ background:{NAVY_3}; }}
        """)
        save_btn.clicked.connect(self._save)

        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(self._status_lbl)
        hl.addWidget(save_btn)
        outer.addWidget(hdr)

        # Accent gradient line under header
        bar = QFrame(); bar.setFixedHeight(2)
        bar.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {NAVY},stop:0.5 {ACCENT},stop:1 {NAVY_3});
        """)
        outer.addWidget(bar)

        # ── Scroll area wraps ALL content below the header ────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: {OFF_WHITE};
            }}
            QScrollBar:vertical {{
                background: {LIGHT}; width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: #b0c4de; border-radius: 4px; min-height: 28px;
            }}
            QScrollBar:horizontal {{
                background: {LIGHT}; height: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: #b0c4de; border-radius: 4px; min-width: 28px;
            }}
        """)

        # ── Scrollable content widget ─────────────────────────────────────────
        content = QWidget()
        content.setStyleSheet(f"background:{OFF_WHITE};")
        root = QVBoxLayout(content)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ═════════════════════════════════════════════════════════════════════
        # TOP ROW — Receipt Details (left) | blank (right)
        # ═════════════════════════════════════════════════════════════════════
        top_row = QHBoxLayout()
        top_row.setSpacing(0)
        top_row.setContentsMargins(0, 0, 0, 0)

        # Receipt Details panel — fixed minimum so it never squeezes
        receipt_p = _panel(WHITE, border_right=True)
        receipt_p.setMinimumHeight(460)
        rl = QVBoxLayout(receipt_p)
        rl.setContentsMargins(32, 28, 32, 28)
        rl.setSpacing(16)

        rl.addWidget(_sec("Receipt Details"))
        rl.addWidget(_hr())

        for label, key in [
            ("Company Name",   "company_name"),
            ("Address Line 1", "address_1"),
            ("Address Line 2", "address_2"),
            ("Email",          "email"),
            ("Phone",          "phone"),
            ("VAT",            "vat_number"),
            ("TIN",            "tin_number"),
        ]:
            i = _inp(); self._inputs[key] = i
            rl.addLayout(_field(label, i, lw=120))

        rl.addStretch()

        # Blank right panel
        blank_p = _panel(OFF_WHITE)
        blank_p.setMinimumHeight(460)

        top_row.addWidget(receipt_p, 1)
        top_row.addWidget(blank_p, 1)

        top_w = QWidget()
        top_w.setLayout(top_row)
        top_w.setMinimumHeight(460)
        root.addWidget(top_w)

        # Divider between top and bottom sections
        mid_line = QFrame(); mid_line.setFixedHeight(1)
        mid_line.setStyleSheet(f"background:{BORDER};border:none;")
        root.addWidget(mid_line)

        # ═════════════════════════════════════════════════════════════════════
        # BOTTOM ROW — Footer Text | ZIMRA Settings | User Info
        # ═════════════════════════════════════════════════════════════════════
        bot_row = QHBoxLayout()
        bot_row.setSpacing(0)
        bot_row.setContentsMargins(0, 0, 0, 0)

        # Footer Text panel
        footer_p = _panel(WHITE, border_right=True)
        footer_p.setMinimumHeight(400)
        fl = QVBoxLayout(footer_p)
        fl.setContentsMargins(32, 24, 32, 24)
        fl.setSpacing(12)

        fl.addWidget(_sec("Footer Text"))
        fl.addWidget(_hr())

        self._footer = QTextEdit()
        self._footer.setMinimumHeight(180)
        self._footer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._footer.setStyleSheet(f"""
            QTextEdit {{
                background:{WHITE}; color:{DARK_TEXT};
                border:1px solid {BORDER}; border-radius:6px;
                padding:8px 10px; font-size:13px;
            }}
            QTextEdit:focus {{ border:1.5px solid {ACCENT}; }}
        """)
        fl.addWidget(self._footer, 1)

        # ZIMRA Settings panel
        zimra_p = _panel(OFF_WHITE, border_right=True)
        zimra_p.setMinimumHeight(400)
        zl = QVBoxLayout(zimra_p)
        zl.setContentsMargins(32, 24, 32, 24)
        zl.setSpacing(16)

        zl.addWidget(_sec("ZIMRA Settings"))
        zl.addWidget(_hr())

        for label, key, pwd in [
            ("Serial No",  "zimra_serial_no", False),
            ("Device ID",  "zimra_device_id", False),
            ("API URL",    "zimra_api_url",   False),
            ("API Key",    "zimra_api_key",   True),
        ]:
            i = _inp(pwd=pwd); self._inputs[key] = i
            zl.addLayout(_field(label, i, lw=80))

        zl.addStretch()

        # User panel
        user_p = _panel(WHITE)
        user_p.setMinimumHeight(400)
        ul = QVBoxLayout(user_p)
        ul.setContentsMargins(32, 24, 32, 24)
        ul.setSpacing(16)

        ul.addWidget(_sec("User"))
        ul.addWidget(_hr())

        for label, key in [
            ("Username",   "server_username"),
            ("First Name", "server_first_name"),
            ("Last Name",  "server_last_name"),
            ("Email",      "server_email"),
            ("Mobile",     "server_mobile"),
        ]:
            v = _ro(); self._ro_labels[key] = v
            ul.addLayout(_field(label, v, lw=90))

        ul.addSpacing(20)
        ul.addWidget(_sec("Login Defaults"))
        ul.addWidget(_hr())
        ul.addSpacing(4)

        for label, key in [
            ("Company",     "server_company"),
            ("Warehouse",   "server_warehouse"),
            ("Cost Centre", "server_cost_center"),
            ("Full Name",   "server_full_name"),
            ("Role",        "server_role"),
        ]:
            v = _ro(); self._ro_labels[key] = v
            ul.addLayout(_field(label, v, lw=90))
            ul.addSpacing(4)

        ul.addStretch()

        bot_row.addWidget(footer_p, 1)
        bot_row.addWidget(zimra_p, 1)
        bot_row.addWidget(user_p, 1)

        bot_w = QWidget()
        bot_w.setLayout(bot_row)
        bot_w.setMinimumHeight(400)
        root.addWidget(bot_w)

        # Push content to top if window is very tall
        root.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    # =========================================================================
    def _load(self):
        try:
            from models.company_defaults import get_defaults
            data = get_defaults()
        except Exception as e:
            print(f"[CompanyDefaultsPage] load error: {e}")
            data = {}

        for key, inp in self._inputs.items():
            val = data.get(key, "")
            if key == "company_name" and not val:
                val = data.get("server_company", "")
            inp.setText(val)

        self._footer.setPlainText(data.get("footer_text", ""))

        for key, lbl in self._ro_labels.items():
            val = data.get(key, "")
            lbl.setText(val if val else "—")

    def _save(self):
        data = {k: i.text().strip() for k, i in self._inputs.items()}
        data["footer_text"] = self._footer.toPlainText().strip()
        for key, lbl in self._ro_labels.items():
            v = lbl.text()
            data[key] = "" if v == "—" else v

        try:
            from models.company_defaults import save_defaults
            save_defaults(data)
            self._show_status("✅  Saved successfully.")
        except Exception as e:
            self._show_status(f"❌  {e}", error=True)

    def _show_status(self, msg, error=False):
        color = DANGER if error else "#2ecc71"
        self._status_lbl.setStyleSheet(
            f"font-size:12px;background:transparent;color:{color};"
        )
        self._status_lbl.setText(msg)
        QTimer.singleShot(3000, lambda: self._status_lbl.setText(""))
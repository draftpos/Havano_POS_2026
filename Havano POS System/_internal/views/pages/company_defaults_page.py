# =============================================================================
# views/pages/company_defaults_page.py
# =============================================================================

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QFrame, QSizePolicy, QScrollArea,
    QSpinBox,
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

FIELD_H   = 38    # height for every input / read-only field
LBL_W     = 130   # label column width
ROW_SP    = 14    # spacing between field rows


# ── Shared widget builders ────────────────────────────────────────────────────

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


def _inp(pwd=False, placeholder=""):
    i = QLineEdit()
    i.setFixedHeight(FIELD_H)
    if pwd:
        i.setEchoMode(QLineEdit.Password)
    if placeholder:
        i.setPlaceholderText(placeholder)
    i.setStyleSheet(f"""
        QLineEdit {{
            background:{WHITE}; color:{DARK_TEXT};
            border:1px solid {BORDER}; border-radius:6px;
            padding:0 12px; font-size:13px;
        }}
        QLineEdit:focus {{ border:2px solid {ACCENT}; }}
        QLineEdit:hover {{ border:1px solid {MID}; }}
    """)
    return i


def _ro(text="—"):
    l = QLabel(text)
    l.setFixedHeight(FIELD_H)
    l.setStyleSheet(
        f"color:{DARK_TEXT};font-size:13px;"
        f"background:{LIGHT};"
        f"border:1px solid {BORDER};border-radius:6px;"
        f"padding:0 12px;"
    )
    return l


def _spinbox():
    s = QSpinBox()
    s.setFixedHeight(FIELD_H)
    s.setMinimum(0)
    s.setMaximum(9999999)
    s.setValue(0)
    s.setStyleSheet(f"""
        QSpinBox {{
            background:{WHITE}; color:{DARK_TEXT};
            border:1px solid {BORDER}; border-radius:6px;
            padding:0 12px; font-size:13px;
        }}
        QSpinBox:focus {{ border:2px solid {ACCENT}; }}
        QSpinBox::up-button, QSpinBox::down-button {{
            width:24px; border:none;
            background:{LIGHT}; border-radius:3px;
        }}
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
            background:{BORDER};
        }}
    """)
    return s


def _field_row(label_text, widget, lw=LBL_W):
    """Returns a QHBoxLayout with label + widget properly spaced."""
    row = QHBoxLayout()
    row.setSpacing(16)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(_lbl(label_text, lw))
    row.addWidget(widget, 1)
    return row


def _section_header(layout, title, top_margin=8):
    """Adds section title + divider to a QVBoxLayout."""
    layout.addSpacing(top_margin)
    layout.addWidget(_sec(title))
    layout.addSpacing(6)
    layout.addWidget(_hr())
    layout.addSpacing(10)


def _panel(bg=WHITE, border_right=False):
    w = QWidget()
    # Use objectName to scope the border-right so it never bleeds into child widgets
    w.setObjectName("panel")
    br = f"border-right:1px solid {BORDER};" if border_right else ""
    w.setStyleSheet(f"QWidget#panel {{ background:{bg}; {br} }}")
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

    # =========================================================================
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)

        # ── Fixed header bar ──────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(64)
        hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(28, 0, 28, 0)
        hl.setSpacing(16)

        title = QLabel("Company Defaults")
        title.setStyleSheet(
            f"font-size:18px;font-weight:bold;color:{WHITE};background:transparent;"
        )

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"font-size:13px;background:transparent;color:#2ecc71;"
        )

        save_btn = QPushButton("  Save  ")
        save_btn.setFixedHeight(38)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background:{SUCCESS}; color:{WHITE}; border:none;
                border-radius:6px; font-size:13px; font-weight:bold; padding:0 24px;
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

        # Accent gradient line
        bar = QFrame(); bar.setFixedHeight(3)
        bar.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {NAVY},stop:0.5 {ACCENT},stop:1 {NAVY_3});
        """)
        outer.addWidget(bar)

        # ── Scroll area ───────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border:none; background:{OFF_WHITE}; }}
            QScrollBar:vertical {{
                background:{LIGHT}; width:8px; border-radius:4px;
            }}
            QScrollBar::handle:vertical {{
                background:#b0c4de; border-radius:4px; min-height:32px;
            }}
            QScrollBar:horizontal {{
                background:{LIGHT}; height:8px; border-radius:4px;
            }}
            QScrollBar::handle:horizontal {{
                background:#b0c4de; border-radius:4px; min-width:32px;
            }}
        """)

        content = QWidget()
        content.setStyleSheet(f"background:{OFF_WHITE};")
        root = QVBoxLayout(content)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ═════════════════════════════════════════════════════════════════════
        # TOP ROW
        # LEFT  — Receipt Details
        # RIGHT — User Info + Login Defaults + Invoice Numbering
        # ═════════════════════════════════════════════════════════════════════
        top_row = QHBoxLayout()
        top_row.setSpacing(0)
        top_row.setContentsMargins(0, 0, 0, 0)

        # ── LEFT panel : Receipt Details ──────────────────────────────────────
        receipt_p = _panel(WHITE, border_right=True)
        rl = QVBoxLayout(receipt_p)
        rl.setContentsMargins(36, 32, 36, 32)
        rl.setSpacing(ROW_SP)

        _section_header(rl, "Receipt Details", top_margin=0)
        rl.addSpacing(8)   # extra gap between header and first field

        for label, key in [
            ("Company Name",   "company_name"),
            ("Address Line 1", "address_1"),
            ("Address Line 2", "address_2"),
            ("Email",          "email"),
            ("Phone",          "phone"),
            ("VAT Number",     "vat_number"),
            ("TIN Number",     "tin_number"),
        ]:
            inp = _inp()
            self._inputs[key] = inp
            rl.addLayout(_field_row(label, inp))

        rl.addStretch()

        # ── RIGHT panel : User + Login Defaults + Invoice Numbering ──────────
        right_p = _panel(OFF_WHITE)
        rr = QVBoxLayout(right_p)
        rr.setContentsMargins(36, 32, 36, 32)
        rr.setSpacing(ROW_SP)

        # User
        _section_header(rr, "User", top_margin=0)
        for label, key in [
            ("Username",   "server_username"),
            ("First Name", "server_first_name"),
            ("Last Name",  "server_last_name"),
            ("Email",      "server_email"),
            ("Mobile",     "server_mobile"),
        ]:
            ro = _ro()
            self._ro_labels[key] = ro
            rr.addLayout(_field_row(label, ro))

        # Invoice Numbering
        _section_header(rr, "Invoice Numbering", top_margin=16)

        self._prefix_inp = _inp(placeholder="e.g. ABC  (max 6 chars)")
        self._prefix_inp.setMaxLength(6)
        self._prefix_inp.textChanged.connect(self._update_preview)
        rr.addLayout(_field_row("Prefix", self._prefix_inp))

        self._start_num = _spinbox()
        self._start_num.valueChanged.connect(self._update_preview)
        rr.addLayout(_field_row("Starting from", self._start_num))

        # Preview badge
        preview_row = QHBoxLayout()
        preview_row.setSpacing(16)
        preview_row.setContentsMargins(0, 4, 0, 0)
        preview_row.addWidget(_lbl("Preview"))
        self._preview_lbl = QLabel("000001")
        self._preview_lbl.setFixedHeight(FIELD_H)
        self._preview_lbl.setStyleSheet(
            f"color:{ACCENT};font-size:14px;font-weight:bold;"
            f"background:{LIGHT};border:1px solid {BORDER};"
            f"border-radius:6px;padding:0 14px;"
        )
        preview_row.addWidget(self._preview_lbl)
        preview_row.addStretch()
        rr.addLayout(preview_row)

        rr.addStretch()

        top_row.addWidget(receipt_p, 1)
        top_row.addWidget(right_p, 1)

        top_w = QWidget()
        top_w.setLayout(top_row)
        root.addWidget(top_w)

        # Divider between top and bottom
        div = QFrame(); div.setFixedHeight(1)
        div.setStyleSheet(f"background:{BORDER};border:none;")
        root.addWidget(div)

        # ═════════════════════════════════════════════════════════════════════
        # BOTTOM ROW
        # LEFT  — Footer Text
        # MID   — ZIMRA Settings
        # RIGHT — blank
        # ═════════════════════════════════════════════════════════════════════
        bot_row = QHBoxLayout()
        bot_row.setSpacing(0)
        bot_row.setContentsMargins(0, 0, 0, 0)

        # Footer Text
        footer_p = _panel(WHITE, border_right=True)
        fl = QVBoxLayout(footer_p)
        fl.setContentsMargins(36, 28, 36, 28)
        fl.setSpacing(ROW_SP)

        _section_header(fl, "Footer Text", top_margin=0)

        self._footer = QTextEdit()
        self._footer.setMinimumHeight(200)
        self._footer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._footer.setStyleSheet(f"""
            QTextEdit {{
                background:{WHITE}; color:{DARK_TEXT};
                border:1px solid {BORDER}; border-radius:6px;
                padding:10px 12px; font-size:13px; line-height:1.5;
            }}
            QTextEdit:focus {{ border:2px solid {ACCENT}; }}
        """)
        fl.addWidget(self._footer, 1)

        # ZIMRA Settings
        zimra_p = _panel(OFF_WHITE, border_right=True)
        zl = QVBoxLayout(zimra_p)
        zl.setContentsMargins(36, 28, 36, 28)
        zl.setSpacing(ROW_SP)

        _section_header(zl, "ZIMRA Settings", top_margin=0)

        for label, key, pwd in [
            ("Serial No", "zimra_serial_no", False),
            ("Device ID", "zimra_device_id", False),
            ("API URL",   "zimra_api_url",   False),
            ("API Key",   "zimra_api_key",   True),
        ]:
            inp = _inp(pwd=pwd)
            self._inputs[key] = inp
            zl.addLayout(_field_row(label, inp, lw=90))

        zl.addStretch()

        # Login Defaults (moved from top-right)
        login_p = _panel(WHITE)
        ll = QVBoxLayout(login_p)
        ll.setContentsMargins(36, 28, 36, 28)
        ll.setSpacing(ROW_SP)

        _section_header(ll, "Login Defaults", top_margin=0)

        for label, key in [
            ("Company",     "server_company"),
            ("Warehouse",   "server_warehouse"),
            ("Cost Centre", "server_cost_center"),
            ("Full Name",   "server_full_name"),
            ("Role",        "server_role"),
        ]:
            ro = _ro()
            self._ro_labels[key] = ro
            ll.addLayout(_field_row(label, ro, lw=100))

        ll.addStretch()

        bot_row.addWidget(footer_p, 1)
        bot_row.addWidget(zimra_p, 1)
        bot_row.addWidget(login_p, 1)

        # ── SECOND BOTTOM ROW — Terms & Conditions (full width) ───────────────
        terms_w = QWidget()
        terms_w.setStyleSheet(f"background:{WHITE};")
        tl = QVBoxLayout(terms_w)
        tl.setContentsMargins(36, 28, 36, 28)
        tl.setSpacing(ROW_SP)

        _section_header(tl, "Terms & Conditions (printed on Sales Orders)", top_margin=0)

        self._terms = QTextEdit()
        self._terms.setMinimumHeight(180)
        self._terms.setPlaceholderText(
            "Enter your sales order terms & conditions here.\n"
            "Each line will be printed as a separate paragraph."
        )
        self._terms.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._terms.setStyleSheet(f"""
            QTextEdit {{
                background:{WHITE}; color:{DARK_TEXT};
                border:1px solid {BORDER}; border-radius:6px;
                padding:10px 12px; font-size:13px; line-height:1.5;
            }}
            QTextEdit:focus {{ border:2px solid {ACCENT}; }}
        """)
        tl.addWidget(self._terms, 1)

        root.addWidget(terms_w)

        bot_w = QWidget()
        bot_w.setLayout(bot_row)
        root.addWidget(bot_w)

        root.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    # ── Live invoice preview ──────────────────────────────────────────────────

    def _update_preview(self):
        prefix = self._prefix_inp.text().strip().upper()
        num    = self._start_num.value()
        text   = f"{prefix}{num:06d}" if prefix else f"{num:06d}"
        self._preview_lbl.setText(text)

    # ── Load data ─────────────────────────────────────────────────────────────

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
        self._terms.setPlainText(data.get("terms_and_conditions", ""))

        for key, lbl in self._ro_labels.items():
            val = data.get(key, "")
            lbl.setText(val if val else "—")

        self._prefix_inp.setText(data.get("invoice_prefix", ""))
        try:
            self._start_num.setValue(int(data.get("invoice_start_number", 0) or 0))
        except (ValueError, TypeError):
            self._start_num.setValue(0)

        self._update_preview()

    # ── Save data ─────────────────────────────────────────────────────────────

    def _save(self):
        data = {k: i.text().strip() for k, i in self._inputs.items()}
        data["footer_text"]           = self._footer.toPlainText().strip()
        data["terms_and_conditions"]  = self._terms.toPlainText().strip()
        data["invoice_prefix"]        = self._prefix_inp.text().strip().upper()
        data["invoice_start_number"] = str(self._start_num.value())

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
            f"font-size:13px;background:transparent;color:{color};"
        )
        self._status_lbl.setText(msg)
        QTimer.singleShot(3000, lambda: self._status_lbl.setText(""))
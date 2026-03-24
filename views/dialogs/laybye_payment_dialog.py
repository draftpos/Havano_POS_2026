# =============================================================================
# views/dialogs/laybye_payment_dialog.py  —  Deposit dialog for Laybye flow
#
# v3 fixes:
#   - Numpad fully rewritten: no more "0.00" seed bug, clean digit building
#   - Backspace and CLR work correctly on all states
#   - Quick amount buttons replace (not append to) current value
#   - Discount passed in from cart and stored on accept()
#   - All outputs exposed after accept():
#       self.deposit_amount, self.deposit_method, self.deposit_splits
#       self.deposit_currency, self.delivery_date (ISO str), self.order_type
#       self.discount_amount, self.discount_percent
#       self.accepted_customer, self.accepted_company, self.accepted_company_name
#
# v4 fix:
#   - _get_default_company() now reads server_company from company_defaults
#     instead of the local companies table, so the correct ERPNext company
#     name is used when building the Sales Order payload.
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QFrame, QSizePolicy,
    QMessageBox, QScrollArea, QComboBox, QDateEdit,
)
from PySide6.QtCore import Qt, QLocale, QDate
from PySide6.QtGui  import QDoubleValidator

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
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"
ORANGE    = "#c05a00"

ORDER_TYPES = ["Sales", "Shopping Cart", "Maintenance"]


# =============================================================================
# Data helpers
# =============================================================================

def _get_local_rate(from_ccy: str, to_ccy: str = "USD") -> float:
    if from_ccy.upper() == to_ccy.upper():
        return 1.0
    try:
        from models.exchange_rate import get_rate
        r = get_rate(from_ccy, to_ccy)
        return float(r) if r else 1.0
    except Exception:
        return 1.0


def _get_default_company() -> dict | None:
    # ── v4: read server_company from company_defaults first ──────────────────
    # This ensures the ERPNext company name (e.g. "Confidence Pro") is used
    # rather than whatever happens to be row[0] in the local companies table.
    try:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
        name = d.get("server_company", "").strip()
        if name:
            return {"name": name}
    except Exception:
        pass

    # Fallback: local companies table (used if company_defaults is not set)
    try:
        from models.company import get_all_companies
        rows = get_all_companies()
        return rows[0] if rows else None
    except Exception:
        return None


def _load_payment_methods(company: str) -> list[dict]:
    try:
        from models.gl_account import get_all_accounts
        all_accts = get_all_accounts()
        accts = [a for a in all_accts if a.get("company") == company] or all_accts
    except Exception:
        accts = []

    seen, result = set(), []
    for a in accts:
        curr  = (a.get("account_currency") or "USD").upper()
        atype = (a.get("account_type") or a.get("name") or "Cash").strip()
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
        result.append({
            "label":       a.get("account_name") or a.get("name") or atype,
            "currency":    curr,
            "rate_to_usd": rate,
            "is_credit":   bool(a.get("is_credit") or a.get("credit_account") or False),
        })

    if not result:
        result = [
            {"label": "Cash",       "currency": "USD", "rate_to_usd": 1.0, "is_credit": False},
            {"label": "Cash (ZIG)", "currency": "ZIG", "rate_to_usd": _get_local_rate("ZIG"), "is_credit": False},
            {"label": "Card",       "currency": "USD", "rate_to_usd": 1.0, "is_credit": False},
            {"label": "Bank / EFT", "currency": "USD", "rate_to_usd": 1.0, "is_credit": False},
        ]
    return result


# =============================================================================
# Widget helpers
# =============================================================================

def _hr():
    ln = QFrame()
    ln.setFrameShape(QFrame.HLine)
    ln.setStyleSheet(f"background:{BORDER}; border:none;")
    ln.setFixedHeight(1)
    return ln


def _method_btn_style(active: bool) -> str:
    if active:
        return (f"QPushButton {{ background:{ACCENT}; color:{WHITE}; border:none;"
                f" border-radius:6px; font-size:12px; font-weight:bold;"
                f" text-align:left; padding:0 12px; }}"
                f"QPushButton:hover {{ background:{ACCENT_H}; }}")
    return (f"QPushButton {{ background:{WHITE}; color:{DARK_TEXT};"
            f" border:1px solid {BORDER}; border-radius:6px;"
            f" font-size:12px; text-align:left; padding:0 12px; }}"
            f"QPushButton:hover {{ background:{LIGHT}; }}")


def _field_style(active: bool, has_value: bool = False) -> str:
    if active:
        return (f"QLineEdit {{ background:{WHITE}; color:{DARK_TEXT};"
                f" border:2px solid {ACCENT}; border-radius:6px;"
                f" font-size:14px; font-weight:bold; padding:0 10px; }}")
    if has_value:
        return (f"QLineEdit {{ background:{WHITE}; color:{DARK_TEXT};"
                f" border:1px solid {BORDER}; border-radius:6px;"
                f" font-size:14px; padding:0 10px; }}")
    # Empty + inactive — truly blank, no box
    return (f"QLineEdit {{ background:transparent; color:{DARK_TEXT};"
            f" border:none; font-size:14px; padding:0 10px; }}")


def _numpad_btn(text, kind="digit"):
    btn = QPushButton(text)
    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFocusPolicy(Qt.NoFocus)
    styles = {
        "digit": (WHITE,   LIGHT,    DARK_TEXT),
        "quick": (NAVY_3,  NAVY_2,   WHITE),
        "del":   (NAVY_2,  NAVY_3,   WHITE),
        "clear": (DANGER,  DANGER_H, WHITE),
    }
    bg, hov, fg = styles.get(kind, styles["digit"])
    btn.setStyleSheet(
        f"QPushButton {{ background:{bg}; color:{fg}; border:1px solid {BORDER};"
        f" border-radius:6px; font-size:15px; font-weight:bold; }}"
        f"QPushButton:hover {{ background:{hov}; }}"
        f"QPushButton:pressed {{ background:{NAVY_3}; color:{WHITE}; }}")
    return btn


def _action_btn(text, color, hover, height=46):
    btn = QPushButton(text)
    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    btn.setFixedHeight(height)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFocusPolicy(Qt.NoFocus)
    btn.setStyleSheet(
        f"QPushButton {{ background:{color}; color:{WHITE}; border:none;"
        f" border-radius:6px; font-size:13px; font-weight:bold; }}"
        f"QPushButton:hover {{ background:{hover}; }}")
    return btn


# =============================================================================
# LAYBYE PAYMENT DIALOG
# =============================================================================

class LaybyePaymentDialog(QDialog):
    """
    Deposit + order details dialog for the Laybye flow.

    Args:
        total           float  — order grand total (after any cart discount)
        customer        dict   — must be a real customer (not walk-in)
        discount_amount float  — discount already applied in the cart (stored only)
        discount_percent float — discount % already applied in the cart (stored only)

    After accept():
        self.deposit_amount        float  USD  (0.0 if skipped)
        self.deposit_method        str
        self.deposit_splits        list
        self.deposit_currency      str
        self.delivery_date         str   ISO  e.g. "2026-04-15"
        self.order_type            str   e.g. "Sales"
        self.discount_amount       float
        self.discount_percent      float
        self.accepted_customer     dict | None
        self.accepted_company      dict | None
        self.accepted_company_name str
    """

    def __init__(
        self,
        parent=None,
        total: float = 0.0,
        customer: dict | None = None,
        discount_amount: float = 0.0,
        discount_percent: float = 0.0,
    ):
        super().__init__(parent)
        self.total = total

        # Cart discount — passed in, stored on accept, not editable here
        self._discount_amount  = discount_amount
        self._discount_percent = discount_percent

        # Outputs (set by _commit)
        self.deposit_amount        = 0.0
        self.deposit_method        = ""
        self.deposit_splits        = []
        self.deposit_currency      = "USD"
        self.delivery_date         = ""
        self.order_type            = "Sales"
        self.discount_amount       = discount_amount
        self.discount_percent      = discount_percent
        self.accepted_customer     = None
        self.accepted_company      = None
        self.accepted_company_name = ""

        self._customer = customer
        self._company  = _get_default_company()  # v4: reads from company_defaults

        co_name = self._company.get("name", "") if self._company else ""
        self._methods: list[dict]         = _load_payment_methods(co_name)
        self._method_rows: dict[str, tuple] = {}
        self._active_method: str          = self._methods[0]["label"] if self._methods else ""

        # Internal numpad buffer — we own the string, not the QLineEdit
        self._numpad_buf: dict[str, str] = {m["label"]: "" for m in self._methods}

        self.setWindowTitle("Laybye — Deposit & Order Details")
        self.setMinimumSize(920, 600)
        self.setModal(True)
        self.setWindowState(Qt.WindowMaximized)

        self._build_ui()
        if self._active_method:
            self._activate_method(self._active_method)

    # =========================================================================
    # UI
    # =========================================================================

    def _build_ui(self):
        self.setStyleSheet(f"""
            QDialog  {{ background:{OFF_WHITE}; font-family:'Segoe UI',sans-serif; }}
            QLabel   {{ background:transparent; color:{DARK_TEXT}; font-size:13px; }}
            QWidget  {{ background:{OFF_WHITE}; }}
        """)

        outer = QVBoxLayout(self)
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)

        # ── Top header bar ────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{WHITE}; border-bottom:2px solid {BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(28, 0, 28, 0)

        title = QLabel("Laybye  —  Deposit")
        title.setStyleSheet(
            f"color:{NAVY}; font-size:17px; font-weight:bold; background:transparent;")
        badge = QLabel("🛍  LAYBYE")
        badge.setStyleSheet(
            f"background:{ORANGE}; color:{WHITE}; border-radius:5px;"
            f" font-size:10px; font-weight:bold; padding:3px 10px;")
        zwg_rate = _get_local_rate("USD", "ZWG")
        rate_pill = QLabel(f"1 USD = {zwg_rate:,.2f} ZWG")
        rate_pill.setStyleSheet(
            f"color:{MUTED}; font-size:10px; background:{LIGHT};"
            f" border-radius:4px; padding:2px 8px;")
        hint = QLabel("Deposit optional  ·  Enter to save  ·  Esc to cancel")
        hint.setStyleSheet(f"color:{MUTED}; font-size:10px; background:transparent;")
        hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        hl.addWidget(title)
        hl.addSpacing(10)
        hl.addWidget(badge)
        hl.addSpacing(12)
        hl.addWidget(rate_pill)
        hl.addStretch()
        hl.addWidget(hint)
        outer.addWidget(hdr)

        # ── Customer info strip ───────────────────────────────────────────────
        cust_strip = QWidget()
        cust_strip.setFixedHeight(34)
        cust_strip.setStyleSheet(f"background:{NAVY_2};")
        cs = QHBoxLayout(cust_strip)
        cs.setContentsMargins(28, 0, 28, 0)
        cs.setSpacing(8)

        cust_icon = QLabel("👤")
        cust_icon.setStyleSheet("background:transparent; font-size:14px;")
        cname = (self._customer or {}).get("customer_name", "Unknown")
        cust_name_lbl = QLabel(cname)
        cust_name_lbl.setStyleSheet(
            f"color:{WHITE}; font-size:13px; font-weight:bold; background:transparent;")
        cust_type = (self._customer or {}).get("customer_type", "")
        cust_type_lbl = QLabel(f"  [{cust_type}]" if cust_type else "")
        cust_type_lbl.setStyleSheet(
            f"color:{MID}; font-size:11px; background:transparent;")

        # Show discount in strip if one was applied
        cs.addWidget(cust_icon)
        cs.addWidget(cust_name_lbl)
        cs.addWidget(cust_type_lbl)
        cs.addStretch()
        if self._discount_amount > 0:
            disc_lbl = QLabel(
                f"Discount: {self._discount_percent:.1f}%  (−USD {self._discount_amount:.2f})")
            disc_lbl.setStyleSheet(
                f"color:{ORANGE}; font-size:11px; font-weight:bold; background:transparent;")
            cs.addWidget(disc_lbl)
        outer.addWidget(cust_strip)

        # ── Content area ──────────────────────────────────────────────────────
        outer_h = QHBoxLayout()
        outer_h.setContentsMargins(0, 0, 0, 0)
        outer_h.setSpacing(0)

        center = QWidget()
        center.setStyleSheet(f"background:{OFF_WHITE};")
        center.setMaximumWidth(1200)
        cv = QVBoxLayout(center)
        cv.setContentsMargins(32, 20, 32, 20)
        cv.setSpacing(0)

        content = QHBoxLayout()
        content.setSpacing(28)
        content.addLayout(self._build_left(), stretch=5)

        vline = QFrame()
        vline.setFrameShape(QFrame.VLine)
        vline.setStyleSheet(f"background:{BORDER}; border:none;")
        vline.setFixedWidth(1)
        content.addWidget(vline)
        content.addLayout(self._build_right(), stretch=4)
        cv.addLayout(content)

        outer_h.addStretch(1)
        outer_h.addWidget(center, stretch=10)
        outer_h.addStretch(1)
        wrap = QWidget()
        wrap.setStyleSheet(f"background:{OFF_WHITE};")
        wrap.setLayout(outer_h)
        outer.addWidget(wrap, stretch=1)

    # =========================================================================
    # Left panel — payment methods
    # =========================================================================

    def _build_left(self):
        vbox = QVBoxLayout()
        vbox.setSpacing(10)

        # ── Cards row ─────────────────────────────────────────────────────────
        cards = QHBoxLayout()
        cards.setSpacing(10)

        # Order total card
        tc = QFrame()
        tc.setFixedHeight(72)
        tc.setStyleSheet(
            f"QFrame {{ background:{WHITE}; border:2px solid {ORANGE}; border-radius:8px; }}")
        tcl = QVBoxLayout(tc)
        tcl.setContentsMargins(14, 6, 14, 6)
        tcl.setSpacing(1)
        cap_t = QLabel("ORDER TOTAL")
        cap_t.setAlignment(Qt.AlignCenter)
        cap_t.setStyleSheet(
            f"color:{ORANGE}; font-size:9px; font-weight:bold;"
            f" letter-spacing:1px; background:transparent;")
        tot_v = QLabel(f"USD  {self.total:.2f}")
        tot_v.setAlignment(Qt.AlignCenter)
        tot_v.setStyleSheet(
            f"color:{DARK_TEXT}; font-size:18px; font-weight:bold;"
            f" font-family:'Courier New',monospace; background:transparent;")
        tcl.addWidget(cap_t)
        tcl.addWidget(tot_v)
        cards.addWidget(tc, 1)

        # Deposit card (live update)
        dc = QFrame()
        dc.setFixedHeight(72)
        dc.setStyleSheet(
            f"QFrame {{ background:{WHITE}; border:2px solid {BORDER}; border-radius:8px; }}")
        self._dep_card = dc
        dcl = QVBoxLayout(dc)
        dcl.setContentsMargins(14, 6, 14, 6)
        dcl.setSpacing(1)
        cap_d = QLabel("DEPOSIT")
        cap_d.setAlignment(Qt.AlignCenter)
        cap_d.setStyleSheet(
            f"color:{MUTED}; font-size:9px; font-weight:bold;"
            f" letter-spacing:1px; background:transparent;")
        self._dep_lbl = QLabel("USD  0.00")
        self._dep_lbl.setAlignment(Qt.AlignCenter)
        self._dep_lbl.setStyleSheet(
            f"color:{DARK_TEXT}; font-size:18px; font-weight:bold;"
            f" font-family:'Courier New',monospace; background:transparent;")
        dcl.addWidget(cap_d)
        dcl.addWidget(self._dep_lbl)
        cards.addWidget(dc, 1)
        vbox.addLayout(cards)
        vbox.addWidget(_hr())

        # ── Column headers ────────────────────────────────────────────────────
        ch = QWidget()
        ch.setFixedHeight(18)
        ch.setStyleSheet("background:transparent;")
        chl = QHBoxLayout(ch)
        chl.setContentsMargins(0, 0, 0, 0)
        chl.setSpacing(8)
        for txt, st, align in [
            ("MODE OF PAYMENT", 4, Qt.AlignLeft),
            ("CCY",             1, Qt.AlignCenter),
            ("DEPOSIT",         3, Qt.AlignRight),
            ("BALANCE DUE",     4, Qt.AlignRight),
        ]:
            lbl = QLabel(txt)
            lbl.setStyleSheet(
                f"color:{MUTED}; font-size:9px; font-weight:bold;"
                f" letter-spacing:0.7px; background:transparent;")
            lbl.setAlignment(align)
            chl.addWidget(lbl, st)
        vbox.addWidget(ch)

        # ── Scrollable method rows ────────────────────────────────────────────
        sw = QWidget()
        sw.setStyleSheet("background:transparent;")
        sl = QVBoxLayout(sw)
        sl.setSpacing(4)
        sl.setContentsMargins(0, 0, 4, 0)

        for method in self._methods:
            label = method["label"]
            curr  = method["currency"]

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
            mb.setStyleSheet(_method_btn_style(False))
            mb.clicked.connect(lambda _, m=label: self._activate_method(m))

            cb = QLabel(curr)
            cb.setFixedHeight(32)
            cb.setFixedWidth(46)
            cb.setAlignment(Qt.AlignCenter)
            cb.setStyleSheet(
                f"background:{LIGHT}; color:{ACCENT}; border:1px solid {BORDER};"
                f" border-radius:6px; font-size:10px; font-weight:bold;")

            # Display field — read-only, driven by numpad buffer
            ae = QLineEdit()
            ae.setFixedHeight(32)
            ae.setReadOnly(True)          # numpad owns the value
            ae.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            ae.setStyleSheet(_field_style(False))
            ae.setPlaceholderText("")

            bal = QLabel(f"USD  {self.total:.2f}")
            bal.setFixedHeight(32)
            bal.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            bal.setStyleSheet(
                f"color:{DARK_TEXT}; font-size:11px; font-weight:bold;"
                f" background:{WHITE}; border:1px solid {BORDER};"
                f" border-radius:6px; padding:0 10px;")

            rl.addWidget(mb, 4)
            rl.addWidget(cb, 1)
            rl.addWidget(ae, 3)
            rl.addWidget(bal, 4)
            sl.addWidget(rw)
            self._method_rows[label] = (mb, ae, bal)

        sl.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(sw)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:transparent;")
        scroll.setMinimumHeight(160)
        vbox.addWidget(scroll, 1)
        return vbox

    # =========================================================================
    # Right panel — numpad + order details + actions
    # =========================================================================

    def _build_right(self):
        vbox = QVBoxLayout()
        vbox.setSpacing(8)

        # ── Numpad ────────────────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(6)

        # Quick amount buttons (row 0)
        for col, val in enumerate([50, 100, 200]):
            b = _numpad_btn(f"${val}", "quick")
            b.clicked.connect(lambda _, v=val: self._numpad_quick(v))
            grid.addWidget(b, 0, col)

        # Digit buttons (rows 1-4)
        digits = [
            ("7", 1, 0), ("8", 1, 1), ("9", 1, 2),
            ("4", 2, 0), ("5", 2, 1), ("6", 2, 2),
            ("1", 3, 0), ("2", 3, 1), ("3", 3, 2),
            (".",  4, 0), ("0", 4, 1), ("00", 4, 2),
        ]
        for txt, row, col in digits:
            b = _numpad_btn(txt)
            b.clicked.connect(lambda _, t=txt: self._numpad_press(t))
            grid.addWidget(b, row, col)

        # Delete / Clear (row 5)
        del_btn = _numpad_btn("⌫", "del")
        del_btn.clicked.connect(self._numpad_back)
        clr_btn = _numpad_btn("CLR", "clear")
        clr_btn.clicked.connect(self._numpad_clear)
        grid.addWidget(del_btn, 5, 0)
        grid.addWidget(clr_btn, 5, 1, 1, 2)

        for i in range(6):
            grid.setRowStretch(i, 1)
        for i in range(3):
            grid.setColumnStretch(i, 1)

        vbox.addLayout(grid, 1)

        # ── Order details ─────────────────────────────────────────────────────
        vbox.addWidget(_hr())

        details_lbl = QLabel("ORDER DETAILS")
        details_lbl.setStyleSheet(
            f"color:{MUTED}; font-size:9px; font-weight:bold;"
            f" letter-spacing:1px; background:transparent;")
        vbox.addWidget(details_lbl)

        # Delivery Date
        dd_row = QHBoxLayout()
        dd_row.setSpacing(8)
        dd_lbl = QLabel("Delivery Date:")
        dd_lbl.setStyleSheet(
            f"color:{DARK_TEXT}; font-size:12px; background:transparent;")
        dd_lbl.setFixedWidth(100)
        self._delivery_date = QDateEdit()
        self._delivery_date.setCalendarPopup(True)
        self._delivery_date.setDate(QDate.currentDate().addDays(7))
        self._delivery_date.setDisplayFormat("dd/MM/yyyy")
        self._delivery_date.setFixedHeight(32)
        self._delivery_date.setStyleSheet(
            f"QDateEdit {{ background:{WHITE}; color:{DARK_TEXT};"
            f" border:1px solid {BORDER}; border-radius:5px;"
            f" padding:0 8px; font-size:13px; }}"
            f"QDateEdit:focus {{ border:2px solid {ACCENT}; }}")
        dd_row.addWidget(dd_lbl)
        dd_row.addWidget(self._delivery_date, 1)
        vbox.addLayout(dd_row)

        # Order Type
        ot_row = QHBoxLayout()
        ot_row.setSpacing(8)
        ot_lbl = QLabel("Order Type:")
        ot_lbl.setStyleSheet(
            f"color:{DARK_TEXT}; font-size:12px; background:transparent;")
        ot_lbl.setFixedWidth(100)
        self._order_type = QComboBox()
        for ot in ORDER_TYPES:
            self._order_type.addItem(ot)
        self._order_type.setFixedHeight(32)
        self._order_type.setStyleSheet(
            f"QComboBox {{ background:{WHITE}; color:{DARK_TEXT};"
            f" border:1px solid {BORDER}; border-radius:5px;"
            f" padding:0 8px; font-size:13px; }}"
            f"QComboBox::drop-down {{ border:none; width:20px; }}"
            f"QComboBox QAbstractItemView {{ background:{WHITE};"
            f" border:1px solid {BORDER};"
            f" selection-background-color:{ACCENT};"
            f" selection-color:{WHITE}; }}")
        ot_row.addWidget(ot_lbl)
        ot_row.addWidget(self._order_type, 1)
        vbox.addLayout(ot_row)

        vbox.addWidget(_hr())

        # ── Action buttons ────────────────────────────────────────────────────
        save_btn  = _action_btn("🛍  Save Laybye",  ORANGE,  "#d96a00", 52)
        skip_btn  = _action_btn("Skip Deposit →",   NAVY_2,  NAVY_3,    40)
        split_btn = _action_btn("Split Payment",    ACCENT,  ACCENT_H,  40)

        save_btn.clicked.connect(self._save)
        skip_btn.clicked.connect(self._skip_deposit)
        split_btn.clicked.connect(self._open_split)

        vbox.addWidget(save_btn)
        vbox.addWidget(skip_btn)
        vbox.addWidget(split_btn)
        return vbox

    # =========================================================================
    # Method activation
    # =========================================================================

    def _activate_method(self, label: str):
        self._active_method = label
        for lbl, (mb, ae, _) in self._method_rows.items():
            active    = lbl == label
            has_value = bool(self._numpad_buf.get(lbl, ""))
            mb.setStyleSheet(_method_btn_style(active))
            ae.setStyleSheet(_field_style(active, has_value))

    def _active_field(self) -> QLineEdit:
        if self._active_method and self._active_method in self._method_rows:
            _, ae, _ = self._method_rows[self._active_method]
            return ae
        return list(self._method_rows.values())[0][1]

    def _method_info(self, label: str) -> tuple[str, float]:
        for m in self._methods:
            if m["label"] == label:
                return m["currency"], m["rate_to_usd"]
        return "USD", 1.0

    # =========================================================================
    # Numpad — buffer-driven (no QLineEdit validator fighting)
    # =========================================================================

    def _buf(self) -> str:
        """Current raw buffer string for the active method."""
        return self._numpad_buf.get(self._active_method, "")

    def _set_buf(self, value: str):
        """Set buffer, update display field, restyle all rows."""
        self._numpad_buf[self._active_method] = value
        for lbl, (mb, ae, _) in self._method_rows.items():
            active    = lbl == self._active_method
            has_value = bool(self._numpad_buf.get(lbl, ""))
            ae.setStyleSheet(_field_style(active, has_value))
            if active:
                ae.setText(value)
        self._refresh_totals()

    def _numpad_press(self, key: str):
        buf = self._buf()

        if key == ".":
            # Only one decimal point allowed
            if "." not in buf:
                self._set_buf(buf + ".")
            return

        if key == "00":
            if not buf:
                return          # don't add "00" to an empty buffer
            # Allow "00" only after decimal if < 2 decimal places already entered
            if "." in buf:
                decimals = buf.split(".")[1]
                if len(decimals) < 2:
                    self._set_buf((buf + "00")[:buf.index(".") + 3])
            else:
                # Append "00" to integer part (max 8 digits)
                integer = buf
                if len(integer) < 7:
                    self._set_buf(buf + "00")
            return

        # Regular digit
        if "." in buf:
            decimals = buf.split(".")[1]
            if len(decimals) < 2:
                self._set_buf(buf + key)
        else:
            integer = buf
            if len(integer) < 8:
                # Strip any leading zero before adding more digits
                new = (integer + key).lstrip("0") or key
                self._set_buf(new)

    def _numpad_back(self):
        buf = self._buf()
        self._set_buf(buf[:-1])

    def _numpad_clear(self):
        self._set_buf("")

    def _numpad_quick(self, amt: int):
        """Replace current value with a preset quick amount."""
        self._set_buf(str(amt))
        self._refresh_totals()

    # =========================================================================
    # Live totals
    # =========================================================================

    def _buf_as_float(self, label: str) -> float:
        """Return the buffer value for a method as a USD float."""
        raw = self._numpad_buf.get(label, "")
        try:
            val = float(raw) if raw else 0.0
        except ValueError:
            val = 0.0
        _, rate = self._method_info(label)
        return val * rate

    def _refresh_totals(self):
        paid = sum(self._buf_as_float(m["label"]) for m in self._methods)
        bal  = max(self.total - paid, 0.0)

        # Update deposit card
        self._dep_lbl.setText(f"USD  {paid:.2f}")
        if paid > 0.005:
            self._dep_card.setStyleSheet(
                f"QFrame {{ background:{WHITE}; border:2px solid {SUCCESS}; border-radius:8px; }}")
            self._dep_lbl.setStyleSheet(
                f"color:{SUCCESS}; font-size:18px; font-weight:bold;"
                f" font-family:'Courier New',monospace; background:transparent;")
        else:
            self._dep_card.setStyleSheet(
                f"QFrame {{ background:{WHITE}; border:2px solid {BORDER}; border-radius:8px; }}")
            self._dep_lbl.setStyleSheet(
                f"color:{DARK_TEXT}; font-size:18px; font-weight:bold;"
                f" font-family:'Courier New',monospace; background:transparent;")

        # Update each method's balance label
        for m in self._methods:
            label = m["label"]
            if label not in self._method_rows:
                continue
            _, _, bal_lbl = self._method_rows[label]
            curr, _ = self._method_info(label)
            if curr.upper() == "USD":
                text = f"USD  {bal:.2f}"
            else:
                rate_for_row = _get_local_rate("USD", curr)
                text = f"{curr}  {bal * rate_for_row:,.2f}"
            bal_lbl.setText(text)
            bal_lbl.setStyleSheet(
                f"color:{DARK_TEXT}; font-size:11px; font-weight:bold;"
                f" background:{WHITE}; border:1px solid {BORDER};"
                f" border-radius:6px; padding:0 10px;")

    # =========================================================================
    # Actions
    # =========================================================================

    def _get_tendered(self) -> float:
        return sum(self._buf_as_float(m["label"]) for m in self._methods)

    def _read_order_fields(self) -> tuple[str, str]:
        dd = self._delivery_date.date().toString("yyyy-MM-dd")
        ot = self._order_type.currentText()
        return dd, ot

    def _save(self):
        tendered = self._get_tendered()
        if tendered < 0:
            QMessageBox.warning(self, "Invalid Amount", "Deposit cannot be negative.")
            return
        if tendered > self.total + 0.005:
            QMessageBox.warning(
                self, "Overpayment",
                f"Deposit USD {tendered:.2f} exceeds order total USD {self.total:.2f}.\n"
                "Please adjust.")
            return
        self._commit(tendered, self._active_method)

    def _skip_deposit(self):
        self._commit(0.0, "")

    def _commit(self, amount: float, method: str):
        curr, _ = self._method_info(method) if method else ("USD", 1.0)
        dd, ot  = self._read_order_fields()

        self.deposit_amount        = amount
        self.deposit_method        = method
        self.deposit_splits        = []
        self.deposit_currency      = curr
        self.delivery_date         = dd
        self.order_type            = ot
        self.discount_amount       = self._discount_amount
        self.discount_percent      = self._discount_percent
        self.accepted_customer     = self._customer
        self.accepted_company      = self._company
        self.accepted_company_name = (
            self._company.get("name", "") if self._company else "")
        self.accept()

    def _open_split(self):
        co = self._company.get("name", "") if self._company else ""
        co_curr = "USD"
        try:
            from models.company_defaults import get_defaults
            d = get_defaults() or {}
            co_curr = d.get("server_company_currency", "USD").strip().upper() or "USD"
        except Exception:
            pass
        try:
            from views.dialogs.split_payment_dialog import SplitPaymentDialog
            dlg = SplitPaymentDialog(
                self, total=self.total, company=co, company_currency=co_curr)
            if dlg.exec() == QDialog.Accepted:
                dd, ot = self._read_order_fields()
                self.deposit_amount        = sum(s["base_value"] for s in dlg.splits)
                self.deposit_method        = "SPLIT"
                self.deposit_splits        = dlg.splits
                self.deposit_currency      = dlg.accepted_currency
                self.delivery_date         = dd
                self.order_type            = ot
                self.discount_amount       = self._discount_amount
                self.discount_percent      = self._discount_percent
                self.accepted_customer     = self._customer
                self.accepted_company      = self._company
                self.accepted_company_name = (
                    self._company.get("name", "") if self._company else "")
                self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Split Error", str(e))

    # =========================================================================
    # Keyboard shortcuts
    # =========================================================================

    def keyPressEvent(self, event):
        k = event.key()

        if k in (Qt.Key_Return, Qt.Key_Enter):
            self._save()
            return
        if k == Qt.Key_Escape:
            self.reject()
            return

        # If a date or combo widget has focus, let Qt handle it normally
        focused = self.focusWidget()
        if isinstance(focused, (QDateEdit, QComboBox)):
            super().keyPressEvent(event)
            return

        # ── Digit / decimal keys → numpad buffer ──────────────────────────────
        _digit_keys = {
            Qt.Key_0: "0", Qt.Key_1: "1", Qt.Key_2: "2",
            Qt.Key_3: "3", Qt.Key_4: "4", Qt.Key_5: "5",
            Qt.Key_6: "6", Qt.Key_7: "7", Qt.Key_8: "8",
            Qt.Key_9: "9", Qt.Key_Period: ".", Qt.Key_Comma: ".",
        }
        if k in _digit_keys:
            self._numpad_press(_digit_keys[k])
            return

        # Backspace → delete last char in buffer
        if k == Qt.Key_Backspace:
            self._numpad_back()
            return

        # Delete → clear buffer
        if k == Qt.Key_Delete:
            self._numpad_clear()
            return

        super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if self._active_method:
            self._activate_method(self._active_method)
        self._refresh_totals()
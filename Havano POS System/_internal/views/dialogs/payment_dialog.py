# =============================================================================
# views/dialogs/payment_dialog.py  —  POS Payment Dialog
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QFrame, QSizePolicy, QMessageBox,
    QScrollArea,
)
from PySide6.QtCore import Qt, QLocale, QTimer
from PySide6.QtGui import QDoubleValidator
import hashlib
import json
import time
import traceback
from datetime import datetime


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

# Debug counter
_debug_counter = 0

def _debug_print(msg: str, level: str = "INFO", force: bool = True):
    """Enhanced debug printing with timestamp and counter."""
    global _debug_counter
    _debug_counter += 1
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    prefix = f"[{timestamp}][PaymentDialog #{_debug_counter}]"
    if force:
        print(f"{prefix} {msg}")
    elif level == "ERROR":
        print(f"{prefix} ❌ {msg}")
    elif level == "WARNING":
        print(f"{prefix} ⚠️ {msg}")
    elif level == "SUCCESS":
        print(f"{prefix} ✅ {msg}")
    else:
        print(f"{prefix} {msg}")


# =============================================================================
# Data helpers
# =============================================================================

def _get_local_rate(from_currency: str, to_currency: str = "USD") -> float:
    """Return the exchange rate from_currency → to_currency."""
    _debug_print(f"_get_local_rate({from_currency}, {to_currency})")
    if from_currency.upper() == to_currency.upper():
        _debug_print(f"  Same currency, returning 1.0")
        return 1.0
    try:
        from models.exchange_rate import get_rate
        r = get_rate(from_currency, to_currency)
        if r:
            _debug_print(f"  Direct rate {from_currency}->{to_currency} = {r}")
            return float(r)
        inv = get_rate(to_currency, from_currency)
        if inv and float(inv) > 0:
            result = 1.0 / float(inv)
            _debug_print(f"  Inverse rate {to_currency}->{from_currency} = {inv}, reciprocal = {result}")
            return result
    except Exception as e:
        _debug_print(f"  Error getting rate: {e}", "WARNING")
    return 1.0


def _get_default_customer() -> dict | None:
    _debug_print("_get_default_customer()")
    try:
        from models.customer import get_all_customers
        for c in get_all_customers():
            if c["customer_name"].strip().lower() in ("walk-in", "default", "walk in"):
                _debug_print(f"  Found default customer: {c['customer_name']}")
                return c
    except Exception as e:
        _debug_print(f"  Error: {e}", "WARNING")
    return None


def _get_default_company() -> dict | None:
    _debug_print("_get_default_company()")
    try:
        from models.company import get_all_companies
        rows = get_all_companies()
        if rows:
            _debug_print(f"  Found company: {rows[0].get('name')}")
            return rows[0]
    except Exception as e:
        _debug_print(f"  Error: {e}", "WARNING")
    return None


def _load_payment_methods(company: str) -> list[dict]:
    """Load payment methods from modes_of_payment table."""
    _debug_print(f"_load_payment_methods(company='{company}')")
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
        _debug_print(f"  Found {len(rows)} rows in modes_of_payment")

        for row in rows:
            mop_name = (row.get("mop_name") or "").strip()
            gl_account = (row.get("gl_account") or "").strip()
            curr = (row.get("currency") or "USD").upper()

            if not mop_name or not gl_account:
                _debug_print(f"  Skipping {mop_name}: missing name or GL account")
                continue

            # Skip group accounts
            try:
                from database.db import get_connection as _gc, fetchone_dict as _fd
                _conn = _gc()
                _cur = _conn.cursor()
                _cur.execute("SELECT account_type FROM gl_accounts WHERE name = ?", (gl_account,))
                _row = _fd(_cur)
                _conn.close()
                if _row is not None and (_row.get("account_type") or "").strip() == "":
                    _debug_print(f"  [skip] '{gl_account}' is a group account")
                    continue
            except Exception:
                pass

            key = mop_name.lower()
            if key in seen:
                _debug_print(f"  Skipping duplicate: {mop_name}")
                continue
            seen.add(key)

            rate = 1.0
            try:
                from models.exchange_rate import get_rate
                r = get_rate(curr, "USD")
                if r and float(r) > 0:
                    rate = float(r)
            except Exception:
                pass

            result.append({
                "label": mop_name,
                "mop_name": mop_name,
                "gl_account": gl_account,
                "currency": curr,
                "rate_to_usd": rate,
                "is_credit": False,
            })
            _debug_print(f"  ✅ Added payment method: {mop_name} ({curr}) -> GL: {gl_account}")

    except Exception as e:
        _debug_print(f"Error loading payment methods: {e}", "ERROR")

    _debug_print(f"Loaded {len(result)} payment methods total")
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


def _oa_btn_style(active: bool) -> str:
    if active:
        return (f"QPushButton {{ background:{ORANGE}; color:{WHITE}; border:none;"
                f" border-radius:6px; font-size:12px; font-weight:bold;"
                f" text-align:left; padding:0 12px; }}"
                f"QPushButton:hover {{ background:#d46800; }}")
    return (f"QPushButton {{ background:{WHITE}; color:{ORANGE};"
            f" border:1px solid {ORANGE}; border-radius:6px;"
            f" font-size:12px; text-align:left; padding:0 12px; }}"
            f"QPushButton:hover {{ background:#fff4ec; }}")


def _field_style(active: bool) -> str:
    if active:
        return (f"QLineEdit {{ background:{WHITE}; color:{DARK_TEXT};"
                f" border:2px solid {ACCENT}; border-radius:6px;"
                f" font-size:14px; font-weight:bold; padding:0 10px; }}")
    return (f"QLineEdit {{ background:{WHITE}; color:{DARK_TEXT};"
            f" border:1px solid {BORDER}; border-radius:6px;"
            f" font-size:14px; padding:0 10px; }}"
            f"QLineEdit:focus {{ border:2px solid {ACCENT}; }}")


def _oa_field_style(active: bool) -> str:
    if active:
        return (f"QLineEdit {{ background:{WHITE}; color:{ORANGE};"
                f" border:2px solid {ORANGE}; border-radius:6px;"
                f" font-size:14px; font-weight:bold; padding:0 10px; }}")
    return (f"QLineEdit {{ background:{WHITE}; color:{ORANGE};"
            f" border:1px solid {ORANGE}; border-radius:6px;"
            f" font-size:14px; padding:0 10px; }}"
            f"QLineEdit:focus {{ border:2px solid {ORANGE}; }}")


def _numpad_btn(text, kind="digit"):
    btn = QPushButton(text)
    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFocusPolicy(Qt.NoFocus)
    styles = {
        "digit": (WHITE, LIGHT, DARK_TEXT),
        "quick": (NAVY_3, NAVY_2, WHITE),
        "del": (NAVY_2, NAVY_3, WHITE),
        "clear": (DANGER, DANGER_H, WHITE),
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
# PAYMENT DIALOG
# =============================================================================

class PaymentDialog(QDialog):
    _OA_LABEL = "On Account"

    def __init__(self, parent=None, total: float = 0.0, customer: dict | None = None,
                 items: list = None, cashier_id: int = None, cashier_name: str = "",
                 subtotal: float = None, total_vat: float = 0.0, discount_amount: float = 0.0,
                 shift_id: int = None):
        super().__init__(parent)

        _debug_print("=" * 80)
        _debug_print("🚀 PaymentDialog.__init__ START")
        _debug_print(f"  total={total}")
        _debug_print(f"  customer={customer.get('customer_name') if customer else None}")
        _debug_print(f"  items count={len(items) if items else 0}")
        _debug_print(f"  cashier_id={cashier_id}")
        _debug_print(f"  shift_id={shift_id}")

        self.total = total
        self.items = items or []
        self.cashier_id = cashier_id
        self.cashier_name = cashier_name
        self.subtotal = subtotal
        self.total_vat = total_vat
        self.discount_amount = discount_amount
        self.shift_id = shift_id

        self._processing_save = False

        self.accepted_method = ""
        self.accepted_tendered = 0.0
        self.accepted_change = 0.0
        self.accepted_currency = "USD"
        self.accepted_splits = []
        self.accepted_customer = None
        self.accepted_company = None
        self.accepted_company_name = ""
        self.accepted_is_credit = False
        self.accepted_sale_id = None
        self.accepted_sale = None

        self._customer = customer or _get_default_customer()
        self._company = _get_default_company()
        self._local_rate = _get_local_rate

        co_name = self._company.get("name", "") if self._company else ""
        _debug_print(f"  Company name: {co_name}")
        self._methods = _load_payment_methods(co_name)

        self._credit_sales_allowed = False
        try:
            from models.company_defaults import get_defaults as _gd
            _defs = _gd() or {}
            self._credit_sales_allowed = str(_defs.get("allow_credit_sales", "0")).strip() == "1"
            _debug_print(f"  Credit sales allowed: {self._credit_sales_allowed}")
        except Exception:
            pass

        self._method_rows = {}
        self._active_method = self._methods[0]["label"] if self._methods else ""

        self._print_btn = None

        self.setWindowTitle("Payment")
        self.setMinimumSize(860, 560)
        self.setModal(True)
        self.setWindowState(Qt.WindowMaximized)

        self._build_ui()
        if self._active_method:
            self._activate_method(self._active_method)

        _debug_print("✅ PaymentDialog.__init__ END")
        _debug_print("=" * 80)

    # =========================================================================
    # Build UI
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

        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{WHITE}; border-bottom:2px solid {BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(28, 0, 28, 0)

        title = QLabel("Payment")
        title.setStyleSheet(
            f"color:{NAVY}; font-size:17px; font-weight:bold; background:transparent;")
        zwg_rate = _get_local_rate("USD", "ZWG")
        rate_pill = QLabel(f"1 USD = {zwg_rate:,.2f} ZWG")
        rate_pill.setStyleSheet(
            f"color:{MUTED}; font-size:10px; background:{LIGHT};"
            f" border-radius:4px; padding:2px 8px;")

        hint = QLabel("Enter to confirm  ·  Esc to cancel")
        hint.setStyleSheet(f"color:{MUTED}; font-size:10px; background:transparent;")
        hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        hl.addWidget(title)
        hl.addSpacing(12)
        hl.addWidget(rate_pill)
        hl.addStretch()
        hl.addWidget(hint)
        outer.addWidget(hdr)

        outer_h = QHBoxLayout()
        outer_h.setContentsMargins(0, 0, 0, 0)
        outer_h.setSpacing(0)

        center = QWidget()
        center.setStyleSheet(f"background:{OFF_WHITE};")
        center.setMaximumWidth(1200)
        center_v = QVBoxLayout(center)
        center_v.setContentsMargins(32, 24, 32, 24)
        center_v.setSpacing(0)

        content = QHBoxLayout()
        content.setSpacing(28)

        content.addLayout(self._build_left(), stretch=5)

        vline = QFrame()
        vline.setFrameShape(QFrame.VLine)
        vline.setStyleSheet(f"background:{BORDER}; border:none;")
        vline.setFixedWidth(1)
        content.addWidget(vline)

        content.addLayout(self._build_right(), stretch=4)
        center_v.addLayout(content)

        outer_h.addStretch(1)
        outer_h.addWidget(center, stretch=10)
        outer_h.addStretch(1)

        wrap = QWidget()
        wrap.setStyleSheet(f"background:{OFF_WHITE};")
        wrap.setLayout(outer_h)
        outer.addWidget(wrap, stretch=1)

    def _build_left(self):
        vbox = QVBoxLayout()
        vbox.setSpacing(0)
        vbox.setContentsMargins(0, 0, 0, 0)

        cards = QHBoxLayout()
        cards.setSpacing(10)

        due_card = QFrame()
        due_card.setFixedHeight(72)
        due_card.setStyleSheet(
            f"QFrame {{ background:{WHITE}; border:2px solid {BORDER}; border-radius:8px; }}")
        dcl = QVBoxLayout(due_card)
        dcl.setContentsMargins(14, 6, 14, 6)
        dcl.setSpacing(1)
        cap_due = QLabel("DUE")
        cap_due.setStyleSheet(
            f"color:{MUTED}; font-size:9px; font-weight:bold;"
            f" letter-spacing:1.1px; background:transparent;")
        cap_due.setAlignment(Qt.AlignCenter)
        due_usd = QLabel(f"USD  {self.total:.2f}")
        due_usd.setStyleSheet(
            f"color:{DARK_TEXT}; font-size:18px; font-weight:bold;"
            f" font-family:'Courier New',monospace; background:transparent;")
        due_usd.setAlignment(Qt.AlignCenter)
        dcl.addWidget(cap_due)
        dcl.addWidget(due_usd)
        cards.addWidget(due_card, 1)

        chg_card = QFrame()
        chg_card.setFixedHeight(72)
        chg_card.setStyleSheet(
            f"QFrame {{ background:{WHITE}; border:2px solid {BORDER}; border-radius:8px; }}")
        self._chg_card = chg_card
        ccl = QVBoxLayout(chg_card)
        ccl.setContentsMargins(14, 6, 14, 6)
        ccl.setSpacing(1)
        cap_chg = QLabel("CHANGE")
        cap_chg.setStyleSheet(
            f"color:{MUTED}; font-size:9px; font-weight:bold;"
            f" letter-spacing:1.1px; background:transparent;")
        cap_chg.setAlignment(Qt.AlignCenter)
        self._chg_usd_lbl = QLabel("USD  0.00")
        self._chg_usd_lbl.setStyleSheet(
            f"color:{DARK_TEXT}; font-size:18px; font-weight:bold;"
            f" font-family:'Courier New',monospace; background:transparent;")
        self._chg_usd_lbl.setAlignment(Qt.AlignCenter)
        ccl.addWidget(cap_chg)
        ccl.addWidget(self._chg_usd_lbl)
        cards.addWidget(chg_card, 1)

        vbox.addLayout(cards)
        vbox.addSpacing(6)
        vbox.addWidget(_hr())
        vbox.addSpacing(4)

        ch = QWidget()
        ch.setFixedHeight(18)
        ch.setStyleSheet("background:transparent;")
        chl = QHBoxLayout(ch)
        chl.setContentsMargins(0, 0, 0, 0)
        chl.setSpacing(8)
        for txt, st, align in [
            ("MODE OF PAYMENT", 4, Qt.AlignLeft),
            ("CCY", 1, Qt.AlignCenter),
            ("PAID", 3, Qt.AlignRight),
            ("AMOUNT DUE", 4, Qt.AlignRight),
        ]:
            l = QLabel(txt)
            l.setStyleSheet(
                f"color:{MUTED}; font-size:9px; font-weight:bold;"
                f" letter-spacing:0.7px; background:transparent;")
            l.setAlignment(align)
            chl.addWidget(l, st)
        vbox.addWidget(ch)
        vbox.addSpacing(2)

        validator = QDoubleValidator(0.0, 999999.99, 2)
        validator.setLocale(QLocale(QLocale.English))

        def _make_row(label, curr, is_oa=False):
            rw = QWidget()
            rw.setFixedHeight(30)
            rw.setStyleSheet("background:transparent;")
            rl = QHBoxLayout(rw)
            rl.setContentsMargins(0, 1, 0, 1)
            rl.setSpacing(6)

            mb = QPushButton(f"  {label}")
            mb.setFixedHeight(26)
            mb.setCursor(Qt.PointingHandCursor)
            mb.setFocusPolicy(Qt.NoFocus)
            mb.setStyleSheet(_oa_btn_style(False) if is_oa else _method_btn_style(False))
            mb.clicked.connect(lambda _, m=label: self._activate_method(m))

            cb = QLabel(curr)
            cb.setFixedHeight(26)
            cb.setFixedWidth(46)
            cb.setAlignment(Qt.AlignCenter)
            if is_oa:
                cb.setStyleSheet(
                    f"background:#fff4ec; color:{ORANGE}; border:1px solid {ORANGE};"
                    f" border-radius:5px; font-size:10px; font-weight:bold;")
            else:
                cb.setStyleSheet(
                    f"background:{LIGHT}; color:{ACCENT}; border:1px solid {BORDER};"
                    f" border-radius:5px; font-size:10px; font-weight:bold;")

            ae = QLineEdit()
            ae.setFixedHeight(26)
            ae.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            ae.setValidator(validator)
            ae.setStyleSheet(_oa_field_style(False) if is_oa else _field_style(False))
            ae.focusInEvent = lambda e, m=label, orig=ae.focusInEvent: (
                self._activate_method(m, focus_field=False), orig(e))
            ae.textChanged.connect(lambda _, m=label: self._on_text_changed(m))

            due = QLabel("—")
            due.setFixedHeight(26)
            due.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            due.setStyleSheet(
                f"color:{DARK_TEXT}; font-size:11px; font-weight:bold;"
                f" background:{WHITE}; border:1px solid {BORDER};"
                f" border-radius:5px; padding:0 8px;")

            rl.addWidget(mb, 4)
            rl.addWidget(cb, 1)
            rl.addWidget(ae, 3)
            rl.addWidget(due, 4)

            self._method_rows[label] = (mb, ae, due)
            return rw

        for method in self._methods:
            vbox.addWidget(_make_row(method["label"], method["currency"], is_oa=False))

        if self._credit_sales_allowed:
            vbox.addSpacing(4)
            vbox.addWidget(_hr())
            vbox.addSpacing(4)
            vbox.addWidget(_make_row(self._OA_LABEL, "USD", is_oa=True))

        vbox.addStretch(1)
        return vbox

    def _build_right(self):
        vbox = QVBoxLayout()
        vbox.setSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(6)

        bback = _numpad_btn("⌫", "del")
        bback.clicked.connect(self._numpad_back)
        grid.addWidget(bback, 0, 0)

        bclr = _numpad_btn("Clear", "clear")
        bclr.clicked.connect(self._numpad_clear)
        grid.addWidget(bclr, 0, 1)

        bcan = _numpad_btn("Cancel", "clear")
        bcan.clicked.connect(self.reject)
        grid.addWidget(bcan, 0, 2, 1, 2)

        digit_rows = [["7", "8", "9"], ["4", "5", "6"], ["1", "2", "3"]]
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
        vbox.addWidget(_hr())

        brow = QHBoxLayout()
        brow.setSpacing(8)
        self._print_btn = _action_btn("🖨  Print  (F2)", NAVY_2, NAVY_3, height=52)
        self._print_btn.clicked.connect(self._save)
        self._print_btn.setEnabled(False)
        brow.addWidget(self._print_btn)
        vbox.addLayout(brow, stretch=1)

        return vbox

    def _activate_method(self, label: str, focus_field: bool = True):
        self._active_method = label
        is_oa = label == self._OA_LABEL
        for m, (mb, ae, _) in self._method_rows.items():
            m_is_oa = m == self._OA_LABEL
            active = m == label
            mb.setStyleSheet(_oa_btn_style(active) if m_is_oa else _method_btn_style(active))
            ae.setStyleSheet(_oa_field_style(active) if m_is_oa else _field_style(active))
        if focus_field and label in self._method_rows:
            ae = self._method_rows[label][1]
            ae.setFocus()
            ae.selectAll()

    def _active_field(self) -> QLineEdit:
        if self._active_method in self._method_rows:
            return self._method_rows[self._active_method][1]
        return next(iter(self._method_rows.values()))[1]

    def _method_info(self, label: str) -> tuple[str, float, str]:
        if label == self._OA_LABEL:
            return "USD", 1.0, ""
        for m in self._methods:
            if m["label"] == label:
                curr = m["currency"]
                gl_acct = m.get("gl_account", "")
                if curr.upper() == "USD":
                    return curr, 1.0, gl_acct
                r = _get_local_rate(curr, "USD")
                return curr, (r if r > 0 else 1.0), gl_acct
        return "USD", 1.0, ""

    def _numpad_press(self, key: str):
        if key in ("±", "+/-"):
            return
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
        curr, usd_per_unit, _ = self._method_info(self._active_method)
        if curr.upper() != "USD" and usd_per_unit > 0:
            native = amt / usd_per_unit
            self._active_field().setText(f"{native:.2f}")
        else:
            self._active_field().setText(f"{amt:.2f}")

    def _get_paid_usd(self, label: str) -> float:
        if label not in self._method_rows:
            return 0.0
        _, ae, _ = self._method_rows[label]
        try:
            val = float(ae.text() or "0")
        except ValueError:
            val = 0.0
        _, rate, _ = self._method_info(label)
        result = val * rate
        return result

    def _get_paid_native(self, label: str) -> float:
        if label not in self._method_rows:
            return 0.0
        _, ae, _ = self._method_rows[label]
        try:
            return float(ae.text() or "0")
        except ValueError:
            return 0.0

    def _on_text_changed(self, _label: str = ""):
        paid_usd = sum(self._get_paid_usd(m) for m in self._method_rows)
        rem_usd = max(self.total - paid_usd, 0.0)
        chg_usd = max(paid_usd - self.total, 0.0)
        settled = rem_usd <= 0.005

        self._chg_usd_lbl.setText(f"USD  {chg_usd:.2f}")
        if chg_usd > 0.005:
            self._chg_usd_lbl.setStyleSheet(
                f"color:{SUCCESS}; font-size:18px; font-weight:bold;"
                f" font-family:'Courier New',monospace; background:transparent;")
            self._chg_card.setStyleSheet(
                f"QFrame {{ background:{WHITE}; border:2px solid {SUCCESS}; border-radius:8px; }}")
        else:
            self._chg_usd_lbl.setStyleSheet(
                f"color:{DARK_TEXT}; font-size:18px; font-weight:bold;"
                f" font-family:'Courier New',monospace; background:transparent;")
            self._chg_card.setStyleSheet(
                f"QFrame {{ background:{WHITE}; border:2px solid {BORDER}; border-radius:8px; }}")

        for label in self._method_rows:
            _, _, due_lbl = self._method_rows[label]
            fg = SUCCESS if settled else DARK_TEXT
            curr, usd_per_unit, _ = self._method_info(label)
            if curr.upper() == "USD":
                text = f"USD  {rem_usd:.2f}"
            else:
                if usd_per_unit > 0:
                    native = rem_usd / usd_per_unit
                else:
                    rate_usd_to_native = _get_local_rate("USD", curr)
                    native = rem_usd * rate_usd_to_native
                text = f"{curr}  {native:,.2f}"
            due_lbl.setText(text)
            due_lbl.setTextFormat(Qt.PlainText)
            due_lbl.setStyleSheet(
                f"color:{fg}; font-size:11px; font-weight:bold;"
                f" background:{WHITE}; border:1px solid {BORDER};"
                f" border-radius:6px; padding:0 10px;")

        if self._print_btn is not None:
            self._print_btn.setEnabled(settled)

    def _get_tendered(self) -> float:
        return sum(self._get_paid_usd(m) for m in self._method_rows)

    def _generate_transaction_hash(self) -> str:
        _debug_print("_generate_transaction_hash()")
        simplified_items = []
        for item in self.items:
            simplified_items.append({
                "part_no": item.get("part_no", ""),
                "product_name": item.get("product_name", ""),
                "qty": float(item.get("qty", 0)),
                "price": float(item.get("price", 0)),
                "total": float(item.get("total", 0))
            })

        simplified_items.sort(key=lambda x: x.get("part_no", ""))

        hash_data = {
            "total": round(self.total, 2),
            "items": simplified_items,
            "customer_id": self._customer.get("id", "") if self._customer else "",
            "cashier_id": self.cashier_id,
            "timestamp": int(time.time() / 10)
        }

        hash_string = json.dumps(hash_data, sort_keys=True)
        result = hashlib.md5(hash_string.encode()).hexdigest()
        _debug_print(f"  Generated hash: {result[:16]}...")
        return result

    def _check_duplicate_transaction(self, transaction_hash: str) -> bool:
        _debug_print(f"_check_duplicate_transaction({transaction_hash[:16]}...)")
        try:
            from models.sale import check_recent_transaction_by_hash
            is_duplicate = check_recent_transaction_by_hash(transaction_hash, seconds=10)
            _debug_print(f"  Is duplicate: {is_duplicate}")
            return is_duplicate
        except Exception as e:
            _debug_print(f"  Error checking duplicate: {e}", "WARNING")
            return False

    def _save(self):
        """Save the sale with duplicate prevention."""
        
        _debug_print("=" * 80)
        _debug_print("💾 _save() START")
        _debug_print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if self._processing_save:
            _debug_print("Save already in progress, ignoring duplicate call", "WARNING")
            return
        
        paid_usd = sum(self._get_paid_usd(m) for m in self._method_rows)
        on_account_amount = self._get_paid_usd(self._OA_LABEL)
        
        _debug_print(f"💰 Total due: ${self.total:.2f} USD")
        _debug_print(f"💰 Total paid: ${paid_usd:.2f} USD")
        _debug_print(f"💰 On account amount: ${on_account_amount:.2f} USD")

        # Check for ridiculous overpayment (more than 2x the total)
        if paid_usd > self.total * 2 and self.total > 0:
            _debug_print(f"⚠️ WARNING: Overpayment detected! Paid ${paid_usd:.2f} but due ${self.total:.2f} ({(paid_usd/self.total)*100:.1f}% of due)", "WARNING")
            reply = QMessageBox.question(
                self, 
                "Excessive Overpayment",
                f"You are paying ${paid_usd:.2f} but the total due is only ${self.total:.2f}.\n\n"
                f"This is {(paid_usd/self.total)*100:.1f}% of the due amount.\n\n"
                f"Did you enter the amounts correctly in the wrong currency?\n\n"
                f"Click Yes to continue anyway, No to go back and correct.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                self._processing_save = False
                return

        if paid_usd <= 0:
            _debug_print("No amount entered", "WARNING")
            QMessageBox.warning(self, "No Amount", "Please enter an amount to proceed.")
            self._active_field().setFocus()
            return

        rem = self.total - paid_usd
        if rem > 0.005:
            _debug_print(f"Insufficient amount: ${rem:.2f} still due", "WARNING")
            QMessageBox.warning(
                self, "Insufficient Amount",
                f"Amount still due:  USD  {rem:.2f}\n"
                "Please enter the full amount.")
            self._active_field().setFocus()
            self._active_field().selectAll()
            return

        transaction_hash = self._generate_transaction_hash()
        
        if self._check_duplicate_transaction(transaction_hash):
            _debug_print("Duplicate transaction detected", "WARNING")
            QMessageBox.warning(
                self,
                "Duplicate Transaction Detected",
                "This transaction appears to have been already processed.\n"
                "Please check if the invoice was already created."
            )
            return
        
        self._processing_save = True
        
        if self._print_btn:
            self._print_btn.setEnabled(False)
            self._print_btn.setText("Processing...")
        
        try:
            # =================================================================
            # FORCE SALE CURRENCY TO USD - CRITICAL FIX!
            # =================================================================
            active_method_currency, _, _ = self._method_info(self._active_method)
            curr = "USD"  # Force USD as sale currency
            _debug_print(f"💰 Active method currency was: {active_method_currency}")
            _debug_print(f"💰 FORCING sale currency to: {curr} (company base currency)")
            _debug_print(f"💰 Sale total USD: ${self.total:.2f}")

            # =================================================================
            # BUILD SPLITS - TRACK EVERY PENNY
            # =================================================================
            _debug_print("-" * 60)
            _debug_print("📊 BUILDING SPLITS FROM PAYMENT METHODS")
            splits = []
            total_split_usd = 0.0
            total_zwd_collected = 0.0
            total_usd_collected = 0.0
            
            for label in self._method_rows:
                amt_usd = self._get_paid_usd(label)
                amt_native = self._get_paid_native(label)
                curr_label, rate, gl_acct = self._method_info(label)
                
                _debug_print(f"  Method: {label}")
                _debug_print(f"    Currency: {curr_label}")
                _debug_print(f"    Amount USD: ${amt_usd:.2f}")
                _debug_print(f"    Amount Native: {amt_native:.2f}")
                _debug_print(f"    Exchange Rate: {rate}")
                _debug_print(f"    GL Account: {gl_acct}")
                
                if amt_usd > 0.005:
                    is_oa = label == self._OA_LABEL
                    mop_name_for_split = next(
                        (m.get("mop_name", m["label"]) for m in self._methods if m["label"] == label),
                        label
                    )
                    split_data = {
                        "method": mop_name_for_split,
                        "base_value": amt_usd,
                        "paid_amount": amt_native,
                        "exchange_rate": rate,
                        "currency": curr_label,
                        "is_credit": is_oa,
                    }
                    if not is_oa:
                        if gl_acct:
                            split_data["gl_account"] = gl_acct
                            split_data["paid_to"] = gl_acct
                    
                    if is_oa:
                        split_data["on_account"] = True
                        _debug_print(f"    🔴 ON ACCOUNT - No payment entry will be created")
                    else:
                        if curr_label in ("ZWD", "ZWG"):
                            total_zwd_collected += amt_native
                        else:
                            total_usd_collected += amt_native
                    
                    splits.append(split_data)
                    total_split_usd += amt_usd
                    _debug_print(f"    ✅ Added to splits")
                else:
                    _debug_print(f"    ⏭️ Skipping (amount <= 0.005)")
            
            _debug_print(f"📊 Total splits built: {len(splits)}")
            _debug_print(f"📊 Total USD from splits: ${total_split_usd:.2f}")
            _debug_print(f"📊 Total ZWD collected: {total_zwd_collected:.2f} ZWD")
            _debug_print(f"📊 Total USD collected from USD methods: ${total_usd_collected:.2f}")
            
            # Verify split total matches sale total
            if abs(total_split_usd - self.total) > 0.01:
                _debug_print(f"⚠️ WARNING: Split total (${total_split_usd:.2f}) does not match sale total (${self.total:.2f})", "WARNING")
            
            _debug_print("-" * 60)

            if splits:
                primary = next((s for s in splits if not s.get("on_account")), splits[0])
                accepted_meth = primary["method"] if len(splits) == 1 else "SPLIT"
            else:
                accepted_meth = self._active_method

            active_rate = self._method_info(self._active_method)[1] or 1.0
            self.accepted_method = accepted_meth
            self.accepted_tendered = self._get_paid_native(self._active_method)
            self.accepted_change = max(self._get_paid_native(self._active_method) - (self.total * active_rate), 0.0)
            self.accepted_currency = curr
            self.accepted_splits = splits
            self.accepted_customer = self._customer
            self.accepted_company = self._company
            self.accepted_company_name = self._company.get("name", "") if self._company else ""
            self.accepted_is_credit = on_account_amount > 0.005
            
            _debug_print(f"Accepted method: {accepted_meth}")
            _debug_print(f"Is credit sale: {self.accepted_is_credit}")
            
            # =================================================================
            # CREATE SALE IN DATABASE
            # =================================================================
            from models.sale import create_sale
            from database.db import get_connection
            
            if not self.items or len(self.items) == 0:
                _debug_print("ERROR: No items to save!", "ERROR")
                QMessageBox.warning(self, "No Items", "Cannot create sale with no items.")
                return
            
            sale_items = []
            _debug_print(f"📦 Processing {len(self.items)} items for sale:")
            for idx, item in enumerate(self.items):
                sale_item = {
                    "product_id": item.get("product_id"),
                    "part_no": str(item.get("part_no", "")),
                    "product_name": str(item.get("product_name", "")),
                    "qty": float(item.get("qty", 1)),
                    "price": float(item.get("price", 0)),
                    "discount": float(item.get("discount", 0)),
                    "tax": str(item.get("tax", "")),
                    "total": float(item.get("total", 0)),
                    "tax_type": str(item.get("tax_type", "")),
                    "tax_rate": float(item.get("tax_rate", 0)),
                    "tax_amount": float(item.get("tax_amount", 0)),
                    "remarks": str(item.get("remarks", "")),
                }
                sale_items.append(sale_item)
                _debug_print(f"  Item {idx+1}: {sale_item['product_name']} - qty: {sale_item['qty']} - total: ${sale_item['total']:.2f}")
            
            _debug_print("🏪 Calling create_sale with currency=" + curr)
            sale = create_sale(
                items=sale_items,
                total=self.total,
                tendered=self._get_paid_native(self._active_method),
                method=accepted_meth,
                cashier_id=self.cashier_id,
                cashier_name=self.cashier_name,
                customer_name=self._customer.get("customer_name", "") if self._customer else "",
                customer_contact=self._customer.get("mobile", "") if self._customer else "",
                company_name=self._company.get("name", "") if self._company else "",
                kot="",
                currency=curr,  # ← FORCED TO "USD"
                subtotal=self.subtotal,
                total_vat=self.total_vat,
                discount_amount=self.discount_amount,
                receipt_type="Invoice",
                footer="",
                change_amount=self.accepted_change,
                is_on_account=self.accepted_is_credit,
                skip_stock=False,
                skip_print=False,
                shift_id=self.shift_id,
                idempotency_key=transaction_hash,
            )
            
            if not sale:
                _debug_print("ERROR: Sale creation failed", "ERROR")
                QMessageBox.critical(self, "Error", "Failed to create sale. Please try again.")
                return
            
            self.accepted_sale_id = sale.get("id")
            self.accepted_sale = sale
            _debug_print(f"✅ Sale created with ID: {self.accepted_sale_id}")
            _debug_print(f"✅ Invoice number: {sale.get('invoice_no', 'N/A')}")
            _debug_print(f"✅ Sale currency from DB: {sale.get('currency', 'N/A')}")
            _debug_print(f"✅ Sale total from DB: {sale.get('total', 'N/A')}")
            
            try:
                from models.sale import record_transaction_hash
                record_transaction_hash(transaction_hash, self.accepted_sale_id)
                _debug_print("✅ Transaction hash recorded")
            except Exception as e:
                _debug_print(f"Could not record transaction hash: {e}", "WARNING")
            
            # =================================================================
            # CREATE PAYMENT ENTRIES
            # =================================================================
            _debug_print("-" * 60)
            _debug_print("💳 CREATING PAYMENT ENTRIES")
            _debug_print(f"Total splits received: {len(splits)}")
            
            # Log each split's details
            for idx, sp in enumerate(splits):
                _debug_print(f"  Split {idx+1}: {sp.get('method')}")
                _debug_print(f"    Amount USD: ${sp.get('base_value', 0):.2f}")
                _debug_print(f"    Amount Native: {sp.get('paid_amount', 0):.2f}")
                _debug_print(f"    Currency: {sp.get('currency')}")
                _debug_print(f"    GL Account: {sp.get('gl_account', 'N/A')}")
                _debug_print(f"    On Account: {sp.get('on_account', False)}")
            
            try:
                from services.payment_entry_service import create_split_payment_entries, create_payment_entry
                
                # Filter out on-account splits (they don't get payment entries)
                real_splits = [s for s in splits if not s.get("on_account", False) and s.get("base_value", 0) > 0.005]
                
                _debug_print(f"🎯 Real payment splits (excluding On Account): {len(real_splits)}")
                for idx, sp in enumerate(real_splits):
                    _debug_print(f"  Real split {idx+1}: {sp.get('method')} - ${sp.get('base_value', 0):.2f} USD - GL: {sp.get('gl_account', 'N/A')}")
                
                if len(real_splits) > 1:
                    _debug_print(f"🔀 Calling create_split_payment_entries with {len(real_splits)} splits")
                    pe_ids = create_split_payment_entries(sale, real_splits)
                    _debug_print(f"✅ Created {len(pe_ids)} split payment entries: {pe_ids}")
                    
                    if len(pe_ids) < len(real_splits):
                        _debug_print(f"⚠️ WARNING: Only created {len(pe_ids)} out of {len(real_splits)} payment entries", "WARNING")
                        
                elif len(real_splits) == 1:
                    _debug_print(f"🔂 Calling create_payment_entry for single payment method")
                    single_split = real_splits[0]
                    sale_copy = dict(sale)
                    sale_copy["method"] = single_split.get("method")
                    sale_copy["gl_account"] = single_split.get("gl_account")
                    sale_copy["paid_amount"] = single_split.get("paid_amount")
                    sale_copy["currency"] = single_split.get("currency")
                    sale_copy["exchange_rate"] = single_split.get("exchange_rate")
                    _debug_print(f"  Single payment: {single_split.get('method')}")
                    _debug_print(f"    Amount: {single_split.get('paid_amount')} {single_split.get('currency')}")
                    pe_id = create_payment_entry(sale_copy)
                    _debug_print(f"✅ Created payment entry ID: {pe_id}")
                else:
                    _debug_print("⚠️ No real payment splits to create entries for", "WARNING")
                    
            except Exception as e:
                _debug_print(f"❌ ERROR creating payment entries: {e}", "ERROR")
                traceback.print_exc()
            
            _debug_print("-" * 60)
            
            # =================================================================
            # VERIFY ITEMS WERE SAVED
            # =================================================================
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM sale_items WHERE sale_id = ?", (self.accepted_sale_id,))
            item_count = cursor.fetchone()[0]
            _debug_print(f"📦 Items found in sale_items: {item_count}")
            
            if item_count == 0:
                _debug_print(f"⚠️ No items found! Inserting {len(sale_items)} items directly...", "WARNING")
                
                for item in sale_items:
                    cursor.execute("""
                        INSERT INTO sale_items (
                            sale_id, part_no, product_name, qty, price,
                            discount, tax, total, tax_type, tax_rate, tax_amount, remarks
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        self.accepted_sale_id,
                        item.get("part_no", ""),
                        item.get("product_name", ""),
                        item.get("qty", 1),
                        item.get("price", 0),
                        item.get("discount", 0),
                        item.get("tax", ""),
                        item.get("total", 0),
                        item.get("tax_type", ""),
                        item.get("tax_rate", 0),
                        item.get("tax_amount", 0),
                        item.get("remarks", ""),
                    ))
                
                conn.commit()
                
                cursor.execute("SELECT COUNT(*) FROM sale_items WHERE sale_id = ?", (self.accepted_sale_id,))
                new_count = cursor.fetchone()[0]
                _debug_print(f"After direct insert: {new_count} items in sale_items")
                
                if new_count == 0:
                    _debug_print("❌ CRITICAL: Still no items after direct insert!", "ERROR")
                    QMessageBox.critical(self, "Database Error", 
                        "Failed to save sale items. Please check the database connection.")
                    return
            
            conn.close()
            
            # =================================================================
            # FINAL SUMMARY
            # =================================================================
            _debug_print("-" * 60)
            _debug_print("📋 FINAL TRANSACTION SUMMARY")
            _debug_print(f"  Sale ID: {self.accepted_sale_id}")
            _debug_print(f"  Sale Currency: {curr}")
            _debug_print(f"  Total: ${self.total:.2f}")
            _debug_print(f"  Paid: ${paid_usd:.2f}")
            _debug_print(f"  Change: ${self.accepted_change:.2f}")
            _debug_print(f"  Method: {accepted_meth}")
            _debug_print(f"  Splits: {len(splits)}")
            for idx, sp in enumerate(splits):
                status = "✅ PE Created" if not sp.get("on_account") else "⏭️ No PE (On Account)"
                _debug_print(f"    {idx+1}. {sp.get('method')}: ${sp.get('base_value', 0):.2f} - {status}")
            _debug_print("-" * 60)
            
            _debug_print("✅ Sale completed successfully, accepting dialog", "SUCCESS")
            self.accept()
            
        except Exception as e:
            _debug_print(f"❌ Error creating sale: {e}", "ERROR")
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to create sale: {e}")
        finally:
            self._processing_save = False
            if self._print_btn:
                self._print_btn.setEnabled(True)
                self._print_btn.setText("🖨  Print  (F2)")
        
        _debug_print("_save() END")
        _debug_print("=" * 80)

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
            dlg = SplitPaymentDialog(self, total=self.total, company=co,
                                     company_currency=co_curr)
            if dlg.exec() == QDialog.Accepted:
                self.accepted_method = "SPLIT"
                self.accepted_tendered = sum(s["base_value"] for s in dlg.splits)
                self.accepted_change = dlg.accepted_change
                self.accepted_currency = dlg.accepted_currency
                self.accepted_splits = dlg.splits
                self.accepted_customer = self._customer
                self.accepted_company = self._company
                self.accepted_company_name = (
                    self._company.get("name", "") if self._company else "")
                self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Split Error", str(e))

    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key_F2:
            if self._get_tendered() >= self.total - 0.005 and self._get_tendered() > 0:
                self._save()
            return
        if k == Qt.Key_F3:
            return
        if k in (Qt.Key_Return, Qt.Key_Enter):
            self._save()
            return
        if k == Qt.Key_Escape:
            self.reject()
            return

        focused = self.focusWidget()
        is_editing = isinstance(focused, QLineEdit) and bool(focused.text())
        if not is_editing:
            idx_map = {
                Qt.Key_1: 0, Qt.Key_2: 1, Qt.Key_3: 2, Qt.Key_4: 3,
                Qt.Key_5: 4, Qt.Key_6: 5, Qt.Key_7: 6, Qt.Key_8: 7, Qt.Key_9: 8,
            }
            if k in idx_map and idx_map[k] < len(self._methods):
                self._activate_method(self._methods[idx_map[k]]["label"])
                return
        super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if self._active_method:
            self._activate_method(self._active_method)
        self._on_text_changed()
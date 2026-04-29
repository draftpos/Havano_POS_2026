# =============================================================================
# views/dialogs/payment_dialog.py  —  POS Payment Dialog
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QFrame, QSizePolicy, QMessageBox,
    QScrollArea,
)
from PySide6.QtCore import Qt, QLocale, QTimer
from PySide6.QtGui  import QDoubleValidator
import qtawesome as qta
import hashlib
import json
import time


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


# =============================================================================
# Data helpers
# =============================================================================

def _get_local_rate(from_currency: str, to_currency: str = "USD") -> float:
    """
    Return the exchange rate from_currency → to_currency.
    Tries the direct rate first; if not stored, tries the inverse pair and
    reciprocals it so that both ZWD→USD and USD→ZWD always resolve.
    """
    if from_currency.upper() == to_currency.upper():
        return 1.0
    try:
        from models.exchange_rate import get_rate
        r = get_rate(from_currency, to_currency)
        if r:
            return float(r)
        # Try the inverse pair and reciprocal it
        inv = get_rate(to_currency, from_currency)
        if inv and float(inv) > 0:
            return 1.0 / float(inv)
    except Exception:
        pass
    return 1.0


def _get_default_customer() -> dict | None:
    try:
        from models.customer import get_all_customers
        for c in get_all_customers():
            if c["customer_name"].strip().lower() in ("walk-in", "default", "walk in"):
                return c
    except Exception:
        pass
    return None


def _get_default_company() -> dict | None:
    try:
        from models.company import get_all_companies
        rows = get_all_companies()
        return rows[0] if rows else None
    except Exception:
        return None


def _load_payment_methods(company: str) -> list[dict]:
    """
    Load payment methods from modes_of_payment table (synced from Frappe).
    Only includes MOPs that have a non-empty gl_account (leaf accounts only —
    group accounts like "Cash In Hand - DC1134" are excluded because Frappe
    rejects them in transactions).

    Returns list of: {label, mop_name, gl_account, currency, rate_to_usd, is_credit}
      label     — display name shown on the button (MOP name, e.g. "Ecocash USD")
      mop_name  — same as label; the Frappe Mode of Payment name to send in PE
      gl_account — the leaf GL account to send as paid_to (e.g. "Ecocash USD - DC1134")
      currency  — account_currency (e.g. "USD", "ZWD")
    On Account is NOT included here — it is added separately as a plain input row.
    """
    result = []
    seen   = set()

    try:
        from database.db import get_connection, fetchall_dicts
        conn = get_connection()
        cur  = conn.cursor()

        # Only pull MOPs with a real gl_account; skip group/parent accounts
        # (group accounts have no account_type row in gl_accounts — they just
        #  appear as parent_account of other rows).
        # ORDER BY display_order first so cashiers can set a preferred order
        # (top row is the default selected method in the payment dialog);
        # fall back to alphabetical for ties / unmigrated rows (all zero).
        cur.execute("""
            SELECT
                m.name            AS mop_name,
                m.gl_account      AS gl_account,
                m.account_currency AS currency,
                COALESCE(m.display_order, 0) AS display_order
            FROM modes_of_payment m
            WHERE m.gl_account IS NOT NULL
              AND m.gl_account <> ''
              AND m.enabled = 1
            ORDER BY display_order, m.name
        """)
        rows = fetchall_dicts(cur)
        conn.close()

        for row in rows:
            mop_name   = (row.get("mop_name")   or "").strip()
            gl_account = (row.get("gl_account") or "").strip()
            curr       = (row.get("currency")   or "USD").upper()

            if not mop_name or not gl_account:
                continue

            # Skip group accounts — they have no account_type in gl_accounts
            # (leaf accounts always have account_type = 'Cash' or 'Bank')
            try:
                from database.db import get_connection as _gc, fetchone_dict as _fd
                _conn = _gc(); _cur = _conn.cursor()
                _cur.execute(
                    "SELECT account_type FROM gl_accounts WHERE name = ?",
                    (gl_account,)
                )
                _row = _fd(_cur)
                _conn.close()
                if _row is not None and (_row.get("account_type") or "").strip() == "":
                    # Group account — skip
                    print(f"  [skip] '{gl_account}' is a group account — excluded from payment methods")
                    continue
            except Exception:
                pass  # If we can't check, allow it through

            key = mop_name.lower()
            if key in seen:
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
                "label":       mop_name,   # shown on button; also used as method name
                "mop_name":    mop_name,   # Frappe MOP name → sent to payment_entry_service
                "gl_account":  gl_account, # leaf GL account → sent as paid_to
                "currency":    curr,
                "rate_to_usd": rate,
                "is_credit":   False,
            })

    except Exception as e:
        print(f"Error loading payment methods from modes_of_payment: {e}")

    print(f"Loaded {len(result)} payment methods from modes_of_payment:")
    for r in result:
        print(f"  - {r['label']} ({r['currency']}) -> GL: {r['gl_account']}")

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
# PAYMENT DIALOG
# =============================================================================

class PaymentDialog(QDialog):
    """
    After accept():
      self.accepted_method       — account label
      self.accepted_tendered     — float (USD)
      self.accepted_change       — float (USD)
      self.accepted_currency     — str
      self.accepted_customer     — dict | None
      self.accepted_company      — dict | None
      self.accepted_company_name — str
      self.accepted_splits       — list
      self.accepted_is_credit    — bool
      self.accepted_sale_id      — int
    """

    _OA_LABEL = "On Account"

    def __init__(self, parent=None, total: float = 0.0, customer: dict | None = None,
                 items: list = None, cashier_id: int = None, cashier_name: str = "",
                 subtotal: float = None, total_vat: float = 0.0, discount_amount: float = 0.0,
                 shift_id: int = None):
        super().__init__(parent)
        self.total             = total
        self.items             = items or []
        self.cashier_id        = cashier_id
        self.cashier_name      = cashier_name
        self.subtotal          = subtotal
        self.total_vat         = total_vat
        self.discount_amount   = discount_amount
        self.shift_id          = shift_id
        
        # ✅ Add processing flag to prevent duplicate saves
        self._processing_save = False
        
        self.accepted_method   = ""
        self.accepted_tendered = 0.0
        self.accepted_change   = 0.0
        self.accepted_currency = "USD"
        self.accepted_splits   = []
        self.accepted_customer = None
        self.accepted_company  = None
        self.accepted_company_name = ""
        self.accepted_is_credit = False
        self.accepted_sale_id   = None

        self._customer = customer or _get_default_customer()
        self._company  = _get_default_company()
        self._local_rate = _get_local_rate

        co_name = self._company.get("name", "") if self._company else ""
        self._methods: list[dict] = _load_payment_methods(co_name)

        self._credit_sales_allowed = False
        try:
            from models.company_defaults import get_defaults as _gd
            _defs = _gd() or {}
            self._credit_sales_allowed = str(_defs.get("allow_credit_sales", "0")).strip() == "1"
        except Exception:
            pass

        self._method_rows: dict[str, tuple] = {}
        self._active_method: str = self._methods[0]["label"] if self._methods else ""

        self._print_btn: QPushButton | None = None

        self.setWindowTitle("Payment")
        self.setMinimumSize(860, 560)
        self.setModal(True)
        self.setWindowState(Qt.WindowMaximized)

        self._build_ui()
        if self._active_method:
            self._activate_method(self._active_method)

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
        hl  = QHBoxLayout(hdr)
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

        content.addLayout(self._build_left(),  stretch=5)

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
            ("CCY",             1, Qt.AlignCenter),
            ("PAID",            3, Qt.AlignRight),
            ("AMOUNT DUE",      4, Qt.AlignRight),
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

            rl.addWidget(mb,  4)
            rl.addWidget(cb,  1)
            rl.addWidget(ae,  3)
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
        vbox.addWidget(_hr())

        brow = QHBoxLayout()
        brow.setSpacing(8)
        self._print_btn = _action_btn("Print  (F2)", NAVY_2, NAVY_3, height=52)
        self._print_btn.setIcon(qta.icon("fa5s.print", color="white"))
        self._print_btn.clicked.connect(self._save)
        self._print_btn.setEnabled(False)
        brow.addWidget(self._print_btn)
        vbox.addLayout(brow, stretch=1)

        return vbox

    # =========================================================================
    # Method management
    # =========================================================================

    def _activate_method(self, label: str, focus_field: bool = True):
        self._active_method = label
        is_oa = label == self._OA_LABEL
        for m, (mb, ae, _) in self._method_rows.items():
            m_is_oa = m == self._OA_LABEL
            active  = m == label
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

    # =========================================================================
    # Numpad
    # =========================================================================

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
        f = self._active_field(); f.setText(f.text()[:-1])

    def _numpad_clear(self):
        self._active_field().clear()

    def _numpad_quick(self, amt: int):
        """
        Insert a quick amount into the active field.
        If the active method is a non-USD currency, convert the USD quick-amount
        to the native equivalent so the cashier sees the right number to enter.
        """
        curr, usd_per_unit, _ = self._method_info(self._active_method)
        if curr.upper() != "USD" and usd_per_unit > 0:
            # usd_per_unit = ZWD→USD rate, e.g. 0.00277
            # native amount = USD amt / rate  (e.g. 10 USD / 0.00277 ≈ 3610 ZWD)
            native = amt / usd_per_unit
            self._active_field().setText(f"{native:.2f}")
        else:
            self._active_field().setText(f"{amt:.2f}")

    # =========================================================================
    # Live totals
    # =========================================================================

    def _get_paid_usd(self, label: str) -> float:
        if label not in self._method_rows:
            return 0.0
        _, ae, _ = self._method_rows[label]
        try:
            val = float(ae.text() or "0")
        except ValueError:
            val = 0.0
        _, rate, _ = self._method_info(label)
        return val * rate

    def _get_paid_native(self, label: str) -> float:
        """Returns the amount exactly as entered by the user, in the account's own currency (no conversion)."""
        if label not in self._method_rows:
            return 0.0
        _, ae, _ = self._method_rows[label]
        try:
            return float(ae.text() or "0")
        except ValueError:
            return 0.0

    def _on_text_changed(self, _label: str = ""):
        paid_usd = sum(self._get_paid_usd(m) for m in self._method_rows)
        rem_usd  = max(self.total - paid_usd, 0.0)
        chg_usd  = max(paid_usd - self.total, 0.0)
        settled  = rem_usd <= 0.005

        # Display change in the *payment's* currency when exactly one
        # method has a non-zero entry — cashiers hand back change in the
        # currency the customer used. Multi-method (split) keeps USD as
        # the common denominator. USD-only single tender → also USD.
        active_methods = [
            m for m in self._method_rows
            if self._get_paid_native(m) > 0.005
        ]
        chg_text = f"USD  {chg_usd:.2f}"
        if len(active_methods) == 1:
            sole = active_methods[0]
            curr, usd_per_unit, _ = self._method_info(sole)
            if curr.upper() != "USD" and usd_per_unit > 0:
                chg_native = max(
                    self._get_paid_native(sole) - (self.total / usd_per_unit),
                    0.0,
                )
                chg_text = f"{curr.upper()}  {chg_native:,.2f}"
        self._chg_usd_lbl.setText(chg_text)

        # Highlight the card whenever ANY change is owed back — derived
        # from the USD figure since chg_native > 0 ↔ chg_usd > 0.
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
                # usd_per_unit = how many USD one native unit buys (e.g. ZWD→USD).
                # To get how many native units are needed, divide remaining USD by that rate.
                if usd_per_unit > 0:
                    native = rem_usd / usd_per_unit
                else:
                    # Fallback: try fetching USD→curr directly (handles inverse-only stored rates)
                    rate_usd_to_native = _get_local_rate("USD", curr)
                    native = rem_usd * rate_usd_to_native
                text = f"{curr}  {native:,.2f}"
            due_lbl.setText(text)
            due_lbl.setTextFormat(Qt.PlainText)
            due_lbl.setStyleSheet(
                f"color:{fg}; font-size:11px; font-weight:bold;"
                f" background:{WHITE}; border:1px solid {BORDER};"
                f" border-radius:6px; padding:0 10px;")

        # Keep Print enabled even when short — _save() shows an
        # "Insufficient Amount" popup so cashier gets a clear message
        # instead of a silently-disabled button.
        if self._print_btn is not None:
            self._print_btn.setEnabled(True)

    def _get_tendered(self) -> float:
        return sum(self._get_paid_usd(m) for m in self._method_rows)

    def _generate_transaction_hash(self) -> str:
        """Generate a unique hash for this transaction to detect duplicates."""
        # Create a simplified representation of items
        simplified_items = []
        for item in self.items:
            simplified_items.append({
                "part_no": item.get("part_no", ""),
                "product_name": item.get("product_name", ""),
                "qty": float(item.get("qty", 0)),
                "price": float(item.get("price", 0)),
                "total": float(item.get("total", 0))
            })
        
        # Sort items to ensure consistent hash
        simplified_items.sort(key=lambda x: x.get("part_no", ""))
        
        # Create hash data
        hash_data = {
            "total": round(self.total, 2),
            "items": simplified_items,
            "customer_id": self._customer.get("id", "") if self._customer else "",
            "cashier_id": self.cashier_id,
            "timestamp": int(time.time() / 10)  # 10-second window
        }
        
        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.md5(hash_string.encode()).hexdigest()

    def _check_duplicate_transaction(self, transaction_hash: str) -> bool:
        """Check if this transaction was already processed."""
        try:
            from models.sale import check_recent_transaction_by_hash
            return check_recent_transaction_by_hash(transaction_hash, seconds=10)
        except Exception as e:
            print(f"[WARNING] Could not check for duplicate: {e}")
            return False

    def _show_big_warning(self, title: str, primary: str, secondary: str = "") -> None:
        """Large, readable warning modal — used for 'Insufficient Amount' /
        'No Amount' at the register. Replaces the tiny default QMessageBox
        so a cashier glancing up sees the blocker at arm's length."""
        dlg = QDialog(self)
        dlg.setWindowTitle(title.title())
        dlg.setModal(True)
        dlg.setWindowFlag(Qt.FramelessWindowHint, False)
        dlg.setFixedSize(600, 340)
        dlg.setStyleSheet(f"QDialog {{ background:{WHITE}; }}")

        root = QVBoxLayout(dlg)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Amber warning band — big & impossible to miss
        band = QWidget()
        band.setFixedHeight(84)
        band.setStyleSheet(f"background:{ORANGE};")
        bl = QVBoxLayout(band)
        bl.setContentsMargins(24, 0, 24, 0)
        bl.setSpacing(0)
        title_lbl = QLabel(title.upper())
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(
            f"color:{WHITE}; font-size:26px; font-weight:900; letter-spacing:2px;"
            f" background:transparent;"
        )
        bl.addWidget(title_lbl)
        root.addWidget(band)

        # Body
        body = QWidget()
        body.setStyleSheet(f"background:{WHITE};")
        bl2 = QVBoxLayout(body)
        bl2.setContentsMargins(28, 26, 28, 22)
        bl2.setSpacing(14)

        primary_lbl = QLabel(primary)
        primary_lbl.setAlignment(Qt.AlignCenter)
        primary_lbl.setWordWrap(True)
        primary_lbl.setStyleSheet(
            f"color:{DANGER}; font-size:28px; font-weight:bold;"
            f" font-family:'Segoe UI',sans-serif; background:transparent;"
        )
        bl2.addWidget(primary_lbl)

        if secondary:
            secondary_lbl = QLabel(secondary)
            secondary_lbl.setAlignment(Qt.AlignCenter)
            secondary_lbl.setWordWrap(True)
            secondary_lbl.setStyleSheet(
                f"color:{DARK_TEXT}; font-size:17px; background:transparent;"
            )
            bl2.addWidget(secondary_lbl)

        bl2.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.setFixedHeight(54)
        ok_btn.setMinimumWidth(220)
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background:{ACCENT}; color:{WHITE};
                border:none; border-radius:8px;
                font-size:18px; font-weight:bold; padding:0 28px;
            }}
            QPushButton:hover {{ background:{ACCENT_H}; }}
            QPushButton:pressed {{ background:{NAVY_3}; }}
        """)
        ok_btn.clicked.connect(dlg.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(ok_btn)
        row.addStretch()
        bl2.addLayout(row)

        root.addWidget(body, 1)

        # Make Enter / Escape both dismiss
        ok_btn.setDefault(True)
        ok_btn.setAutoDefault(True)
        ok_btn.setFocus()

        dlg.exec()

    def _save(self):
        """Save the sale with duplicate prevention."""
        
        # ✅ Prevent multiple simultaneous saves
        if self._processing_save:
            print("[PaymentDialog] Save already in progress, ignoring duplicate call")
            return
        
        paid_usd = sum(self._get_paid_usd(m) for m in self._method_rows)
        on_account_amount = self._get_paid_usd(self._OA_LABEL)

        if paid_usd <= 0:
            self._show_big_warning(
                "NO AMOUNT",
                "Please enter an amount to proceed.",
            )
            self._active_field().setFocus()
            return

        rem = self.total - paid_usd
        if rem > 0.005:
            self._show_big_warning(
                "INSUFFICIENT AMOUNT",
                f"Amount still due:  USD  {rem:,.2f}",
                "Please enter the full amount before printing.",
            )
            self._active_field().setFocus()
            self._active_field().selectAll()
            return

        # ✅ Generate transaction hash for duplicate detection
        transaction_hash = self._generate_transaction_hash()
        
        # ✅ Check for duplicate before proceeding
        if self._check_duplicate_transaction(transaction_hash):
            QMessageBox.warning(
                self,
                "Duplicate Transaction Detected",
                "This transaction appears to have been already processed.\n"
                "Please check if the invoice was already created."
            )
            return
        
        # Set processing flag
        self._processing_save = True
        
        # Disable the print button while processing
        if self._print_btn:
            self._print_btn.setEnabled(False)
            self._print_btn.setText("Processing...")
        
        try:
            curr, _, _ = self._method_info(self._active_method)

            splits = []
            for label in self._method_rows:
                amt_usd    = self._get_paid_usd(label)
                amt_native = self._get_paid_native(label)
                if amt_usd > 0.005:
                    is_oa = label == self._OA_LABEL
                    curr_label, rate, gl_acct = self._method_info(label)
                    # Find the MOP name for this label (same as label since we now
                    # load from modes_of_payment where label == mop_name)
                    mop_name_for_split = next(
                        (m.get("mop_name", m["label"]) for m in self._methods
                         if m["label"] == label),
                        label
                    )
                    split_data = {
                        "method":        mop_name_for_split,  # ← Frappe MOP name
                        "base_value":    amt_usd,
                        "paid_amount":   amt_native,    # ← always USD basis for DB storage
                        "exchange_rate": rate,
                        "currency":      curr_label,       # ← always store as USD in DB
                        "native_currency":  curr_label,   # ← original currency kept for reference
                        "native_amount":    amt_native,   # ← original local amount kept for reference
                        "is_credit":     is_oa,
                    }
                    if not is_oa:
                        if gl_acct:
                            split_data["gl_account"] = gl_acct
                            split_data["paid_to"] = gl_acct
                    if is_oa:
                        split_data["on_account"] = True
                    splits.append(split_data)

            if splits:
                primary = next((s for s in splits if not s.get("on_account")), splits[0])
                accepted_meth = primary["method"] if len(splits) == 1 else "SPLIT"
            else:
                accepted_meth = self._active_method

            # `active_rate` is usd-per-native (see _method_info — for ZWG it
            # might be 0.0667). Converting the USD sale total into the
            # active method's native currency therefore needs DIVISION,
            # not multiplication. The previous `total * rate` flipped the
            # rate direction and produced nonsense change values
            # (e.g. ZWG 200 - 0.667 = 199.33 instead of 200 - 150 = 50).
            active_rate = self._method_info(self._active_method)[1] or 1.0
            self.accepted_method = accepted_meth
            self.accepted_tendered = self._get_paid_native(self._active_method)
            if accepted_meth == "SPLIT":
                _total_splits_usd = sum(s.get("base_value", 0) for s in splits if not s.get("on_account"))
                self.accepted_change = round(max(_total_splits_usd - self.total, 0.0), 4)
            else:
                paid_native  = self._get_paid_native(self._active_method)
                total_native = (self.total / active_rate) if active_rate > 0 else self.total
                self.accepted_change = round(max(paid_native - total_native, 0.0), 4)

            self.accepted_currency = curr
            self.accepted_splits = splits
            self.accepted_customer = self._customer
            self.accepted_company = self._company
            self.accepted_company_name = self._company.get("name", "") if self._company else ""
            self.accepted_is_credit = on_account_amount > 0.005
            
            # ✅ CREATE THE SALE IN DATABASE
            from models.sale import create_sale
            from database.db import get_connection
            
            # VALIDATE items before proceeding
            if not self.items or len(self.items) == 0:
                print(f"[PaymentDialog] ERROR: No items to save!")
                QMessageBox.warning(self, "No Items", "Cannot create sale with no items.")
                return
            
            # Prepare items for sale creation
            sale_items = []
            print(f"[PaymentDialog] Processing {len(self.items)} items for sale")

            # For non-USD single-currency sales, convert price and total to the
            # local currency so sale_items reflect what was actually charged.
            # SPLIT payments always stay in USD (rate = 1.0).
            if accepted_meth == "SPLIT":
                _item_rate = 1.0
                _item_currency = "USD"
            else:
                _item_currency, _rate_to_usd, _ = self._method_info(self._active_method)
                _rate_to_usd = float(_rate_to_usd) if _rate_to_usd else 1.0
                # _method_info returns ZWG->USD (e.g. 0.033).
                # We need USD->ZWG (e.g. 30) to convert USD catalog prices into local currency.
                _item_rate = (1.0 / _rate_to_usd) if _rate_to_usd not in (0.0, 1.0) else 1.0

            _convert = _item_rate != 1.0 and _item_currency.upper() not in ("USD", "US")

            for idx, item in enumerate(self.items):
                raw_price = float(item.get("price", 0))
                raw_total = float(item.get("total", 0))

                sale_item = {
                    "product_id":   item.get("product_id"),
                    "part_no":      str(item.get("part_no",      "")),
                    "product_name": str(item.get("product_name", "")),
                    "qty":          float(item.get("qty", 1)),
                    "price":        round(raw_price * _item_rate, 4) if _convert else raw_price,
                    "discount":     float(item.get("discount",   0)),
                    "tax":          str(item.get("tax",      "")),
                    "total":        round(raw_total * _item_rate, 4) if _convert else raw_total,
                    "tax_type":     str(item.get("tax_type", "")),
                    "tax_rate":     float(item.get("tax_rate",   0)),
                    "tax_amount":   round(float(item.get("tax_amount", 0)) * _item_rate, 4) if _convert else float(item.get("tax_amount", 0)),
                    "remarks":      str(item.get("remarks",  "")),
                }
                sale_items.append(sale_item)
                print(f"   Item {idx+1}: {sale_item['product_name']} qty={sale_item['qty']} "
                      f"price={raw_price}→{sale_item['price']} total={raw_total}→{sale_item['total']} "
                      f"[{_item_currency} rate={_item_rate}]")

            # ✅ Create the sale with idempotency_key
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
                currency="USD" if accepted_meth == "SPLIT" else curr,
                subtotal=self.subtotal,
                total_vat=self.total_vat,
                discount_amount=self.discount_amount,
                receipt_type="Invoice",
                footer="",
                change_amount=self.accepted_change,
                is_on_account=self.accepted_is_credit,
                skip_stock=False,
                skip_print=True,  # main_window prints after fiscal wait — never auto-print here
                shift_id=self.shift_id,
                idempotency_key=transaction_hash,  # ✅ Pass transaction hash
                splits=splits,                     # ✅ Per-method breakdown for receipt Payment Details
            )
            
            # Check if sale was created successfully
            if not sale:
                print("[PaymentDialog] ERROR: Sale creation failed")
                QMessageBox.critical(self, "Error", "Failed to create sale. Please try again.")
                return
            
            # Store the sale ID
            self.accepted_sale_id = sale.get("id")
            self.accepted_sale = sale
            print(f"[PaymentDialog] Sale created with ID: {self.accepted_sale_id}")
            if sale and sale.get("items"):
                from models.sale import print_s
                print(f"[PaymentDialog] Printing kitchen orders for sale {self.accepted_sale_id}")
                print_s(sale)  # This will print kitchen orders without reprinting the receipt
            # ✅ Record the transaction hash in database
            try:
                from models.sale import record_transaction_hash
                record_transaction_hash(transaction_hash, self.accepted_sale_id)
            except Exception as e:
                print(f"[WARNING] Could not record transaction hash: {e}")
                
            # ✅ Create Payment Entries for Syncing
            # FIX: ONLY create payment entries if NOT an On Account payment
            if not self.accepted_is_credit:
                try:
                    # Add necessary details to the sale dict for payment creation
                    sale_copy = dict(sale)
                    sale_copy["method"] = self.accepted_method
                    if splits and isinstance(splits, list) and len(splits) > 0:
                        sale_copy["gl_account"] = splits[0].get("gl_account") or splits[0].get("paid_to", "")
                    
                    if self.accepted_method == "SPLIT":
                        from services.payment_entry_service import create_split_payment_entries
                        create_split_payment_entries(sale_copy, splits, shift_id=self.shift_id)
                        print(f"[PaymentDialog] Created split payment entries for sale {self.accepted_sale_id}")
                    else:
                        from services.payment_entry_service import create_payment_entry
                        create_payment_entry(sale_copy, shift_id=self.shift_id)
                        print(f"[PaymentDialog] Created single payment entry for sale {self.accepted_sale_id}")
                except Exception as e:
                    print(f"[ERROR] Failed to create payment entry records: {e}")
            else:
                print(f"[PaymentDialog] On Account payment - NO payment entry created for sale {self.accepted_sale_id}")
            
            # CRITICAL FIX: Verify items were saved and insert directly if not
            conn = get_connection()
            cursor = conn.cursor()
            
            # Check if items exist
            cursor.execute("SELECT COUNT(*) FROM sale_items WHERE sale_id = ?", (self.accepted_sale_id,))
            item_count = cursor.fetchone()[0]
            print(f"[PaymentDialog] Items found in sale_items: {item_count}")
            
            if item_count == 0:
                print(f"[PaymentDialog] ⚠️ No items found! Inserting {len(sale_items)} items directly...")
                
                # Direct insert of items
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
                
                # Verify again
                cursor.execute("SELECT COUNT(*) FROM sale_items WHERE sale_id = ?", (self.accepted_sale_id,))
                new_count = cursor.fetchone()[0]
                print(f"[PaymentDialog] After direct insert: {new_count} items in sale_items")
                
                if new_count == 0:
                    print(f"[PaymentDialog] ❌ CRITICAL: Still no items after direct insert!")
                    QMessageBox.critical(self, "Database Error", 
                        "Failed to save sale items. Please check the database connection.")
                    return
            
            conn.close()
            
            # Accept the dialog
            self.accept()
            
        except Exception as e:
            print(f"[PaymentDialog] Error creating sale: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to create sale: {e}")
        finally:
            # ✅ Reset processing flag
            self._processing_save = False
            if self._print_btn:
                self._print_btn.setEnabled(True)
                self._print_btn.setText("Print  (F2)")
                self._print_btn.setIcon(qta.icon("fa5s.print", color="white"))

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
                self.accepted_method       = "SPLIT"
                self.accepted_tendered     = sum(s["base_value"] for s in dlg.splits)
                self.accepted_change       = dlg.accepted_change
                self.accepted_currency     = dlg.accepted_currency
                self.accepted_splits       = dlg.splits
                self.accepted_customer     = self._customer
                self.accepted_company      = self._company
                self.accepted_company_name = (
                    self._company.get("name", "") if self._company else "")
                self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Split Error", str(e))

    # =========================================================================
    # Keyboard
    # =========================================================================

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

        # Up/Down arrows cycle through payment methods regardless of focus —
        # arrows don't conflict with numeric entry in QLineEdits.
        if k in (Qt.Key_Up, Qt.Key_Down) and self._methods:
            try:
                cur_idx = next(
                    i for i, m in enumerate(self._methods)
                    if m.get("label") == self._active_method
                )
            except StopIteration:
                cur_idx = 0
            step = -1 if k == Qt.Key_Up else 1
            new_idx = (cur_idx + step) % len(self._methods)
            self._activate_method(self._methods[new_idx]["label"])
            return

        focused = self.focusWidget()
        is_editing = isinstance(focused, QLineEdit) and bool(focused.text())
        if not is_editing:
            idx_map = {
                Qt.Key_1:0, Qt.Key_2:1, Qt.Key_3:2, Qt.Key_4:3,
                Qt.Key_5:4, Qt.Key_6:5, Qt.Key_7:6, Qt.Key_8:7, Qt.Key_9:8,
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
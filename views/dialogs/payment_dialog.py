# =============================================================================
# views/dialogs/payment_dialog.py  —  POS Payment Dialog
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QFrame, QSizePolicy, QMessageBox,
    QScrollArea,
)
from PySide6.QtCore import Qt, QLocale
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

# =============================================================================
# Data helpers
# =============================================================================

def _get_local_rate(from_currency: str, to_currency: str = "USD") -> float:
    """Fetch exchange rate via models.exchange_rate — same source as split payment dialog."""
    if from_currency.upper() == to_currency.upper():
        return 1.0
    try:
        from models.exchange_rate import get_rate
        r = get_rate(from_currency, to_currency)
        return float(r) if r else 1.0
    except Exception:
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
    Pull GL accounts for this company, deduplicated by (account_type, currency).
    Returns list of: {label, currency, rate_to_usd, is_credit}

    #16 — Accounts whose `is_credit` field is truthy in Frappe are included in
    the display list so the cashier can see them, but they are tagged with
    is_credit=True.  _save() checks this flag and skips payment-entry creation
    for those methods.  The UI also shows a small badge so it is visually clear.
    """
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

        # #16 — read the is_credit flag from the Frappe account record.
        # Frappe stores this as 1 / 0 or True / False on the Account doctype.
        is_credit = bool(a.get("is_credit") or a.get("credit_account") or False)

        result.append({
            "label":       a.get("account_name") or a.get("name") or atype,
            "currency":    curr,
            "rate_to_usd": rate,
            "is_credit":   is_credit,   # #16
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


def _field_style(active: bool) -> str:
    if active:
        return (f"QLineEdit {{ background:{WHITE}; color:{DARK_TEXT};"
                f" border:2px solid {ACCENT}; border-radius:6px;"
                f" font-size:14px; font-weight:bold; padding:0 10px; }}")
    return (f"QLineEdit {{ background:{WHITE}; color:{DARK_TEXT};"
            f" border:1px solid {BORDER}; border-radius:6px;"
            f" font-size:14px; padding:0 10px; }}"
            f"QLineEdit:focus {{ border:2px solid {ACCENT}; }}")


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
    """

    def __init__(self, parent=None, total: float = 0.0, customer: dict | None = None):
        super().__init__(parent)
        self.total             = total
        self.accepted_method   = ""
        self.accepted_tendered = 0.0
        self.accepted_change   = 0.0
        self.accepted_currency = "USD"
        self.accepted_splits   = []
        self.accepted_customer = None
        self.accepted_company  = None
        self.accepted_company_name = ""
        self.accepted_is_credit = False   # #16 — True when method is credit-flagged

        self._customer = customer or _get_default_customer()
        self._company  = _get_default_company()
        # Rate fetched live from exchange_rate model — same source as split payment
        self._local_rate = _get_local_rate  # callable: _local_rate(from_ccy, to_ccy)

        co_name = self._company.get("name", "") if self._company else ""
        self._methods: list[dict] = _load_payment_methods(co_name)

        # label -> (QPushButton, QLineEdit, due_QLabel)
        self._method_rows: dict[str, tuple] = {}
        self._active_method: str = self._methods[0]["label"] if self._methods else ""

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

        # ── header ────────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{WHITE}; border-bottom:2px solid {BORDER};")
        hl  = QHBoxLayout(hdr)
        hl.setContentsMargins(28, 0, 28, 0)

        title = QLabel("Payment")
        title.setStyleSheet(
            f"color:{NAVY}; font-size:17px; font-weight:bold; background:transparent;")
        # Rate pill — fetched live from exchange_rate model
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

        # ── centred content wrapper ───────────────────────────────────────────
        # Everything lives inside a fixed-max-width container that is centred.
        # This prevents the two panels from stretching absurdly on wide screens.
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

    # =========================================================================
    # Left panel
    # =========================================================================

    def _build_left(self):
        vbox = QVBoxLayout()
        vbox.setSpacing(10)

        # ── DUE card (static) + CHANGE card (live) ───────────────────────────
        cards = QHBoxLayout()
        cards.setSpacing(10)

        # DUE — static total
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

        # CHANGE — live, shows overpayment (0.00 until paid > total)
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
        vbox.addWidget(_hr())

        # ── column headers ────────────────────────────────────────────────────
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
            ("AMOUNT DUE",      4, Qt.AlignRight),   # label matches per-row due cell
        ]:
            l = QLabel(txt)
            l.setStyleSheet(
                f"color:{MUTED}; font-size:9px; font-weight:bold;"
                f" letter-spacing:0.7px; background:transparent;")
            l.setAlignment(align)
            chl.addWidget(l, st)
        vbox.addWidget(ch)

        # ── scrollable rows ───────────────────────────────────────────────────
        sw = QWidget(); sw.setStyleSheet("background:transparent;")
        sl = QVBoxLayout(sw)
        sl.setSpacing(4)
        sl.setContentsMargins(0, 0, 4, 0)

        validator = QDoubleValidator(0.0, 999999.99, 2)
        validator.setLocale(QLocale(QLocale.English))

        for method in self._methods:
            label     = method["label"]
            curr      = method["currency"]
            is_credit = method.get("is_credit", False)   # #16

            rw = QWidget()
            rw.setFixedHeight(40)
            rw.setStyleSheet("background:transparent;")
            rl = QHBoxLayout(rw)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(8)

            # method button — append "[Credit]" tag so cashier can see it
            display_label = f"  {label}"
            mb = QPushButton(display_label)
            mb.setFixedHeight(32)
            mb.setCursor(Qt.PointingHandCursor)
            mb.setFocusPolicy(Qt.NoFocus)
            mb.setStyleSheet(_method_btn_style(False))
            mb.clicked.connect(lambda _, m=label: self._activate_method(m))

            # #16 — credit badge (shown only for credit-flagged methods)
            if is_credit:
                credit_badge = QLabel("CREDIT")
                credit_badge.setFixedHeight(20)
                credit_badge.setAlignment(Qt.AlignCenter)
                credit_badge.setStyleSheet(
                    f"background:{ORANGE}; color:{WHITE}; border-radius:4px;"
                    f" font-size:9px; font-weight:bold; padding:0 5px;")

            # currency badge
            cb = QLabel(curr)
            cb.setFixedHeight(32)
            cb.setFixedWidth(46)
            cb.setAlignment(Qt.AlignCenter)
            cb.setStyleSheet(
                f"background:{LIGHT}; color:{ACCENT}; border:1px solid {BORDER};"
                f" border-radius:6px; font-size:10px; font-weight:bold;")

            # paid field
            ae = QLineEdit()
            ae.setFixedHeight(32)
            ae.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            ae.setValidator(validator)
            ae.setStyleSheet(_field_style(False))
            ae.focusInEvent = lambda e, m=label, orig=ae.focusInEvent: (
                self._activate_method(m, focus_field=False), orig(e))
            ae.textChanged.connect(lambda _, m=label: self._on_text_changed(m))

            # amount due label
            due = QLabel("—")
            due.setFixedHeight(32)
            due.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            due.setStyleSheet(
                f"color:{DARK_TEXT}; font-size:11px; font-weight:bold;"
                f" background:{WHITE}; border:1px solid {BORDER};"
                f" border-radius:6px; padding:0 8px;")

            # Build the method-label cell: button + optional credit badge stacked
            if is_credit:
                mb_wrap = QWidget()
                mb_wrap.setStyleSheet("background:transparent;")
                mb_vl = QVBoxLayout(mb_wrap)
                mb_vl.setContentsMargins(0, 0, 0, 0)
                mb_vl.setSpacing(1)
                mb_vl.addWidget(mb)
                mb_vl.addWidget(credit_badge)
                rl.addWidget(mb_wrap, 4)
            else:
                rl.addWidget(mb, 4)

            rl.addWidget(cb,  1)
            rl.addWidget(ae,  3)
            rl.addWidget(due, 4)

            self._method_rows[label] = (mb, ae, due)
            sl.addWidget(rw)

        sl.addStretch(1)

        sa = QScrollArea()
        sa.setWidget(sw)
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sa.setStyleSheet("background:transparent;")
        vbox.addWidget(sa, stretch=1)

        return vbox

    # =========================================================================
    # Right panel
    # =========================================================================

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

        # ── Digit rows 7–1  (unchanged) ──────────────────────────────────────
        # #2 — Layout: 4 columns.  Bottom two rows are rearranged to fit 00 / 000.
        #
        #   Row 1:  7   8   9   [10]
        #   Row 2:  4   5   6   [20]
        #   Row 3:  1   2   3   [50]
        #   Row 4:  0   00  .   [100]
        #   Row 5: 000       ←  spans cols 0-1, so it is wide and touch-friendly
        #
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

        # Row 4:  0 | 00 | . | 100-quick
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

        # Row 5:  000 (spans 3 cols — visually prominent for 1 000 entry)
        b000 = _numpad_btn("000", "digit")
        b000.clicked.connect(lambda: self._numpad_press_multi("000"))
        grid.addWidget(b000, 5, 0, 1, 3)   # colspan 3

        for r in range(6):
            grid.setRowStretch(r, 1)
        for c in range(4):
            grid.setColumnStretch(c, 1)

        vbox.addLayout(grid, stretch=5)
        vbox.addWidget(_hr())

        # #15 — Only ONE button on the finalisation row.
        # The old layout had both "Save (F2)" and "Print (F3)" — both called
        # self._save(), making them identical.  Per requirement #15 the "Save"
        # button is removed; only "Print" remains.  The keyboard shortcut F2
        # still works via keyPressEvent (calls _save), but there is no separate
        # on-screen Save button.
        brow = QHBoxLayout()
        brow.setSpacing(8)
        bprint = _action_btn("🖨  Print  (F2)", NAVY_2, NAVY_3, height=52)
        bprint.clicked.connect(self._save)
        brow.addWidget(bprint)
        vbox.addLayout(brow, stretch=1)

        return vbox

    # =========================================================================
    # Method management
    # =========================================================================

    def _activate_method(self, label: str, focus_field: bool = True):
        self._active_method = label
        for m, (mb, ae, _) in self._method_rows.items():
            mb.setStyleSheet(_method_btn_style(m == label))
            ae.setStyleSheet(_field_style(m == label))
        if focus_field and label in self._method_rows:
            ae = self._method_rows[label][1]
            ae.setFocus()
            ae.selectAll()

    def _active_field(self) -> QLineEdit:
        if self._active_method in self._method_rows:
            return self._method_rows[self._active_method][1]
        return next(iter(self._method_rows.values()))[1]

    def _method_info(self, label: str) -> tuple[str, float]:
        """Return (currency, usd_per_unit) using live exchange rates.
        usd_per_unit: multiply entered amount by this to get USD equivalent.
        Rate source: models.exchange_rate — same as split payment dialog.
        """
        for m in self._methods:
            if m["label"] == label:
                curr = m["currency"]
                if curr.upper() == "USD":
                    return curr, 1.0
                # Always fetch live from exchange_rate model
                r = _get_local_rate(curr, "USD")
                return curr, (r if r > 0 else 1.0)
        return "USD", 1.0

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
        """#2 — Handle multi-digit presses: '00' and '000'.
        Appends each digit in turn so the integer-part length cap (8 chars)
        is honoured.  Decimal part is never touched by these buttons.
        """
        for d in digits:
            self._numpad_press(d)

    def _numpad_back(self):
        f = self._active_field(); f.setText(f.text()[:-1])

    def _numpad_clear(self):
        self._active_field().clear()

    def _numpad_quick(self, amt: int):
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
        _, rate = self._method_info(label)
        return val * rate   # rate_to_usd already handles ZIG → USD

    def _on_text_changed(self, _label: str = ""):
        paid_usd = sum(self._get_paid_usd(m["label"]) for m in self._methods)
        rem_usd  = max(self.total - paid_usd, 0.0)
        local_ccy = "ZWG"   # display secondary currency
        local_rate = _get_local_rate("USD", local_ccy)   # USD → ZWG
        rem_zig  = rem_usd * local_rate
        chg_usd  = max(paid_usd - self.total, 0.0)
        settled  = rem_usd <= 0.005

        # CHANGE card — live
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

        # Per-row AMOUNT DUE labels — show remaining in the row's own currency only.
        # Tiny muted secondary (the other currency) after the primary figure.
        for m in self._methods:
            label = m["label"]
            if label not in self._method_rows:
                continue
            _, _, due_lbl = self._method_rows[label]
            curr, usd_per_unit = self._method_info(label)
            fg = SUCCESS if settled else DARK_TEXT

            if curr.upper() == "USD":
                text = f"USD  {rem_usd:.2f}"
            else:
                # Convert remaining USD into this row's currency using live rate
                rate_for_row = _get_local_rate("USD", curr)
                native = rem_usd * rate_for_row
                text   = f"{curr}  {native:,.2f}"

            due_lbl.setText(text)
            due_lbl.setTextFormat(Qt.PlainText)
            due_lbl.setStyleSheet(
                f"color:{fg}; font-size:11px; font-weight:bold;"
                f" background:{WHITE}; border:1px solid {BORDER};"
                f" border-radius:6px; padding:0 10px;")

    # =========================================================================
    # Actions
    # =========================================================================

    def _get_tendered(self) -> float:
        return sum(self._get_paid_usd(m["label"]) for m in self._methods)

    def _save(self):
        tendered = self._get_tendered()
        if tendered <= 0:
            QMessageBox.warning(self, "No Amount", "Please enter the tendered amount.")
            self._active_field().setFocus()
            return
        rem = self.total - tendered
        if rem > 0.005:
            QMessageBox.warning(
                self, "Insufficient Amount",
                f"Amount still due:  USD  {rem:.2f}\n"
                "Please enter the full amount.")
            self._active_field().setFocus()
            self._active_field().selectAll()
            return

        curr, _ = self._method_info(self._active_method)

        # #16 — look up is_credit for the active method
        is_credit = False
        for m in self._methods:
            if m["label"] == self._active_method:
                is_credit = bool(m.get("is_credit", False))
                break

        self.accepted_method       = self._active_method
        self.accepted_tendered     = tendered
        self.accepted_change       = max(tendered - self.total, 0.0)
        self.accepted_currency     = curr
        self.accepted_splits       = []
        self.accepted_customer     = self._customer
        self.accepted_company      = self._company
        self.accepted_company_name = (
            self._company.get("name", "") if self._company else "")
        self.accepted_is_credit    = is_credit   # #16 — caller reads this
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

    def _print(self):
        QMessageBox.information(self, "Print Receipt",
                                "Print receipt — connect to printer model.")

    # =========================================================================
    # Keyboard
    # =========================================================================

    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key_F2:              self._save();    return
        if k == Qt.Key_F3:              self._print();   return
        if k in (Qt.Key_Return, Qt.Key_Enter): self._save(); return
        if k == Qt.Key_Escape:          self.reject();   return

        focused    = self.focusWidget()
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
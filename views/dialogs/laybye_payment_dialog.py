# =============================================================================
# views/dialogs/laybye_payment_dialog.py  —  Deposit dialog for Laybye flow
#
# UPDATED: Now uses modes_of_payment table (same as payment_dialog.py)
#   - Loads payment methods from modes_of_payment with GL accounts
#   - On Account NOT included in Laybye deposits
#   - Proper currency conversion using exchange rates
#   - All outputs exposed for Sales Order creation
#   - SUPPORTS SPLIT PAYMENTS - one payment entry per method
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QFrame, QSizePolicy,
    QMessageBox, QScrollArea, QComboBox, QDateEdit,
)
from PySide6.QtCore import Qt, QLocale, QDate
from PySide6.QtGui import QDoubleValidator, QKeyEvent
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

ORDER_TYPES = ["Sales", "Shopping Cart", "Maintenance"]


# =============================================================================
# Data helpers (same as payment_dialog.py)
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
    """Get the default company from company_defaults (same as payment_dialog.py)"""
    try:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
        name = d.get("server_company", "").strip()
        if name:
            return {"name": name, "currency": d.get("server_company_currency", "USD")}
    except Exception:
        pass

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
    """
    result = []
    seen = set()

    try:
        from database.db import get_connection, fetchall_dicts
        conn = get_connection()
        cur = conn.cursor()

        # Only pull MOPs with a real gl_account; skip group/parent accounts
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

        for row in rows:
            mop_name = (row.get("mop_name") or "").strip()
            gl_account = (row.get("gl_account") or "").strip()
            curr = (row.get("currency") or "USD").upper()

            if not mop_name or not gl_account:
                continue

            # Skip group accounts — they have no account_type in gl_accounts
            try:
                from database.db import get_connection as _gc, fetchone_dict as _fd
                _conn = _gc()
                _cur = _conn.cursor()
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

            rate = _get_local_rate(curr, "USD")

            result.append({
                "label": mop_name,      # shown on button
                "mop_name": mop_name,   # Frappe MOP name → sent to payment_entry_service
                "gl_account": gl_account,  # leaf GL account → sent as paid_to
                "currency": curr,
                "rate_to_usd": rate,
                "is_credit": False,
            })

    except Exception as e:
        print(f"Error loading payment methods from modes_of_payment: {e}")

    print(f"Loaded {len(result)} payment methods from modes_of_payment:")
    for r in result:
        print(f"  - {r['label']} ({r['currency']}) -> GL: {r['gl_account']}")

    return result


# =============================================================================
# Widget helpers (same as payment_dialog.py)
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
    After accept():
        self.deposit_amount        — float (USD)
        self.deposit_method        — str (MOP name)
        self.deposit_splits        — dict {method_label: {amount_native, amount_usd, currency, gl_account}}
        self.deposit_currency      — str
        self.delivery_date         — str (ISO date)
        self.order_type            — str
        self.discount_amount       — float
        self.discount_percent      — float
        self.accepted_customer     — dict | None
        self.accepted_company      — dict | None
        self.accepted_company_name — str
        self.accepted_sale_id      — int (if laybye sale created)
    """

    def __init__(
        self,
        parent=None,
        total: float = 0.0,
        customer: dict | None = None,
        discount_amount: float = 0.0,
        discount_percent: float = 0.0,
        cashier_id: int = None,
        cashier_name: str = "",
        subtotal: float = None,
        total_vat: float = 0.0,
        shift_id: int = None,
        items: list = None,
    ):
        super().__init__(parent)
        self.total = total
        self.items = items or []
        self.cashier_id = cashier_id
        self.cashier_name = cashier_name
        self.subtotal = subtotal
        self.total_vat = total_vat
        self.discount_amount = discount_amount
        self.discount_percent = discount_percent
        self.shift_id = shift_id

        # Outputs
        self.deposit_amount = 0.0
        self.deposit_method = ""
        self.deposit_splits = {}   # {method_label: {amount_native, amount_usd, currency, gl_account}}
        self.deposit_currency = "USD"
        self.delivery_date = ""
        self.order_type = "Sales"
        self.accepted_customer = None
        self.accepted_company = None
        self.accepted_company_name = ""
        self.accepted_sale_id = None

        # Processing flag to prevent duplicate saves
        self._processing_save = False

        # Customer and company
        self._customer = customer or _get_default_customer()
        self._company = _get_default_company()

        co_name = self._company.get("name", "") if self._company else ""
        self._methods: list[dict] = _load_payment_methods(co_name)

        # Store numpad buffer per method
        self._numpad_buf: dict[str, str] = {m["label"]: "" for m in self._methods}
        self._method_rows: dict[str, tuple] = {}
        self._active_method: str = self._methods[0]["label"] if self._methods else ""

        # Instance widget refs
        self._dep_card: QFrame | None = None
        self._dep_lbl: QLabel | None = None

        self.setWindowTitle("Laybye — Deposit & Order Details")
        self.setMinimumSize(920, 600)
        self.setModal(True)
        self.setWindowState(Qt.WindowMaximized)

        self._build_ui()
        if self._active_method:
            self._activate_method(self._active_method)

    # =========================================================================
    # UI Build
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

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{WHITE}; border-bottom:2px solid {BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(28, 0, 28, 0)

        title = QLabel("Laybye  —  Deposit")
        title.setStyleSheet(f"color:{NAVY}; font-size:17px; font-weight:bold; background:transparent;")

        badge = QLabel("LAYBYE")
        badge.setStyleSheet(f"background:{ORANGE}; color:{WHITE}; border-radius:5px; font-size:10px; font-weight:bold; padding:3px 10px;")

        zwg_rate = _get_local_rate("USD", "ZWG")
        rate_pill = QLabel(f"1 USD = {zwg_rate:,.2f} ZWG")
        rate_pill.setStyleSheet(f"color:{MUTED}; font-size:10px; background:{LIGHT}; border-radius:4px; padding:2px 8px;")

        hint = QLabel("Deposit optional  ·  Enter to save  ·  Esc to cancel  ·  Backspace to delete")
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

        # Customer strip
        cust_strip = QWidget()
        cust_strip.setFixedHeight(34)
        cust_strip.setStyleSheet(f"background:{NAVY_2};")
        cs = QHBoxLayout(cust_strip)
        cs.setContentsMargins(28, 0, 28, 0)

        cust_icon = QLabel()
        cust_icon.setPixmap(qta.icon("fa5s.user", color=WHITE).pixmap(16, 16))
        cust_icon.setStyleSheet("background:transparent;")
        cust_name_lbl = QLabel((self._customer or {}).get("customer_name", "Unknown"))
        cust_name_lbl.setStyleSheet(f"color:{WHITE}; font-size:13px; font-weight:bold; background:transparent;")

        cs.addWidget(cust_icon)
        cs.addWidget(cust_name_lbl)
        cs.addStretch()

        if self.discount_amount > 0:
            disc_lbl = QLabel(f"Discount: {self.discount_percent:.1f}%  (−USD {self.discount_amount:.2f})")
            disc_lbl.setStyleSheet(f"color:{ORANGE}; font-size:11px; font-weight:bold; background:transparent;")
            cs.addWidget(disc_lbl)

        outer.addWidget(cust_strip)

        # Main content
        content_area = QWidget()
        ch_layout = QHBoxLayout(content_area)
        ch_layout.setContentsMargins(32, 20, 32, 20)
        ch_layout.setSpacing(28)

        ch_layout.addLayout(self._build_left(), stretch=5)

        vline = QFrame()
        vline.setFrameShape(QFrame.VLine)
        vline.setStyleSheet(f"background:{BORDER};")
        vline.setFixedWidth(1)
        ch_layout.addWidget(vline)

        ch_layout.addLayout(self._build_right(), stretch=4)

        outer.addWidget(content_area, stretch=1)

    def _build_left(self):
        vbox = QVBoxLayout()
        vbox.setSpacing(10)

        # Summary cards
        cards = QHBoxLayout()

        # ORDER TOTAL card
        tot_card = QFrame()
        tot_card.setFixedHeight(72)
        tot_card.setStyleSheet(f"QFrame {{ background:{WHITE}; border:2px solid {ORANGE}; border-radius:8px; }}")
        tot_fl = QVBoxLayout(tot_card)
        tot_fl.setContentsMargins(14, 6, 14, 6)

        tot_cap = QLabel("ORDER TOTAL")
        tot_cap.setAlignment(Qt.AlignCenter)
        tot_cap.setStyleSheet(f"color:{ORANGE}; font-size:9px; font-weight:bold;")

        tot_val = QLabel(f"USD {self.total:.2f}")
        tot_val.setAlignment(Qt.AlignCenter)
        tot_val.setStyleSheet(f"color:{DARK_TEXT}; font-size:18px; font-weight:bold; font-family:'Courier New';")

        tot_fl.addWidget(tot_cap)
        tot_fl.addWidget(tot_val)
        cards.addWidget(tot_card, 1)

        # DEPOSIT card
        self._dep_card = QFrame()
        self._dep_card.setFixedHeight(72)
        self._dep_card.setStyleSheet(f"QFrame {{ background:{WHITE}; border:2px solid {BORDER}; border-radius:8px; }}")
        dep_fl = QVBoxLayout(self._dep_card)
        dep_fl.setContentsMargins(14, 6, 14, 6)

        dep_cap = QLabel("DEPOSIT")
        dep_cap.setAlignment(Qt.AlignCenter)
        dep_cap.setStyleSheet(f"color:{MUTED}; font-size:9px; font-weight:bold;")

        self._dep_lbl = QLabel("USD 0.00")
        self._dep_lbl.setAlignment(Qt.AlignCenter)
        self._dep_lbl.setStyleSheet(f"color:{DARK_TEXT}; font-size:18px; font-weight:bold; font-family:'Courier New';")

        dep_fl.addWidget(dep_cap)
        dep_fl.addWidget(self._dep_lbl)
        cards.addWidget(self._dep_card, 1)

        vbox.addLayout(cards)
        vbox.addWidget(_hr())

        # Header row
        hrw = QHBoxLayout()
        hrw.setContentsMargins(0, 0, 0, 0)
        for txt, st, al in [
            ("MODE OF PAYMENT", 4, Qt.AlignLeft),
            ("CCY", 1, Qt.AlignCenter),
            ("DEPOSIT", 3, Qt.AlignRight),
            ("BALANCE DUE", 4, Qt.AlignRight),
        ]:
            lh = QLabel(txt)
            lh.setStyleSheet(f"color:{MUTED}; font-size:9px; font-weight:bold;")
            lh.setAlignment(al)
            hrw.addWidget(lh, st)
        vbox.addLayout(hrw)

        # Payment methods rows
        sw = QWidget()
        sl = QVBoxLayout(sw)
        sl.setSpacing(4)

        for method in self._methods:
            lbl = method["label"]
            curr = method["currency"]
            rate = method["rate_to_usd"]

            rw = QWidget()
            rw.setFixedHeight(40)
            rl = QHBoxLayout(rw)
            rl.setContentsMargins(0, 0, 0, 0)

            mb = QPushButton(f"  {lbl}")
            mb.setFixedHeight(32)
            mb.setStyleSheet(_method_btn_style(False))
            mb.clicked.connect(lambda _, m=lbl: self._activate_method(m))

            cb = QLabel(curr)
            cb.setFixedSize(46, 32)
            cb.setAlignment(Qt.AlignCenter)
            cb.setStyleSheet(
                f"background:{LIGHT}; color:{ACCENT}; border:1px solid {BORDER};"
                f" border-radius:6px; font-size:10px; font-weight:bold;")

            ae = QLineEdit()
            ae.setFixedHeight(32)
            ae.setReadOnly(True)
            ae.setAlignment(Qt.AlignRight)
            ae.setStyleSheet(_field_style(False))

            # USD to native conversion: USD / rate
            bal = QLabel(f"{curr}  {(self.total / rate):,.2f}" if rate > 0 else f"{curr}  0.00")
            bal.setFixedHeight(32)
            bal.setAlignment(Qt.AlignRight)
            bal.setStyleSheet(
                f"color:{DARK_TEXT}; font-size:11px; font-weight:bold;"
                f" background:{WHITE}; border:1px solid {BORDER};"
                f" border-radius:6px; padding:0 10px;")

            rl.addWidget(mb, 4)
            rl.addWidget(cb, 1)
            rl.addWidget(ae, 3)
            rl.addWidget(bal, 4)
            sl.addWidget(rw)

            self._method_rows[lbl] = (mb, ae, bal)

        sl.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(sw)
        scroll.setFrameShape(QFrame.NoFrame)
        vbox.addWidget(scroll, 1)

        return vbox

    def _build_right(self):
        vbox = QVBoxLayout()
        vbox.setSpacing(8)

        # Numpad grid
        grid = QGridLayout()
        grid.setSpacing(6)

        # Quick amount buttons
        for col, val in enumerate([10, 20, 50, 100]):
            b = _numpad_btn(f"${val}", "quick")
            b.clicked.connect(lambda _, v=val: self._numpad_quick(v))
            grid.addWidget(b, 0, col)

        # Digit buttons
        digits = [
            ("7", 1, 0), ("8", 1, 1), ("9", 1, 2),
            ("4", 2, 0), ("5", 2, 1), ("6", 2, 2),
            ("1", 3, 0), ("2", 3, 1), ("3", 3, 2),
            (".", 4, 0), ("0", 4, 1), ("00", 4, 2),
        ]
        for txt, r, c in digits:
            b = _numpad_btn(txt)
            b.clicked.connect(lambda _, t=txt: self._numpad_press(t))
            grid.addWidget(b, r, c)

        # Backspace and Clear
        db = _numpad_btn("", "del")
        db.setIcon(qta.icon("fa5s.backspace", color="white"))
        db.clicked.connect(self._numpad_back)
        grid.addWidget(db, 5, 0)

        cb = _numpad_btn("CLR", "clear")
        cb.clicked.connect(self._numpad_clear)
        grid.addWidget(cb, 5, 1, 1, 2)

        vbox.addLayout(grid, 1)
        vbox.addWidget(_hr())

        # Delivery date and order type
        self._delivery_date = QDateEdit()
        self._delivery_date.setCalendarPopup(True)
        self._delivery_date.setDate(QDate.currentDate().addDays(7))
        self._delivery_date.setFixedHeight(32)
        self._delivery_date.setStyleSheet(
            f"QDateEdit {{ background:{WHITE}; border:1px solid {BORDER};"
            f" border-radius:5px; padding:0 8px; }}")

        self._order_type = QComboBox()
        self._order_type.addItems(ORDER_TYPES)
        self._order_type.setFixedHeight(32)
        self._order_type.setStyleSheet(
            f"QComboBox {{ background:{WHITE}; border:1px solid {BORDER};"
            f" border-radius:5px; padding:0 8px; }}")

        vbox.addWidget(QLabel("Delivery Date:"))
        vbox.addWidget(self._delivery_date)
        vbox.addWidget(QLabel("Order Type:"))
        vbox.addWidget(self._order_type)
        vbox.addWidget(_hr())

        # Save button
        save_btn = _action_btn("Save Laybye", ORANGE, "#d96a00", 52)
        save_btn.setIcon(qta.icon("fa5s.shopping-bag", color="white"))
        save_btn.clicked.connect(self._save)
        vbox.addWidget(save_btn)

        return vbox

    # =========================================================================
    # Method Management
    # =========================================================================

    def _activate_method(self, label: str):
        self._active_method = label
        for lbl, (mb, ae, _) in self._method_rows.items():
            active = (lbl == label)
            mb.setStyleSheet(_method_btn_style(active))
            ae.setStyleSheet(_field_style(active, bool(self._numpad_buf.get(lbl, ""))))
            if active:
                ae.setText(self._numpad_buf.get(lbl, ""))

    def _method_info(self, label: str) -> tuple[str, float, str]:
        """Return (currency, rate_to_usd, gl_account) for a method."""
        for m in self._methods:
            if m["label"] == label:
                curr = m["currency"]
                rate = m["rate_to_usd"]
                gl_acct = m.get("gl_account", "")
                return curr, rate, gl_acct
        return "USD", 1.0, ""

    # =========================================================================
    # Numpad Logic
    # =========================================================================

    def _numpad_press(self, key: str):
        buf = self._numpad_buf.get(self._active_method, "")

        if key == "." and "." in buf:
            return

        if key == "00":
            if not buf:
                return
            if "." in buf:
                if len(buf.split(".")[1]) < 2:
                    buf = (buf + "00")[:buf.index(".") + 3]
            else:
                if len(buf) < 7:
                    buf += "00"
        else:
            if "." in buf:
                if len(buf.split(".")[1]) < 2:
                    buf += key
            else:
                if len(buf) < 8:
                    buf = (buf + key).lstrip("0") or key

        self._set_buf(buf)

    def _numpad_back(self):
        buf = self._numpad_buf.get(self._active_method, "")
        self._set_buf(buf[:-1])

    def _numpad_clear(self):
        self._set_buf("")

    def _numpad_quick(self, amt: int):
        """Insert a quick amount into the active field with currency conversion."""
        curr, rate_to_usd, _ = self._method_info(self._active_method)

        if curr.upper() != "USD" and rate_to_usd > 0:
            # rate_to_usd = local→USD rate (e.g., 0.033 for ZWG)
            # native amount = USD amt / rate (e.g., 10 USD / 0.033 ≈ 303 ZWG)
            native = amt / rate_to_usd
            self._set_buf(f"{native:.2f}")
        else:
            self._set_buf(str(amt))

    def _set_buf(self, value: str):
        self._numpad_buf[self._active_method] = value
        _, ae, _ = self._method_rows[self._active_method]
        ae.setText(value)
        self._refresh_totals()

    def _refresh_totals(self):
        """Update deposit total and balance due for all methods."""
        paid_usd = 0.0

        for lbl, buf_val in self._numpad_buf.items():
            if not buf_val:
                continue
            try:
                native_amt = float(buf_val)
            except ValueError:
                continue

            _, rate_to_usd, _ = self._method_info(lbl)
            paid_usd += native_amt * rate_to_usd

        bal_usd = max(self.total - paid_usd, 0.0)

        # Update deposit card
        self._dep_lbl.setText(f"USD  {paid_usd:.2f}")
        color = SUCCESS if paid_usd > 0.005 else BORDER
        self._dep_card.setStyleSheet(
            f"QFrame {{ background:{WHITE}; border:2px solid {color}; border-radius:8px; }}")

        # Update balance due for each method
        for lbl, (_, _, bal_lbl) in self._method_rows.items():
            curr, rate_to_usd, _ = self._method_info(lbl)
            # Convert remaining USD balance to method's native currency
            if rate_to_usd > 0:
                native_bal = bal_usd / rate_to_usd
            else:
                native_bal = bal_usd
            bal_lbl.setText(f"{curr}  {native_bal:,.2f}")

    # =========================================================================
    # Save Logic - ONLY creates Sales Order and Payment Entries, NOT a Sale/Invoice
    # =========================================================================

    def _generate_transaction_hash(self) -> str:
        """Generate a unique hash for this laybye transaction."""
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
            "timestamp": int(time.time() / 10),  # 10-second window
            "is_laybye": True,
        }

        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.md5(hash_string.encode()).hexdigest()

    def _check_duplicate_transaction(self, transaction_hash: str) -> bool:
        """Check if this laybye was already processed."""
        try:
            from models.sale import check_recent_transaction_by_hash
            return check_recent_transaction_by_hash(transaction_hash, seconds=10)
        except Exception as e:
            print(f"[WARNING] Could not check for duplicate: {e}")
            return False

    def _save(self):
        """
        Save the laybye deposit.
        CRITICAL: This creates a SALES ORDER, NOT a Sales Invoice.
        Payment entries are created per split leg with correct currencies.
        """
        if self._processing_save:
            print("[LaybyePaymentDialog] Save already in progress, ignoring duplicate call")
            return

        print("\n" + "="*60)
        print("[LaybyePaymentDialog] ========== STARTING SAVE ==========")
        
        # Calculate total deposit in USD and collect splits with full details
        paid_usd = 0.0
        # splits dict now stores full details: {method_label: {"native": amount, "usd": usd_amount, "currency": curr, "gl_account": gl_acct}}
        splits: dict[str, dict] = {}

        print("[LaybyePaymentDialog] Scanning numpad buffers:")
        for lbl, buf_val in self._numpad_buf.items():
            print(f"  {lbl}: '{buf_val}'")
            if not buf_val:
                continue
            try:
                native_amt = float(buf_val)
            except ValueError:
                continue

            curr, rate_to_usd, gl_acct = self._method_info(lbl)
            usd_amount = native_amt * rate_to_usd
            print(f"    native_amt={native_amt}, curr={curr}, rate_to_usd={rate_to_usd}, usd_amount={usd_amount}")

            if usd_amount > 0.005:
                paid_usd += usd_amount
                splits[lbl] = {
                    "native": native_amt,
                    "usd": round(usd_amount, 4),
                    "currency": curr,
                    "gl_account": gl_acct,
                    "rate_to_usd": rate_to_usd
                }
                print(f"    ADDED to splits: {lbl} = {native_amt} {curr} (USD {usd_amount:.2f})")

        print(f"[LaybyePaymentDialog] Total USD collected: {paid_usd}")
        print(f"[LaybyePaymentDialog] Splits dict: {splits}")
        print(f"[LaybyePaymentDialog] Number of splits: {len(splits)}")

        # Validate
        if paid_usd > self.total + 0.005:
            QMessageBox.warning(self, "Overpayment", "Deposit exceeds total order amount.")
            return

        if paid_usd <= 0:
            QMessageBox.warning(self, "No Deposit", "Please enter a deposit amount.")
            return

        # Generate hash for duplicate detection
        transaction_hash = self._generate_transaction_hash()

        if self._check_duplicate_transaction(transaction_hash):
            QMessageBox.warning(
                self,
                "Duplicate Transaction Detected",
                "This laybye appears to have been already processed.\n"
                "Please check if the laybye order was already created."
            )
            return

        self._processing_save = True

        try:
            # Set outputs
            self.deposit_amount = round(paid_usd, 4)
            self.deposit_method = self._active_method
            # Store splits with full details for the caller
            self.deposit_splits = splits
            self.deposit_currency = "USD"
            self.delivery_date = self._delivery_date.date().toString("yyyy-MM-dd")
            self.order_type = self._order_type.currentText()
            self.accepted_customer = self._customer
            self.accepted_company = self._company
            self.accepted_company_name = self._company.get("name", "") if self._company else ""

            print(f"[LaybyePaymentDialog] Deposit amount: {self.deposit_amount}")
            print(f"[LaybyePaymentDialog] Deposit splits: {self.deposit_splits}")

            # Accept the dialog - The Sales Order and its Payment Entries 
            # will now be created in a single flow by the caller (POSView) 
            # via models/sales_order.py:create_sales_order

            # Accept the dialog - The Sales Order will be created by the caller (POSView)
            print("[LaybyePaymentDialog] ========== ACCEPTING DIALOG ==========")
            print("="*60 + "\n")
            self.accept()

        except Exception as e:
            print(f"[LaybyePaymentDialog] ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to save laybye: {e}")
        finally:
            self._processing_save = False

    # =========================================================================
    # Keyboard Handling
    # =========================================================================

    def keyPressEvent(self, event: QKeyEvent):
        k = event.key()
        focused = self.focusWidget()
        is_date_or_combo = isinstance(focused, (QDateEdit, QComboBox))

        # Enter / Escape
        if k in (Qt.Key_Return, Qt.Key_Enter):
            self._save()
            return

        if k == Qt.Key_Escape:
            self.reject()
            return

        # Backspace / Delete - always apply to numpad
        if k in (Qt.Key_Backspace, Qt.Key_Delete):
            self._numpad_back()
            return

        # Let date/combo handle their own navigation
        if is_date_or_combo:
            super().keyPressEvent(event)
            return

        # Digit / decimal keys -> numpad
        _digit_keys = {
            Qt.Key_0: "0", Qt.Key_1: "1", Qt.Key_2: "2", Qt.Key_3: "3",
            Qt.Key_4: "4", Qt.Key_5: "5", Qt.Key_6: "6", Qt.Key_7: "7",
            Qt.Key_8: "8", Qt.Key_9: "9", Qt.Key_Period: ".", Qt.Key_Comma: ".",
        }
        if k in _digit_keys:
            self._numpad_press(_digit_keys[k])
            return

        super().keyPressEvent(event)
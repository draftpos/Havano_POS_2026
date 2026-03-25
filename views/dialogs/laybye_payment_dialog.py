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
    try:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
        name = d.get("server_company", "").strip()
        if name:
            return {"name": name}
    except Exception:
        pass

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
        self._discount_amount  = discount_amount
        self._discount_percent = discount_percent

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
        self._company  = _get_default_company()

        co_name = self._company.get("name", "") if self._company else ""
        self._methods: list[dict]         = _load_payment_methods(co_name)
        self._method_rows: dict[str, tuple] = {}
        self._active_method: str          = self._methods[0]["label"] if self._methods else ""
        self._numpad_buf: dict[str, str] = {m["label"]: "" for m in self._methods}

        self.setWindowTitle("Laybye — Deposit & Order Details")
        self.setMinimumSize(920, 600)
        self.setModal(True)
        self.setWindowState(Qt.WindowMaximized)

        self._build_ui()
        if self._active_method:
            self._activate_method(self._active_method)

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

        title = QLabel("Laybye  —  Deposit")
        title.setStyleSheet(f"color:{NAVY}; font-size:17px; font-weight:bold; background:transparent;")
        badge = QLabel("🛍  LAYBYE")
        badge.setStyleSheet(f"background:{ORANGE}; color:{WHITE}; border-radius:5px; font-size:10px; font-weight:bold; padding:3px 10px;")
        
        zwg_rate = _get_local_rate("USD", "ZWG")
        rate_pill = QLabel(f"1 USD = {zwg_rate:,.2f} ZWG")
        rate_pill.setStyleSheet(f"color:{MUTED}; font-size:10px; background:{LIGHT}; border-radius:4px; padding:2px 8px;")
        
        hint = QLabel("Deposit optional  ·  Enter to save  ·  Esc to cancel")
        hint.setStyleSheet(f"color:{MUTED}; font-size:10px; background:transparent;")
        hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        hl.addWidget(title); hl.addSpacing(10); hl.addWidget(badge); hl.addSpacing(12); hl.addWidget(rate_pill)
        hl.addStretch(); hl.addWidget(hint)
        outer.addWidget(hdr)

        cust_strip = QWidget()
        cust_strip.setFixedHeight(34)
        cust_strip.setStyleSheet(f"background:{NAVY_2};")
        cs = QHBoxLayout(cust_strip)
        cs.setContentsMargins(28, 0, 28, 0)
        
        cust_icon = QLabel("👤")
        cust_name_lbl = QLabel((self._customer or {}).get("customer_name", "Unknown"))
        cust_name_lbl.setStyleSheet(f"color:{WHITE}; font-size:13px; font-weight:bold; background:transparent;")
        
        cs.addWidget(cust_icon); cs.addWidget(cust_name_lbl); cs.addStretch()
        if self._discount_amount > 0:
            disc_lbl = QLabel(f"Discount: {self._discount_percent:.1f}%  (−USD {self._discount_amount:.2f})")
            disc_lbl.setStyleSheet(f"color:{ORANGE}; font-size:11px; font-weight:bold; background:transparent;")
            cs.addWidget(disc_lbl)
        outer.addWidget(cust_strip)

        content_area = QWidget()
        ch_layout = QHBoxLayout(content_area)
        ch_layout.setContentsMargins(32, 20, 32, 20)
        ch_layout.setSpacing(28)

        ch_layout.addLayout(self._build_left(), stretch=5)
        vline = QFrame(); vline.setFrameShape(QFrame.VLine); vline.setStyleSheet(f"background:{BORDER};"); vline.setFixedWidth(1)
        ch_layout.addWidget(vline)
        ch_layout.addLayout(self._build_right(), stretch=4)
        
        outer.addWidget(content_area, stretch=1)

    def _build_left(self):
        vbox = QVBoxLayout()
        vbox.setSpacing(10)

        cards = QHBoxLayout()
        for label, val, color in [("ORDER TOTAL", f"USD {self.total:.2f}", ORANGE), ("DEPOSIT", "USD 0.00", BORDER)]:
            f = QFrame(); f.setFixedHeight(72)
            f.setStyleSheet(f"QFrame {{ background:{WHITE}; border:2px solid {color}; border-radius:8px; }}")
            fl = QVBoxLayout(f); fl.setContentsMargins(14, 6, 14, 6)
            cap = QLabel(label); cap.setAlignment(Qt.AlignCenter); cap.setStyleSheet(f"color:{MUTED if label=='DEPOSIT' else color}; font-size:9px; font-weight:bold;")
            v = QLabel(val); v.setAlignment(Qt.AlignCenter); v.setStyleSheet(f"color:{DARK_TEXT}; font-size:18px; font-weight:bold; font-family:'Courier New';")
            fl.addWidget(cap); fl.addWidget(v)
            cards.addWidget(f, 1)
            if label == "DEPOSIT": self._dep_card = f; self._dep_lbl = v
        
        vbox.addLayout(cards); vbox.addWidget(_hr())

        # Header Row
        hrw = QHBoxLayout(); hrw.setContentsMargins(0,0,0,0)
        for txt, st, al in [("MODE OF PAYMENT", 4, Qt.AlignLeft), ("CCY", 1, Qt.AlignCenter), ("DEPOSIT", 3, Qt.AlignRight), ("BALANCE DUE", 4, Qt.AlignRight)]:
            l = QLabel(txt); l.setStyleSheet(f"color:{MUTED}; font-size:9px; font-weight:bold;"); l.setAlignment(al)
            hrw.addWidget(l, st)
        vbox.addLayout(hrw)

        sw = QWidget(); sl = QVBoxLayout(sw); sl.setSpacing(4)
        for method in self._methods:
            lbl = method["label"]
            rw = QWidget(); rw.setFixedHeight(40); rl = QHBoxLayout(rw); rl.setContentsMargins(0,0,0,0)
            mb = QPushButton(f"  {lbl}"); mb.setFixedHeight(32); mb.setStyleSheet(_method_btn_style(False))
            mb.clicked.connect(lambda _, m=lbl: self._activate_method(m))
            cb = QLabel(method["currency"]); cb.setFixedSize(46, 32); cb.setAlignment(Qt.AlignCenter)
            cb.setStyleSheet(f"background:{LIGHT}; color:{ACCENT}; border:1px solid {BORDER}; border-radius:6px; font-size:10px; font-weight:bold;")
            ae = QLineEdit(); ae.setFixedHeight(32); ae.setReadOnly(True); ae.setAlignment(Qt.AlignRight); ae.setStyleSheet(_field_style(False))
            bal = QLabel(f"USD {self.total:.2f}"); bal.setFixedHeight(32); bal.setAlignment(Qt.AlignRight)
            bal.setStyleSheet(f"color:{DARK_TEXT}; font-size:11px; font-weight:bold; background:{WHITE}; border:1px solid {BORDER}; border-radius:6px; padding:0 10px;")
            rl.addWidget(mb, 4); rl.addWidget(cb, 1); rl.addWidget(ae, 3); rl.addWidget(bal, 4)
            sl.addWidget(rw); self._method_rows[lbl] = (mb, ae, bal)
        
        sl.addStretch(); scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(sw); scroll.setFrameShape(QFrame.NoFrame)
        vbox.addWidget(scroll, 1)
        return vbox

    def _build_right(self):
        vbox = QVBoxLayout(); vbox.setSpacing(8)
        grid = QGridLayout(); grid.setSpacing(6)
        for col, val in enumerate([50, 100, 200]):
            b = _numpad_btn(f"${val}", "quick"); b.clicked.connect(lambda _, v=val: self._numpad_quick(v))
            grid.addWidget(b, 0, col)
        digits = [("7",1,0),("8",1,1),("9",1,2),("4",2,0),("5",2,1),("6",2,2),("1",3,0),("2",3,1),("3",3,2),(".",4,0),("0",4,1),("00",4,2)]
        for txt, r, c in digits:
            b = _numpad_btn(txt); b.clicked.connect(lambda _, t=txt: self._numpad_press(t))
            grid.addWidget(b, r, c)
        db = _numpad_btn("⌫", "del"); db.clicked.connect(self._numpad_back); grid.addWidget(db, 5, 0)
        cb = _numpad_btn("CLR", "clear"); cb.clicked.connect(self._numpad_clear); grid.addWidget(cb, 5, 1, 1, 2)
        vbox.addLayout(grid, 1); vbox.addWidget(_hr())

        self._delivery_date = QDateEdit(); self._delivery_date.setCalendarPopup(True); self._delivery_date.setDate(QDate.currentDate().addDays(7))
        self._delivery_date.setFixedHeight(32); self._delivery_date.setStyleSheet(f"QDateEdit {{ background:{WHITE}; border:1px solid {BORDER}; border-radius:5px; padding:0 8px; }}")
        
        self._order_type = QComboBox(); self._order_type.addItems(ORDER_TYPES); self._order_type.setFixedHeight(32)
        self._order_type.setStyleSheet(f"QComboBox {{ background:{WHITE}; border:1px solid {BORDER}; border-radius:5px; padding:0 8px; }}")
        
        vbox.addWidget(QLabel("Delivery Date:")); vbox.addWidget(self._delivery_date)
        vbox.addWidget(QLabel("Order Type:")); vbox.addWidget(self._order_type)
        vbox.addWidget(_hr())
        
        save_btn = _action_btn("🛍  Save Laybye", ORANGE, "#d96a00", 52); save_btn.clicked.connect(self._save)
        vbox.addWidget(save_btn)
        return vbox

    def _activate_method(self, label: str):
        self._active_method = label
        for lbl, (mb, ae, _) in self._method_rows.items():
            active = (lbl == label)
            mb.setStyleSheet(_method_btn_style(active))
            ae.setStyleSheet(_field_style(active, bool(self._numpad_buf.get(lbl, ""))))
            if active: ae.setText(self._numpad_buf.get(lbl, ""))

    def _numpad_press(self, key: str):
        buf = self._numpad_buf.get(self._active_method, "")
        if key == "." and "." in buf: return
        if key == "00":
            if not buf: return
            if "." in buf:
                if len(buf.split(".")[1]) < 2: buf = (buf + "00")[:buf.index(".")+3]
            else:
                if len(buf) < 7: buf += "00"
        else:
            if "." in buf:
                if len(buf.split(".")[1]) < 2: buf += key
            else:
                if len(buf) < 8: buf = (buf + key).lstrip("0") or key
        self._set_buf(buf)

    def _numpad_back(self):
        buf = self._numpad_buf.get(self._active_method, "")
        self._set_buf(buf[:-1])

    def _numpad_clear(self):
        self._set_buf("")

    def _numpad_quick(self, amt: int):
        self._set_buf(str(amt))

    def _set_buf(self, value: str):
        self._numpad_buf[self._active_method] = value
        _, ae, _ = self._method_rows[self._active_method]
        ae.setText(value)
        self._refresh_totals()

    def _refresh_totals(self):
        paid = 0.0
        for lbl, val in self._numpad_buf.items():
            rate = 1.0
            for m in self._methods:
                if m["label"] == lbl: rate = m["rate_to_usd"]; break
            try: paid += (float(val) if val else 0.0) * rate
            except: pass
        
        bal = max(self.total - paid, 0.0)
        self._dep_lbl.setText(f"USD  {paid:.2f}")
        color = SUCCESS if paid > 0.005 else BORDER
        self._dep_card.setStyleSheet(f"QFrame {{ background:{WHITE}; border:2px solid {color}; border-radius:8px; }}")
        
        for lbl, (mb, ae, bl) in self._method_rows.items():
            curr = "USD"
            for m in self._methods:
                if m["label"] == lbl: curr = m["currency"]; break
            r = _get_local_rate("USD", curr)
            bl.setText(f"{curr}  {bal * r:,.2f}")

    def _save(self):
        paid = 0.0
        for lbl, val in self._numpad_buf.items():
            rate = 1.0
            for m in self._methods:
                if m["label"] == lbl: rate = m["rate_to_usd"]; break
            paid += (float(val) if val else 0.0) * rate
            
        if paid > self.total + 0.005:
            QMessageBox.warning(self, "Overpayment", "Deposit exceeds total.")
            return

        self.deposit_amount = paid
        self.deposit_method = self._active_method
        self.delivery_date = self._delivery_date.date().toString("yyyy-MM-dd")
        self.order_type = self._order_type.currentText()
        self.accepted_customer = self._customer
        self.accepted_company = self._company
        self.accepted_company_name = self._company.get("name", "") if self._company else ""
        self.accept()

    def keyPressEvent(self, event):
        k = event.key()
        if k in (Qt.Key_Return, Qt.Key_Enter): self._save(); return
        if k == Qt.Key_Escape: self.reject(); return
        if k == Qt.Key_Backspace: self._numpad_back(); return
        if k == Qt.Key_Delete: self._numpad_clear(); return

        focused = self.focusWidget()
        if isinstance(focused, (QDateEdit, QComboBox)):
            super().keyPressEvent(event)
            return

        _digit_keys = {
            Qt.Key_0: "0", Qt.Key_1: "1", Qt.Key_2: "2", Qt.Key_3: "3",
            Qt.Key_4: "4", Qt.Key_5: "5", Qt.Key_6: "6", Qt.Key_7: "7",
            Qt.Key_8: "8", Qt.Key_9: "9", Qt.Key_Period: ".", Qt.Key_Comma: ".",
        }
        if k in _digit_keys:
            self._numpad_press(_digit_keys[k])
            return
        super().keyPressEvent(event)
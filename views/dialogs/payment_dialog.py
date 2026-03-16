# =============================================================================
# views/dialogs/payment_dialog.py  —  POS Payment Dialog
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QFrame, QSizePolicy, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt, QLocale
from PySide6.QtGui  import QDoubleValidator, QColor

# ── Palette — identical to main_window.py ─────────────────────────────────────
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
ROW_ALT   = "#edf3fb"
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"
ORANGE    = "#c05a00"

PAYMENT_METHODS = ["CASH", "CHECK", "C / CARD", "AMEX", "DINERS", "EFTPOS"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _navy_btn(text, height=44, font_size=13, color=None, hover=None):
    bg  = color or NAVY
    hov = hover or NAVY_2
    btn = QPushButton(text)
    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    btn.setMinimumHeight(height)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFocusPolicy(Qt.NoFocus)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: {WHITE}; border: none;
            border-radius: 5px; font-size: {font_size}px;
            font-weight: bold; padding: 0 14px;
        }}
        QPushButton:hover   {{ background-color: {hov}; }}
        QPushButton:pressed {{ background-color: {NAVY_3}; }}
    """)
    return btn


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
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: {fg};
            border: 1px solid {BORDER}; border-radius: 6px;
            font-size: 16px; font-weight: bold;
        }}
        QPushButton:hover   {{ background-color: {hov}; }}
        QPushButton:pressed {{ background-color: {NAVY_3}; color: {WHITE}; }}
    """)
    return btn


def _hr():
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"background-color: {BORDER}; border: none;")
    line.setFixedHeight(1)
    return line


def _method_btn_style(active):
    if active:
        return f"""
            QPushButton {{
                background-color: {ACCENT}; color: {WHITE};
                border: none; border-radius: 5px;
                font-size: 12px; font-weight: bold;
                text-align: left; padding: 0 10px;
            }}
            QPushButton:hover {{ background-color: {ACCENT_H}; }}
        """
    return f"""
        QPushButton {{
            background-color: {WHITE}; color: {DARK_TEXT};
            border: 1px solid {BORDER}; border-radius: 5px;
            font-size: 12px; text-align: left; padding: 0 10px;
        }}
        QPushButton:hover {{ background-color: {LIGHT}; }}
    """


def _field_style(active):
    if active:
        return f"""
            QLineEdit {{
                background-color: {WHITE}; color: {DARK_TEXT};
                border: 2px solid {ACCENT}; border-radius: 5px;
                font-size: 14px; font-weight: bold; padding: 0 10px;
            }}
        """
    return f"""
        QLineEdit {{
            background-color: {WHITE}; color: {DARK_TEXT};
            border: 1px solid {BORDER}; border-radius: 5px;
            font-size: 14px; padding: 0 10px;
        }}
        QLineEdit:focus {{ border: 2px solid {ACCENT}; }}
    """


def _get_default_customer() -> dict | None:
    """
    Try to load a default customer from settings/DB.
    Returns None if no default is configured — treated as Walk-in.
    """
    try:
        from models.customer import get_all_customers
        custs = get_all_customers()
        for c in custs:
            if c["customer_name"].strip().lower() in ("walk-in", "default", "walk in"):
                return c
    except Exception:
        pass
    return None


# =============================================================================
# INLINE CUSTOMER SEARCH  (embedded inside the payment dialog)
# =============================================================================

class _CustomerPickerWidget(QWidget):
    """
    Compact inline customer selector embedded in the payment dialog left panel.
    """
    def __init__(self, parent=None, initial_customer=None):
        super().__init__(parent)
        self.current_customer = initial_customer
        self._build()
        if initial_customer:
            self._update_display(initial_customer)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(4)
        lay.setContentsMargins(0, 0, 0, 0)

        self._cust_lbl = QLabel()
        self._cust_lbl.setFixedHeight(32)
        self._cust_lbl.setWordWrap(False)
        self._update_display(self.current_customer)
        lay.addWidget(self._cust_lbl)

        sr = QHBoxLayout(); sr.setSpacing(6)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search customer…")
        self._search.setFixedHeight(30)
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background:{WHITE}; border:1px solid {BORDER}; border-radius:4px;
                font-size:12px; padding:0 8px; color:{DARK_TEXT};
            }}
            QLineEdit:focus {{ border:2px solid {ACCENT}; }}
        """)
        self._search.textChanged.connect(self._do_search)

        walkin_btn = QPushButton("Walk-in")
        walkin_btn.setFixedHeight(30)
        walkin_btn.setFixedWidth(68)
        walkin_btn.setCursor(Qt.PointingHandCursor)
        walkin_btn.setFocusPolicy(Qt.NoFocus)
        walkin_btn.setStyleSheet(f"""
            QPushButton {{
                background:{NAVY_2}; color:{WHITE}; border:none;
                border-radius:4px; font-size:11px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{NAVY_3}; }}
        """)
        walkin_btn.clicked.connect(self._set_walkin)
        sr.addWidget(self._search, 1)
        sr.addWidget(walkin_btn)
        lay.addLayout(sr)

        self._tbl = QTableWidget(0, 3)
        self._tbl.setHorizontalHeaderLabels(["Name", "Phone", "City"])
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Fixed); self._tbl.setColumnWidth(1, 100)
        hh.setSectionResizeMode(2, QHeaderView.Fixed); self._tbl.setColumnWidth(2, 80)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setMaximumHeight(130)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tbl.setStyleSheet(f"""
            QTableWidget {{
                background:{WHITE}; border:1px solid {BORDER};
                gridline-color:{LIGHT}; font-size:12px; outline:none;
            }}
            QTableWidget::item           {{ padding:4px 6px; }}
            QTableWidget::item:selected  {{ background-color:{ACCENT}; color:{WHITE}; }}
            QTableWidget::item:alternate {{ background-color:{ROW_ALT}; }}
            QHeaderView::section {{
                background-color:{NAVY}; color:{WHITE};
                padding:6px; border:none; font-size:11px; font-weight:bold;
            }}
        """)
        self._tbl.doubleClicked.connect(self._pick_current)
        self._tbl.hide()
        lay.addWidget(self._tbl)

    def _update_display(self, customer):
        if customer:
            name  = customer.get("customer_name","")
            phone = customer.get("custom_telephone_number","")
            extra = f"  ·  {phone}" if phone else ""
            self._cust_lbl.setText(f"👤  {name}{extra}")
            self._cust_lbl.setStyleSheet(
                f"background:{ACCENT}14; color:{ACCENT}; font-size:12px; "
                f"font-weight:bold; border:1px solid {ACCENT}44; "
                f"border-radius:4px; padding:0 8px;"
            )
        else:
            self._cust_lbl.setText("👤  Walk-in  (no customer)")
            self._cust_lbl.setStyleSheet(
                f"background:{LIGHT}; color:{MUTED}; font-size:12px; "
                f"border:1px solid {BORDER}; border-radius:4px; padding:0 8px;"
            )

    def _do_search(self, query):
        if not query.strip():
            self._tbl.hide()
            return
        try:
            from models.customer import search_customers, get_all_customers
            custs = search_customers(query) if query.strip() else get_all_customers()
        except Exception:
            custs = []

        self._tbl.setRowCount(0)
        for c in custs[:20]:
            r = self._tbl.rowCount(); self._tbl.insertRow(r)
            for col, val in enumerate([
                c.get("customer_name",""),
                c.get("custom_telephone_number",""),
                c.get("custom_city",""),
            ]):
                it = QTableWidgetItem(str(val)); it.setData(Qt.UserRole, c)
                self._tbl.setItem(r, col, it)
            self._tbl.setRowHeight(r, 26)

        if self._tbl.rowCount() > 0:
            self._tbl.setCurrentRow(0)
            self._tbl.show()
        else:
            self._tbl.hide()

    def _pick_current(self):
        row = self._tbl.currentRow()
        if row < 0:
            return
        self.current_customer = self._tbl.item(row, 0).data(Qt.UserRole)
        self._update_display(self.current_customer)
        self._search.clear()
        self._tbl.hide()

    def _set_walkin(self):
        self.current_customer = None
        self._update_display(None)
        self._search.clear()
        self._tbl.hide()

    def pick_from_table(self):
        """Called by Enter key — select highlighted row."""
        if self._tbl.isVisible():
            self._pick_current()


# =============================================================================
# PAYMENT DIALOG
# =============================================================================

class PaymentDialog(QDialog):
    """
    Navy-branded POS payment dialog with inline customer selector.
    """

    def __init__(self, parent=None, total: float = 0.0, customer: dict | None = None):
        super().__init__(parent)
        self.total             = total
        self.accepted_method   = "CASH"
        self.accepted_tendered = 0.0
        self.accepted_change   = 0.0
        self.accepted_customer = None

        if customer:
            self._customer = customer
        else:
            self._customer = _get_default_customer()

        self._active_method = "CASH"
        self._method_rows: dict[str, tuple[QPushButton, QLineEdit]] = {}

        self.setWindowTitle("Payment")
        self.setMinimumSize(860, 600)
        self.resize(920, 660)
        self.setModal(True)

        self._build_ui()
        self._activate_method("CASH")

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setStyleSheet(f"""
            QDialog  {{ background-color: {OFF_WHITE}; color: {DARK_TEXT};
                        font-family: 'Segoe UI', sans-serif; }}
            QLabel   {{ background: transparent; color: {DARK_TEXT}; font-size: 13px; }}
            QWidget  {{ background-color: {OFF_WHITE}; }}
        """)

        outer = QVBoxLayout(self)
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)

        # Navy header
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet(f"background-color: {NAVY}; border: none;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)
        title = QLabel("Payment")
        title.setStyleSheet(
            f"color: {WHITE}; font-size: 16px; font-weight: bold; background: transparent;"
        )
        hint = QLabel("Click a field and type  |  numpad  |  Enter to confirm")
        hint.setStyleSheet(f"color: {MID}; font-size: 11px; background: transparent;")
        hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(hint)
        outer.addWidget(header)

        # Body
        body = QWidget()
        body.setStyleSheet(f"background-color: {OFF_WHITE};")
        bl = QHBoxLayout(body)
        bl.setSpacing(16)
        bl.setContentsMargins(16, 14, 16, 14)
        bl.addLayout(self._build_left(),  stretch=4)

        vline = QFrame()
        vline.setFrameShape(QFrame.VLine)
        vline.setStyleSheet(f"background-color: {BORDER}; border: none;")
        vline.setFixedWidth(1)
        bl.addWidget(vline)

        bl.addLayout(self._build_right(), stretch=5)
        outer.addWidget(body, stretch=1)

    # ── Left panel ────────────────────────────────────────────────────────────

    def _build_left(self):
        vbox = QVBoxLayout()
        vbox.setSpacing(8)

        # ── Customer section ──────────────────────────────────────────────────
        cust_sec = QLabel("CUSTOMER")
        cust_sec.setStyleSheet(
            f"color:{MUTED}; font-size:10px; font-weight:bold;"
            " letter-spacing:0.8px; background:transparent;"
        )
        vbox.addWidget(cust_sec)

        self._cust_picker = _CustomerPickerWidget(self, initial_customer=self._customer)
        vbox.addWidget(self._cust_picker)

        vbox.addWidget(_hr())

        # ── Green-on-black display ────────────────────────────────────────────
        display_frame = QFrame()
        display_frame.setFixedHeight(64)
        display_frame.setStyleSheet(
            "QFrame { background-color: #000; border: 2px solid #222; border-radius: 6px; }"
        )
        dfl = QHBoxLayout(display_frame)
        dfl.setContentsMargins(14, 4, 14, 4)
        self._display_lbl = QLabel(f"{self.total:.2f}")
        self._display_lbl.setStyleSheet(
            "color: #00ff44; font-size: 30px; font-weight: bold;"
            " font-family: 'Courier New', monospace; background: transparent;"
        )
        self._display_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        dfl.addWidget(self._display_lbl)
        vbox.addWidget(display_frame)

        # ── Method rows ───────────────────────────────────────────────────────
        validator = QDoubleValidator(0.0, 999999.99, 2)
        validator.setLocale(QLocale(QLocale.English))

        for idx, method in enumerate(PAYMENT_METHODS, 1):
            row = QWidget()
            row.setFixedHeight(42)
            row.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(8)

            mb = QPushButton(f"  {idx}  {method}")
            mb.setFixedHeight(36)
            mb.setMinimumWidth(120)
            mb.setCursor(Qt.PointingHandCursor)
            mb.setFocusPolicy(Qt.NoFocus)
            mb.setStyleSheet(_method_btn_style(False))
            mb.clicked.connect(lambda _, m=method: self._activate_method(m))

            ae = QLineEdit()
            ae.setPlaceholderText("")
            ae.setFixedHeight(36)
            ae.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            ae.setValidator(validator)
            ae.setStyleSheet(_field_style(False))
            ae.focusInEvent = lambda e, m=method, orig=ae.focusInEvent: (
                self._activate_method(m, focus_field=False), orig(e)
            )
            ae.textChanged.connect(lambda _, m=method: self._on_text_changed(m))

            rl.addWidget(mb, 3)
            rl.addWidget(ae, 4)
            self._method_rows[method] = (mb, ae)
            vbox.addWidget(row)

        vbox.addStretch(1)
        vbox.addWidget(_hr())

        # ── Rounding & Change ─────────────────────────────────────────────────
        for label, is_change in [("Rounding $", False), ("Change $", True)]:
            card = QFrame()
            card.setFixedHeight(38)
            card.setStyleSheet(
                f"QFrame {{ background-color: {WHITE}; border: 1px solid {BORDER}; border-radius: 5px; }}"
            )
            cl = QHBoxLayout(card)
            cl.setContentsMargins(12, 0, 12, 0)
            lw = QLabel(label)
            lw.setStyleSheet(f"color: {MUTED}; font-size: 12px; font-weight: bold; background: transparent;")
            vw = QLabel("0.00")
            vw.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if is_change:
                vw.setStyleSheet(f"color: {ORANGE}; font-size: 15px; font-weight: bold; background: transparent;")
                self._change_lbl = vw
            else:
                vw.setStyleSheet(f"color: {DARK_TEXT}; font-size: 13px; background: transparent;")
                self._rounding_lbl = vw
            cl.addWidget(lw)
            cl.addWidget(vw)
            vbox.addWidget(card)

        return vbox

    # ── Right panel ───────────────────────────────────────────────────────────

    def _build_right(self):
        vbox = QVBoxLayout()
        vbox.setSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(6)

        b40 = _numpad_btn("40", "quick")
        b40.clicked.connect(lambda: self._numpad_quick(40))
        grid.addWidget(b40, 0, 0)

        bback = _numpad_btn("⌫  Back", "del")
        bback.clicked.connect(self._numpad_back)
        grid.addWidget(bback, 0, 1)

        bclr = _numpad_btn("Clear", "clear")
        bclr.clicked.connect(self._numpad_clear)
        grid.addWidget(bclr, 0, 2)

        bcan = _navy_btn("Cancel", color=DANGER, hover=DANGER_H)
        bcan.clicked.connect(self.reject)
        grid.addWidget(bcan, 0, 3)

        digit_rows = [["7","8","9"], ["4","5","6"], ["1","2","3"], ["0",".","±"]]
        quick_amts = [10, 20, 50, 100]

        for ri, row_digits in enumerate(digit_rows, 1):
            for ci, d in enumerate(row_digits):
                b = _numpad_btn(d, "digit")
                b.clicked.connect(lambda _, x=d: self._numpad_press(x))
                grid.addWidget(b, ri, ci)
            qa = quick_amts[ri - 1]
            qb = _numpad_btn(str(qa), "quick")
            qb.clicked.connect(lambda _, a=qa: self._numpad_quick(a))
            grid.addWidget(qb, ri, 3)

        for r in range(5): grid.setRowStretch(r, 1)
        for c in range(4): grid.setColumnStretch(c, 1)

        vbox.addLayout(grid, stretch=5)
        vbox.addWidget(_hr())

        # ── Save & Print buttons ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        bsave  = _navy_btn("💾  Save  (F2)",  color=SUCCESS, hover=SUCCESS_H, height=48)
        bsave.clicked.connect(self._save)
        bprint = _navy_btn("🖨  Print  (F3)", color=NAVY_2,  hover=NAVY_3,   height=48)
        bprint.clicked.connect(self._save)
        btn_row.addWidget(bsave)
        btn_row.addWidget(bprint)
        vbox.addLayout(btn_row, stretch=1)

        return vbox

    # ── Method management ─────────────────────────────────────────────────────

    def _activate_method(self, method: str, focus_field: bool = True):
        self._active_method = method
        for m, (mb, ae) in self._method_rows.items():
            active = (m == method)
            mb.setStyleSheet(_method_btn_style(active))
            ae.setStyleSheet(_field_style(active))
        if focus_field:
            _, ae = self._method_rows[method]
            ae.setFocus()
            ae.selectAll()

    def _active_field(self) -> QLineEdit:
        return self._method_rows[self._active_method][1]

    # ── Numpad ────────────────────────────────────────────────────────────────

    def _numpad_press(self, key: str):
        if key in ("±", "+/-"):
            return
        field = self._active_field()
        cur   = field.text()
        if key == ".":
            if "." not in cur:
                field.setText(cur + ".")
        else:
            int_part = cur.split(".")[0]
            if "." in cur:
                if len(cur.split(".")[1]) < 2:
                    field.setText(cur + key)
            else:
                if len(int_part) < 8:
                    field.setText(cur + key)

    def _numpad_back(self):
        field = self._active_field()
        field.setText(field.text()[:-1])

    def _numpad_clear(self):
        self._active_field().clear()

    def _numpad_quick(self, amount: int):
        self._active_field().setText(f"{amount:.2f}")

    # ── Live totals ───────────────────────────────────────────────────────────

    def _on_text_changed(self, method: str):
        if method != self._active_method:
            return
        field = self._method_rows[method][1]
        try:
            tendered = float(field.text() or "0")
        except ValueError:
            tendered = 0.0

        self._display_lbl.setText(
            f"{tendered:.2f}" if tendered > 0 else f"{self.total:.2f}"
        )
        change = tendered - self.total
        self._change_lbl.setText(
            f"{change:.2f}" if tendered > 0 else f"{-self.total:.2f}"
        )
        if tendered > 0:
            rounded = round(tendered * 20) / 20
            self._rounding_lbl.setText(f"{rounded - tendered:.2f}")
        else:
            self._rounding_lbl.setText("0.00")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _get_tendered(self) -> float:
        try:
            return float(self._active_field().text() or "0")
        except ValueError:
            return 0.0

    def _save(self):
        tendered = self._get_tendered()
        if tendered <= 0:
            QMessageBox.warning(self, "No Amount", "Please enter the tendered amount.")
            return
        if tendered < self.total:
            if QMessageBox.question(
                self, "Insufficient Amount",
                f"Tendered ${tendered:.2f} is less than total ${self.total:.2f}.\n"
                "Confirm partial payment?",
                QMessageBox.Yes | QMessageBox.No,
            ) != QMessageBox.Yes:
                return

        self.accepted_method   = self._active_method
        self.accepted_tendered = tendered
        self.accepted_change   = max(tendered - self.total, 0.0)
        self.accepted_customer = self._cust_picker.current_customer

        self._method = self._active_method
        _t = tendered
        self._amt = type("_Amt", (), {"text": lambda s, t=_t: str(t)})()

        self.accept()

    def _print(self):
        QMessageBox.information(self, "Print Receipt",
                                "Print receipt — connect to printer model.")

    # ── Keyboard ─────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key_F2:
            self._save();  return
        if key == Qt.Key_F3:
            self._print(); return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if self._cust_picker._tbl.isVisible():
                self._cust_picker.pick_from_table()
                return
            self._save()
            return
        if key == Qt.Key_Escape:
            if self._cust_picker._tbl.isVisible():
                self._cust_picker._tbl.hide()
                self._cust_picker._search.clear()
                return
            self.reject()
            return

        focused = self.focusWidget()
        if focused is self._cust_picker._search:
            super().keyPressEvent(event)
            return

        is_editing = isinstance(focused, QLineEdit) and focused.text()
        if not is_editing:
            method_keys = {
                Qt.Key_1: "CASH",     Qt.Key_2: "CHECK",
                Qt.Key_3: "C / CARD", Qt.Key_4: "AMEX",
                Qt.Key_5: "DINERS",   Qt.Key_6: "EFTPOS",
            }
            if key in method_keys:
                self._activate_method(method_keys[key])
                return

        super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._activate_method("CASH")
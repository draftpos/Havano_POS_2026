# =============================================================================
# views/dialogs/payment_dialog.py  —  POS Payment Dialog
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QFrame, QSizePolicy, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QComboBox,
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


def _section_label(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(
        f"color: {MUTED}; font-size: 10px; font-weight: bold; "
        f"letter-spacing: 0.8px; background: transparent;"
    )
    return l


def _get_default_customer() -> dict | None:
    try:
        from models.customer import get_all_customers
        custs = get_all_customers()
        for c in custs:
            if c["customer_name"].strip().lower() in ("walk-in", "default", "walk in"):
                return c
    except Exception:
        pass
    return None


def _get_default_company() -> dict | None:
    try:
        from models.company import get_all_companies
        companies = get_all_companies()
        return companies[0] if companies else None
    except Exception:
        return None


def _get_all_companies() -> list[dict]:
    try:
        from models.company import get_all_companies
        return get_all_companies()
    except Exception:
        return []


def _get_all_customers() -> list[dict]:
    try:
        from models.customer import get_all_customers
        return get_all_customers()
    except Exception:
        return []


# =============================================================================
# CUSTOMER PICKER DIALOG
# =============================================================================

class _CustomerPickerDialog(QDialog):

    def __init__(self, parent=None, current_customer=None):
        super().__init__(parent)
        self.setWindowTitle("Select Customer")
        self.setFixedSize(520, 440)
        self.setModal(True)
        self.chosen = current_customer
        self._all   = _get_all_customers()
        self._build()
        self._populate(self._all)

    def _build(self):
        self.setStyleSheet(f"QDialog {{ background: {OFF_WHITE}; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        hdr = QWidget()
        hdr.setStyleSheet(f"background: {NAVY}; border-radius: 6px;")
        hl  = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 10, 14, 10)
        t   = QLabel("Select Customer")
        t.setStyleSheet(
            f"color:{WHITE}; font-size:14px; font-weight:bold; background:transparent;"
        )
        hl.addWidget(t)
        root.addWidget(hdr)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by name, phone or city…")
        self._search.setFixedHeight(36)
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background:{WHITE}; border:2px solid {ACCENT};
                border-radius:6px; font-size:13px; padding:0 10px; color:{DARK_TEXT};
            }}
        """)
        self._search.textChanged.connect(self._on_search)
        root.addWidget(self._search)

        self._tbl = QTableWidget(0, 3)
        self._tbl.setHorizontalHeaderLabels(["Name", "Phone", "City"])
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        self._tbl.setColumnWidth(1, 120)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        self._tbl.setColumnWidth(2, 100)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tbl.setStyleSheet(f"""
            QTableWidget {{
                background:{WHITE}; border:1px solid {BORDER};
                gridline-color:{LIGHT}; font-size:13px; outline:none;
            }}
            QTableWidget::item           {{ padding:7px 10px; }}
            QTableWidget::item:selected  {{ background:{ACCENT}; color:{WHITE}; }}
            QTableWidget::item:alternate {{ background:{ROW_ALT}; }}
            QHeaderView::section {{
                background:{NAVY}; color:{WHITE}; padding:8px;
                border:none; border-right:1px solid {NAVY_2};
                font-size:12px; font-weight:bold;
            }}
        """)
        self._tbl.doubleClicked.connect(self._pick)
        root.addWidget(self._tbl, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        walkin = QPushButton("Walk-in (no customer)")
        walkin.setFixedHeight(38)
        walkin.setCursor(Qt.PointingHandCursor)
        walkin.setFocusPolicy(Qt.NoFocus)
        walkin.setStyleSheet(f"""
            QPushButton {{
                background:{NAVY_2}; color:{WHITE}; border:none;
                border-radius:6px; font-size:12px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{NAVY_3}; }}
        """)
        walkin.clicked.connect(self._set_walkin)

        select_btn = QPushButton("Select  ↵")
        select_btn.setFixedHeight(38)
        select_btn.setFixedWidth(110)
        select_btn.setCursor(Qt.PointingHandCursor)
        select_btn.setFocusPolicy(Qt.NoFocus)
        select_btn.setStyleSheet(f"""
            QPushButton {{
                background:{ACCENT}; color:{WHITE}; border:none;
                border-radius:6px; font-size:12px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{ACCENT_H}; }}
        """)
        select_btn.clicked.connect(self._pick)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(38)
        cancel_btn.setFixedWidth(90)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFocusPolicy(Qt.NoFocus)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background:{LIGHT}; color:{DARK_TEXT}; border:1px solid {BORDER};
                border-radius:6px; font-size:12px;
            }}
            QPushButton:hover {{ background:{BORDER}; }}
        """)
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(walkin, 1)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(select_btn)
        root.addLayout(btn_row)

    def _populate(self, customers: list[dict]):
        self._tbl.setRowCount(0)
        for c in customers:
            r = self._tbl.rowCount()
            self._tbl.insertRow(r)
            for col, val in enumerate([
                c.get("customer_name", ""),
                c.get("custom_telephone_number", ""),
                c.get("custom_city", ""),
            ]):
                it = QTableWidgetItem(str(val))
                it.setData(Qt.UserRole, c)
                self._tbl.setItem(r, col, it)
            self._tbl.setRowHeight(r, 34)
        if self._tbl.rowCount():
            self._tbl.selectRow(0)

    def _on_search(self, query):
        if not query.strip():
            self._populate(self._all)
            return
        try:
            from models.customer import search_customers
            self._populate(search_customers(query))
        except Exception:
            q = query.lower()
            self._populate([
                c for c in self._all
                if q in c.get("customer_name", "").lower()
                or q in c.get("custom_telephone_number", "").lower()
            ])

    def _pick(self):
        row = self._tbl.currentRow()
        if row < 0:
            return
        self.chosen = self._tbl.item(row, 0).data(Qt.UserRole)
        self.accept()

    def _set_walkin(self):
        self.chosen = None
        self.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._pick()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)


# =============================================================================
# PAYMENT DIALOG
# =============================================================================

class PaymentDialog(QDialog):
    """
    After accept():
      self.accepted_method       — payment method string
      self.accepted_tendered     — float
      self.accepted_change       — float
      self.accepted_customer     — customer dict or None
      self.accepted_company      — company dict or None
      self.accepted_company_name — str  ← pass to create_sale()
    """

    def __init__(self, parent=None, total: float = 0.0, customer: dict | None = None):
        super().__init__(parent)
        self.total              = total
        self.accepted_method    = "CASH"
        self.accepted_tendered  = 0.0
        self.accepted_change    = 0.0
        self.accepted_customer  = None
        self.accepted_company   = None
        self.accepted_company_name = ""

        self._customer      = customer or _get_default_customer()
        self._company       = _get_default_company()
        self._active_method = "CASH"
        self._method_rows: dict[str, tuple[QPushButton, QLineEdit]] = {}

        self.setWindowTitle("Payment")
        self.setMinimumSize(1100, 680)
        self.resize(1160, 720)
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

        # navy header
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet(f"background-color: {NAVY}; border: none;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)
        title = QLabel("Payment")
        title.setStyleSheet(
            f"color: {WHITE}; font-size: 16px; font-weight: bold; background: transparent;"
        )
        hint = QLabel("Number keys switch method  |  Enter to confirm")
        hint.setStyleSheet(f"color: {MID}; font-size: 11px; background: transparent;")
        hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(hint)
        outer.addWidget(header)

        # body
        body = QWidget()
        body.setStyleSheet(f"background-color: {OFF_WHITE};")
        bl = QHBoxLayout(body)
        bl.setSpacing(16)
        bl.setContentsMargins(16, 14, 16, 14)
        bl.addLayout(self._build_left(), stretch=4)

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
        vbox.setSpacing(6)

        # ── COMPANY + CUSTOMER side by side ───────────────────────────────────
        cc_row = QHBoxLayout()
        cc_row.setSpacing(8)

        # company column
        co_col = QVBoxLayout()
        co_col.setSpacing(2)
        co_col.addWidget(_section_label("COMPANY"))
        company_name = (
            self._company.get("name", "—") if self._company else "No company"
        )
        co_lbl = QLabel(f"🏢  {company_name}")
        co_lbl.setFixedHeight(28)
        co_lbl.setStyleSheet(f"""
            background: {NAVY}; color: {WHITE};
            font-size: 12px; font-weight: bold;
            border-radius: 5px; padding: 0 10px;
        """)
        co_col.addWidget(co_lbl)
        cc_row.addLayout(co_col, 1)

        # customer column
        cu_col = QVBoxLayout()
        cu_col.setSpacing(2)
        cu_col.addWidget(_section_label("CUSTOMER"))
        self._cust_btn = QPushButton()
        self._cust_btn.setFixedHeight(28)
        self._cust_btn.setCursor(Qt.PointingHandCursor)
        self._cust_btn.setFocusPolicy(Qt.NoFocus)
        self._cust_btn.clicked.connect(self._open_customer_picker)
        self._refresh_customer_btn()
        cu_col.addWidget(self._cust_btn)
        cc_row.addLayout(cu_col, 1)

        vbox.addLayout(cc_row)
        vbox.addWidget(_hr())

        # ── TWO DISPLAYS ──────────────────────────────────────────────────────
        displays = QHBoxLayout()
        displays.setSpacing(8)

        # Total to pay — static, blue border
        total_frame = QFrame()
        total_frame.setFixedHeight(68)
        total_frame.setStyleSheet(
            f"QFrame {{ background:#000; border:2px solid {WHITE}; border-radius:6px; }}"
        )
        tfl = QVBoxLayout(total_frame)
        tfl.setContentsMargins(10, 4, 10, 4)
        tfl.setSpacing(1)
        cap1 = QLabel("TOTAL TO PAY")
        cap1.setStyleSheet(
            f"color:{WHITE}; font-size:9px; font-weight:bold; "
            f"letter-spacing:1px; background:transparent;"
        )
        cap1.setAlignment(Qt.AlignRight)
        self._total_display = QLabel(f"{self.total:.2f}")
        self._total_display.setStyleSheet(
            "color:#ffffff; font-size:24px; font-weight:bold;"
            " font-family:'Courier New',monospace; background:transparent;"
        )
        self._total_display.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tfl.addWidget(cap1)
        tfl.addWidget(self._total_display)
        displays.addWidget(total_frame, 1)

        # Change — updates as cashier types, orange border
        tendered_frame = QFrame()
        tendered_frame.setFixedHeight(68)
        tendered_frame.setStyleSheet(
            f"QFrame {{ background:#000; border:2px solid {ORANGE}; border-radius:6px; }}"
        )
        tndfl = QVBoxLayout(tendered_frame)
        tndfl.setContentsMargins(10, 4, 10, 4)
        tndfl.setSpacing(1)
        cap2 = QLabel("CHANGE")
        cap2.setStyleSheet(
            f"color:{ORANGE}; font-size:9px; font-weight:bold; "
            f"letter-spacing:1px; background:transparent;"
        )
        cap2.setAlignment(Qt.AlignRight)
        self._tendered_display = QLabel("0.00")
        self._tendered_display.setStyleSheet(
            f"color:{ORANGE}; font-size:24px; font-weight:bold;"
            " font-family:'Courier New',monospace; background:transparent;"
        )
        self._tendered_display.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tndfl.addWidget(cap2)
        tndfl.addWidget(self._tendered_display)
        displays.addWidget(tendered_frame, 1)

        vbox.addLayout(displays)

        # ── method rows ───────────────────────────────────────────────────────
        validator = QDoubleValidator(0.0, 999999.99, 2)
        validator.setLocale(QLocale(QLocale.English))

        for idx, method in enumerate(PAYMENT_METHODS, 1):
            row = QWidget()
            row.setFixedHeight(38)
            row.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(8)

            mb = QPushButton(f"  {idx}  {method}")
            mb.setFixedHeight(32)
            mb.setMinimumWidth(110)
            mb.setCursor(Qt.PointingHandCursor)
            mb.setFocusPolicy(Qt.NoFocus)
            mb.setStyleSheet(_method_btn_style(False))
            mb.clicked.connect(lambda _, m=method: self._activate_method(m))

            ae = QLineEdit()
            ae.setPlaceholderText("")
            ae.setFixedHeight(32)
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

        # ── rounding & change ─────────────────────────────────────────────────
        for label, is_change in [("Rounding $", False), ("Tendered $", True)]:
            card = QFrame()
            card.setFixedHeight(34)
            card.setStyleSheet(
                f"QFrame {{ background:{WHITE}; border:1px solid {BORDER}; border-radius:5px; }}"
            )
            cl = QHBoxLayout(card)
            cl.setContentsMargins(12, 0, 12, 0)
            lw = QLabel(label)
            lw.setStyleSheet(
                f"color:{MUTED}; font-size:12px; font-weight:bold; background:transparent;"
            )
            vw = QLabel("0.00")
            vw.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if is_change:
                vw.setStyleSheet(
                    f"color:{ORANGE}; font-size:14px; font-weight:bold; background:transparent;"
                )
                self._change_lbl = vw
            else:
                vw.setStyleSheet(
                    f"color:{DARK_TEXT}; font-size:12px; background:transparent;"
                )
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

        for r in range(5):
            grid.setRowStretch(r, 1)
        for c in range(4):
            grid.setColumnStretch(c, 1)

        vbox.addLayout(grid, stretch=5)
        vbox.addWidget(_hr())

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

    # ── Customer picker ───────────────────────────────────────────────────────

    def _open_customer_picker(self):
        dlg = _CustomerPickerDialog(self, current_customer=self._customer)
        if dlg.exec() == QDialog.Accepted:
            self._customer = dlg.chosen
            self._refresh_customer_btn()

    def _refresh_customer_btn(self):
        if self._customer:
            name  = self._customer.get("customer_name", "")
            phone = self._customer.get("custom_telephone_number", "")
            extra = f"   ·   {phone}" if phone else ""
            self._cust_btn.setText(f"👤  {name}{extra}   ▾")
            self._cust_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {ACCENT}; color: {WHITE};
                    border: none; border-radius: 5px;
                    font-size: 12px; font-weight: bold;
                    text-align: left; padding: 0 10px;
                }}
                QPushButton:hover {{ background: {ACCENT_H}; }}
            """)
        else:
            self._cust_btn.setText("👤  Walk-in   ▾")
            self._cust_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {LIGHT}; color: {MUTED};
                    border: 1px solid {BORDER}; border-radius: 5px;
                    font-size: 12px;
                    text-align: left; padding: 0 10px;
                }}
                QPushButton:hover {{ background: {BORDER}; }}
            """)

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

        change = tendered - self.total
        self._tendered_display.setText(f"{change:.2f}" if tendered > 0 else "0.00")
        self._total_display.setText(f"{self.total:.2f}")

        self._change_lbl.setText(f"{tendered:.2f}" if tendered > 0 else "0.00")

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
            self._active_field().setFocus()
            return
        if tendered < self.total:
            QMessageBox.warning(
                self, "Insufficient Amount",
                f"Tendered ${tendered:.2f} is less than total ${self.total:.2f}.\n"
                "Please enter the full amount or more."
            )
            self._active_field().setFocus()
            self._active_field().selectAll()
            return

        self.accepted_method       = self._active_method
        self.accepted_tendered     = tendered
        self.accepted_change       = max(tendered - self.total, 0.0)
        self.accepted_customer     = self._customer
        self.accepted_company      = self._company
        self.accepted_company_name = (
            self._company.get("name", "") if self._company else ""
        )
        self.accept()

    def _print(self):
        QMessageBox.information(self, "Print Receipt",
                                "Print receipt — connect to printer model.")

    # ── Keyboard ─────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key_F2:
            self._save()
            return
        if key == Qt.Key_F3:
            self._print()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._save()
            return
        if key == Qt.Key_Escape:
            self.reject()
            return

        focused = self.focusWidget()
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
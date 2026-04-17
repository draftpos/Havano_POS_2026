# =============================================================================
# views/dialogs/split_payment_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QLineEdit, QMessageBox,
)
from PySide6.QtCore  import Qt, QLocale
from PySide6.QtGui   import QColor, QDoubleValidator

NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
NAVY_3    = "#1e3d6e"
ACCENT    = "#1a5fb4"
ACCENT_H  = "#1c6dd0"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
LIGHT     = "#e4eaf4"
BORDER    = "#c8d8ec"
DARK_TEXT = "#0d1f3c"
MUTED     = "#5a7a9a"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
GREEN     = "#1e8449"
AMBER     = "#b7770d"
ORANGE    = "#c05a00"

# Default fallback ZIG rate — overridden by _get_zig_rate() at runtime
ZIG_RATE: float = 26.0


def _get_company_defaults() -> dict:
    try:
        from models.company_defaults import get_defaults
        return get_defaults() or {}
    except Exception:
        return {}


def _get_zig_rate() -> float:
    try:
        from models.company_defaults import get_defaults
        d = get_defaults() or {}
        rate = float(d.get("zig_rate", 0) or 0)
        return rate if rate > 0 else ZIG_RATE
    except Exception:
        return ZIG_RATE


def _load_accounts_for_company(company: str) -> list[dict]:
    try:
        from models.gl_account import get_all_accounts
        accounts = get_all_accounts()
        company_accts = [a for a in accounts if a.get("company") == company]
        return company_accts if company_accts else accounts
    except Exception:
        return []


def _get_rate(from_currency: str, to_currency: str) -> float:
    if from_currency.upper() == to_currency.upper():
        return 1.0
    try:
        from models.exchange_rate import get_rate
        rate = get_rate(from_currency, to_currency)
        return rate if rate else 1.0
    except Exception:
        return 1.0


# =============================================================================
# SPLIT PAYMENT DIALOG
# =============================================================================

class SplitPaymentDialog(QDialog):
    """
    After accept():
      self.splits           = [ { account_name, account_currency, mode, rate,
                                   amount_paid, base_value }, ... ]
      self.accepted_change  = float
      self.accepted_method  = "SPLIT"
      self.accepted_currency = str
    """

    def __init__(self, parent=None, total: float = 0.0,
                 company: str = "", company_currency: str = "USD"):
        super().__init__(parent)
        self.total            = total
        self.company          = company
        self.company_currency = company_currency.upper()

        self.splits            = []
        self.accepted_change   = 0.0
        self.accepted_method   = "SPLIT"
        self.accepted_currency = company_currency

        self._accounts   = []
        self._rate_cache = {}
        self._editors    = {}   # row_idx -> (QLineEdit, currency, rate)
        self._zig_rate   = _get_zig_rate()

        self.setWindowTitle("Split Payment")
        self.setMinimumSize(700, 480)
        self.setModal(True)
        self.setWindowState(Qt.WindowMaximized)
        self.setStyleSheet(f"QDialog {{ background:{OFF_WHITE}; }}")

        self._build()
        self._load_accounts()

    # =========================================================================
    # UI
    # =========================================================================

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── header ────────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 0, 24, 0)
        hl.addWidget(self._lbl("⚡  Split Payment", WHITE, 16, bold=True))
        hl.addStretch()
        rate_hint = self._lbl(
            f"Rate: 1 USD = {self._zig_rate:.2f} ZIG", "#8fa8c8", 11
        )
        hl.addWidget(rate_hint)
        hl.addSpacing(20)
        self._total_lbl = self._lbl(
            f"Total: {self.company_currency} {self.total:.2f}", WHITE, 14, bold=True
        )
        hl.addWidget(self._total_lbl)
        root.addWidget(hdr)

        # ── body ──────────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet(f"background:{OFF_WHITE};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(24, 16, 24, 16)
        bl.setSpacing(12)

        # ── summary cards ─────────────────────────────────────────────────────
        summary_row = QHBoxLayout()
        summary_row.setSpacing(10)

        for attr, label, color, is_rem in [
            ("_paid_card",   "PAID",        ACCENT, False),
            ("_remain_card", "AMOUNT DUE",  ACCENT, True),
        ]:
            card = QFrame()
            card.setFixedHeight(80)
            border = ACCENT if is_rem else BORDER
            card.setStyleSheet(
                f"QFrame {{ background:{WHITE}; border:2px solid {border}; border-radius:8px; }}"
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 6, 14, 6)
            cl.setSpacing(2)

            cap = QLabel(label)
            cap.setStyleSheet(
                f"color:{color}; font-size:9px; font-weight:bold; "
                f"letter-spacing:1.2px; background:transparent;"
            )
            cap.setAlignment(Qt.AlignRight)

            usd_lbl = QLabel("USD  0.00")
            usd_lbl.setStyleSheet(
                f"color:{DARK_TEXT}; font-size:20px; font-weight:bold;"
                " font-family:'Courier New',monospace; background:transparent;"
            )
            usd_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            zig_lbl = QLabel("ZIG  0.00")
            zig_lbl.setStyleSheet(
                f"color:{MUTED}; font-size:11px;"
                " font-family:'Courier New',monospace; background:transparent;"
            )
            zig_lbl.setAlignment(Qt.AlignRight)

            cl.addWidget(cap)
            cl.addWidget(usd_lbl)
            cl.addWidget(zig_lbl)
            summary_row.addWidget(card, 1)

            if is_rem:
                self._rem_card    = card
                self._rem_usd_lbl = usd_lbl
                self._rem_zig_lbl = zig_lbl
            else:
                self._paid_usd_lbl = usd_lbl
                self._paid_zig_lbl = zig_lbl

        bl.addLayout(summary_row)

        # ── table ─────────────────────────────────────────────────────────────
        # Visible columns: MODE/ACCOUNT | CURRENCY | PAID (input) | AMOUNT DUE
        # Hidden / commented-out: RATE, BASE VAL
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels([
            "MODE / ACCOUNT", "CURRENCY", "PAID", "AMOUNT DUE",
        ])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Fixed); self._table.setColumnWidth(1, 90)
        hh.setSectionResizeMode(2, QHeaderView.Fixed); self._table.setColumnWidth(2, 160)
        hh.setSectionResizeMode(3, QHeaderView.Fixed); self._table.setColumnWidth(3, 220)

        # Commented-out columns kept for reference:
        # hh.setSectionResizeMode(RATE_COL,     QHeaderView.Fixed); table.setColumnWidth(RATE_COL, 80)
        # hh.setSectionResizeMode(BASE_VAL_COL, QHeaderView.Fixed); table.setColumnWidth(BASE_VAL_COL, 100)

        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background:{WHITE}; border:1px solid {BORDER};
                gridline-color:{LIGHT}; font-size:13px; outline:none;
            }}
            QTableWidget::item           {{ padding:4px 8px; }}
            QTableWidget::item:alternate {{ background:{OFF_WHITE}; }}
            QHeaderView::section {{
                background:{NAVY}; color:{WHITE};
                padding:8px; border:none;
                border-right:1px solid {NAVY_2};
                font-size:11px; font-weight:bold;
            }}
        """)
        bl.addWidget(self._table, 1)

        # ── buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        bclear = QPushButton("Clear All")
        bclear.setFixedHeight(44)
        bclear.setCursor(Qt.PointingHandCursor)
        bclear.setStyleSheet(f"""
            QPushButton {{ background:{LIGHT}; color:{DARK_TEXT}; border:1px solid {BORDER};
                           border-radius:6px; font-size:13px; font-weight:bold; }}
            QPushButton:hover {{ background:{BORDER}; }}
        """)
        bclear.clicked.connect(self._clear_all)

        self._confirm_btn = QPushButton("✅  Confirm Payment")
        self._confirm_btn.setFixedHeight(44)
        self._confirm_btn.setCursor(Qt.PointingHandCursor)
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.setStyleSheet(f"""
            QPushButton {{ background:{SUCCESS}; color:{WHITE}; border:none;
                           border-radius:6px; font-size:13px; font-weight:bold; }}
            QPushButton:hover    {{ background:{SUCCESS_H}; }}
            QPushButton:disabled {{ background:{LIGHT}; color:{MUTED}; }}
        """)
        self._confirm_btn.clicked.connect(self._confirm)

        bcancel = QPushButton("Cancel")
        bcancel.setFixedHeight(44)
        bcancel.setCursor(Qt.PointingHandCursor)
        bcancel.setStyleSheet(f"""
            QPushButton {{ background:{DANGER}; color:{WHITE}; border:none;
                           border-radius:6px; font-size:13px; font-weight:bold; }}
            QPushButton:hover {{ background:{DANGER_H}; }}
        """)
        bcancel.clicked.connect(self.reject)

        btn_row.addWidget(bclear)
        btn_row.addStretch()
        btn_row.addWidget(bcancel)
        btn_row.addWidget(self._confirm_btn)
        bl.addLayout(btn_row)

        root.addWidget(body, 1)

    # =========================================================================
    # Load accounts → populate table
    # =========================================================================

    def _load_accounts(self):
        self._accounts = _load_accounts_for_company(self.company)
        if not self._accounts:
            self._accounts = [
                {"name": "Cash", "account_name": "Cash",
                 "account_type": "Cash",
                 "account_currency": self.company_currency,
                 "company": self.company},
            ]

        validator = QDoubleValidator(0.0, 9999999.99, 4)
        validator.setLocale(QLocale(QLocale.English))

        self._table.setRowCount(0)
        self._editors.clear()

        for acct in self._accounts:
            curr = acct.get("account_currency", self.company_currency).upper()
            rate = _get_rate(curr, self.company_currency)
            self._rate_cache[curr] = rate

            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setRowHeight(r, 46)

            # Col 0 — MODE / ACCOUNT name
            name = acct.get("account_name") or acct.get("name", "")
            name_item = QTableWidgetItem(name)
            name_item.setFont(self._bold_font())
            self._table.setItem(r, 0, name_item)

            # Col 1 — CURRENCY badge
            curr_item = QTableWidgetItem(curr)
            curr_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            curr_item.setForeground(
                QColor(ACCENT if curr == self.company_currency else AMBER)
            )
            curr_item.setFont(self._bold_font())
            self._table.setItem(r, 1, curr_item)

            # Col 2 — PAID input (editable QLineEdit)
            edit = QLineEdit()
            edit.setPlaceholderText("0.00")
            edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            edit.setValidator(validator)
            edit.setStyleSheet(f"""
                QLineEdit {{
                    background:{WHITE}; color:{DARK_TEXT};
                    border:2px solid {BORDER}; border-radius:4px;
                    font-size:14px; font-weight:bold; padding:0 10px;
                    margin: 3px 4px;
                }}
                QLineEdit:focus {{ border:2px solid {ACCENT}; }}
            """)
            edit.textChanged.connect(lambda _, row=r: self._on_amount_changed(row))
            self._table.setCellWidget(r, 2, edit)
            self._editors[r] = (edit, curr, rate)

            # Col 3 — AMOUNT DUE label (live remaining in this row's currency)
            due_item = QTableWidgetItem(self._format_due(curr, rate))
            due_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            due_item.setFont(self._bold_font())
            due_item.setForeground(QColor(DARK_TEXT))
            self._table.setItem(r, 3, due_item)

            # --- Hidden columns (commented out) ---
            # rate_item = QTableWidgetItem(f"{rate:.4f}")
            # self._table.setItem(r, RATE_COL, rate_item)
            # base_item = QTableWidgetItem("0.0000")
            # self._table.setItem(r, BASE_VAL_COL, base_item)

        self._recalc()

    # =========================================================================
    # Live recalc
    # =========================================================================

    def _format_due(self, currency: str, rate: float, remaining_usd: float = None) -> str:
        """Format the AMOUNT DUE cell text for a given row currency."""
        if remaining_usd is None:
            remaining_usd = self.total
        if currency == "ZIG" or (currency != self.company_currency and rate > 0):
            # show in that currency
            if currency == "ZIG":
                val = remaining_usd * self._zig_rate
            else:
                val = remaining_usd / rate if rate else remaining_usd
            return f"{currency}  {val:.2f}\nUSD  {remaining_usd:.2f}"
        return f"USD  {remaining_usd:.2f}\nZIG  {remaining_usd * self._zig_rate:.2f}"

    def _on_amount_changed(self, row: int):
        self._recalc()

    def _recalc(self):
        # Sum all paid amounts converted to USD (company base)
        total_paid_usd = 0.0
        for row, (edit, curr, rate) in self._editors.items():
            try:
                paid = float(edit.text() or "0")
            except ValueError:
                paid = 0.0
            if curr == self.company_currency:
                total_paid_usd += paid
            else:
                total_paid_usd += paid * rate

        remaining_usd = max(self.total - total_paid_usd, 0.0)
        remaining_zig = remaining_usd * self._zig_rate
        paid_zig      = total_paid_usd * self._zig_rate

        # ── summary cards ─────────────────────────────────────────────────────
        self._paid_usd_lbl.setText(f"USD  {total_paid_usd:.2f}")
        self._paid_zig_lbl.setText(f"ZIG  {paid_zig:.2f}")
        self._rem_usd_lbl.setText(f"USD  {remaining_usd:.2f}")
        self._rem_zig_lbl.setText(f"ZIG  {remaining_zig:.2f}")

        # Green when fully settled
        if remaining_usd <= 0.005:
            for lbl in (self._rem_usd_lbl, self._rem_zig_lbl):
                fg = SUCCESS if lbl is self._rem_usd_lbl else SUCCESS
                lbl.setStyleSheet(
                    f"color:{SUCCESS}; font-size:{'20' if lbl is self._rem_usd_lbl else '11'}px;"
                    f" font-weight:bold; font-family:'Courier New',monospace; background:transparent;"
                )
            self._rem_card.setStyleSheet(
                f"QFrame {{ background:{WHITE}; border:2px solid {SUCCESS}; border-radius:8px; }}"
            )
        else:
            self._rem_usd_lbl.setStyleSheet(
                f"color:{DARK_TEXT}; font-size:20px; font-weight:bold;"
                " font-family:'Courier New',monospace; background:transparent;"
            )
            self._rem_zig_lbl.setStyleSheet(
                f"color:{MUTED}; font-size:11px;"
                " font-family:'Courier New',monospace; background:transparent;"
            )
            self._rem_card.setStyleSheet(
                f"QFrame {{ background:{WHITE}; border:2px solid {ACCENT}; border-radius:8px; }}"
            )

        # ── update per-row AMOUNT DUE cells ───────────────────────────────────
        for row, (edit, curr, rate) in self._editors.items():
            item = self._table.item(row, 3)
            if item is None:
                continue
            # Show remaining in the row's own currency + USD equivalent
            if curr == "ZIG":
                item.setText(
                    f"ZIG  {remaining_zig:.2f}   /   USD  {remaining_usd:.2f}"
                )
            elif curr != self.company_currency and rate > 0:
                local_val = remaining_usd / rate
                item.setText(
                    f"{curr}  {local_val:.2f}   /   USD  {remaining_usd:.2f}"
                )
            else:
                item.setText(
                    f"USD  {remaining_usd:.2f}   /   ZIG  {remaining_zig:.2f}"
                )

            # colour: green when zero, dark otherwise
            item.setForeground(QColor(SUCCESS if remaining_usd <= 0.005 else DARK_TEXT))

        self._confirm_btn.setEnabled(total_paid_usd >= self.total - 0.005)

    # =========================================================================
    # Clear
    # =========================================================================

    def _clear_all(self):
        for edit, _, _ in self._editors.values():
            edit.clear()

    # =========================================================================
    # Confirm
    # =========================================================================

    def _confirm(self):
        splits = []
        currency_totals = {}

        for row, (edit, curr, rate) in self._editors.items():
            try:
                paid = float(edit.text() or "0")
            except ValueError:
                paid = 0.0
            if paid <= 0:
                continue

            base = paid * rate if curr != self.company_currency else paid
            acct = self._accounts[row]
            splits.append({
                "account_name":     acct.get("name", ""),
                "account_label":    acct.get("account_name") or acct.get("name", ""),
                "account_currency": curr,
                "mode":             acct.get("account_type", "Cash"),
                "rate":             rate,
                "amount_paid":      paid,
                "base_value":       base,
            })
            currency_totals[curr] = currency_totals.get(curr, 0.0) + base

        if not splits:
            QMessageBox.warning(self, "No Amount",
                                "Please enter at least one payment amount.")
            return

        total_base = sum(s["base_value"] for s in splits)
        if total_base < self.total - 0.005:
            remaining = self.total - total_base
            QMessageBox.warning(
                self, "Insufficient",
                f"Amount still due:\n"
                f"  USD  {remaining:.2f}\n"
                f"  ZIG  {remaining * self._zig_rate:.2f}"
            )
            return

        self.splits            = splits
        self.accepted_change   = max(0.0, total_base - self.total)
        self.accepted_method   = "SPLIT"
        self.accepted_currency = max(currency_totals, key=currency_totals.get)
        self.accept()

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def _lbl(text, color=DARK_TEXT, size=13, bold=False):
        l = QLabel(text)
        w = "bold" if bold else "normal"
        l.setStyleSheet(
            f"color:{color}; font-size:{size}px; font-weight:{w}; background:transparent;"
        )
        return l

    @staticmethod
    def _bold_font():
        from PySide6.QtGui import QFont
        f = QFont(); f.setBold(True)
        return f

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._confirm()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
# =============================================================================
# views/dialogs/sync_dialog.py
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui  import QColor

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
GREEN     = "#1e8449"
AMBER     = "#b7770d"

_TBL_STYLE = f"""
    QTableWidget {{
        background:{WHITE}; border:1px solid {BORDER};
        gridline-color:{LIGHT}; font-size:12px; outline:none;
    }}
    QTableWidget::item           {{ padding:8px 10px; }}
    QTableWidget::item:alternate {{ background:{OFF_WHITE}; }}
    QHeaderView::section {{
        background:{NAVY}; color:{WHITE};
        padding:8px 10px; border:none;
        border-right:1px solid {NAVY_2};
        font-size:11px; font-weight:bold;
    }}
"""


# =============================================================================
# BACKGROUND WORKER
# =============================================================================

class _SyncWorker(QObject):
    progress = Signal(str, str)   # (item_name, status)
    finished = Signal(dict)

    def run(self):
        results = {}

        self.progress.emit("GL Accounts & Rates", "Syncing…")
        try:
            from services.accounts_sync_service import sync_accounts_and_rates
            r = sync_accounts_and_rates()
            results["accounts"] = r.get("accounts", 0)
            results["rates"]    = r.get("rates",    0)
            self.progress.emit("GL Accounts & Rates",
                f"✅ {r.get('accounts',0)} accounts, {r.get('rates',0)} rate(s)")
        except Exception as e:
            results["accounts"] = results["rates"] = 0
            self.progress.emit("GL Accounts & Rates", f"❌ {e}")

        self.progress.emit("Products", "Syncing…")
        try:
            from services.product_sync_windows_service import sync_products_smart
            from services.accounts_sync_service import _get_credentials, _get_host
            api_key, api_secret = _get_credentials()
            r2 = sync_products_smart(api_key, api_secret)
            results["products"] = r2.get("inserted", 0) + r2.get("updated", 0)
            self.progress.emit("Products",
                f"✅ {r2.get('inserted',0)} new, {r2.get('updated',0)} updated")
        except Exception as e:
            results["products"] = 0
            self.progress.emit("Products", f"❌ {e}")

        self.progress.emit("Customers", "Syncing…")
        try:
            from services.customer_sync_service import sync_customers
            sync_customers()
            results["customers"] = "done"
            self.progress.emit("Customers", "✅ Synced")
        except Exception as e:
            results["customers"] = 0
            self.progress.emit("Customers", f"❌ {e}")

        self.finished.emit(results)


# =============================================================================
# HELPERS
# =============================================================================

def _make_table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setAlternatingRowColors(True)
    t.setStyleSheet(_TBL_STYLE)
    hh = t.horizontalHeader()
    for i in range(len(headers) - 1):
        hh.setSectionResizeMode(i, QHeaderView.ResizeToContents)
    hh.setSectionResizeMode(len(headers) - 1, QHeaderView.Stretch)
    return t


def _cell(text: str, color: str = None, bold: bool = False) -> QTableWidgetItem:
    it = QTableWidgetItem(str(text) if text is not None else "")
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    if color:
        it.setForeground(QColor(color))
    if bold:
        f = it.font(); f.setBold(True); it.setFont(f)
    return it


# =============================================================================
# DIALOG
# =============================================================================

class SyncDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sync")
        self.setMinimumSize(700, 540)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background:{OFF_WHITE}; }}")
        self._thread = None
        self._build()
        self._load_tables()   # show existing data immediately

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QWidget(); hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{NAVY};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20, 0, 20, 0)
        title = QLabel("🔄  Sync with Frappe")
        title.setStyleSheet(
            f"font-size:16px; font-weight:bold; color:{WHITE}; background:transparent;"
        )
        self._close_btn = QPushButton("✕  Close")
        self._close_btn.setFixedSize(90, 32)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setStyleSheet(f"""
            QPushButton {{ background:{DANGER};color:{WHITE};border:none;
                           border-radius:4px;font-size:12px;font-weight:bold; }}
            QPushButton:hover {{ background:{DANGER_H}; }}
        """)
        self._close_btn.clicked.connect(self.reject)
        hl.addWidget(title); hl.addStretch(); hl.addWidget(self._close_btn)
        root.addWidget(hdr)

        # ── Body ──────────────────────────────────────────────────────────────
        body = QWidget(); body.setStyleSheet(f"background:{OFF_WHITE};")
        bl = QVBoxLayout(body); bl.setContentsMargins(20, 16, 20, 16); bl.setSpacing(12)

        # Sync status strip
        self._status_tbl = _make_table(["Item", "Status"])
        self._status_tbl.setFixedHeight(130)
        self._status_rows = {}
        for name in ["GL Accounts & Rates", "Products", "Customers"]:
            r = self._status_tbl.rowCount()
            self._status_tbl.insertRow(r)
            self._status_tbl.setRowHeight(r, 34)
            self._status_tbl.setItem(r, 0, _cell(name, bold=True))
            self._status_tbl.setItem(r, 1, _cell("—", MUTED))
            self._status_rows[name] = r
        bl.addWidget(self._status_tbl)

        # Sync Now button
        self._sync_btn = QPushButton("🔄  Sync Now")
        self._sync_btn.setFixedHeight(40)
        self._sync_btn.setCursor(Qt.PointingHandCursor)
        self._sync_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT};color:{WHITE};border:none;
                           border-radius:6px;font-size:13px;font-weight:bold; }}
            QPushButton:hover {{ background:{ACCENT_H}; }}
            QPushButton:disabled {{ background:{LIGHT};color:{MUTED}; }}
        """)
        self._sync_btn.clicked.connect(self._start_sync)
        bl.addWidget(self._sync_btn)

        # ── Tabs: GL Accounts | Exchange Rates ────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border:1px solid {BORDER}; background:{WHITE}; }}
            QTabBar::tab {{
                background:{LIGHT}; color:{DARK_TEXT};
                padding:8px 20px; font-size:12px; font-weight:bold;
                border:1px solid {BORDER}; border-bottom:none;
            }}
            QTabBar::tab:selected {{ background:{WHITE}; color:{NAVY}; }}
            QTabBar::tab:hover    {{ background:{BORDER}; }}
        """)

        # GL Accounts tab
        self._accounts_tbl = _make_table(
            ["Account Name", "Type", "Currency", "Company"]
        )
        self._tabs.addTab(self._accounts_tbl, "💳  GL Accounts")

        # Exchange Rates tab
        self._rates_tbl = _make_table(
            ["From", "To", "Rate", "Date"]
        )
        self._tabs.addTab(self._rates_tbl, "💱  Exchange Rates")

        bl.addWidget(self._tabs, 1)

        self._footer = QLabel("")
        self._footer.setStyleSheet(
            f"color:{MUTED}; font-size:11px; background:transparent;"
        )
        bl.addWidget(self._footer)

        root.addWidget(body, 1)

    # ── Load existing data ─────────────────────────────────────────────────────

    def _load_tables(self):
        self._load_accounts()
        self._load_rates()

    def _load_accounts(self):
        self._accounts_tbl.setRowCount(0)
        try:
            from models.gl_account import get_all_accounts
            accounts = get_all_accounts()
            for a in accounts:
                r = self._accounts_tbl.rowCount()
                self._accounts_tbl.insertRow(r)
                self._accounts_tbl.setRowHeight(r, 34)
                self._accounts_tbl.setItem(r, 0, _cell(a.get("account_name") or a.get("name"), bold=True))
                self._accounts_tbl.setItem(r, 1, _cell(a.get("account_type", "")))
                # Currency cell — colour-coded
                curr = a.get("account_currency", "USD")
                curr_color = ACCENT if curr == "USD" else AMBER
                self._accounts_tbl.setItem(r, 2, _cell(curr, color=curr_color, bold=True))
                self._accounts_tbl.setItem(r, 3, _cell(a.get("company", "")))
            self._footer.setText(f"{len(accounts)} account(s) in local DB")
        except Exception as e:
            self._footer.setText(f"Could not load accounts: {e}")

    def _load_rates(self):
        self._rates_tbl.setRowCount(0)
        try:
            from models.exchange_rate import get_all_rates
            rates = get_all_rates()
            for rate in rates:
                r = self._rates_tbl.rowCount()
                self._rates_tbl.insertRow(r)
                self._rates_tbl.setRowHeight(r, 34)
                self._rates_tbl.setItem(r, 0, _cell(rate.get("from_currency", ""), bold=True))
                self._rates_tbl.setItem(r, 1, _cell(rate.get("to_currency",   "")))
                self._rates_tbl.setItem(r, 2, _cell(f"{float(rate.get('rate', 0)):.6f}", color=GREEN, bold=True))
                self._rates_tbl.setItem(r, 3, _cell(rate.get("rate_date", "")))
        except Exception as e:
            pass

    # ── Sync ──────────────────────────────────────────────────────────────────

    def _start_sync(self):
        if self._thread and self._thread.isRunning():
            return

        for name, r in self._status_rows.items():
            self._status_tbl.item(r, 1).setText("Waiting…")
            self._status_tbl.item(r, 1).setForeground(QColor(MUTED))

        self._sync_btn.setEnabled(False)
        self._sync_btn.setText("Syncing…")
        self._close_btn.setEnabled(False)

        self._thread = QThread()
        self._worker = _SyncWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def _on_progress(self, name: str, status: str):
        if name in self._status_rows:
            item = self._status_tbl.item(self._status_rows[name], 1)
            item.setText(status)
            item.setForeground(QColor(
                GREEN  if "✅" in status else
                DANGER if "❌" in status else
                AMBER
            ))

    def _on_finished(self, results: dict):
        self._sync_btn.setEnabled(True)
        self._sync_btn.setText("🔄  Sync Now")
        self._close_btn.setEnabled(True)
        # Refresh both data tables
        self._load_accounts()
        self._load_rates()
        total = results.get("accounts", 0)
        self._footer.setText(
            f"Sync complete — {total} account(s), "
            f"{results.get('rates', 0)} rate(s), "
            f"{results.get('products', 0)} product(s)"
        )
        self._footer.setStyleSheet(
            f"color:{GREEN}; font-size:11px; font-weight:bold; background:transparent;"
        )
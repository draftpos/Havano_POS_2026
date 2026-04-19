from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QWidget,
)

NAVY      = "#0d1f3c"
ACCENT    = "#1a5fb4"
ACCENT_H  = "#1c6dd0"
SUCCESS   = "#1e8449"
SUCCESS_H = "#28a05c"
MUTED     = "#5a7a9a"
WHITE     = "#ffffff"
LIGHT     = "#e4eaf4"
BORDER    = "#c8d8ec"
DARK_TEXT = "#0d1f3c"


_COLUMNS = [
    ("Order No.",  "order_no",      140),
    ("Customer",   "customer_name", 200),
    ("Order Date", "order_date",    100),
    ("Total",      "total",          90),
    ("Deposit",    "deposit_amount", 90),
    ("Balance",    "balance_due",    90),
    ("Status",     "status",         110),
    ("Frappe Ref", "frappe_ref",    160),
]


def _btn(text: str, color: str, hover: str, *, enabled: bool = True) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(36)
    b.setCursor(Qt.PointingHandCursor)
    b.setEnabled(enabled)
    b.setStyleSheet(f"""
        QPushButton {{
            background:{color}; color:{WHITE};
            border:none; border-radius:6px;
            font-size:12px; font-weight:bold; padding:0 14px;
        }}
        QPushButton:hover    {{ background:{hover}; }}
        QPushButton:disabled {{ background:{LIGHT}; color:{MUTED}; }}
    """)
    return b


class SalesOrderListDialog(QDialog):
    """Lists local Sales Orders (synced from Frappe) and lets the cashier
    convert a fully-paid order into a Sales Invoice."""

    def __init__(self, parent: Optional[QWidget] = None, user: Optional[dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Sales Orders")
        self.resize(1100, 620)
        self.setStyleSheet(f"QDialog {{ background:{WHITE}; }}")
        self._user = user or {}
        self._selected_order: Optional[dict] = None
        self._rows_cache: list[dict] = []
        self._build()
        self._reload()

    # ── UI ────────────────────────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Sales Orders")
        title.setStyleSheet(f"font-size:18px; font-weight:bold; color:{NAVY};")
        root.addWidget(title)

        # Action bar
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self._refresh_btn = _btn("Refresh from Frappe", ACCENT, ACCENT_H)
        self._refresh_btn.clicked.connect(self._on_refresh)
        bar.addWidget(self._refresh_btn)

        self._convert_btn = _btn("Convert to Invoice", SUCCESS, SUCCESS_H, enabled=False)
        self._convert_btn.clicked.connect(self._on_convert)
        self._convert_btn.setToolTip("Enabled when the selected order's balance is fully paid.")
        bar.addWidget(self._convert_btn)

        bar.addStretch()

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color:{MUTED}; font-size:12px;")
        bar.addWidget(self._status_lbl)

        close_btn = _btn("Close", MUTED, "#6a8aaa")
        close_btn.clicked.connect(self.reject)
        bar.addWidget(close_btn)

        root.addLayout(bar)

        # Table
        self._tbl = QTableWidget()
        self._tbl.setColumnCount(len(_COLUMNS))
        self._tbl.setHorizontalHeaderLabels([h for h, _k, _w in _COLUMNS])
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setStyleSheet(f"""
            QTableWidget {{
                background:{WHITE}; color:{DARK_TEXT};
                border:1px solid {BORDER}; gridline-color:{LIGHT};
                font-size:12px;
            }}
            QHeaderView::section {{
                background:{NAVY}; color:{WHITE};
                padding:6px 8px; border:none; font-weight:bold;
            }}
        """)
        hh = self._tbl.horizontalHeader()
        for idx, (_h, _k, w) in enumerate(_COLUMNS):
            hh.setSectionResizeMode(idx, QHeaderView.Interactive)
            self._tbl.setColumnWidth(idx, w)
        # Let the Customer column stretch
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        self._tbl.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self._tbl, 1)

    # ── Data ──────────────────────────────────────────────────────────────
    def _reload(self):
        try:
            from models.sales_order import list_orders
            self._rows_cache = list_orders()
        except Exception as e:
            self._rows_cache = []
            self._set_status(f"Load failed: {e}", error=True)

        self._tbl.setRowCount(len(self._rows_cache))
        for r, order in enumerate(self._rows_cache):
            for c, (_h, key, _w) in enumerate(_COLUMNS):
                val = order.get(key, "")
                if key in ("total", "deposit_amount", "balance_due"):
                    try:
                        val = f"{float(val or 0):,.2f}"
                    except Exception:
                        val = str(val)
                it = QTableWidgetItem(str(val) if val is not None else "")
                if key in ("total", "deposit_amount", "balance_due"):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                # Colour the balance cell green when fully paid
                if key == "balance_due":
                    try:
                        if float(order.get("balance_due") or 0) <= 0.005:
                            it.setForeground(QColor(SUCCESS))
                            f = it.font(); f.setBold(True); it.setFont(f)
                    except Exception:
                        pass
                self._tbl.setItem(r, c, it)

        self._selected_order = None
        self._convert_btn.setEnabled(False)
        self._set_status(f"{len(self._rows_cache)} order(s) loaded.")

    def _on_selection_changed(self):
        rows = self._tbl.selectionModel().selectedRows() if self._tbl.selectionModel() else []
        if not rows:
            self._selected_order = None
            self._convert_btn.setEnabled(False)
            return
        idx = rows[0].row()
        if 0 <= idx < len(self._rows_cache):
            self._selected_order = self._rows_cache[idx]
            self._update_convert_enabled()

    def _update_convert_enabled(self):
        order = self._selected_order or {}
        bal    = float(order.get("balance_due") or 0)
        status = (order.get("status") or "").lower()
        can_convert = (bal <= 0.005) and status not in ("completed", "cancelled")
        self._convert_btn.setEnabled(can_convert)

    # ── Actions ───────────────────────────────────────────────────────────
    def _on_refresh(self):
        self._set_status("Pulling from Frappe…")
        self._refresh_btn.setEnabled(False)
        try:
            from services.sales_order_pull_service import pull_sales_orders_from_frappe
            res = pull_sales_orders_from_frappe()
            msg = f"Pulled: scanned={res.get('scanned',0)} updated={res.get('updated',0)}"
            if res.get("errors"):
                msg += f" errors={res['errors']}"
            self._set_status(msg)
        except Exception as e:
            self._set_status(f"Pull failed: {e}", error=True)
        finally:
            self._refresh_btn.setEnabled(True)
            self._reload()

    def _on_convert(self):
        order = self._selected_order
        if not order:
            return
        bal = float(order.get("balance_due") or 0)
        if bal > 0.005:
            QMessageBox.warning(self, "Not Ready",
                f"Order {order.get('order_no','?')} still has a balance of {bal:.2f}.")
            return
        reply = QMessageBox.question(
            self, "Convert to Invoice",
            f"Convert order {order.get('order_no','?')} into a Sales Invoice?\n"
            f"Customer: {order.get('customer_name','—')}\n"
            f"Total:    {float(order.get('total',0)):,.2f}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        self._convert_btn.setEnabled(False)
        try:
            from models.sales_order import convert_order_to_sale
            sale = convert_order_to_sale(
                int(order["id"]),
                cashier_id   = self._user.get("id")       if isinstance(self._user, dict) else None,
                cashier_name = self._user.get("username") if isinstance(self._user, dict) else "",
            )
        except Exception as e:
            QMessageBox.critical(self, "Convert Failed", f"Could not convert order:\n{e}")
            return

        if not sale:
            QMessageBox.warning(self, "Convert Failed",
                "Order could not be converted. Check the logs for details.")
            return

        QMessageBox.information(self, "Invoice Created",
            f"Invoice {sale.get('invoice_no','?')} created from "
            f"order {order.get('order_no','?')}.")
        self._reload()

    # ── Status helpers ────────────────────────────────────────────────────
    def _set_status(self, text: str, error: bool = False):
        col = "#b02020" if error else MUTED
        self._status_lbl.setStyleSheet(f"color:{col}; font-size:12px;")
        self._status_lbl.setText(text)
        if not error:
            QTimer.singleShot(4000, lambda: self._status_lbl.setText(""))

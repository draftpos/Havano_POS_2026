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
    ("#",             "order_badge",    60),
    ("Payment Mode",  "name",           220),
    ("GL Account",    "gl_account",     260),
    ("Currency",      "account_currency", 90),
    ("Rate → USD",    "rate_to_usd",    120),
    ("Enabled",       "enabled",        80),
]


def _btn(text: str, color: str, hover: str, *, enabled: bool = True) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(34)
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


def _fetch_rate_to_usd(currency: str) -> float:
    """Best-effort lookup of the native→USD rate from local exchange_rates.
    Returns 1.0 for USD, 0.0 when no rate is stored."""
    curr = (currency or "").strip().upper()
    if curr == "USD" or not curr:
        return 1.0
    try:
        from models.exchange_rate import get_rate
        r = get_rate(curr, "USD")
        return float(r or 0.0)
    except Exception:
        return 0.0


class PaymentModesDialog(QDialog):
    """Manage Modes of Payment — reorder them (top = default in the POS
    payment dialog) and edit the exchange rate to USD. MOP names, GL accounts
    and currency come from Frappe and are read-only here."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Payment Modes")
        self.resize(1000, 600)
        self.setStyleSheet(f"QDialog {{ background:{WHITE}; }}")
        self._rows: list[dict] = []
        self._build()
        self._reload()

    # ── UI ────────────────────────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Payment Modes")
        title.setStyleSheet(f"font-size:18px; font-weight:bold; color:{NAVY};")
        root.addWidget(title)

        hint = QLabel(
            "The topmost mode is the default selection in the POS payment "
            "dialog. Use ↑ / ↓ to re-order. Rates are used for non-USD "
            "conversions when printing receipts and pushing to Frappe."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{MUTED}; font-size:12px;")
        root.addWidget(hint)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self._up_btn   = _btn("↑  Move Up",   ACCENT,  ACCENT_H,  enabled=False)
        self._down_btn = _btn("↓  Move Down", ACCENT,  ACCENT_H,  enabled=False)
        self._save_btn = _btn("Save",         SUCCESS, SUCCESS_H)
        self._close_btn= _btn("Close",        MUTED,   "#6a8aaa")
        self._up_btn.clicked.connect(lambda: self._move(-1))
        self._down_btn.clicked.connect(lambda: self._move(+1))
        self._save_btn.clicked.connect(self._on_save)
        self._close_btn.clicked.connect(self.reject)
        bar.addWidget(self._up_btn)
        bar.addWidget(self._down_btn)
        bar.addStretch()
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color:{MUTED}; font-size:12px;")
        bar.addWidget(self._status_lbl)
        bar.addWidget(self._save_btn)
        bar.addWidget(self._close_btn)
        root.addLayout(bar)

        # Table
        self._tbl = QTableWidget()
        self._tbl.setColumnCount(len(_COLUMNS))
        self._tbl.setHorizontalHeaderLabels([h for h, _k, _w in _COLUMNS])
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
        hh.setSectionResizeMode(2, QHeaderView.Stretch)   # GL Account stretches
        self._tbl.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self._tbl, 1)

    # ── Data ──────────────────────────────────────────────────────────────
    def _reload(self):
        try:
            from database.db import get_connection, fetchall_dicts
            conn = get_connection()
            cur  = conn.cursor()
            cur.execute("""
                SELECT id, name, gl_account, account_currency,
                       COALESCE(enabled, 1)       AS enabled,
                       COALESCE(display_order, 0) AS display_order
                FROM   modes_of_payment
                ORDER BY display_order, name
            """)
            rows = fetchall_dicts(cur)
            conn.close()
        except Exception as e:
            rows = []
            self._set_status(f"Load failed: {e}", error=True)

        self._rows = []
        for r in rows:
            self._rows.append({
                "id":               int(r["id"]),
                "name":             r.get("name") or "",
                "gl_account":       r.get("gl_account") or "",
                "account_currency": (r.get("account_currency") or "USD").upper(),
                "enabled":          bool(r.get("enabled")),
                "display_order":    int(r.get("display_order") or 0),
                "rate_to_usd":      _fetch_rate_to_usd(r.get("account_currency") or "USD"),
            })

        self._render()

    def _render(self):
        self._tbl.setRowCount(len(self._rows))
        for r, row in enumerate(self._rows):
            # #, Name, GL Account, Currency, Rate, Enabled
            self._tbl.setItem(r, 0, self._cell(str(r + 1), align=Qt.AlignCenter, bold=(r == 0)))
            self._tbl.setItem(r, 1, self._cell(row["name"], bold=(r == 0)))
            self._tbl.setItem(r, 2, self._cell(row["gl_account"]))
            self._tbl.setItem(r, 3, self._cell(row["account_currency"], align=Qt.AlignCenter))
            rate = row["rate_to_usd"]
            rate_text = f"{rate:.6f}" if rate else "—"
            rate_cell = self._cell(rate_text, align=Qt.AlignRight | Qt.AlignVCenter)
            rate_cell.setFlags(rate_cell.flags() | Qt.ItemIsEditable)
            self._tbl.setItem(r, 4, rate_cell)
            self._tbl.setItem(r, 5, self._cell("Yes" if row["enabled"] else "No",
                                               align=Qt.AlignCenter))
        self._update_move_enabled()

    def _cell(self, text: str, *, align=Qt.AlignLeft | Qt.AlignVCenter, bold: bool = False) -> QTableWidgetItem:
        it = QTableWidgetItem(text)
        it.setTextAlignment(align)
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        if bold:
            f = it.font(); f.setBold(True); it.setFont(f)
            it.setForeground(QColor(ACCENT))
        return it

    # ── Selection + move ──────────────────────────────────────────────────
    def _current_row(self) -> int:
        rows = self._tbl.selectionModel().selectedRows() if self._tbl.selectionModel() else []
        return rows[0].row() if rows else -1

    def _on_selection_changed(self):
        self._update_move_enabled()

    def _update_move_enabled(self):
        r = self._current_row()
        self._up_btn.setEnabled(r > 0)
        self._down_btn.setEnabled(0 <= r < len(self._rows) - 1)

    def _move(self, delta: int):
        r = self._current_row()
        if r < 0:
            return
        j = r + delta
        if j < 0 or j >= len(self._rows):
            return
        self._rows[r], self._rows[j] = self._rows[j], self._rows[r]
        self._render()
        self._tbl.selectRow(j)

    # ── Save ──────────────────────────────────────────────────────────────
    def _on_save(self):
        # Pull any edits made in the Rate column
        for r, row in enumerate(self._rows):
            cell = self._tbl.item(r, 4)
            if cell is None:
                continue
            txt = cell.text().strip().replace(",", "")
            if txt in ("", "—"):
                row["rate_to_usd"] = 0.0
                continue
            try:
                row["rate_to_usd"] = float(txt)
            except ValueError:
                QMessageBox.warning(self, "Invalid Rate",
                    f"Row {r + 1}: '{txt}' is not a valid number.")
                return

        try:
            from database.db import get_connection
            conn = get_connection()
            cur  = conn.cursor()
            # Rewrite display_order so the visible table order becomes the
            # authoritative sort key for the POS payment dialog.
            for idx, row in enumerate(self._rows):
                cur.execute(
                    "UPDATE modes_of_payment SET display_order = ?, updated_at = SYSDATETIME() WHERE id = ?",
                    (idx + 1, row["id"]),
                )
            conn.commit()
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "Save Failed",
                f"Could not save payment mode order:\n{e}")
            return

        # Persist exchange rates — best-effort, same model the checkout uses.
        try:
            from models.exchange_rate import upsert_rate
            for row in self._rows:
                curr = row["account_currency"]
                rate = float(row.get("rate_to_usd") or 0)
                if curr and curr != "USD" and rate > 0:
                    try:
                        upsert_rate(curr, "USD", rate)
                    except Exception as _re:
                        print(f"[PaymentModes] rate upsert {curr}->USD failed: {_re}")
        except Exception as _re:
            # exchange_rate module missing upsert_rate is non-fatal; order saved above
            print(f"[PaymentModes] rate persistence skipped: {_re}")

        self._set_status("Saved — new order is live on the next payment dialog open.")

    # ── Status helpers ────────────────────────────────────────────────────
    def _set_status(self, text: str, error: bool = False):
        col = "#b02020" if error else MUTED
        self._status_lbl.setStyleSheet(f"color:{col}; font-size:12px;")
        self._status_lbl.setText(text)
        if not error:
            QTimer.singleShot(4000, lambda: self._status_lbl.setText(""))

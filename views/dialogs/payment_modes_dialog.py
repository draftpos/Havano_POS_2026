from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QWidget, QLineEdit, QComboBox
)
from theme import *


_COLUMNS = [
    ("#",             "order_badge",    60),
    ("Payment Mode",  "name",           220),
    ("GL Account",    "gl_account",     260),
    ("Currency",      "account_currency", 90),
    ("Rate -> USD",    "rate_to_usd",    120),
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
    """Best-effort lookup of the native->USD rate from local exchange_rates.
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
    """Manage Modes of Payment - reorder them (top = default in the POS
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
        from views.reports.report_template import ReportTemplate
        import qtawesome as qta
        
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        
        self.report = ReportTemplate("Payment Modes", is_report=False, show_date_filter=False, parent=self)
        self.report.set_headers([h for h, _k, _w in _COLUMNS])
        
        self._tbl = self.report.table
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tbl.itemSelectionChanged.connect(self._on_selection_changed)
        
        hh = self._tbl.horizontalHeader()
        for idx, (_h, _k, w) in enumerate(_COLUMNS):
            hh.setSectionResizeMode(idx, QHeaderView.Interactive)
            self._tbl.setColumnWidth(idx, w)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        
        self._add_btn = self.report.btn_add
        self._add_btn.clicked.connect(self._on_add)
        
        self.report.table.itemDoubleClicked.connect(self._open_edit_dialog)
        
        root.addWidget(self.report)
        
        self._status_lbl = QLabel("")
        root.addWidget(self._status_lbl)

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
            rate_text = f"{rate:.6f}" if rate else "-"
            self._tbl.setItem(r, 4, self._cell(rate_text, align=Qt.AlignRight | Qt.AlignVCenter))
            
            self._tbl.setItem(r, 5, self._cell("Yes" if row["enabled"] else "No", align=Qt.AlignCenter))
            
            # Store row data in the first column for double-click retrieval
            self._tbl.item(r, 0).setData(Qt.UserRole, row)
            
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
        pass

    def _on_add(self):
        # Premium Add Dialog for Payment Mode
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Payment Mode")
        dlg.setFixedWidth(400)
        lay = QVBoxLayout(dlg)
        
        name_f = QLineEdit(); name_f.setPlaceholderText("Mode Name (e.g. Standard Bank)")
        
        gl_lay = QHBoxLayout()
        gl_f = QComboBox()
        gl_f.setPlaceholderText("GL Account")
        gl_add_btn = QPushButton("+")
        gl_add_btn.setFixedSize(32, 32)
        gl_add_btn.setCursor(Qt.PointingHandCursor)
        gl_add_btn.setStyleSheet(f"background-color: {SUCCESS}; color: {WHITE}; border-radius: 4px; font-weight: bold; font-size: 16px;")
        gl_lay.addWidget(gl_f, 1)
        gl_lay.addWidget(gl_add_btn)
        
        curr_lay = QHBoxLayout()
        curr_f = QComboBox()
        curr_f.setPlaceholderText("Currency")
        curr_add_btn = QPushButton("+")
        curr_add_btn.setFixedSize(32, 32)
        curr_add_btn.setCursor(Qt.PointingHandCursor)
        curr_add_btn.setStyleSheet(f"background-color: {SUCCESS}; color: {WHITE}; border-radius: 4px; font-weight: bold; font-size: 16px;")
        curr_lay.addWidget(curr_f, 1)
        curr_lay.addWidget(curr_add_btn)
        
        def reload_gls():
            gl_f.clear()
            try:
                from database.db import get_connection, fetchall_dicts
                conn = get_connection(); cur = conn.cursor()
                cur.execute("SELECT name FROM gl_accounts ORDER BY name")
                gls = fetchall_dicts(cur)
                gl_f.addItems([g["name"] for g in gls])
                conn.close()
            except: pass
            
        def reload_currs():
            curr_f.clear()
            try:
                from database.db import get_connection, fetchall_dicts
                conn = get_connection(); cur = conn.cursor()
                cur.execute("SELECT DISTINCT account_currency FROM gl_accounts WHERE account_currency != ''")
                currs = [r["account_currency"] for r in fetchall_dicts(cur)]
                if "USD" not in currs: currs.insert(0, "USD")
                curr_f.addItems(currs)
                conn.close()
            except: 
                curr_f.addItems(["USD", "ZAR", "EUR", "GBP"])

        reload_gls()
        reload_currs()
        
        def add_new_gl():
            from PySide6.QtWidgets import QInputDialog
            add_dlg = QDialog(dlg)
            add_dlg.setWindowTitle("New GL Account")
            l = QVBoxLayout(add_dlg)
            n_f = QLineEdit(); n_f.setPlaceholderText("Account Name")
            t_f = QComboBox(); t_f.addItems(["Cash", "Bank", "Receivable", "Payable", "Expense", "Income"])
            cur_f = QLineEdit("USD"); cur_f.setPlaceholderText("Currency (e.g. USD)")
            
            l.addWidget(QLabel("Account Name:"))
            l.addWidget(n_f)
            l.addWidget(QLabel("Account Type:"))
            l.addWidget(t_f)
            l.addWidget(QLabel("Currency:"))
            l.addWidget(cur_f)
            
            btns = QHBoxLayout()
            ok = _btn("Save", SUCCESS, SUCCESS_H)
            can = _btn("Cancel", MUTED, "#6a8aaa")
            ok.clicked.connect(add_dlg.accept)
            can.clicked.connect(add_dlg.reject)
            btns.addWidget(can); btns.addWidget(ok)
            l.addLayout(btns)
            
            if add_dlg.exec() == QDialog.Accepted:
                aname = n_f.text().strip()
                if not aname: return
                from models.company_defaults import get_defaults
                comp = get_defaults().get("server_company", "")
                fullname = f"{aname} - {comp}" if comp else aname
                from models.gl_account import upsert_account
                try:
                    upsert_account({
                        "name": fullname,
                        "account_name": aname,
                        "company": comp,
                        "account_type": t_f.currentText(),
                        "account_currency": cur_f.text().strip().upper(),
                        "is_group": 0
                    })
                    reload_gls()
                    idx = gl_f.findText(fullname)
                    if idx >= 0: gl_f.setCurrentIndex(idx)
                    reload_currs()
                    idx_c = curr_f.findText(cur_f.text().strip().upper())
                    if idx_c >= 0: curr_f.setCurrentIndex(idx_c)
                except Exception as e:
                    QMessageBox.warning(dlg, "Error", str(e))
                
        def add_new_curr():
            from PySide6.QtWidgets import QInputDialog
            text, ok = QInputDialog.getText(dlg, "New Currency", "Enter 3-letter currency code (e.g. GBP):")
            if ok and text.strip():
                code = text.strip().upper()
                if curr_f.findText(code) == -1:
                    curr_f.addItem(code)
                curr_f.setCurrentText(code)
                
        gl_add_btn.clicked.connect(add_new_gl)
        curr_add_btn.clicked.connect(add_new_curr)
        
        lay.addWidget(QLabel("Payment Mode Name:"))
        lay.addWidget(name_f)
        lay.addWidget(QLabel("GL Account:"))
        lay.addLayout(gl_lay)
        lay.addWidget(QLabel("Currency:"))
        lay.addLayout(curr_lay)
        
        btns = QHBoxLayout()
        ok = _btn("Create", SUCCESS, SUCCESS_H)
        can = _btn("Cancel", MUTED, "#6a8aaa")
        ok.clicked.connect(dlg.accept)
        can.clicked.connect(dlg.reject)
        btns.addWidget(can); btns.addWidget(ok)
        lay.addLayout(btns)
        
        if dlg.exec() == QDialog.Accepted:
            name = name_f.text().strip()
            gl = gl_f.currentText().strip()
            curr = curr_f.currentText().strip().upper()
            if not name or not gl:
                QMessageBox.warning(self, "Error", "Name and GL Account are required.")
                return
            try:
                from database.db import get_connection
                conn = get_connection(); cur = conn.cursor()
                cur.execute("""
                    INSERT INTO modes_of_payment (name, gl_account, account_currency, enabled, display_order)
                    VALUES (?, ?, ?, 1, 99)
                """, (name, gl, curr))
                conn.commit(); conn.close()
                self._reload()
                self._set_status(f"Mode '{name}' added.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add mode: {e}")

    def _open_edit_dialog(self, item):
        row_idx = item.row()
        mode_data = self._tbl.item(row_idx, 0).data(Qt.UserRole)
        if not mode_data: return
        
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Payment Mode")
        dlg.setFixedWidth(400)
        lay = QVBoxLayout(dlg)
        
        # TOP BUTTONS
        btn_lay = QHBoxLayout()
        can = _btn("Cancel", MUTED, "#6a8aaa")
        can.clicked.connect(dlg.reject)
        
        del_btn = _btn("Delete", DANGER, "#cc2828")
        del_btn.clicked.connect(lambda: dlg.done(99))
        
        save = _btn("Save", SUCCESS, SUCCESS_H)
        save.clicked.connect(dlg.accept)
        
        btn_lay.addWidget(can)
        btn_lay.addWidget(del_btn)
        btn_lay.addStretch()
        btn_lay.addWidget(save)
        lay.addLayout(btn_lay)
        
        # FIELDS
        from PySide6.QtWidgets import QCheckBox
        name_f = QLineEdit(mode_data.get("name", ""))
        gl_f = QLineEdit(mode_data.get("gl_account", ""))
        curr_f = QLineEdit(mode_data.get("account_currency", "USD"))
        rate = mode_data.get("rate_to_usd", 1.0)
        rate_f = QLineEdit(f"{rate:.6f}" if rate else "1.000000")
        
        enabled_chk = QCheckBox("Enabled")
        enabled_chk.setChecked(mode_data.get("enabled", True))
        
        lay.addWidget(QLabel("Payment Mode Name:"))
        lay.addWidget(name_f)
        lay.addWidget(QLabel("GL Account:"))
        lay.addWidget(gl_f)
        lay.addWidget(QLabel("Currency:"))
        lay.addWidget(curr_f)
        lay.addWidget(QLabel("Rate to USD:"))
        lay.addWidget(rate_f)
        lay.addWidget(enabled_chk)
        
        res = dlg.exec()
        if res == 99: # Delete
            if QMessageBox.question(self, "Confirm Delete", f"Delete payment mode '{mode_data['name']}'?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                try:
                    from models.payment_mode import delete_payment_mode
                    delete_payment_mode(mode_data["id"])
                    self._reload()
                    self._set_status(f"Mode '{mode_data['name']}' deleted.")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to delete mode: {e}")
        elif res == QDialog.Accepted:
            try:
                r_val = float(rate_f.text().strip() or "1")
            except:
                r_val = 1.0
                
            try:
                from database.db import get_connection
                conn = get_connection(); cur = conn.cursor()
                cur.execute("""
                    UPDATE modes_of_payment 
                    SET name = ?, gl_account = ?, account_currency = ?, enabled = ?, updated_at = SYSDATETIME() 
                    WHERE id = ?
                """, (name_f.text().strip(), gl_f.text().strip(), curr_f.text().strip().upper(), 1 if enabled_chk.isChecked() else 0, mode_data["id"]))
                conn.commit(); conn.close()
                
                # Try to upsert rate
                try:
                    curr_val = curr_f.text().strip().upper()
                    if curr_val and curr_val != "USD" and r_val > 0:
                        from models.exchange_rate import upsert_rate
                        upsert_rate(curr_val, "USD", r_val)
                except Exception as _re: pass
                
                self._reload()
                self._set_status("Payment Mode updated.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update mode: {e}")

    # ── Status helpers ────────────────────────────────────────────────────
    def _set_status(self, text: str, error: bool = False):
        col = "#b02020" if error else MUTED
        self._status_lbl.setStyleSheet(f"color:{col}; font-size:12px;")
        self._status_lbl.setText(text)
        if not error:
            QTimer.singleShot(4000, lambda: self._status_lbl.setText(""))

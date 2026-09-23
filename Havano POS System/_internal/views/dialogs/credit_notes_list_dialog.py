from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QMessageBox, QMainWindow
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from models.credit_note import get_all_credit_notes, get_credit_note_by_id
from theme import *
import qtawesome as qta


class CreditNotesListDialog(QMainWindow):
    """
    Usage:
        dlg = CreditNotesListDialog(dashboard.parent_window)
        dlg.show()
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Credit Notes")
        self.showMaximized()
        self.setStyleSheet(f"QMainWindow {{ background:{WHITE}; }}")

        self._all_cns = []

        import json
        from pathlib import Path
        try:
            settings_data = json.loads(Path("app_data/sql_settings.json").read_text(encoding="utf-8"))
            self._is_offline = (settings_data.get("system_mode") == "offline")
        except Exception:
            self._is_offline = False

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        from views.reports.report_template import ReportTemplate
        self.report = ReportTemplate("Credit Notes", is_report=True, parent=self)
        
        headers = [
            "CN Number", "Date", "Time", "Orig. Invoice", 
            "Customer", "Cashier", "Currency", "Amount $", 
            "Status", "Frappe CN Ref"
        ]
        self.report.set_headers(headers)
        
        self.setCentralWidget(self.report)

        self.report.table.itemSelectionChanged.connect(self._on_selection)
        self.report.table.doubleClicked.connect(self._on_view)

    def _load_data(self):
        self._all_cns = get_all_credit_notes()
        
        data = []
        for cn in self._all_cns:
            status = (cn.get("cn_status") or "").lower()
            if status == "synced":
                status_text = "Synced"
            elif status == "ready":
                status_text = "Ready to Sync"
            else:
                status_text = "Pending"
                
            frappe_ref = (cn.get("frappe_cn_ref") or "").strip()
            
            data.append([
                cn.get("cn_number", ""),
                cn.get("date", ""),
                cn.get("time", ""),
                cn.get("original_invoice_no", ""),
                cn.get("customer_name", ""),
                cn.get("cashier_name", ""),
                cn.get("currency", ""),
                f"{float(cn.get('total', 0)):.2f}",
                status_text,
                frappe_ref if frappe_ref else "-"
            ])
            
        self.report.set_data(data)

        # Apply specific styling to columns
        for r in range(1, self.report.table.rowCount() - 1):
            status_item = self.report.table.item(r, 8)
            frappe_item = self.report.table.item(r, 9)
            
            if status_item:
                status_text = status_item.text().lower()
                status_item.setForeground(QColor(SUCCESS if "synced" in status_text else AMBER))
                f = status_item.font()
                f.setBold(True)
                status_item.setFont(f)
                
            if frappe_item:
                frappe_ref = frappe_item.text()
                frappe_item.setForeground(QColor(MUTED if frappe_ref == "-" else "#1a5fb4"))

        # Hide columns if offline
        if self._is_offline:
            self.report.table.setColumnHidden(8, True)
            self.report.table.setColumnHidden(9, True)

    def _get_selected_cn(self):
        rows = self.report.table.selectionModel().selectedRows()
        if not rows: return None
        
        row = rows[0].row()
        if row == 0 or row == self.report.table.rowCount() - 1:
            return None
            
        cn_item = self.report.table.item(row, 0)
        if not cn_item or not cn_item.text().strip(): return None
        
        cn_number = cn_item.text()
        return next((c for c in self._all_cns if c["cn_number"] == cn_number), None)

    def _on_selection(self):
        has = self._get_selected_cn() is not None

    def _on_view(self):
        cn_stub = self._get_selected_cn()
        if not cn_stub: return
        
        full_cn = get_credit_note_by_id(cn_stub["id"])
        if not full_cn:
            self._msg("Error", "Could not load credit note details.")
            return
            
        items = full_cn.get("items_to_return", [])
        
        msg_text = f"<b>Credit Note:</b> {full_cn['cn_number']}<br>"
        msg_text += f"<b>Original Invoice:</b> {full_cn['original_invoice_no']}<br>"
        msg_text += f"<b>Customer:</b> {full_cn['customer_name']}<br><br>"
        
        msg_text += "<b>Returned Items:</b><br>"
        msg_text += "<table width='100%' border='1' cellspacing='0' cellpadding='4'>"
        msg_text += "<tr bgcolor='#f5f8fc'><th>Item</th><th>Qty</th><th>Amount</th></tr>"
        
        for item in items:
            msg_text += f"<tr><td>{item.get('product_name')}</td>"
            msg_text += f"<td align='center'>{float(item.get('qty', 0))}</td>"
            msg_text += f"<td align='right'>${float(item.get('total', 0)):.2f}</td></tr>"
            
        msg_text += "</table><br>"
        msg_text += f"<div align='right'><b>Total Refund: ${float(full_cn.get('total', 0)):.2f}</b></div>"
        
        m = QMessageBox(self)
        m.setWindowTitle("Credit Note Details")
        m.setText(msg_text)
        m.setStyleSheet(f"""
            QMessageBox {{ background-color:{WHITE}; }}
            QLabel {{ color:{DARK_TEXT};font-size:13px; }}
            QPushButton {{ background-color:{ACCENT};color:{WHITE};border:none;
                           border-radius:6px;padding:8px 20px;min-width:70px; }}
            QPushButton:hover {{ background-color:{ACCENT_H}; }}
        """)
        m.exec()

    def _msg(self, title, text):
        m = QMessageBox(self)
        m.setWindowTitle(title)
        m.setText(text)
        m.setStyleSheet(f"""
            QMessageBox {{ background-color:{WHITE}; }}
            QLabel {{ color:{DARK_TEXT};font-size:13px; }}
            QPushButton {{ background-color:{ACCENT};color:{WHITE};border:none;
                           border-radius:6px;padding:8px 20px;min-width:70px; }}
            QPushButton:hover {{ background-color:{ACCENT_H}; }}
        """)
        m.exec()

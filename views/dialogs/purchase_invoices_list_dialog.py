from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QMessageBox, QWidget
)

from database.db import get_connection, fetchall_dicts
from theme import *
from views.reports.report_template import ReportTemplate

_COLUMNS = [
    ("Invoice No.", "doc_no", 160),
    ("Supplier",    "supplier", 220),
    ("Date & Time", "date_time", 140),
    ("Balance",     "balance", 120),
    ("Status",      "status", 100),
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

class PurchaseInvoicesReport(ReportTemplate):
    def __init__(self, parent_dialog, is_return=False, selection_mode=False):
        self.parent_dialog = parent_dialog
        self.is_return = is_return
        self.selection_mode = selection_mode
        self._rows_cache = []
        
        title_str = "Purchase Returns" if self.is_return else "Purchase Invoices"
        if self.selection_mode:
            title_str = "Select Purchase Invoice to Return"
            
        super().__init__(title_str, is_report=False, show_date_filter=True, parent=parent_dialog)
        self.set_headers([h for h, _, _ in _COLUMNS])
        
        # Action bar buttons
        if not self.selection_mode:
            add_str = " Add New Return" if self.is_return else " Add New Invoice"
            self.btn_add.setText(add_str)
            self.btn_add.clicked.connect(self._on_add_new)
            self.btn_add.show()
            
            self._edit_btn = _btn("Edit", ACCENT, ACCENT_H, enabled=False)
            self._edit_btn.clicked.connect(self._on_edit)
            self.filters_layout.addWidget(self._edit_btn)
            
            self._delete_btn = _btn("Delete", "#b02020", "#cc2828", enabled=False)
            self._delete_btn.clicked.connect(self._on_delete)
            self.filters_layout.addWidget(self._delete_btn)
        
        view_str = "Select for Return" if self.selection_mode else "View Details"
        self._view_btn = _btn(view_str, "#34495e", "#2c3e50", enabled=False)
        self._view_btn.clicked.connect(self._on_view_details)
        self.filters_layout.addWidget(self._view_btn)
        
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_view_details)
        
        self.table.horizontalHeader().setStretchLastSection(False)
        for idx, (_h, _k, w) in enumerate(_COLUMNS):
            if idx in (0, 1):
                self.table.horizontalHeader().setSectionResizeMode(idx, self.table.horizontalHeader().ResizeMode.Stretch)
            else:
                self.table.horizontalHeader().setSectionResizeMode(idx, self.table.horizontalHeader().ResizeMode.Interactive)
                self.table.setColumnWidth(idx, w)
        
        # Rewire refresh
        self.btn_apply.clicked.connect(self._reload)
        self.btn_apply.setText("Refresh")
        
        self._reload()

    def _on_selection_changed(self):
        rows = self.table.selectionModel().selectedRows()
        self._view_btn.setEnabled(len(rows) > 0)
        if not self.selection_mode:
            self._edit_btn.setEnabled(len(rows) > 0)
            self._delete_btn.setEnabled(len(rows) > 0)

    def _reload(self):
        try:
            conn = get_connection()
            cur = conn.cursor()
            if self.selection_mode:
                prefix = "PINV-%"
            else:
                prefix = "PRET-%" if self.is_return else "PINV-%"
            date_from = self.start_date.date().toString("yyyy-MM-dd") + " 00:00:00"
            date_to = self.end_date.date().toString("yyyy-MM-dd") + " 23:59:59"
            cur.execute("""
                SELECT id, doc_no, supplier, date_time, balance, is_paid,
                       warehouse_id, address, supplier_invoice_no, reference,
                       (
                            (SELECT ISNULL(SUM(sei.qty), 0) FROM stock_entry_items sei WHERE sei.parent_id = se.id)
                            -
                            (SELECT ISNULL(SUM(ret_sei.qty), 0)
                             FROM stock_entry_items ret_sei
                             JOIN stock_entries ret_se ON ret_se.id = ret_sei.parent_id
                             WHERE ret_se.source_doc_no = se.doc_no)
                       ) as remaining_qty
                FROM stock_entries se
                WHERE se.doc_no LIKE ? AND se.date_time BETWEEN ? AND ?
                ORDER BY se.id DESC
            """, (prefix, date_from, date_to))
            self._rows_cache = fetchall_dicts(cur)
            conn.close()
        except Exception as e:
            self._rows_cache = []
            
        data_rows = []
        for row in self._rows_cache:
            if str(row.get("doc_no", "")).startswith("PINV-") and row.get("remaining_qty") is not None and row.get("remaining_qty") <= 0:
                row["status"] = "Returned"
            else:
                row["status"] = "Paid" if row.get("is_paid") else "Unpaid"
            
            row_data = []
            for _h, key, _w in _COLUMNS:
                val = row.get(key, "")
                if key == "balance":
                    try: val = f"${float(val or 0):,.2f}"
                    except: val = str(val)
                elif key == "date_time":
                    try: val = val.strftime("%Y-%m-%d %H:%M")
                    except: val = str(val)
                row_data.append(str(val) if val is not None else "")
            data_rows.append(row_data)
            
        self.set_data(data_rows)
        
        # Formatting
        for r in range(1, self.table.rowCount()):
            bal_item = self.table.item(r, 3)
            if bal_item: bal_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            sup_item = self.table.item(r, 1)
            if sup_item: sup_item.setTextAlignment(Qt.AlignCenter)
            
            status_item = self.table.item(r, 4)
            if status_item:
                status_txt = status_item.text()
                if status_txt == "Returned":
                    status_item.setForeground(QColor("#e67e22"))
                    f = status_item.font(); f.setBold(True); status_item.setFont(f)
                elif status_txt == "Paid":
                    status_item.setForeground(QColor(SUCCESS))
                    f = status_item.font(); f.setBold(True); status_item.setFont(f)
                else:
                    status_item.setForeground(QColor("#b02020"))

    def _on_add_new(self):
        if self.is_return:
            sel_dlg = PurchaseInvoicesListDialog(self, selection_mode=True)
            if sel_dlg.exec():
                if sel_dlg.selected_doc_no:
                    from views.dialogs.purchase_invoice_dialog import PurchaseInvoiceDialog
                    dlg = PurchaseInvoiceDialog(self, is_return=True, source_invoice_doc_no=sel_dlg.selected_doc_no)
                    if dlg.exec():
                        self._reload()
        else:
            from views.dialogs.purchase_invoice_dialog import PurchaseInvoiceDialog
            dlg = PurchaseInvoiceDialog(self, is_return=False)
            if dlg.exec():
                self._reload()

    def _on_view_details(self, item=None):
        # When triggered by double-click, item is a QTableWidgetItem — use its row directly.
        # When triggered by the button, item is a boolean (False) — fall back to selectionModel.
        if item is not None and hasattr(item, 'row'):
            idx = item.row()
        else:
            rows = self.table.selectionModel().selectedRows()
            if not rows:
                return
            idx = rows[0].row()
        first_item = self.table.item(idx, 0)
        if not first_item:
            return
            
        doc_no = first_item.text().strip()
        data = next((row for row in getattr(self, "_rows_cache", []) if str(row.get("doc_no", "")).strip() == doc_no), None)
        
        if not data:
            return
        
        if self.selection_mode:
            if data.get("status") == "Returned":
                QMessageBox.warning(self, "Fully Returned", "This invoice has already been fully returned and cannot be returned again.")
                return
            self.parent_dialog.selected_doc_no = data.get("doc_no")
            self.parent_dialog.accept()
            return
            
        try:
            from views.dialogs.purchase_invoice_dialog import PurchaseInvoiceDialog
            dlg = PurchaseInvoiceDialog(self, read_only_data=data, is_return=self.is_return)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load details: {e}")

    def _on_edit(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows: return
        QMessageBox.information(self, "Edit Not Supported", "Editing an existing invoice is restricted to maintain inventory integrity. Please delete the invoice and recreate it.")

    def _on_delete(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows: return
        idx = rows[0].row()
        first_item = self.table.item(idx, 0)
        if not first_item: return
        data = first_item.data(Qt.UserRole)
        if not data: return
        ans = QMessageBox.question(self, "Delete", f"Are you sure you want to delete {data['doc_no']}? This will remove all associated stock entries.", QMessageBox.Yes | QMessageBox.No)
        if ans == QMessageBox.Yes:
            try:
                from database.db import get_connection
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM stock_entry_items WHERE parent_id = ?", (data['id'],))
                cur.execute("DELETE FROM stock_entries WHERE id = ?", (data['id'],))
                conn.commit()
                conn.close()
                self._reload()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete invoice:\n{str(e)}")

class PurchaseInvoicesListDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None, is_return: bool = False, selection_mode: bool = False):
        super().__init__(parent)
        self.is_return = is_return
        self.selection_mode = selection_mode
        self.selected_doc_no = None
        
        if self.selection_mode:
            title_str = "Select Purchase Invoice to Return"
        else:
            title_str = "Purchase Returns" if self.is_return else "Purchase Invoices"
        self.setWindowTitle(title_str)
        
        self.setMinimumSize(850, 600)
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setWindowState(Qt.WindowMaximized)
        self.setStyleSheet(f"QDialog {{ background:{WHITE}; }}")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.report_widget = PurchaseInvoicesReport(self, is_return, selection_mode)
        self.layout.addWidget(self.report_widget)

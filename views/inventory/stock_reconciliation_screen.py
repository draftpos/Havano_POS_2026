import time
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QMessageBox, QAbstractItemView, QFileDialog
)
from PySide6.QtCore import Qt, QStandardPaths
from PySide6.QtGui import QColor, QTextDocument, QPageSize, QPageLayout
from PySide6.QtPrintSupport import QPrinter
from database.db import get_connection, fetchall_dicts
from models.company_defaults import get_defaults
from views.dialogs.pdf_preview_dialog import PdfPreviewDialog
import qtawesome as qta
from theme import *

class StockReconciliationScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {WHITE};")
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        
        from views.reports.report_template import ReportTemplate
        self.report = ReportTemplate("Stock Take", is_report=False, show_date_filter=True, parent=self)
        self.report.set_headers(["Date", "Doc No", "Created By", "Items Count", "Net Variance", "Variance Value"])
        
        self._tbl = self.report.table
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        
        self.report.btn_add.clicked.connect(self._open_add_dialog)
        self._tbl.cellDoubleClicked.connect(self._on_row_double_clicked)
        
        if hasattr(self, '_export_pdf'):
            self.report.btn_pdf.clicked.connect(self._export_pdf)
            
        if hasattr(self, '_export_excel'):
            self.report.btn_excel.clicked.connect(self._export_excel)
            
        if hasattr(self, '_on_search'):
            self.report.global_search.textChanged.connect(self._on_search)
            self._search_input = self.report.global_search

        main_lay.addWidget(self.report, 1)

    def _load_data(self):
        while self._tbl.rowCount() > 1:
            self._tbl.removeRow(1)
        try:
            sql = """
                SELECT se.id as entry_id, se.date, se.doc_no, se.reference, se.created_by,
                       COUNT(sei.id) as items_count, 
                       SUM(sei.qty) as net_variance,
                       SUM(sei.qty * sei.cost_price) as net_variance_value
                FROM stock_entries se
                LEFT JOIN stock_entry_items sei ON se.id = sei.parent_id
                WHERE se.doc_no LIKE 'TAKE-%' OR se.doc_no LIKE 'REC-%' OR se.reference = 'Stock Reconciliation' OR se.reference = 'Stock Take'
                GROUP BY se.id, se.date, se.doc_no, se.reference, se.created_by
                ORDER BY se.date DESC, se.id DESC
            """
            conn = get_connection(); cur = conn.cursor()
            cur.execute(sql)
            rows = fetchall_dicts(cur)
            conn.close()

            for r, row in enumerate(rows, start=1):
                self._tbl.insertRow(r)
                
                items_count = int(row['items_count'] or 0)
                net_var = float(row['net_variance'] or 0)
                net_val = float(row['net_variance_value'] or 0)
                
                comp = get_defaults()
                currency = comp.get('currency', '$')
                
                def _item(val):
                    it = QTableWidgetItem(str(val) if val is not None else "")
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    return it

                first_item = _item(str(row['date']).split(" ")[0])
                first_item.setData(Qt.UserRole, row)
                
                self._tbl.setItem(r, 0, first_item)
                self._tbl.setItem(r, 1, _item(row['doc_no']))
                self._tbl.setItem(r, 2, _item(row.get('created_by', 'Admin')))
                self._tbl.setItem(r, 3, _item(str(items_count)))
                self._tbl.setItem(r, 4, _item(f"{net_var:+.2f}"))
                self._tbl.setItem(r, 5, _item(f"{currency}{net_val:+.2f}"))
                
        except Exception as e:
            print(f"Error loading reconciliations: {e}")

    def _export_pdf(self):
        if self._tbl.rowCount() == 0:
            QMessageBox.information(self, "Empty", "No data to export.")
            return

        try:
            comp = get_defaults()
            c_name = comp.get('company_name', 'Havano POS')
            c_addr = f"{comp.get('address_1', '')} {comp.get('address_2', '')}"
        except:
            c_name, c_addr = "Havano POS", ""

        c_header = f"<div style='font-size: 24px; font-weight: bold; color: {NAVY}; margin:0;'>{c_name}</div>" if c_name.strip() else ""
        a_header = f"<div style='color: #666; margin:0; margin-bottom:10px;'>{c_addr}</div>" if c_addr.strip() else ""

        html = f"""<html><body style="font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 0;">
    <div style="text-align:center; margin-bottom: 10px;">{c_header}{a_header}<div style="font-size: 18px; font-weight: bold; color: {ACCENT}; margin-top: 5px;">Stock Take History</div></div>
    <table width="100%" cellpadding="10" cellspacing="0" style="border-collapse: collapse; font-size: 12px;">
        <thead>
            <tr style="background-color: {NAVY}; color: white; text-align: left;">"""
        headers = ["Date", "Doc No", "Created By", "Items Count", "Net Variance", "Variance Value"]
        for h in headers:
            html += f"<th>{h}</th>"
        html += "</tr></thead><tbody>"

        for r in range(self._tbl.rowCount()):
            bg = OFF_WHITE if r % 2 == 0 else WHITE
            html += f"<tr style='background-color: {bg}; border-bottom: 1px solid #ddd;'>"
            # Skip the Action column which is the last one (index 5)
            for c in range(self._tbl.columnCount() - 1):
                val = self._tbl.item(r, c).text() if self._tbl.item(r, c) else ""
                html += f"<td>{val}</td>"
            html += "</tr>"

        html += """
                </tbody>
            </table>
            <div style="margin-top:40px; font-size:10px; color:#888; text-align:center;">
                Generated by Havano ERP
            </div>
        </body>
        </html>
        """
        
        docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        export_path = os.path.join(docs, f"Stock_Take_History_{int(time.time())}.pdf")

        printer = QPrinter()
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(export_path)
        printer.setFullPage(True)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Landscape)
        from PySide6.QtCore import QMarginsF
        printer.setPageMargins(QMarginsF(10, 2, 10, 10), QPageLayout.Millimeter)

        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(html.replace('\n', '').replace('\r', ''))
        doc.print_(printer)

        try:
            dlg = PdfPreviewDialog(export_path, title="Preview: Stock Take History", parent=self)
            dlg.exec()
        except Exception as e:
            QMessageBox.information(self, "PDF Saved", f"Report saved successfully to:\n{export_path}\n(Preview error: {e})")

    def _export_excel(self):
        if self._tbl.rowCount() == 0:
            QMessageBox.information(self, "Empty", "No data to export.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save Excel", 
            os.path.join(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation), f"Stock_Take_History_{int(time.time())}.csv"), 
            "CSV Files (*.csv)")
            
        if not path: return
        
        try:
            import csv
            headers = ["Date", "Doc No", "Created By", "Items Count", "Net Variance", "Variance Value"]
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for r in range(self._tbl.rowCount()):
                    # Skip Action column
                    row = [self._tbl.item(r, c).text() if self._tbl.item(r, c) else "" for c in range(self._tbl.columnCount() - 1)]
                    writer.writerow(row)
            QMessageBox.information(self, "Success", f"Data exported successfully to\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export Excel:\n{e}")

    def _open_add_dialog(self):
        from views.dialogs.stock_reconciliation_dialog import StockReconciliationDialog
        dlg = StockReconciliationDialog(self.window())
        dlg.exec()
        if hasattr(self, "_load_data"): self._load_data()

    def _on_row_double_clicked(self, row, col):
        item = self._tbl.item(row, 0)
        if not item: return
        data = item.data(Qt.UserRole)
        if not data or 'entry_id' not in data: return
        
        from views.dialogs.stock_reconciliation_dialog import StockReconciliationDialog
        dlg = StockReconciliationDialog(self.window(), entry_id=data['entry_id'])
        dlg.exec()

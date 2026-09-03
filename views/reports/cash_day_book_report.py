from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QFrame, QDateEdit
)
from PySide6.QtCore import Qt, QDate, QStandardPaths
from PySide6.QtGui import QFont, QColor, QTextDocument, QPageSize, QPageLayout
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QMessageBox, QFileDialog
import qtawesome as qta
import os
from database.db import get_connection, fetchall_dicts
from models.company_defaults import get_defaults, get_currency_symbol
from views.dialogs.pdf_preview_dialog import PdfPreviewDialog

class CashDayBookReport(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #f5f8fc;")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 15, 40, 40)
        
        # Header
        hdr_layout = QHBoxLayout()
        title = QLabel("Cash Day Book")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1a5fb4;")
        hdr_layout.addWidget(title)
        hdr_layout.addStretch()
        
        # Date Filters
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setStyleSheet("padding: 5px; font-size: 14px; border: 1px solid #c8d8ec; border-radius: 4px; background: white;")
        
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setStyleSheet("padding: 5px; font-size: 14px; border: 1px solid #c8d8ec; border-radius: 4px; background: white;")
        
        hdr_layout.addWidget(QLabel("From:"))
        hdr_layout.addWidget(self.start_date)
        hdr_layout.addWidget(QLabel("To:"))
        hdr_layout.addWidget(self.end_date)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a5fb4; color: white; border: none;
                border-radius: 4px; padding: 6px 16px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #1c6dd0; }
        """)
        refresh_btn.clicked.connect(self._load_data)
        
        btn_pdf = QPushButton("Preview PDF")
        btn_pdf.setIcon(qta.icon("fa5s.file-pdf", color="#ffffff"))
        btn_pdf.setStyleSheet("background-color: #b02020; color: white; border: none; border-radius: 4px; padding: 6px 16px; font-weight: bold; font-size: 13px;")
        btn_pdf.clicked.connect(self._export_pdf)
        
        btn_excel = QPushButton("Export Excel")
        btn_excel.setIcon(qta.icon("fa5s.file-excel", color="#ffffff"))
        btn_excel.setStyleSheet("background-color: #1a7a3c; color: white; border: none; border-radius: 4px; padding: 6px 16px; font-weight: bold; font-size: 13px;")
        btn_excel.clicked.connect(self._export_excel)

        hdr_layout.addWidget(refresh_btn)
        hdr_layout.addWidget(btn_pdf)
        hdr_layout.addWidget(btn_excel)
        
        layout.addLayout(hdr_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Description", "Amount"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setStyleSheet("""
            QTableWidget { gridline-color: #e4eaf4; border: 1px solid #c8d8ec; background-color: white; font-size: 14px;}
            QHeaderView::section { background-color: #f0e8d0; padding: 8px; border: none; border-right: 1px solid #c8d8ec; font-weight: bold; font-size: 14px; color: #1a5fb4;}
            QTableWidget::item { padding: 8px; }
        """)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        layout.addWidget(self.table)
        
        self._load_data()

    def showEvent(self, event):
        super().showEvent(event)
        self._load_data()

    def _add_row(self, label, amount, is_header=False, is_total=False, indent=0):
        r = self.table.rowCount()
        self.table.insertRow(r)
        
        lbl_item = QTableWidgetItem(" " * (indent * 4) + label)
        sym = get_currency_symbol()
        amt_str = f"{sym}{amount:,.2f}" if amount is not None else ""
        amt_item = QTableWidgetItem(amt_str)
        amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        font = QFont()
        if is_header or is_total:
            font.setBold(True)
        if is_total:
            font.setPointSize(11)
            
        lbl_item.setFont(font)
        amt_item.setFont(font)
        
        if is_total:
            bg_color = QColor("#eaf0f8")
            lbl_item.setBackground(bg_color)
            amt_item.setBackground(bg_color)
        
        self.table.setItem(r, 0, lbl_item)
        self.table.setItem(r, 1, amt_item)

    def _load_data(self):
        from models.supplier_payment import ensure_supplier_payment_table
        ensure_supplier_payment_table()
        
        self.table.setRowCount(0)
        conn = get_connection()
        cur = conn.cursor()
        
        start_d = self.start_date.date().toString("yyyy-MM-dd")
        end_d = self.end_date.date().toString("yyyy-MM-dd")
        
        try:
            # Cash Received
            cur.execute("""
                SELECT method, currency, SUM(amount) as total, SUM(native_amount) as native_total
                FROM (
                    SELECT mode_of_payment as method, ISNULL(amount_usd, paid_amount) as amount, 
                           ISNULL(currency, 'USD') as currency, ISNULL(received_amount, paid_amount) as native_amount
                    FROM payment_entries 
                    WHERE CAST(reference_date AS DATE) BETWEEN ? AND ?
                    
                    UNION ALL
                    
                    SELECT method, amount, 'USD' as currency, amount as native_amount 
                    FROM customer_payments 
                    WHERE CAST(created_at AS DATE) BETWEEN ? AND ?
                ) t
                GROUP BY method, currency
                HAVING SUM(amount) > 0
                ORDER BY method
            """, (start_d, end_d, start_d, end_d))
            received_rows = fetchall_dicts(cur)
            total_in = sum(float(r['total']) for r in received_rows)
            
            # Expenses
            cur.execute("""
                SELECT c.name, ISNULL(SUM(e.amount), 0) as total
                FROM expenses e
                LEFT JOIN expense_categories c ON e.expense_category_id = c.id
                WHERE CAST(e.created_at AS DATE) BETWEEN ? AND ?
                GROUP BY c.name
                HAVING SUM(e.amount) > 0
                ORDER BY c.name
            """, (start_d, end_d))
            expense_rows = fetchall_dicts(cur)
            total_expenses = sum(float(r['total']) for r in expense_rows)
            
            # Supplier Payments
            cur.execute("""
                SELECT method, ISNULL(SUM(amount), 0) as total
                FROM supplier_payments
                WHERE CAST(created_at AS DATE) BETWEEN ? AND ?
                GROUP BY method
                HAVING SUM(amount) > 0
                ORDER BY method
            """, (start_d, end_d))
            supplier_payment_rows = fetchall_dicts(cur)
            total_supplier_payments = sum(float(r['total']) for r in supplier_payment_rows)
            
            cash_balance = total_in - total_expenses - total_supplier_payments
            
            # Build Table
            self._add_row("Total Cash", None, is_header=True)
            self._add_row("Cash Received", None, is_header=True)
            
            valid_received_rows = [r for r in received_rows if float(r['total']) > 0.005]
            if valid_received_rows:
                for row in valid_received_rows:
                    method_name = row['method'] or "Unknown"
                    curr = row['currency'] or "USD"
                    native_tot = float(row['native_total'] or 0)
                    
                    # If it's a non-USD currency, show the local amount in the description
                    if curr.upper() not in ("USD", "US") and native_tot > 0:
                        method_name = f"{method_name} ({curr.upper()} {native_tot:,.2f})"
                        
                    self._add_row(method_name, float(row['total']), indent=1)
                
            self._add_row("Total In", total_in, is_total=True)
            
            self._add_row("", None) # Spacer
            
            self._add_row("Cash Payments", None, is_header=True)
            self._add_row("Expenses", None, is_header=True)
            
            if expense_rows:
                for row in expense_rows:
                    self._add_row(row['name'] or "Uncategorized", float(row['total']), indent=1)
            else:
                self._add_row("No Expenses", 0, indent=1)
                
            self._add_row("Total Expenses", total_expenses, is_total=True)
            self._add_row("", None) # Spacer
            
            self._add_row("Supplier Payments", None, is_header=True)
            if supplier_payment_rows:
                for row in supplier_payment_rows:
                    self._add_row(row['method'] or "Unknown", float(row['total']), indent=1)
            else:
                self._add_row("No Supplier Payments", 0, indent=1)
                
            self._add_row("Total Supplier Payments", total_supplier_payments, is_total=True)
            
            self._add_row("", None) # Spacer
            
            self._add_row("Cash Balance", cash_balance, is_total=True)
            
            # Highlight Cash Balance differently
            r = self.table.rowCount() - 1
            bg_color = QColor("#d4edda") if cash_balance >= 0 else QColor("#f8d7da")
            self.table.item(r, 0).setBackground(bg_color)
            self.table.item(r, 1).setBackground(bg_color)
            
        except Exception as e:
            print("Error loading Cash Day Book:", e)
        finally:
            conn.close()

    def _export_pdf(self):
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "Empty", "No data to export.")
            return

        try:
            comp = get_defaults()
            c_name = comp.get('company_name', 'Havano POS')
            c_addr = f"{comp.get('address_1', '')} {comp.get('address_2', '')}"
        except:
            c_name, c_addr = "Havano POS", ""

        df = self.start_date.date().toString("yyyy-MM-dd")
        dt = self.end_date.date().toString("yyyy-MM-dd")
        period = f"{df} to {dt}"
        title = "Cash Day Book"

        html = f"""<html><body style="font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 0;">
    <div style="text-align:center; margin-bottom: 10px;">
        {f'<div style="font-size: 24px; font-weight: bold; "color: #1a5fb4; margin:0;">{c_name}</div>' if c_name.strip() else ""}
        {f'<div style="color: #666; margin:0; margin-bottom:10px;">{c_addr}</div>' if c_addr.strip() else ""}
        <div style="font-size: 18px; font-weight: bold; "color: #1a5fb4; margin-top: 5px; margin-bottom: 5px;">{title}</div>
        <div style="color: #666; font-size:12px; margin: 0;">Period: {period}</div>
    </div>
    <table width="100%" cellpadding="10" cellspacing="0" style="border-collapse: collapse; font-size: 12px;">
        <thead>
            <tr style="background-color: #1a5fb4; color: white; text-align: left;">
                        <th>Description</th>
                        <th style='text-align:right;'>Amount</th>
                    </tr>
                </thead>
                <tbody>
        """

        for r in range(self.table.rowCount()):
            bg = "#f5f8fc" if r % 2 == 0 else "#ffffff"
            lbl = self.table.item(r, 0).text() if self.table.item(r, 0) else ""
            amt = self.table.item(r, 1).text() if self.table.item(r, 1) else ""
            
            # Format rows based on whether they are bold/headers in the table
            font = self.table.item(r, 0).font() if self.table.item(r, 0) else QFont()
            is_bold = "font-weight:bold;" if font.bold() else ""
            html += f"<tr style='background-color: {bg}; border-bottom: 1px solid #ddd; {is_bold}'>"
            html += f"<td style='text-align:left; color:#333;'>{lbl}</td>"
            html += f"<td style='text-align:right; color:#333;'>{amt}</td>"
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
        export_path = os.path.join(docs, f"{title.replace(' ', '_')}_{df}_{dt}.pdf")

        printer = QPrinter()
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(export_path)
        printer.setFullPage(True)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Portrait)
        from PySide6.QtCore import QMarginsF
        printer.setPageMargins(QMarginsF(10, 2, 10, 10), QPageLayout.Millimeter)

        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(html.replace('\n', '').replace('\r', ''))
        doc.print_(printer)

        try:
            dlg = PdfPreviewDialog(export_path, title=f"Preview: {title}", parent=self)
            dlg.exec()
        except Exception as e:
            QMessageBox.information(self, "PDF Saved", f"Report saved successfully to:\n{export_path}\n(Preview error: {e})")

    def _export_excel(self):
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "Empty", "No data to export.")
            return
            
        docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        df = self.start_date.date().toString("yyyy-MM-dd")
        dt = self.end_date.date().toString("yyyy-MM-dd")
        default_name = f"Cash_Day_Book_{df}_{dt}.csv"
        export_path, _ = QFileDialog.getSaveFileName(self, "Save Excel/CSV", os.path.join(docs, default_name), "CSV Files (*.csv)")
        
        if not export_path:
            return
            
        try:
            import csv
            with open(export_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Description", "Amount"])
                for r in range(self.table.rowCount()):
                    row_data = []
                    for c in range(self.table.columnCount()):
                        item = self.table.item(r, c)
                        row_data.append(item.text().strip() if item else "")
                    writer.writerow(row_data)
            QMessageBox.information(self, "Success", f"Data exported successfully to:\n{export_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export data: {e}")

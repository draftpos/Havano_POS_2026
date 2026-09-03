from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QComboBox, QDateEdit
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
from datetime import datetime

class CashLedgerReport(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #f5f8fc;")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 15, 40, 40)
        
        # Header
        hdr_layout = QHBoxLayout()
        title = QLabel("Cash Ledger Report")
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
        
        # Payment Method Filter
        self.method_combo = QComboBox()
        self.method_combo.setStyleSheet("padding: 5px; font-size: 14px; border: 1px solid #c8d8ec; border-radius: 4px; background: white;")
        
        hdr_layout.addWidget(QLabel("From:"))
        hdr_layout.addWidget(self.start_date)
        hdr_layout.addWidget(QLabel("To:"))
        hdr_layout.addWidget(self.end_date)
        hdr_layout.addWidget(QLabel("Payment Method:"))
        hdr_layout.addWidget(self.method_combo)
        
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
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Date", "Payment Method", "Type", "Debit (In)", "Credit (Out)", "Running Balance"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet("""
            QTableWidget { gridline-color: #e4eaf4; border: 1px solid #c8d8ec; background-color: white; font-size: 14px;}
            QHeaderView::section { background-color: #f0e8d0; padding: 8px; border: none; border-right: 1px solid #c8d8ec; font-weight: bold; font-size: 14px; color: #1a5fb4;}
            QTableWidget::item { padding: 8px; }
        """)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        layout.addWidget(self.table)
        
        self._populate_methods()
        self._load_data()

    def showEvent(self, event):
        super().showEvent(event)
        self._populate_methods()
        self._load_data()

    def _populate_methods(self):
        try:
            if not hasattr(self, "method_combo") or not self.method_combo:
                return
            current = self.method_combo.currentText()
            self.method_combo.clear()
            self.method_combo.addItem("All Payment Methods")
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT name FROM modes_of_payment ORDER BY name")
            rows = fetchall_dicts(cur)
            conn.close()
            for r in rows:
                m_name = str(r.get("name") or "").strip()
                if m_name:
                    self.method_combo.addItem(m_name)
            idx = self.method_combo.findText(current)
            if idx >= 0:
                self.method_combo.setCurrentIndex(idx)
        except Exception as e:
            print(f"[CashLedgerReport] Error populating methods: {e}")

    def _add_row(self, date_str, method, type_str, debit, credit, balance, is_total=False):
        r = self.table.rowCount()
        self.table.insertRow(r)
        
        sym = get_currency_symbol()
        items = [
            QTableWidgetItem(date_str),
            QTableWidgetItem(method),
            QTableWidgetItem(type_str),
            QTableWidgetItem(f"{sym}{debit:,.2f}" if debit is not None else ""),
            QTableWidgetItem(f"{sym}{credit:,.2f}" if credit is not None else ""),
            QTableWidgetItem(f"{sym}{balance:,.2f}" if balance is not None else "")
        ]
        
        font = QFont()
        if is_total:
            font.setBold(True)
            font.setPointSize(11)
            bg_color = QColor("#eaf0f8")
            for item in items:
                item.setFont(font)
                item.setBackground(bg_color)
                
        # Alignment
        items[0].setTextAlignment(Qt.AlignCenter)
        items[1].setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        items[2].setTextAlignment(Qt.AlignCenter)
        items[3].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        items[4].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        items[5].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        for i, item in enumerate(items):
            self.table.setItem(r, i, item)

    def _load_data(self):
        from models.supplier_payment import ensure_supplier_payment_table
        ensure_supplier_payment_table()
        
        self.table.setRowCount(0)
        conn = get_connection()
        cur = conn.cursor()
        
        start_d = self.start_date.date().toString("yyyy-MM-dd")
        end_d = self.end_date.date().toString("yyyy-MM-dd")
        
        try:
            # 1. Income (Debit)
            cur.execute("""
                SELECT CAST(reference_date AS DATE) as t_date, 
                       mode_of_payment as method, 
                       'Sale' as type, 
                       ISNULL(amount_usd, paid_amount) as amount
                FROM payment_entries 
                WHERE CAST(reference_date AS DATE) BETWEEN ? AND ?
                
                UNION ALL
                
                SELECT CAST(created_at AS DATE) as t_date, 
                       method, 
                       'Payment' as type, 
                       amount 
                FROM customer_payments 
                WHERE CAST(created_at AS DATE) BETWEEN ? AND ?
            """, (start_d, end_d, start_d, end_d))
            income_rows = fetchall_dicts(cur)
            
            # 2. Expenses (Credit)
            cur.execute("""
                SELECT CAST(e.created_at AS DATE) as t_date, 
                       'Cash' as method, 
                       'Expense' as type, 
                       ISNULL(e.amount, 0) as amount
                FROM expenses e
                LEFT JOIN expense_categories c ON e.expense_category_id = c.id
                WHERE CAST(e.created_at AS DATE) BETWEEN ? AND ?
            """, (start_d, end_d))
            expense_rows = fetchall_dicts(cur)
            
            # 3. Supplier Payments (Credit)
            cur.execute("""
                SELECT CAST(created_at AS DATE) as t_date, 
                       method, 
                       'Supplier Payment' as type, 
                       ISNULL(amount, 0) as amount
                FROM supplier_payments
                WHERE CAST(created_at AS DATE) BETWEEN ? AND ?
            """, (start_d, end_d))
            supplier_payment_rows = fetchall_dicts(cur)
            
            # Combine and sort
            transactions = []
            for r in income_rows:
                transactions.append({
                    'date': r['t_date'],
                    'method': r['method'] or 'Unknown',
                    'type': r['type'],
                    'debit': float(r['amount']),
                    'credit': 0.0
                })
                
            for r in expense_rows:
                transactions.append({
                    'date': r['t_date'],
                    'method': r['method'],
                    'type': r['type'],
                    'debit': 0.0,
                    'credit': float(r['amount'])
                })
                
            for r in supplier_payment_rows:
                transactions.append({
                    'date': r['t_date'],
                    'method': r['method'] or 'Unknown',
                    'type': r['type'],
                    'debit': 0.0,
                    'credit': float(r['amount'])
                })
                
            transactions.sort(key=lambda x: x['date'])
            
            # Running Balance
            running_balance = 0.0
            total_debit = 0.0
            total_credit = 0.0
            
            for t in transactions:
                # Filter out zero-amount transactions
                if t['debit'] < 0.005 and t['credit'] < 0.005:
                    continue
                    
                running_balance += t['debit']
                running_balance -= t['credit']
                total_debit += t['debit']
                total_credit += t['credit']
                
                # Format date string
                dt_str = str(t['date'])
                if len(dt_str) >= 10:
                    dt_str = dt_str[:10]
                    
                self._add_row(
                    dt_str, 
                    t['method'], 
                    t['type'], 
                    t['debit'] if t['debit'] > 0 else None, 
                    t['credit'] if t['credit'] > 0 else None, 
                    running_balance
                )
                
            self._add_row("TOTAL", "", "", total_debit, total_credit, running_balance, is_total=True)
            
        except Exception as e:
            print(f"[CashLedgerReport] Error loading data: {e}")
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
        title = "Cash Ledger Report"

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
                        <th style='text-align:center;'>Date</th>
                        <th style='text-align:left;'>Method</th>
                        <th style='text-align:center;'>Type</th>
                        <th style='text-align:right;'>Debit</th>
                        <th style='text-align:right;'>Credit</th>
                        <th style='text-align:right;'>Balance</th>
                    </tr>
                </thead>
                <tbody>
        """

        for r in range(self.table.rowCount()):
            bg = "#f5f8fc" if r % 2 == 0 else "#ffffff"
            date_str = self.table.item(r, 0).text() if self.table.item(r, 0) else ""
            method = self.table.item(r, 1).text() if self.table.item(r, 1) else ""
            type_str = self.table.item(r, 2).text() if self.table.item(r, 2) else ""
            debit = self.table.item(r, 3).text() if self.table.item(r, 3) else ""
            credit = self.table.item(r, 4).text() if self.table.item(r, 4) else ""
            balance = self.table.item(r, 5).text() if self.table.item(r, 5) else ""
            
            # Format rows based on whether they are bold/headers in the table
            font = self.table.item(r, 0).font() if self.table.item(r, 0) else QFont()
            is_bold = "font-weight:bold;" if font.bold() else ""
            html += f"<tr style='background-color: {bg}; border-bottom: 1px solid #ddd; {is_bold}'>"
            html += f"<td style='text-align:center; color:#333;'>{date_str}</td>"
            html += f"<td style='text-align:left; color:#333;'>{method}</td>"
            html += f"<td style='text-align:center; color:#333;'>{type_str}</td>"
            html += f"<td style='text-align:right; color:#333;'>{debit}</td>"
            html += f"<td style='text-align:right; color:#333;'>{credit}</td>"
            html += f"<td style='text-align:right; color:#333;'>{balance}</td>"
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
        default_name = f"Cash_Ledger_Report_{df}_{dt}.csv"
        export_path, _ = QFileDialog.getSaveFileName(self, "Save Excel/CSV", os.path.join(docs, default_name), "CSV Files (*.csv)")
        
        if not export_path:
            return
            
        try:
            import csv
            with open(export_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Date", "Method", "Type", "Debit", "Credit", "Balance"])
                for r in range(self.table.rowCount()):
                    row_data = []
                    for c in range(self.table.columnCount()):
                        item = self.table.item(r, c)
                        row_data.append(item.text().strip() if item else "")
                    writer.writerow(row_data)
            QMessageBox.information(self, "Success", f"Data exported successfully to:\n{export_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export data: {e}")

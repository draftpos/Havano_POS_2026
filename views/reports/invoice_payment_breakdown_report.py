# views/reports/invoice_payment_breakdown_report.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QDateEdit, QLineEdit, QFrame, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, QDate, QStandardPaths
from PySide6.QtGui import QFont, QColor, QTextDocument, QPageSize, QPageLayout
from PySide6.QtPrintSupport import QPrinter
import qtawesome as qta
import os
from database.db import get_connection, fetchall_dicts
from models.company_defaults import get_defaults, get_currency_symbol
from views.dialogs.pdf_preview_dialog import PdfPreviewDialog

class InvoicePaymentBreakdownReport(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #f5f8fc;")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 15, 30, 30)
        layout.setSpacing(15)
        
        # ── Header ─────────────────────────────────────────────────────────────
        hdr_layout = QHBoxLayout()
        title = QLabel("Sales Invoices & Payment Currency Breakdown")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a5fb4;")
        hdr_layout.addWidget(title)
        hdr_layout.addStretch()
        
        # Filters
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setStyleSheet("padding: 5px; font-size: 13px; border: 1px solid #c8d8ec; border-radius: 4px; background: white;")
        
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setStyleSheet("padding: 5px; font-size: 13px; border: 1px solid #c8d8ec; border-radius: 4px; background: white;")
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter Invoice # or Customer...")
        self.search_input.setStyleSheet("padding: 5px; font-size: 13px; border: 1px solid #c8d8ec; border-radius: 4px; background: white; min-width: 200px;")
        self.search_input.textChanged.connect(self._filter_table)
        
        hdr_layout.addWidget(QLabel("From:"))
        hdr_layout.addWidget(self.start_date)
        hdr_layout.addWidget(QLabel("To:"))
        hdr_layout.addWidget(self.end_date)
        hdr_layout.addWidget(self.search_input)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a5fb4; color: white; border: none;
                border-radius: 4px; padding: 6px 14px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #1c6dd0; }
        """)
        refresh_btn.clicked.connect(self._load_data)
        
        btn_pdf = QPushButton("Preview PDF")
        btn_pdf.setIcon(qta.icon("fa5s.file-pdf", color="#ffffff"))
        btn_pdf.setStyleSheet("background-color: #b02020; color: white; border: none; border-radius: 4px; padding: 6px 14px; font-weight: bold; font-size: 13px;")
        btn_pdf.clicked.connect(self._export_pdf)
        
        btn_excel = QPushButton("Export Excel")
        btn_excel.setIcon(qta.icon("fa5s.file-excel", color="#ffffff"))
        btn_excel.setStyleSheet("background-color: #1a7a3c; color: white; border: none; border-radius: 4px; padding: 6px 14px; font-weight: bold; font-size: 13px;")
        btn_excel.clicked.connect(self._export_excel)

        hdr_layout.addWidget(refresh_btn)
        hdr_layout.addWidget(btn_pdf)
        hdr_layout.addWidget(btn_excel)
        
        layout.addLayout(hdr_layout)
        
        # ── KPI Cards ──────────────────────────────────────────────────────────
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(15)
        
        self.lbl_total_invoices = self._create_kpi_card(kpi_layout, "Total Invoices", "0", "#1a5fb4")
        self.lbl_total_sales = self._create_kpi_card(kpi_layout, "Total Sales (Base)", f"{get_currency_symbol()}0.00", "#2e7d32")
        self.lbl_multi_curr_summary = self._create_kpi_card(kpi_layout, "Currencies Collected", "None", "#7b1fa2")
        
        layout.addLayout(kpi_layout)
        
        # ── Data Table ─────────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Invoice #", "Date & Time", "Customer", "Cashier", 
            "Invoice Total (Base)", "Payment Breakdown & Exchange Rates", "Converted Total (Base)", "Change"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        
        self.table.setStyleSheet("""
            QTableWidget { gridline-color: #e4eaf4; border: 1px solid #c8d8ec; background-color: white; font-size: 13px;}
            QHeaderView::section { background-color: #1a5fb4; padding: 8px; border: none; font-weight: bold; font-size: 13px; color: white;}
            QTableWidget::item { padding: 6px; }
        """)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)
        
        self._all_rows_data = []
        self._load_data()

    def _create_kpi_card(self, parent_layout, label_text, val_text, color_hex):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-left: 4px solid {color_hex};
                border: 1px solid #c8d8ec;
                border-radius: 6px;
            }}
        """)
        l = QVBoxLayout(frame)
        l.setContentsMargins(15, 10, 15, 10)
        l.setSpacing(4)
        
        t_lbl = QLabel(label_text)
        t_lbl.setStyleSheet("color: #666; font-size: 12px; font-weight: 500;")
        v_lbl = QLabel(val_text)
        v_lbl.setStyleSheet(f"color: {color_hex}; font-size: 18px; font-weight: bold;")
        
        l.addWidget(t_lbl)
        l.addWidget(v_lbl)
        parent_layout.addWidget(frame)
        return v_lbl

    def showEvent(self, event):
        super().showEvent(event)
        self._load_data()

    def _load_data(self):
        self.table.setRowCount(0)
        self._all_rows_data = []
        
        conn = get_connection()
        cur = conn.cursor()
        
        start_d = self.start_date.date().toString("yyyy-MM-dd") + " 00:00:00"
        end_d = self.end_date.date().toString("yyyy-MM-dd") + " 23:59:59"
        sym = get_currency_symbol()
        
        try:
            # 1. Fetch Sales Invoices
            cur.execute("""
                SELECT id, invoice_no, created_at, customer_name, cashier_name, total, subtotal, tendered, change_amount, currency
                FROM sales
                WHERE created_at BETWEEN ? AND ?
                ORDER BY id DESC
            """, (start_d, end_d))
            sales = fetchall_dicts(cur)
            
            # 2. Fetch Payment Entries breakdown for these sales
            cur.execute("""
                SELECT sale_id, sale_invoice_no, mode_of_payment, currency, 
                       ISNULL(paid_amount, received_amount) as paid_amount, 
                       ISNULL(source_exchange_rate, exchange_rate) as exchange_rate,
                       ISNULL(amount_usd, paid_amount) as amount_usd
                FROM payment_entries
                WHERE created_at BETWEEN ? AND ?
                ORDER BY sale_id DESC, id ASC
            """, (start_d, end_d))
            payments = fetchall_dicts(cur)
            
            # Group payments by sale_id & sale_invoice_no
            pmt_map = {}
            currency_totals = {}
            
            for p in payments:
                sid = p.get("sale_id") or p.get("sale_invoice_no")
                if sid not in pmt_map:
                    pmt_map[sid] = []
                pmt_map[sid].append(p)
                
                curr = str(p.get("currency") or "USD").upper()
                amt = float(p.get("paid_amount") or 0)
                currency_totals[curr] = currency_totals.get(curr, 0.0) + amt
                
            total_sales_base = 0.0
            
            for s in sales:
                sale_id = s.get("id")
                inv_no = str(s.get("invoice_no") or f"INV-{sale_id}")
                date_str = str(s.get("created_at") or "")[:19]
                cust = str(s.get("customer_name") or "Walk-In Customer")
                cashier = str(s.get("cashier_name") or "Cashier")
                total_base = float(s.get("total") or 0)
                change_amt = float(s.get("change_amount") or 0)
                total_sales_base += total_base
                
                # Match payment entries
                pmts = pmt_map.get(sale_id) or pmt_map.get(inv_no) or []
                breakdown_parts = []
                converted_paid_total = 0.0
                
                if pmts:
                    for p in pmts:
                        mop = str(p.get("mode_of_payment") or "Cash")
                        p_curr = str(p.get("currency") or "USD").upper()
                        p_amt = float(p.get("paid_amount") or 0)
                        p_rate = float(p.get("exchange_rate") or 1.0)
                        
                        # Converted value calculation
                        if p_rate > 0 and p_rate != 1.0:
                            p_base = float(p.get("amount_usd") or (p_amt / p_rate))
                            breakdown_parts.append(f"{mop}: {p_curr} {p_amt:,.2f} (Rate: {p_rate:,.4f} -> {sym}{p_base:,.2f})")
                        else:
                            p_base = float(p.get("amount_usd") or p_amt)
                            breakdown_parts.append(f"{mop}: {p_curr} {p_amt:,.2f} ({sym}{p_base:,.2f})")
                        converted_paid_total += p_base
                else:
                    # Fallback to sale method column if no payment entries record
                    method_fallback = str(s.get("method") or "Cash")
                    breakdown_parts.append(f"{method_fallback}: {sym}{total_base:,.2f}")
                    converted_paid_total = total_base
                    
                breakdown_str = " | ".join(breakdown_parts)
                
                row_data = {
                    "inv_no": inv_no,
                    "date_str": date_str,
                    "customer": cust,
                    "cashier": cashier,
                    "total_base": total_base,
                    "breakdown": breakdown_str,
                    "converted_paid": converted_paid_total,
                    "change": change_amt
                }
                self._all_rows_data.append(row_data)
                
            # Update KPI Cards
            self.lbl_total_invoices.setText(str(len(sales)))
            self.lbl_total_sales.setText(f"{sym}{total_sales_base:,.2f}")
            
            curr_summary = ", ".join([f"{c}: {amt:,.2f}" for c, amt in currency_totals.items() if amt > 0])
            self.lbl_multi_curr_summary.setText(curr_summary if curr_summary else "Base Currency Only")
            
            self._render_rows(self._all_rows_data)
            
        except Exception as e:
            print("[InvoicePaymentBreakdownReport] Load error:", e)
        finally:
            conn.close()

    def _render_rows(self, data_list):
        self.table.setRowCount(0)
        sym = get_currency_symbol()
        
        for r_idx, d in enumerate(data_list):
            self.table.insertRow(r_idx)
            
            self.table.setItem(r_idx, 0, QTableWidgetItem(d["inv_no"]))
            self.table.setItem(r_idx, 1, QTableWidgetItem(d["date_str"]))
            self.table.setItem(r_idx, 2, QTableWidgetItem(d["customer"]))
            self.table.setItem(r_idx, 3, QTableWidgetItem(d["cashier"]))
            
            item_tot = QTableWidgetItem(f"{sym}{d['total_base']:,.2f}")
            item_tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r_idx, 4, item_tot)
            
            item_breakdown = QTableWidgetItem(d["breakdown"])
            item_breakdown.setForeground(QColor("#1a5fb4"))
            self.table.setItem(r_idx, 5, item_breakdown)
            
            item_conv = QTableWidgetItem(f"{sym}{d['converted_paid']:,.2f}")
            item_conv.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r_idx, 6, item_conv)
            
            item_chg = QTableWidgetItem(f"{sym}{d['change']:,.2f}")
            item_chg.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r_idx, 7, item_chg)

    def _filter_table(self):
        query = self.search_input.text().strip().lower()
        if not query:
            self._render_rows(self._all_rows_data)
            return
            
        filtered = [
            d for d in self._all_rows_data
            if query in d["inv_no"].lower() or query in d["customer"].lower() or query in d["cashier"].lower() or query in d["breakdown"].lower()
        ]
        self._render_rows(filtered)

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
        title = "Sales Invoices & Payment Currency Breakdown"

        html = f"""<html><body style="font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0;">
    <div style="text-align:center; margin-bottom: 10px;">
        {f'<div style="font-size: 22px; font-weight: bold; color: #1a5fb4; margin:0;">{c_name}</div>' if c_name.strip() else ""}
        {f'<div style="color: #666; margin:0; margin-bottom:10px;">{c_addr}</div>' if c_addr.strip() else ""}
        <div style="font-size: 16px; font-weight: bold; color: #1a5fb4; margin-top: 5px; margin-bottom: 5px;">{title}</div>
        <div style="color: #666; font-size:12px; margin: 0;">Period: {period}</div>
    </div>
    <table width="100%" cellpadding="6" cellspacing="0" style="border-collapse: collapse; font-size: 10px;">
        <thead>
            <tr style="background-color: #1a5fb4; color: white; text-align: left;">
                <th>Invoice #</th>
                <th>Date & Time</th>
                <th>Customer</th>
                <th>Cashier</th>
                <th style='text-align:right;'>Total (Base)</th>
                <th>Payment & Conversion Breakdown</th>
                <th style='text-align:right;'>Converted Paid</th>
            </tr>
        </thead>
        <tbody>
        """

        for r in range(self.table.rowCount()):
            bg = "#f5f8fc" if r % 2 == 0 else "#ffffff"
            inv = self.table.item(r, 0).text() if self.table.item(r, 0) else ""
            dt_s = self.table.item(r, 1).text() if self.table.item(r, 1) else ""
            cust = self.table.item(r, 2).text() if self.table.item(r, 2) else ""
            cash = self.table.item(r, 3).text() if self.table.item(r, 3) else ""
            tot = self.table.item(r, 4).text() if self.table.item(r, 4) else ""
            bd = self.table.item(r, 5).text() if self.table.item(r, 5) else ""
            conv = self.table.item(r, 6).text() if self.table.item(r, 6) else ""

            html += f"<tr style='background-color: {bg}; border-bottom: 1px solid #ddd;'>"
            html += f"<td>{inv}</td><td>{dt_s}</td><td>{cust}</td><td>{cash}</td>"
            html += f"<td style='text-align:right; font-weight:bold;'>{tot}</td>"
            html += f"<td style='color:#1a5fb4;'>{bd}</td>"
            html += f"<td style='text-align:right;'>{conv}</td>"
            html += "</tr>"

        html += """
                </tbody>
            </table>
            <div style="margin-top:20px; font-size:9px; color:#888; text-align:center;">
                Generated by Havano POS Finance Module
            </div>
        </body>
        </html>
        """
        
        docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        export_path = os.path.join(docs, f"Invoice_Payment_Breakdown_{df}_{dt}.pdf")

        printer = QPrinter()
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(export_path)
        printer.setFullPage(True)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Landscape)
        from PySide6.QtCore import QMarginsF
        printer.setPageMargins(QMarginsF(8, 2, 8, 8), QPageLayout.Millimeter)

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
        default_name = f"Invoice_Payment_Breakdown_{df}_{dt}.csv"
        export_path, _ = QFileDialog.getSaveFileName(self, "Save Excel/CSV", os.path.join(docs, default_name), "CSV Files (*.csv)")
        
        if not export_path:
            return
            
        try:
            import csv
            with open(export_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                headers = [self.table.horizontalHeaderItem(c).text() for c in range(self.table.columnCount())]
                writer.writerow(headers)
                
                for r in range(self.table.rowCount()):
                    row_data = []
                    for c in range(self.table.columnCount()):
                        item = self.table.item(r, c)
                        row_data.append(item.text().strip() if item else "")
                    writer.writerow(row_data)
            QMessageBox.information(self, "Success", f"Data exported successfully to:\n{export_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export data: {e}")

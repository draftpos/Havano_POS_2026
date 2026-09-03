import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QDateEdit, QPushButton, QLabel, QTextBrowser, QMessageBox)
from PySide6.QtCore import QDate, Qt, QStandardPaths
from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout
from PySide6.QtPrintSupport import QPrinter
import qtawesome as qta

from models.reports import get_management_report_data
from models.company_defaults import get_defaults
from views.dialogs.pdf_preview_dialog import PdfPreviewDialog

class ManagementReportPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: white;")
        lay = QVBoxLayout(self)
        
        lbl = QLabel("Management Report")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a5fb4;")
        lay.addWidget(lbl)
        
        ctrls = QHBoxLayout()
        d = QDate.currentDate()
        self.dt_from = QDateEdit(d)
        self.dt_to = QDateEdit(d)
        for d_edit in [self.dt_from, self.dt_to]:
            d_edit.setCalendarPopup(True); d_edit.setFixedWidth(120)

        btn_load = QPushButton("  Generate Report")
        btn_load.setIcon(qta.icon("fa5s.sync-alt", color="#ffffff"))
        btn_load.setFixedHeight(34)
        btn_load.setCursor(Qt.PointingHandCursor)
        btn_load.setStyleSheet("""
            QPushButton {
                background: #1a5fb4; color: #ffffff;
                font-weight: bold; font-size: 13px;
                border: none; border-radius: 5px; padding: 0 16px;
            }
            QPushButton:hover   { background: #1451a0; }
            QPushButton:pressed { background: #0f3d80; }
            QPushButton:disabled { background: #6a8fc4; color: #cde; }
        """)
        self._btn_load = btn_load
        btn_load.clicked.connect(self._load_data)

        btn_pdf = QPushButton("  Preview PDF")
        btn_pdf.setIcon(qta.icon("fa5s.file-pdf", color="#ffffff"))
        btn_pdf.setFixedHeight(34)
        btn_pdf.setCursor(Qt.PointingHandCursor)
        btn_pdf.setStyleSheet("""
            QPushButton {
                background-color: #b02020; color: white;
                font-weight: bold; font-size: 13px;
                border: none; border-radius: 5px; padding: 0 16px;
            }
            QPushButton:hover   { background: #911a1a; }
            QPushButton:pressed { background: #6e1212; }
        """)
        btn_pdf.clicked.connect(self._export_pdf)
        
        ctrls.addWidget(QLabel("From:")); ctrls.addWidget(self.dt_from)
        ctrls.addWidget(QLabel("To:")); ctrls.addWidget(self.dt_to)
        ctrls.addWidget(btn_load)
        ctrls.addWidget(btn_pdf)
        ctrls.addStretch()
        lay.addLayout(ctrls)

        # Status label shown while loading
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("font-size: 12px; color: #555; padding: 2px 0;")
        lay.addWidget(self._status_lbl)

        self.browser = QTextBrowser()
        self.browser.setMaximumHeight(340)
        self.browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setStyleSheet("background: #fdfdfd; border: 1px solid #c8d8ec; border-radius: 4px;")
        lay.addWidget(self.browser)
        
        self._load_data()

    def showEvent(self, event):
        super().showEvent(event)
        self._load_data()

    def _load_data(self):
        # Show loading state on button
        self._btn_load.setEnabled(False)
        self._btn_load.setText("  Generating…")
        self._btn_load.setIcon(qta.icon("fa5s.spinner", color="#ffffff"))
        self._status_lbl.setText("⏳ Loading report data...")
        self._status_lbl.setStyleSheet("font-size: 12px; color: #1a5fb4;")
        
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()  # Force UI repaint so the spinner shows

        try:
            df = self.dt_from.date().toString("yyyy-MM-dd")
            dt = self.dt_to.date().toString("yyyy-MM-dd")
            df_py = self.dt_from.date().toPython().isoformat()
            dt_py = self.dt_to.date().toPython().isoformat()

            data = get_management_report_data(df_py, dt_py)
            html = self._build_html(data, df, dt)
            self.browser.setHtml(html)

            self._status_lbl.setText(f"Report loaded for {df} to {dt}")
            self._status_lbl.setStyleSheet("font-size: 12px; color: #1e7e34; font-weight: bold;")
        except Exception as e:
            import traceback
            self._status_lbl.setText(f"Error: {e}")
            self._status_lbl.setStyleSheet("font-size: 12px; color: #b02020; font-weight: bold;")
            self.browser.setHtml(f"<div style='color:red; font-size:14px;'><b>Report Error:</b><br>{e}<br><pre>{traceback.format_exc()}</pre></div>")
        finally:
            self._btn_load.setEnabled(True)
            self._btn_load.setText("  Generate Report")
            self._btn_load.setIcon(qta.icon("fa5s.sync-alt", color="#ffffff"))

    def _export_pdf(self):
        df = self.dt_from.date().toString("yyyy-MM-dd")
        dt = self.dt_to.date().toString("yyyy-MM-dd")
        df_py = self.dt_from.date().toPython().isoformat()
        dt_py = self.dt_to.date().toPython().isoformat()
        
        data = get_management_report_data(df_py, dt_py)
        html = self._build_html(data, df, dt)
        
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(html.replace('\n', '').replace('\r', ''))
        
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        pdf_path = os.path.join(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation), f"Management_Report_{df}_{dt}.pdf")
        printer.setOutputFileName(pdf_path)
        printer.setFullPage(True)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Portrait)
        from PySide6.QtCore import QMarginsF
        printer.setPageMargins(QMarginsF(10, 2, 10, 10), QPageLayout.Millimeter)
        doc.print_(printer)
        
        PdfPreviewDialog(pdf_path, parent=self).exec()

    def _build_html(self, data, df, dt):
        defaults = get_defaults()
        cname = defaults.get("company_name", "Havano POS")

        def fmt(val): return f"{val:,.2f}"

        sales   = data["sales"]
        costing = data["costing"]
        gross   = data["gross_profit"]
        exp     = data["expenses"]
        net     = data["net_profit"]
        orders  = data["orders"]
        avg_inv = data["avg_inv_profit"]
        avg_pct = data["avg_perc_profit"]

        methods_rows = ""
        total_methods = 0.0
        for m, v in data["methods"].items():
            methods_rows += f"<tr><td style='padding:2px 6px;'>{m}</td><td align='right' style='padding:2px 6px;'>{fmt(v)}</td></tr>"
            total_methods += v
        methods_rows += f"<tr style='font-weight:bold; border-top:1px solid #ccc;'><td style='padding:2px 6px;'>Total</td><td align='right' style='padding:2px 6px;'>{fmt(total_methods)}</td></tr>"

        net_color = "#1e7e34" if net >= 0 else "#b02020"

        html = f"""<html><body style="font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; font-size:12px; color:#222; margin: 0; padding:0;">
    <div style='text-align:center; margin:0; font-size:13px; font-weight:bold;'>{cname} &mdash; Management Report</div>
    <div style='text-align:center; margin:0 0 6px 0; color:#666; font-size:11px;'>Period: {df} to {dt}</div>

    <div align='center'>
            <table width='480' cellspacing='0' cellpadding='3'>
                <tr><td width='60%'>Sales</td><td align='right'>{fmt(sales)}</td></tr>
                <tr><td style='color:#555;'>Costing</td><td align='right' style='color:#555;'>({fmt(costing)})</td></tr>
                <tr style='border-top:1px solid #aaa; border-bottom:1px solid #aaa; font-weight:bold;'>
                    <td>Gross Profit</td><td align='right'>{fmt(gross)}</td>
                </tr>
                <tr><td style='color:#555;'>Expenses</td><td align='right' style='color:#555;'>({fmt(exp)})</td></tr>
                <tr style='border-top:1px solid #333; border-bottom:2px solid #333; font-weight:bold; font-size:13px; color:{net_color};'>
                    <td>Net Profit</td><td align='right'>{fmt(net)}</td>
                </tr>
            </table>
            </div>

            <div align='center'>
            <table width='480' cellspacing='0' cellpadding='3' style='margin-top:8px;'>
                <tr><td width='60%' style='color:#555;'>Total Orders</td><td align='right' style='font-weight:bold;'>{orders}</td></tr>
                <tr><td style='color:#555;'>Avg Invoice Profit</td><td align='right' style='font-weight:bold;'>{fmt(avg_inv)}</td></tr>
                <tr><td style='color:#555;'>Avg % Invoice Profit</td><td align='right' style='font-weight:bold;'>{avg_pct:.1f}%</td></tr>
            </table>
            </div>

            <p align='center' style='margin:12px 0 2px 0; font-size:11px; font-weight:bold; color:#333;'>Cash by Payment Method</div>
            <div align='center'>
            <table width='480' cellspacing='0' cellpadding='0' border='0' style='border-collapse:collapse; font-size:12px;'>
                <tr style='background:#f0f0f0; font-weight:bold;'>
                    <td style='padding:4px 6px; border-bottom:1px solid #ccc;'>Method</td>
                    <td align='right' style='padding:4px 6px; border-bottom:1px solid #ccc;'>Amount</td>
                </tr>
                {methods_rows}
            </table>
            </div>
        </body></html>
        """
        return html

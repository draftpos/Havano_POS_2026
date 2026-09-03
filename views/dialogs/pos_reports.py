# =============================================================================
# views/dialogs/pos_reports.py - Requirement 5 (X-Report) & 7 (Sales Items)
#                                + Sales Report with PDF Export
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QDateEdit, QPushButton, QLabel,
    QHeaderView, QTabWidget, QWidget, QMessageBox,
    QComboBox, QFileDialog
)
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout
import qtawesome as qta

from models.reports import get_sales_items_report
from models.shift import get_shift_reports
from database.db import get_connection, fetchall_dicts
from theme import *


class POSReportsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sales Reports")
        self.setWindowState(Qt.WindowMaximized)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self._setup_sales_report_ui(layout)
        
        # Auto-load today's data so the view isn't blank when opened
        self._load_sales_report()

    # ── SALES REPORT UI ────────────────────────────────────────────────
    def _setup_sales_report_ui(self, parent_layout):
        from views.reports.report_template import ReportTemplate
        import qtawesome as qta
        
        self.sr_report = ReportTemplate("Sales Reports", is_report=True, show_date_filter=True, parent=self)
        self.sr_report.set_headers(["Item Code", "Item Name", "Qty Sold", "UoM", "Cost Price", "Selling Price", "Gross Profit", "Warehouse"])
        self.table_sr = self.sr_report.table
        
        # Override the apply button to use our reload
        # btn_apply has no default connections, so we can connect directly without disconnecting.
        self.sr_report.btn_apply.clicked.connect(self._load_sales_report)
        
        # Override PDF button
        try:
            self.sr_report.btn_pdf.clicked.disconnect()
        except Exception:
            pass
        self.sr_report.btn_pdf.clicked.connect(self._export_pdf)
        
        # Keep references to start/end dates
        self.sr_from = self.sr_report.start_date
        self.sr_to = self.sr_report.end_date
        
        self.current_filters = {
            "date_from":    self.sr_from.date().toString("yyyy-MM-dd"),
            "date_to":      self.sr_to.date().toString("yyyy-MM-dd"),
            "warehouse_id": None,
            "user_id":      None,
            "category":     None,
        }

        btn_filter = QPushButton(" Filters...")
        btn_filter.setIcon(qta.icon("fa5s.filter", color="white"))
        btn_filter.setStyleSheet(f"background:{ACCENT}; color:{WHITE}; padding:4px 12px; border-radius:4px; font-weight:bold; font-size:11px;")
        btn_filter.clicked.connect(self._open_filter_dialog)
        
        # Insert filter right next to apply
        self.sr_report.filters_layout.insertWidget(4, btn_filter)

        parent_layout.addWidget(self.sr_report, 1)

        totals = QHBoxLayout()
        self.lbl_total_qty  = QLabel("Total Qty: 0")
        self.lbl_total_cost = QLabel("Total Cost: $0.00")
        self.lbl_total_rev  = QLabel("Total Revenue: $0.00")
        self.lbl_total_gp   = QLabel("Gross Profit: $0.00")
        for lbl in [self.lbl_total_qty, self.lbl_total_cost,
                    self.lbl_total_rev, self.lbl_total_gp]:
            lbl.setStyleSheet(f"color:{NAVY}; font-weight:bold; font-size:13px;")
            totals.addWidget(lbl)
        totals.addStretch()
        parent_layout.addLayout(totals)

    # ── FILTER DIALOG ─────────────────────────────────────────────────────────
    def _open_filter_dialog(self):
        from views.dialogs.sales_report_filter_dialog import SalesReportFilterDialog
        dlg = SalesReportFilterDialog(self.current_filters, self)
        if dlg.exec() == QDialog.Accepted:
            self.current_filters = dlg.get_filters()

            from PySide6.QtCore import QDate
            df = QDate.fromString(self.current_filters.get('date_from'), "yyyy-MM-dd")
            dt = QDate.fromString(self.current_filters.get('date_to'),   "yyyy-MM-dd")
            if df.isValid(): self.sr_from.setDate(df)
            if dt.isValid(): self.sr_to.setDate(dt)

            self._load_sales_report()

    def _populate_sr_combos(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT id, name FROM warehouses ORDER BY name")
            for w in fetchall_dicts(cur):
                self.sr_warehouse.addItem(w['name'], w['id'])
            cur.execute("SELECT id, username FROM users ORDER BY username")
            for u in fetchall_dicts(cur):
                self.sr_user.addItem(u['username'], u['id'])
            cur.execute(
                "SELECT DISTINCT category FROM products "
                "WHERE category IS NOT NULL AND category != '' ORDER BY category"
            )
            for c in cur.fetchall():
                self.sr_category.addItem(c[0], c[0])
            conn.close()
        except Exception:
            pass

    # ── LOAD DATA ─────────────────────────────────────────────────────────────
    def _load_sales_report(self):
        df  = self.sr_from.date().toPython().isoformat()
        dt  = self.sr_to.date().toPython().isoformat()
        wh  = self.current_filters.get('warehouse_id')
        usr = self.current_filters.get('user_id')
        cat = self.current_filters.get('category')

        try:
            conn = get_connection(); cur = conn.cursor()
            sql = """
                SELECT
                    si.part_no,
                    si.product_name,
                    SUM(si.qty)                                    AS total_qty,
                    MAX(si.uom)                                    AS uom,
                    AVG(COALESCE(si.cost_price, p.cost_price, 0)) AS avg_cost,
                    AVG(si.price)                                  AS avg_price,
                    MAX(COALESCE(w.name, 'Main'))                  AS warehouse_name
                FROM sale_items si
                JOIN sales s           ON si.sale_id     = s.id
                LEFT JOIN warehouses w ON s.warehouse_id = w.id
                LEFT JOIN products   p ON si.part_no     = p.part_no
                WHERE s.invoice_date >= ? AND s.invoice_date <= ?
            """
            params = [df, dt]
            if wh  is not None: sql += " AND s.warehouse_id = ?"; params.append(wh)
            if usr is not None: sql += " AND s.cashier_id   = ?"; params.append(usr)
            if cat is not None: sql += " AND p.category     = ?"; params.append(cat)
            sql += " GROUP BY si.part_no, si.product_name ORDER BY si.product_name"

            cur.execute(sql, params)
            rows = fetchall_dicts(cur)
            conn.close()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load sales report:\n{e}")
            return

        while self.table_sr.rowCount() > 1:
            self.table_sr.removeRow(1)

        total_qty = total_cost = total_rev = total_gp = 0.0

        for r, row in enumerate(rows):
            row_idx = self.table_sr.rowCount()
            self.table_sr.insertRow(row_idx)

            qty  = float(row['total_qty']  or 0)
            cost = float(row['avg_cost']   or 0)
            sell = float(row['avg_price']  or 0)
            gp   = (sell - cost) * qty

            total_qty  += qty
            total_cost += cost * qty
            total_rev  += sell * qty
            total_gp   += gp

            def _ci(txt, align=Qt.AlignLeft):
                it = QTableWidgetItem(str(txt))
                it.setTextAlignment(align | Qt.AlignVCenter)
                return it

            self.table_sr.setItem(row_idx, 0, _ci(row['part_no']      or ""))
            self.table_sr.setItem(row_idx, 1, _ci(row['product_name'] or ""))
            self.table_sr.setItem(row_idx, 2, _ci(f"{qty:.2f}",        Qt.AlignCenter))
            self.table_sr.setItem(row_idx, 3, _ci(row['uom']          or "Unit"))
            self.table_sr.setItem(row_idx, 4, _ci(f"${cost:.2f}",      Qt.AlignRight))
            self.table_sr.setItem(row_idx, 5, _ci(f"${sell:.2f}",      Qt.AlignRight))

            gp_item = _ci(f"${gp:.2f}", Qt.AlignRight)
            if   gp > 0: gp_item.setForeground(QColor(SUCCESS))
            elif gp < 0: gp_item.setForeground(QColor(DANGER))
            self.table_sr.setItem(row_idx, 6, gp_item)
            self.table_sr.setItem(row_idx, 7, _ci(row['warehouse_name'] or "Main"))

        self.lbl_total_qty.setText(f"Total Qty: {total_qty:,.2f}")
        self.lbl_total_cost.setText(f"Total Cost: ${total_cost:,.2f}")
        self.lbl_total_rev.setText(f"Total Revenue: ${total_rev:,.2f}")
        self.lbl_total_gp.setText(f"Gross Profit: ${total_gp:,.2f}")

    # ── PDF EXPORT ────────────────────────────────────────────────────────────
    def _export_pdf(self):
        if self.table_sr.rowCount() == 0:
            QMessageBox.information(
                self, "No Data", "Generate the report first before exporting."
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", "Sales_Report.pdf", "PDF Files (*.pdf)"
        )
        if not path:
            return

        try:
            from models.company_defaults import get_defaults
            comp   = get_defaults()
            c_name = comp.get('company_name', 'Havano POS')
            c_addr = f"{comp.get('address_1', '')} {comp.get('address_2', '')}".strip()
        except Exception:
            c_name, c_addr = "Havano POS", ""

        date_range = (
            f"{self.sr_from.date().toString('dd/MM/yyyy')} "
            f"- {self.sr_to.date().toString('dd/MM/yyyy')}"
        )

        # ── Column config: (header label, width%, align, td-padding) ──
        # Widths must add up to 100%
        COLS = [
            ("Item Code",     "10%", "left",   "7px 10px 7px 10px"),
            ("Item Name",     "22%", "left",   "7px 10px 7px 10px"),
            ("Qty Sold",      "8%",  "center", "7px 10px 7px 10px"),
            ("UoM",           "7%",  "center", "7px 10px 7px 10px"),
            ("Cost Price",    "13%", "right",  "7px 14px 7px 6px"),
            ("Selling Price", "13%", "right",  "7px 14px 7px 6px"),
            ("Gross Profit",  "13%", "right",  "7px 14px 7px 6px"),
            ("Warehouse",     "14%", "left",   "7px 10px 7px 10px"),
        ]

        # ── Build header row ──
        header_cells = "".join(
            f"<th width='{w}' align='{a}' "
            f"style='padding:9px 10px; color:white;'>{lbl}</th>"
            for lbl, w, a, _ in COLS
        )

        # ── Build data rows ──
        rows_html = ""
        for r in range(self.table_sr.rowCount()):
            bg = "#f5f8fc" if r % 2 == 0 else "#ffffff"
            cells = ""
            for c, (_, _, aln, pad) in enumerate(COLS):
                val = self.table_sr.item(r, c).text() if self.table_sr.item(r, c) else ""
                cells += (
                    f"<td align='{aln}' "
                    f"style='padding:{pad}; border-bottom:1px solid #e0e8f0;'>"
                    f"{val}</td>"
                )
            rows_html += f"<tr style='background:{bg};'>{cells}</tr>"

        html = f"""<html><body style="font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 0;">

  <!-- ═══ HEADER ═══ -->
  <table width='100%' cellpadding='0' cellspacing='0'>
            <tr>
              <td align='center'>
                <div style='font-size:26px; font-weight:bold; color:#1a5fb4;
                           margin:0 0 6px 0;'>Sales Report</div>
                <div style='font-size:13px; font-weight:bold; color:#1a5fb4;
                           margin:0 0 3px 0;'>{c_name}</div>
                <div style='font-size:11px; color:#444444;
                           margin:0 0 3px 0;'>{c_addr}</div>
                <div style='font-size:11px; color:#5a7a9a;
                           margin:0;'>Period: {date_range}</div>
              </td>
            </tr>
          </table>

          <!-- ═══ DIVIDER ═══ -->
          <table width='100%' cellpadding='0' cellspacing='0'
                 style='border-top:2px solid #1a5fb4; margin:14px 0 20px 0;'>
            <tr><td></td></tr>
          </table>

          <!-- ═══ DATA TABLE ═══ -->
          <table width='100%' cellpadding='0' cellspacing='0'
                 style='border-collapse:collapse; font-size:11px;'>
            <thead>
              <tr style='background:#1a5fb4; color:white;'>
                {header_cells}
              </tr>
            </thead>
            <tbody>
              {rows_html}
            </tbody>
          </table>

          <!-- ═══ TOTALS ═══ -->
          <table width='100%' cellpadding='0' cellspacing='0'
                 style='border-top:2px solid #1a5fb4; margin-top:16px;
                        font-size:12px; font-weight:bold;'>
            <tr>
              <td align='left' style='padding:10px 4px; color:#1a5fb4;'>
                {self.lbl_total_qty.text()}
              </td>
              <td align='left' style='padding:10px 4px; color:#1a5fb4;'>
                {self.lbl_total_cost.text()}
              </td>
              <td align='left' style='padding:10px 4px; color:#1a5fb4;'>
                {self.lbl_total_rev.text()}
              </td>
              <td align='left' style='padding:10px 4px; color:#1a7a3c;'>
                {self.lbl_total_gp.text()}
              </td>
            </tr>
          </table>

          <!-- ═══ FOOTER ═══ -->
          <table width='100%' cellpadding='0' cellspacing='0'
                 style='font-size:10px; color:#5a7a9a; margin-top:40px;'>
            <tr>
              <td align='left'   width='33%'></td>
              <td align='center' width='34%'>Powered by Havano ERP</td>
              <td align='right'  width='33%'>Licensed to {c_name}</td>
            </tr>
          </table>

        </body>
        </html>
        """

        printer = QPrinter()
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        printer.setFullPage(True)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Landscape)
        from PySide6.QtCore import QMarginsF
        printer.setPageMargins(QMarginsF(10, 2, 10, 10), QPageLayout.Millimeter)

        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(html.replace('\n', '').replace('\r', ''))
        doc.print_(printer)

        QMessageBox.information(self, "PDF Saved", f"Report saved to:\n{path}")

    # ── CONSUMED ITEMS REPORT UI ──────────────────────────────────────────────
    def _setup_consumed_items_ui(self, parent_layout):
        from views.reports.report_template import ReportTemplate
        import qtawesome as qta
        
        self.ci_report = ReportTemplate("Consumed Bundle Items Report", is_report=True, show_date_filter=True, parent=self)
        self.ci_report.set_headers(["Parent Bundle", "Component Code", "Component Name", "Total Consumed Qty"])
        self.table_ci = self.ci_report.table
        
        # Override apply
        try:
            self.ci_report.btn_apply.clicked.disconnect()
        except:
            pass
        self.ci_report.btn_apply.clicked.connect(self._load_consumed_items_report)
        
        # Override PDF
        try:
            self.ci_report.btn_pdf.clicked.disconnect()
        except:
            pass
        self.ci_report.btn_pdf.clicked.connect(self._export_consumed_pdf)
        
        # Override Excel
        try:
            self.ci_report.btn_excel.clicked.disconnect()
        except:
            pass
        self.ci_report.btn_excel.clicked.connect(self._export_consumed_excel)
        
        # Keep refs
        self.ci_from = self.ci_report.start_date
        self.ci_to = self.ci_report.end_date

        parent_layout.addWidget(self.ci_report, 1)

    def _load_consumed_items_report(self):
        from models.reports import get_consumed_bundle_items_report
        df = self.ci_from.date().toPython().isoformat()
        dt = self.ci_to.date().toPython().isoformat()
        
        try:
            data = get_consumed_bundle_items_report(df, dt)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load consumed items:\n{e}")
            return
            
        self.table_ci.setRowCount(len(data))
        for r, row in enumerate(data):
            self.table_ci.setItem(r, 0, QTableWidgetItem(row['parent_bundle']))
            self.table_ci.setItem(r, 1, QTableWidgetItem(row['component_part_no']))
            self.table_ci.setItem(r, 2, QTableWidgetItem(row['component_name']))
            
            qty_item = QTableWidgetItem(f"{row['consumed_qty']:.2f}")
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table_ci.setItem(r, 3, qty_item)

    def _export_consumed_pdf(self):
        if self.table_ci.rowCount() == 0:
            QMessageBox.information(self, "No Data", "Generate the report first before exporting.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", "Consumed_Bundle_Items.pdf", "PDF Files (*.pdf)"
        )
        if not path:
            return

        try:
            from models.company_defaults import get_defaults
            comp   = get_defaults()
            c_name = comp.get('company_name', 'Havano POS')
            c_addr = f"{comp.get('address_1', '')} {comp.get('address_2', '')}".strip()
        except Exception:
            c_name, c_addr = "Havano POS", ""

        date_range = f"{self.ci_from.date().toString('dd/MM/yyyy')} - {self.ci_to.date().toString('dd/MM/yyyy')}"

        COLS = [
            ("Parent Bundle",      "35%", "left",   "7px 10px"),
            ("Component Code",     "20%", "left",   "7px 10px"),
            ("Component Name",     "30%", "left",   "7px 10px"),
            ("Consumed Qty",       "15%", "right",  "7px 10px"),
        ]

        header_cells = "".join(f"<th width='{w}' align='{a}' style='padding:9px 10px; color:white;'>{lbl}</th>" for lbl, w, a, _ in COLS)

        rows_html = ""
        for r in range(self.table_ci.rowCount()):
            bg = "#f5f8fc" if r % 2 == 0 else "#ffffff"
            cells = ""
            for c, (_, _, aln, pad) in enumerate(COLS):
                val = self.table_ci.item(r, c).text() if self.table_ci.item(r, c) else ""
                cells += f"<td align='{aln}' style='padding:{pad}; border-bottom:1px solid #e0e8f0;'>{val}</td>"
            rows_html += f"<tr style='background:{bg};'>{cells}</tr>"

        html = f"""<html><body style="font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 0;">
  <table width='100%' cellpadding='0' cellspacing='0'>
            <tr>
              <td align='center'>
                <div style='font-size:26px; font-weight:bold; color:#1a5fb4; margin:0 0 6px 0;'>Consumed Bundle Items Report</div>
                <div style='font-size:13px; font-weight:bold; color:#1a5fb4; margin:0 0 3px 0;'>{c_name}</div>
                <div style='font-size:11px; color:#444444; margin:0 0 3px 0;'>{c_addr}</div>
                <div style='font-size:11px; color:#5a7a9a; margin:0;'>Period: {date_range}</div>
              </td>
            </tr>
          </table>
          <table width='100%' cellpadding='0' cellspacing='0' style='border-top:2px solid #1a5fb4; margin:14px 0 20px 0;'>
            <tr><td></td></tr>
          </table>
          <table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; font-size:11px;'>
            <thead>
              <tr style='background:#1a5fb4; color:white;'>
                {header_cells}
              </tr>
            </thead>
            <tbody>
              {rows_html}
            </tbody>
          </table>
          <table width='100%' cellpadding='0' cellspacing='0' style='font-size:10px; color:#5a7a9a; margin-top:40px;'>
            <tr>
              <td align='left' width='33%'></td>
              <td align='center' width='34%'>Powered by Havano ERP</td>
              <td align='right' width='33%'>Licensed to {c_name}</td>
            </tr>
          </table>
        </body>
        </html>
        """

        printer = QPrinter()
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        printer.setFullPage(True)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Portrait)
        from PySide6.QtCore import QMarginsF
        printer.setPageMargins(QMarginsF(10, 2, 10, 10), QPageLayout.Millimeter)

        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(html.replace('\n', '').replace('\r', ''))
        QMessageBox.information(self, "PDF Saved", f"Report saved to:\n{path}")

    def _export_consumed_excel(self):
        if self.table_ci.rowCount() == 0:
            QMessageBox.information(self, "Empty", "No data to export.")
            return
            
        from PySide6.QtCore import QStandardPaths
        import os
        docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        df = self.ci_from.date().toString("yyyy-MM-dd")
        dt = self.ci_to.date().toString("yyyy-MM-dd")
        default_name = f"Consumed_Bundle_Items_{df}_{dt}.csv"
        
        export_path, _ = QFileDialog.getSaveFileName(self, "Save Excel/CSV", os.path.join(docs, default_name), "CSV Files (*.csv)")
        
        if not export_path:
            return
            
        try:
            import csv
            with open(export_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                headers = ["Parent Bundle", "Component Code", "Component Name", "Total Consumed Qty"]
                writer.writerow(headers)
                for r in range(self.table_ci.rowCount()):
                    row_data = []
                    for c in range(self.table_ci.columnCount()):
                        item = self.table_ci.item(r, c)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
            QMessageBox.information(self, "Success", f"Data exported successfully to:\n{export_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export data: {e}")

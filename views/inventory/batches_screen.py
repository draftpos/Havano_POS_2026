import time
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox, 
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
    QLabel, QDateEdit, QMessageBox, QCompleter, QFileDialog, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate, QStandardPaths
from PySide6.QtGui import QColor, QTextDocument, QPageSize, QPageLayout
from PySide6.QtPrintSupport import QPrinter
from database.db import get_connection, fetchall_dicts
from models.company_defaults import get_defaults
from views.dialogs.pdf_preview_dialog import PdfPreviewDialog
import qtawesome as qta
from theme import *

from PySide6.QtWidgets import QDialog

class AddBatchDialog(QDialog):
    def __init__(self, parent=None, parent_screen=None, batch_data=None):
        super().__init__(parent)
        self.parent_screen = parent_screen
        self.batch_data = batch_data
        self.setWindowTitle("Edit Batch" if batch_data else "Add Batch")
        self.setMinimumWidth(500)
        self._all_products = parent_screen._all_products if parent_screen else []
        self.setup_ui()

    def setup_ui(self):
        main_lay = QVBoxLayout(self)
        
        top_bar = QHBoxLayout()
        lbl_title = QLabel("Edit Batch" if self.batch_data else "Add Batch")
        lbl_title.setStyleSheet(f"color:{NAVY}; font-size:16px; font-weight:bold;")
        top_bar.addWidget(lbl_title)
        top_bar.addStretch()
        
        btn_style = f"color:{WHITE}; padding:6px 14px; border-radius:4px; font-weight:bold; font-size: 12px;"
        
        if self.batch_data:
            btn_del = QPushButton(" Delete")
            btn_del.setIcon(qta.icon("fa5s.trash", color="white"))
            btn_del.setStyleSheet(f"background:#e11d48; {btn_style}")
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.clicked.connect(self._on_delete_batch)
            top_bar.addWidget(btn_del)
            
        btn_add = QPushButton(" Save")
        btn_add.setIcon(qta.icon("fa5s.save", color="white"))
        btn_add.setStyleSheet(f"background:{SUCCESS}; {btn_style}")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(self._on_add_batch)
        top_bar.addWidget(btn_add)
        
        main_lay.addLayout(top_bar)
        
        form_lay = QFormLayout()
        form_lay.setContentsMargins(0, 15, 0, 0)

        edit_style = f"padding:6px; border:1px solid {BORDER}; border-radius:4px; background:white; color:{NAVY}; font-weight:bold;"
        
        self.f_batch_no = QLineEdit()
        self.f_batch_no.setStyleSheet(edit_style)
        
        self.f_mfg_date = QDateEdit()
        self.f_mfg_date.setCalendarPopup(True)
        self.f_mfg_date.setDate(QDate.currentDate())
        self.f_mfg_date.setStyleSheet(edit_style)
        
        self.f_exp_date = QDateEdit()
        self.f_exp_date.setCalendarPopup(True)
        self.f_exp_date.setDate(QDate.currentDate().addYears(1))
        self.f_exp_date.setStyleSheet(edit_style)
        
        self.f_created_by = QLineEdit()
        self.f_created_by.setStyleSheet(edit_style)
        
        current_username = "Admin"
        try:
            if hasattr(self.parent(), "user") and self.parent().user:
                current_username = self.parent().user.get("username", "Admin")
        except:
            pass
            
        self.f_created_by.setText(current_username)
        self.f_created_by.setReadOnly(True)

        self.f_item_code = QComboBox()
        self.f_item_code.setEditable(True)
        self.f_item_code.setStyleSheet(edit_style)
        self.f_item_code.currentTextChanged.connect(self._on_code_changed)

        self.f_item_name = QComboBox()
        self.f_item_name.setEditable(True)
        self.f_item_name.setStyleSheet(edit_style)
        self.f_item_name.currentTextChanged.connect(self._on_name_changed)

        self.f_qty = QLineEdit("0.00")
        self.f_qty.setStyleSheet(edit_style + "background-color: #e2e8f0;")
        self.f_qty.setReadOnly(True)

        # Completers are now handled directly by QComboBox with MatchContains
        self.code_completer = QCompleter()
        self.code_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.code_completer.setFilterMode(Qt.MatchContains)
        self.f_item_code.setCompleter(self.code_completer)

        self.name_completer = QCompleter()
        self.name_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.name_completer.setFilterMode(Qt.MatchContains)
        self.f_item_name.setCompleter(self.name_completer)

        def add_row(label_text, widget):
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color:{NAVY}; font-weight:bold;")
            form_lay.addRow(lbl, widget)

        add_row("Batch Name / No:", self.f_batch_no)
        add_row("Manufacture Date:", self.f_mfg_date)
        add_row("Expiry Date:", self.f_exp_date)
        add_row("Item Code:", self.f_item_code)
        add_row("Item Name:", self.f_item_name)
        add_row("Quantity:", self.f_qty)
        add_row("Created By:", self.f_created_by)

        main_lay.addLayout(form_lay)
        
        self._setup_completers()
        
        if self.batch_data:
            self.f_batch_no.setText(self.batch_data.get('batch_no', ''))
            self.f_item_code.setCurrentText(self.batch_data.get('part_no', ''))
            self.f_item_name.setCurrentText(self.batch_data.get('name', ''))
            self.f_qty.setText(str(self.batch_data.get('qty', '0.00')))
            
            mfg = self.batch_data.get('manufacture_date')
            if mfg: self.f_mfg_date.setDate(QDate.fromString(str(mfg), "yyyy-MM-dd"))
            
            exp = self.batch_data.get('expiry_date')
            if exp: self.f_exp_date.setDate(QDate.fromString(str(exp), "yyyy-MM-dd"))
            
            if self.batch_data.get('created_by'):
                self.f_created_by.setText(str(self.batch_data.get('created_by')))

    def _setup_completers(self):
        codes = [p['part_no'] for p in self._all_products if p.get('part_no')]
        names = [p['name'] for p in self._all_products if p.get('name')]
        
        self.f_item_code.clear()
        self.f_item_code.addItems([""] + codes)
        self.f_item_name.clear()
        self.f_item_name.addItems([""] + names)
        
        from PySide6.QtCore import QStringListModel
        self.code_completer.setModel(QStringListModel(codes))
        self.name_completer.setModel(QStringListModel(names))
        
        for comp in (self.code_completer, self.name_completer):
            popup = comp.popup()
            popup.setStyleSheet(f"background-color:{WHITE}; color:{NAVY}; selection-background-color:{ACCENT}; selection-color:{WHITE};")

    def _on_code_changed(self, text):
        if not self.f_item_code.hasFocus(): return
        match = next((p for p in self._all_products if p.get('part_no') and p['part_no'].upper() == text.strip().upper()), None)
        if match:
            self.f_item_name.setCurrentText(match['name'])

    def _on_name_changed(self, text):
        if not self.f_item_name.hasFocus(): return
        match = next((p for p in self._all_products if p.get('name') and p['name'].lower() == text.strip().lower()), None)
        if match:
            self.f_item_code.setCurrentText(match['part_no'])

    def _on_add_batch(self):
        batch_no = self.f_batch_no.text().strip()
        part_no = self.f_item_code.currentText().strip().upper()
        
        if not batch_no:
            QMessageBox.warning(self, "Validation", "Batch Name / No is required.")
            return
        if not part_no:
            QMessageBox.warning(self, "Validation", "Item Code is required.")
            return

        match = next((p for p in self._all_products if p.get('part_no') and p['part_no'].upper() == part_no), None)
        if not match:
            QMessageBox.warning(self, "Validation", f"Item Code '{part_no}' not found in products.")
            return

        mfg = self.f_mfg_date.date().toString("yyyy-MM-dd")
        exp = self.f_exp_date.date().toString("yyyy-MM-dd")
        created_by = self.f_created_by.text().strip()

        try:
            conn = get_connection(); cur = conn.cursor()
            
            if self.batch_data:
                cur.execute("""
                    UPDATE product_batches 
                    SET batch_no = ?, manufacture_date = ?, expiry_date = ?, product_id = ?, synced = 0
                    WHERE id = ?
                """, (batch_no, mfg, exp, match['id'], self.batch_data['id']))
                msg = f"Batch {batch_no} updated successfully."
            else:
                cur.execute("""
                    INSERT INTO product_batches 
                    (product_id, batch_no, manufacture_date, expiry_date, qty, created_by, synced)
                    VALUES (?, ?, ?, ?, 0, ?, 0)
                """, (match['id'], batch_no, mfg, exp, created_by))
                msg = f"Batch {batch_no} created successfully."
                
            conn.commit(); conn.close()
            
            QMessageBox.information(self, "Success", msg)
            if self.parent_screen:
                self.parent_screen._load_batches()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save batch:\n{e}")

    def _on_delete_batch(self):
        if not self.batch_data: return
        
        reply = QMessageBox.question(self, "Confirm Delete", 
                                   f"Are you sure you want to delete batch {self.batch_data.get('batch_no')}?\nThis will not delete stock, only the batch record.",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("DELETE FROM product_batches WHERE id = ?", (self.batch_data['id'],))
                conn.commit(); conn.close()
                QMessageBox.information(self, "Success", "Batch deleted successfully.")
                if self.parent_screen:
                    self.parent_screen._load_batches()
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete batch:\n{e}")

class BatchesScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {WHITE};")
        self._all_products = []
        self.setup_ui()
        self._load_products()
        self._load_batches()

    def setup_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        
        from views.reports.report_template import ReportTemplate
        self.report = ReportTemplate("Batches", is_report=False, show_date_filter=True, parent=self)
        self.report.set_headers(["Batch #", "Product", "Qty", "Expiry Date", "Notes"])
        
        self.table_batches = self.report.table
        hh = self.table_batches.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for i in [0, 2, 3, 4]: hh.setSectionResizeMode(i, QHeaderView.Fixed)
        self.table_batches.setColumnWidth(0, 150)
        self.table_batches.setColumnWidth(2, 100)
        self.table_batches.setColumnWidth(3, 120)
        self.table_batches.setColumnWidth(4, 200)

        # Filters
        self.combo_product = QComboBox()
        self.combo_product.setFixedWidth(200)
        self.combo_product.addItem("- All Products -", None)
        self.combo_product.currentIndexChanged.connect(self._load_batches)
        self.report.filters_layout.insertWidget(4, self.combo_product)

        # Add Button
        self.report.btn_add.clicked.connect(self._open_add_dialog)
        
        # Connect PDF & Excel
        self.report.btn_pdf.clicked.connect(self._export_pdf)
        self.report.btn_excel.clicked.connect(self._export_excel)

        self.table_batches.itemDoubleClicked.connect(self._on_row_double_clicked)
        main_lay.addWidget(self.report, 1)

    def _load_products(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT id, part_no, name FROM products WHERE ISNULL(active, 1) = 1")
            self._all_products = fetchall_dicts(cur)
            conn.close()
        except Exception as e:
            print(f"Error loading products: {e}")

    def _open_add_dialog(self):
        self._load_products()  # Refresh product list so newly added products show up
        dlg = AddBatchDialog(self.window(), self)
        dlg.exec()

    def _load_batches(self):
        while self.table_batches.rowCount() > 1:
            self.table_batches.removeRow(1)
        try:
            sql = """
                SELECT b.id, b.batch_no, p.part_no, p.name, 
                       b.manufacture_date, b.expiry_date, b.qty, b.created_by
                FROM product_batches b
                JOIN products p ON b.product_id = p.id
                ORDER BY b.id DESC
            """
            conn = get_connection(); cur = conn.cursor()
            cur.execute(sql)
            rows = fetchall_dicts(cur)
            conn.close()

            for r, row in enumerate(rows, start=1):
                self.table_batches.insertRow(r)
                
                def _item(val, align=Qt.AlignLeft):
                    it = QTableWidgetItem(str(val) if val is not None else "")
                    it.setTextAlignment(align | Qt.AlignVCenter)
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    return it

                self.table_batches.setItem(r, 0, _item(row['batch_no']))
                # store the row data in the first item so we can access it on double-click
                self.table_batches.item(r, 0).setData(Qt.UserRole, row)
                
                self.table_batches.setItem(r, 1, _item(row['part_no']))
                self.table_batches.setItem(r, 2, _item(row['name']))
                self.table_batches.setItem(r, 3, _item(row['manufacture_date']))
                self.table_batches.setItem(r, 4, _item(row['expiry_date']))
                self.table_batches.setItem(r, 5, _item(f"{float(row['qty'] or 0):.2f}", Qt.AlignCenter))
                self.table_batches.setItem(r, 6, _item(row['created_by']))
                
        except Exception as e:
            print(f"Error loading batches: {e}")

    def _on_row_double_clicked(self, item):
        row_idx = item.row()
        first_item = self.table_batches.item(row_idx, 0)
        if not first_item: return
        
        batch_data = first_item.data(Qt.UserRole)
        if batch_data:
            self._load_products()  # Refresh product list here too
            dlg = AddBatchDialog(self.window(), self, batch_data)
            dlg.exec()

    def _export_pdf(self):
        if self.table_batches.rowCount() == 0:
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
    <div style="text-align:center; margin-bottom: 10px;">{c_header}{a_header}<div style="font-size: 18px; font-weight: bold; color: {ACCENT}; margin-top: 5px;">Batch Management Report</div></div>
    <table width="100%" cellpadding="10" cellspacing="0" style="border-collapse: collapse; font-size: 12px;">
        <thead>
            <tr style="background-color: {NAVY}; color: white; text-align: left;">"""
        headers = ["Batch No", "Item Code", "Item Name", "Mfg Date", "Expiry Date", "Qty", "Created By"]
        for h in headers:
            html += f"<th>{h}</th>"
        html += "</tr></thead><tbody>"

        for r in range(self.table_batches.rowCount()):
            bg = OFF_WHITE if r % 2 == 0 else WHITE
            html += f"<tr style='background-color: {bg}; border-bottom: 1px solid #ddd;'>"
            for c in range(self.table_batches.columnCount()):
                val = self.table_batches.item(r, c).text() if self.table_batches.item(r, c) else ""
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
        export_path = os.path.join(docs, f"Batch_Report_{int(time.time())}.pdf")

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
            dlg = PdfPreviewDialog(export_path, title="Preview: Batch Management", parent=self)
            dlg.exec()
        except Exception as e:
            QMessageBox.information(self, "PDF Saved", f"Report saved successfully to:\n{export_path}\n(Preview error: {e})")

    def _export_excel(self):
        if self.table_batches.rowCount() == 0:
            QMessageBox.information(self, "Empty", "No data to export.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save Excel", 
            os.path.join(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation), f"Batch_Report_{int(time.time())}.csv"), 
            "CSV Files (*.csv)")
            
        if not path: return
        
        try:
            import csv
            headers = ["Batch No", "Item Code", "Item Name", "Mfg Date", "Expiry Date", "Qty", "Created By"]
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for r in range(self.table_batches.rowCount()):
                    row = [self.table_batches.item(r, c).text() if self.table_batches.item(r, c) else "" for c in range(self.table_batches.columnCount())]
                    writer.writerow(row)
            QMessageBox.information(self, "Success", f"Data exported successfully to\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export Excel:\n{e}")

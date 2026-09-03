import qtawesome as qta
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QMessageBox, QMenu
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

# Patch numpy 2.0+ compatibility for openpyxl
try:
    import numpy
    for _k, _v in [('short', getattr(numpy, 'int16', int)), ('ushort', getattr(numpy, 'uint16', int)),
                   ('intc', getattr(numpy, 'int32', int)), ('uintc', getattr(numpy, 'uint32', int)),
                   ('int_', getattr(numpy, 'int64', int)), ('uint', getattr(numpy, 'uint64', int)),
                   ('half', getattr(numpy, 'float16', float)), ('single', getattr(numpy, 'float32', float)),
                   ('double', getattr(numpy, 'float64', float)), ('longdouble', getattr(numpy, 'float64', float))]:
        if not hasattr(numpy, _k):
            setattr(numpy, _k, _v)
except Exception:
    pass

try:
    import openpyxl
except ImportError:
    openpyxl = None

from theme import SUCCESS, WHITE, DANGER, AMBER, MUTED, ROW_ALT, BORDER, NAVY, NAVY_2
from views.reports.report_template import ReportTemplate

class InventoryListDialog(QDialog):
    """Inventory list dialog showing products with stock levels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stock on Hand")
        self.setMinimumSize(900, 600)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.report = ReportTemplate("Stock on Hand", is_report=False, show_date_filter=True, parent=self)
        self.report.set_headers(["Part No.", "Product Name", "Category", "Stock", "Cost Price", "Sale Price", "Cost Value", "Sale Value"])
        layout.addWidget(self.report)
        
        # Custom actions
        self.import_stock_btn = QPushButton("  Import Stock")
        self.import_stock_btn.setIcon(qta.icon("fa5s.file-excel"))
        self.import_stock_btn.setFixedHeight(30)
        self.import_stock_btn.setCursor(Qt.PointingHandCursor)
        self.import_stock_btn.setStyleSheet(f"""
            QPushButton {
                background-color: {NAVY}; color: {WHITE}; border: none;
                border-radius: 4px; font-size: 12px; font-weight: bold; padding: 0 16px;
            }
            QPushButton:hover { background-color: #3b5bdb; }
        """)
        self.import_stock_btn.clicked.connect(self._open_import_stock)
        self.add_stock_btn = QPushButton("  Add Stock")
        self.add_stock_btn.setIcon(qta.icon("fa5s.plus-circle"))
        self.add_stock_btn.setFixedHeight(30)
        self.add_stock_btn.setCursor(Qt.PointingHandCursor)
        self.add_stock_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SUCCESS}; color: {WHITE}; border: none;
                border-radius: 4px; font-size: 12px; font-weight: bold; padding: 0 16px;
            }}
            QPushButton:hover {{ background-color: #1f9447; }}
        """)
        self.add_stock_btn.clicked.connect(self._open_add_stock)
        
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setIcon(qta.icon("fa5s.trash"))
        self.delete_btn.setFixedHeight(30)
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DANGER}; color: {WHITE}; border: none;
                border-radius: 4px; font-size: 12px; font-weight: bold; padding: 0 16px;
            }}
            QPushButton:hover {{ background-color: #cc2828; }}
            QPushButton:disabled {{ background-color: {MUTED}; }}
        """)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_product)

        # Print Sheet button
        self.btn_print = QPushButton("  Print Count Sheet")
        self.btn_print.setIcon(qta.icon("fa5s.print", color="white"))
        self.btn_print.setFixedHeight(30)
        self.btn_print.setCursor(Qt.PointingHandCursor)
        self.btn_print.setStyleSheet(f"""
            QPushButton {{
                background-color: #1a7a3c; color: white; border: none;
                border-radius: 4px; font-size: 12px; font-weight: bold; padding: 0 16px;
            }}
            QPushButton::menu-indicator {{ image: none; }}
            QPushButton:hover {{ background-color: #1e8f46; }}
        """)
        
        print_menu = QMenu(self.btn_print)
        print_menu.setStyleSheet("QMenu { background: white; border: 1px solid #c8d8ec; } QMenu::item { padding: 8px 25px; color: #1a5fb4; } QMenu::item:selected { background: #e8f1f8; }")
        a_blind = print_menu.addAction("Print Blind Count (Hide Qty)")
        a_show = print_menu.addAction("Print Standard Count (Show Qty)")
        a_blind.triggered.connect(lambda: self._print_count_sheet(blind=True))
        a_show.triggered.connect(lambda: self._print_count_sheet(blind=False))
        self.btn_print.setMenu(print_menu)
        
        # Insert custom buttons to the left of the global search
        self.report.btn_apply.clicked.connect(self._load_data)
        self.report.filters_layout.addWidget(self.btn_print)
        self.report.filters_layout.addWidget(self.import_stock_btn)
        self.report.filters_layout.addWidget(self.add_stock_btn)
        self.report.filters_layout.addWidget(self.delete_btn)
        
        # Connect table selection to toggle delete button
        self.report.table.itemSelectionChanged.connect(self._on_selection_changed)
        
        self._load_data()

    def _open_import_stock(self):
        """Open a file dialog, read an Excel file and update product stock.
        Expected columns: 'part_no' (or 'Part No.') and 'stock' (numeric).
        Existing products are updated; missing products are created with minimal data.
        """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        # Prompt for file
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Stock from Excel",
            "",
            "Excel Files (*.xlsx *.xls);;All Files (*)",
        )
        if not file_path:
            return
        if openpyxl is None:
            QMessageBox.critical(self, "Import Error", "openpyxl (and et_xmlfile) library is required to import Excel files.")
            return
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to read Excel file:\n{e}")
            return
            
        if not rows or len(rows) < 2:
            QMessageBox.critical(self, "Import Error", "Excel file is empty or missing data.")
            return

        header = [str(c).lower().strip() if c is not None else "" for c in rows[0]]
        df_columns = {k: i for i, k in enumerate(header) if k}
        
        part_col = None
        stock_col = None
        for key, idx in df_columns.items():
            if "part" in key:
                part_col = idx
            if "stock" in key:
                stock_col = idx
                
        if part_col is None or stock_col is None:
            QMessageBox.critical(self, "Import Error", "Excel must contain 'part_no' (or similar) and 'stock' columns.")
            return
            
        from models.product import get_product_by_part_no, create_product, update_product
        from views.components.smart_progress_dialog import SmartProgressDialog
        
        success = 0
        errors = []
        total_rows = len(rows) - 1
        loader = SmartProgressDialog(title="Bulk Stock Excel Import", total_items=total_rows, parent=self)
        loader.show()

        for idx, row in enumerate(rows[1:]):
            if idx % 5 == 0 or idx == total_rows - 1:
                part_preview = str(row[part_col]).strip().upper() if part_col is not None and len(row) > part_col and row[part_col] else ""
                loader.update_progress(idx + 1, part_preview)
                if loader.was_canceled():
                    break
            try:
                part_val = row[part_col]
                if part_val is None:
                    continue
                part_no = str(part_val).strip().upper()
                if not part_no:
                    continue
                
                stock_val_raw = row[stock_col]
                stock_val = float(stock_val_raw) if stock_val_raw is not None else 0.0
                
                prod = get_product_by_part_no(part_no)
                if prod:
                    # Update existing product stock
                    update_product(prod['id'], stock=stock_val)
                else:
                    # Create a new minimal product
                    # Name defaults to part_no, price 0
                    create_product(
                        part_no=part_no,
                        name=part_no,
                        price=0.0,
                        stock=stock_val,
                        category="",
                        uom="Unit",
                        conversion_factor=1.0,
                    )
                success += 1
            except Exception as e:
                errors.append(f"Row {idx + 2}: {e}")
        loader.accept()
        # Refresh view
        self._load_data()
        # Report outcome
        msg = f"Imported stock for {success} items."
        if errors:
            msg += f"\nErrors ({len(errors)}):\n" + "\n".join(errors)
        QMessageBox.information(self, "Import Completed", msg)


    def _open_add_stock(self):
        from views.dialogs.stock_file_dialog import StockEditDialog
        from models.product import create_product, upsert_item_price
        dlg = StockEditDialog(self)
        if dlg.exec():
            try:
                p = create_product(**dlg.result_data)
                upsert_item_price(
                    p['part_no'],
                    dlg.result_data.get('price_list', 'Standard Selling'),
                    p.get('uom', 'Unit'),
                    dlg.result_data['price']
                )
                self._load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create product:\n{e}")

    def _on_selection_changed(self):
        has_selection = len(self.report.table.selectedItems()) > 0
        self.delete_btn.setEnabled(has_selection)

    def _delete_product(self):
        row = self.report.table.currentRow()
        if row < 0:
            return
            
        item = self.report.table.item(row, 0)
        product = item.data(Qt.UserRole)
        if not product:
            return
            
        reply = QMessageBox.question(
            self, "Delete Product",
            f"Are you sure you want to delete the product '{product.get('name', '')}'?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                from models.product import delete_product
                if delete_product(product['id']):
                    self._load_data()
                else:
                    QMessageBox.warning(self, "Failed", "Could not delete product. It may be in use.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete product:\n{e}")

    def _load_data(self):
        """Load all products from database with 95% faster batch rendering."""
        try:
            from models.product import get_all_products
            products = get_all_products()
            
            display_data = []
            for p in products:
                stock = float(p.get("stock", 0) or 0)
                price = float(p.get("price", 0) or 0)
                cost = float(p.get("cost_price", 0) or 0)
                display_data.append([
                    p.get("part_no", ""),
                    p.get("name", ""),
                    p.get("category", ""),
                    f"{stock:.2f}" if stock != int(stock) else f"{int(stock)}",
                    f"${cost:.2f}",
                    f"${price:.2f}",
                    f"${(cost * stock):.2f}",
                    f"${(price * stock):.2f}"
                ])
                
            tbl = self.report.table
            tbl.setUpdatesEnabled(False)
            tbl.blockSignals(True)
            try:
                self.report.set_data(display_data)
                
                # Post-process to add coloring and UserRole data
                for r, p in enumerate(products):
                    stock = float(p.get("stock", 0) or 0)
                    stock_item = tbl.item(r, 3)
                    if stock_item:
                        if stock <= 5:
                            stock_item.setForeground(QColor(DANGER))
                        elif stock <= 10:
                            stock_item.setForeground(QColor(AMBER))
                        else:
                            stock_item.setForeground(QColor(SUCCESS))
                            
                    cost_item = tbl.item(r, 4)
                    if cost_item:
                        cost_item.setForeground(QColor("#1a7a3c"))
                        
                    price_item = tbl.item(r, 5)
                    if price_item:
                        price_item.setForeground(QColor("#1a7a3c"))
                        
                    cost_val_item = tbl.item(r, 6)
                    if cost_val_item:
                        cost_val_item.setForeground(QColor(NAVY_2))
                        
                    sale_val_item = tbl.item(r, 7)
                    if sale_val_item:
                        sale_val_item.setForeground(QColor(NAVY))

                    part_no_item = tbl.item(r, 0)
                    if part_no_item:
                        part_no_item.setData(Qt.UserRole, p)
            finally:
                tbl.setUpdatesEnabled(True)
                tbl.blockSignals(False)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading products: {e}")

    def _print_count_sheet(self, blind=True):
        from PySide6.QtCore import QStandardPaths
        from PySide6.QtPrintSupport import QPrinter
        from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout
        from models.company_defaults import get_defaults
        from views.dialogs.pdf_preview_dialog import PdfPreviewDialog
        import os
        import datetime
        
        if self.report.table.rowCount() == 0:
            QMessageBox.information(self, "Empty", "No data to print. Please wait for items to load.")
            return

        try:
            comp = get_defaults()
            c_name = comp.get('company_name', 'Havano POS')
            c_addr = f"{comp.get('address_1', '')} {comp.get('address_2', '')}"
        except:
            c_name, c_addr = "Havano POS", ""
            
        dt_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        c_header = f"<div style='font-size: 24px; font-weight: bold; color: #1a5fb4; margin:0;'>{c_name}</div>" if c_name.strip() else ""
        a_header = f"<div style='color: #666; margin:0; margin-bottom:10px;'>{c_addr}</div>" if c_addr.strip() else ""
        title = "Stock Count Sheet (Blind)" if blind else "Stock Count Sheet (Standard)"

        html = f"""<html><body style="font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 0;">
    <div style="text-align:center; margin-bottom: 10px;">{c_header}{a_header}<div style="font-size: 18px; font-weight: bold; color: #1a5fb4; margin-top: 5px; margin-bottom: 5px;">{title}</div><div style="color: #666; font-size:12px; margin: 0;">Date: {dt_str}</div></div>
    <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse: collapse; font-size: 12px; border: 1px solid #ddd;">
                <thead>
                    <tr style="background-color: #1a5fb4; color: white; text-align: left;">
                        <th style="border: 1px solid #ddd; width: 15%;">CODE</th>
                        <th style="border: 1px solid #ddd; width: 40%;">ITEM NAME</th>
                        <th style="border: 1px solid #ddd; width: 15%;">CATEGORY</th>
        """
        if not blind:
            html += '<th style="border: 1px solid #ddd; width: 15%; text-align: right;">SYS QTY</th>'
        
        html += """
                        <th style="border: 1px solid #ddd; width: 15%; text-align: center;">COUNTED QTY</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for r in range(self.report.table.rowCount()):
            if self.report.table.isRowHidden(r): continue
            
            code = self.report.table.item(r, 0).text() if self.report.table.item(r, 0) else ""
            name = self.report.table.item(r, 1).text() if self.report.table.item(r, 1) else ""
            cat = self.report.table.item(r, 2).text() if self.report.table.item(r, 2) else ""
            sys = self.report.table.item(r, 3).text() if self.report.table.item(r, 3) else ""
            
            bg = "#fdfbf7" if r % 2 == 0 else "#ffffff"
            html += f"<tr style='background-color: {bg};'>"
            html += f"<td style='border: 1px solid #ddd; color:#333;'>{code}</td>"
            html += f"<td style='border: 1px solid #ddd; color:#333;'>{name}</td>"
            html += f"<td style='border: 1px solid #ddd; color:#333;'>{cat}</td>"
            
            if not blind:
                html += f"<td style='border: 1px solid #ddd; color:#333; text-align:right;'>{sys}</td>"
                
            html += "<td style='border: 1px solid #ddd; color:#333;'></td>"
            html += "</tr>"
            
        html += """
                </tbody>
            </table>
            <div style="margin-top:20px; font-size:12px; color:#333;">
                <p>Counted by: ________________________   Date: ________________________</p>
                <p>Checked by: ________________________   Date: ________________________</p>
            </div>
            <div style="margin-top:40px; font-size:10px; color:#888; text-align:center;">
                Generated by Havano ERP Inventory Module
            </div>
        </body>
        </html>
        """
        
        docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        export_path = os.path.join(docs, f"Stock_Count_Sheet_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.pdf")

        printer = QPrinter()
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(export_path)
        printer.setFullPage(True)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Portrait)
        from PySide6.QtCore import QMarginsF
        printer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter)

        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(html.replace('\n', '').replace('\r', ''))
        doc.print_(printer)

        try:
            dlg = PdfPreviewDialog(export_path, title=title, parent=self)
            dlg.exec()
        except Exception as e:
            QMessageBox.information(self, "PDF Saved", f"Count sheet saved successfully to:\n{export_path}\n(Preview error: {e})")
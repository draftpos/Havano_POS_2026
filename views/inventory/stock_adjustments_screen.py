import time
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QDialog, QFormLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
    QLabel, QComboBox, QMessageBox, QAbstractItemView, QFileDialog
)
from PySide6.QtCore import Qt, QDate, QStandardPaths
from PySide6.QtGui import QDoubleValidator, QColor, QTextDocument, QPageSize, QPageLayout
from PySide6.QtPrintSupport import QPrinter
from database.db import get_connection, fetchall_dicts
from models.company_defaults import get_defaults
from views.dialogs.pdf_preview_dialog import PdfPreviewDialog
import qtawesome as qta
from theme import *

class AddStockAdjustmentDialog(QDialog):
    def __init__(self, parent=None, parent_screen=None):
        super().__init__(parent)
        self.setWindowTitle("Add Stock Adjustments")
        self.setWindowState(Qt.WindowMaximized)
        self.setMinimumWidth(900)
        self.setMinimumHeight(600)
        self.parent_screen = parent_screen
        self._products = []
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        
        from views.reports.report_template import ReportTemplate
        self.report = ReportTemplate("StockAdjustments", is_report=False, show_date_filter=True, parent=self, show_column_filters=False)
        self.report._update_totals = lambda *args, **kwargs: None
        self.report.set_headers(["ITEM", "ON HAND", "ACTION", "REASON", "ADJ QTY", "UNIT COST", "VARIANCE"])
        
        self._tbl = self.report.table
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        self._tbl.setSelectionMode(QAbstractItemView.NoSelection)
        self._tbl.setFocusPolicy(Qt.NoFocus)
        self.report.global_search.hide()
        
        self.report.btn_add.setText(" Submit Adjustments")
        self.report.btn_add.clicked.connect(self._on_submit)
        
        if hasattr(self, '_export_pdf'):
            self.report.btn_pdf.clicked.connect(self._export_pdf)
            
        if hasattr(self, '_export_excel'):
            self.report.btn_excel.clicked.connect(self._export_excel)
            
        if hasattr(self, '_on_search'):
            self.report.global_search.textChanged.connect(self._on_search)
            self._search_input = self.report.global_search

        main_lay.addWidget(self.report, 1)

    def _load_data(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT id, part_no, name, stock, cost_price FROM products WHERE ISNULL(active, 1) = 1 ORDER BY name")
            self._products = fetchall_dicts(cur)
            conn.close()
            
            words = [f"{p['part_no']} - {p['name']}" for p in self._products]
            from PySide6.QtWidgets import QCompleter
            self.completer = QCompleter(words, self)
            self.completer.setCaseSensitivity(Qt.CaseInsensitive)
            self.completer.setFilterMode(Qt.MatchContains)
            self.completer.activated.connect(self._add_product_row)
            
            self.completer.popup().setStyleSheet(f"""
                QListView {{
                    background-color: {WHITE}; color: {NAVY};
                    border: 1px solid {BORDER}; border-radius: 4px;
                    font-size: 14px; padding: 4px; outline: none;
                }}
                QListView::item {{
                    padding: 12px;
                    border-radius: 4px;
                    border-bottom: 1px solid #f1f5f9;
                }}
                QListView::item:selected {{
                    background-color: {SUCCESS};
                    color: {WHITE};
                }}
                QListView::item:hover {{
                    background-color: #e2e8f0;
                    color: {NAVY};
                }}
            """)
            
            self._setup_inline_search_row()
            
        except Exception as e:
            pass

    def _setup_inline_search_row(self):
        row = self._tbl.rowCount()
        self._tbl.insertRow(row)
        self._tbl.setRowHeight(row, 45)
        
        for c in range(1, self._tbl.columnCount()):
            empty_it = QTableWidgetItem("")
            empty_it.setFlags(empty_it.flags() & ~Qt.ItemIsEditable & ~Qt.ItemIsSelectable)
            self._tbl.setItem(row, c, empty_it)
            
        it = QTableWidgetItem("")
        it.setFlags(it.flags() & ~Qt.ItemIsSelectable)
        self._tbl.setItem(row, 0, it)

        self.inline_search_edit = QLineEdit()
        self.inline_search_edit.is_inline_search = True
        self.inline_search_edit.setPlaceholderText("Scan barcode or search product here to add inline...")
        self.inline_search_edit.setStyleSheet(f"""
            QLineEdit {{
                border: none !important;
                background-color: transparent !important;
                background: transparent !important;
                padding:0 12px; margin:0; color:{{NAVY}};
                font-size:14px; font-weight:500;
            }}
        """)
        
        if hasattr(self, 'completer'):
            self.inline_search_edit.setCompleter(self.completer)
            
        def _on_return():
            text = self.inline_search_edit.text().strip()
            if text: self._add_product_row(text)
            
        self.inline_search_edit.returnPressed.connect(_on_return)
        self._tbl.setCellWidget(row, 0, self.inline_search_edit)

    def _add_product_row(self, text):
        match = next((p for p in self._products if f"{p['part_no']} - {p['name']}" == text), None)
        if not match: return
        
        if hasattr(self, 'inline_search_edit'):
            self.inline_search_edit.clear()
            self.inline_search_edit.setFocus()
            if self.inline_search_edit.completer() and self.inline_search_edit.completer().popup():
                self.inline_search_edit.completer().popup().hide()
        
        # Exclude the last row (inline search) when checking duplicates
        for r in range(max(0, self._tbl.rowCount() - 1)):
            item = self._tbl.item(r, 0)
            if item and item.data(Qt.UserRole) == match['id']:
                QMessageBox.warning(self, "Duplicate", "This product is already in the adjustment list.")
                return
                
        r = max(0, self._tbl.rowCount() - 1)
        self._tbl.insertRow(r)
        
        unit_cost = float(match['cost_price'] or 0.0)
        stock_qty = float(match['stock'] or 0.0)
        
        it_name = QTableWidgetItem(f"{match['part_no']} - {match['name']}")
        it_name.setFlags(it_name.flags() & ~Qt.ItemIsEditable)
        it_name.setData(Qt.UserRole, match['id'])
        it_name.setData(Qt.UserRole + 1, unit_cost)
        self._tbl.setItem(r, 0, it_name)
        
        it_onhand = QTableWidgetItem(f"{stock_qty:.2f}")
        it_onhand.setFlags(it_onhand.flags() & ~Qt.ItemIsEditable)
        it_onhand.setTextAlignment(Qt.AlignCenter)
        self._tbl.setItem(r, 1, it_onhand)
        
        combo_style = f"QComboBox {{ border:1px solid {BORDER}; border-radius:4px; padding:4px 10px; background:white; color:{NAVY}; }}"
        
        act_combo = QComboBox()
        act_combo.addItems(["", "Subtract", "Add"])
        act_combo.setStyleSheet(combo_style)
        self._tbl.setCellWidget(r, 2, act_combo)
        
        rsn_combo = QComboBox()
        rsn_combo.addItems(["Adjustments", "Breakages", "Wastages"])
        rsn_combo.setStyleSheet(combo_style)
        self._tbl.setCellWidget(r, 3, rsn_combo)

        adj_edit = QLineEdit("")
        adj_edit.setPlaceholderText("0.00")
        adj_edit.setValidator(QDoubleValidator(0.00, 100000.00, 2))
        adj_edit.setAlignment(Qt.AlignCenter)
        adj_edit.setStyleSheet(f"QLineEdit {{ border: 1px solid {BORDER}; border-radius: 4px; padding: 4px; background: {WHITE}; font-size: 14px; font-weight: bold; color: {NAVY}; }}")
        self._tbl.setCellWidget(r, 4, adj_edit)

        it_cost = QTableWidgetItem(f"${unit_cost:.2f}")
        it_cost.setFlags(it_cost.flags() & ~Qt.ItemIsEditable)
        it_cost.setTextAlignment(Qt.AlignCenter)
        self._tbl.setItem(r, 5, it_cost)

        it_var = QTableWidgetItem("$0.00")
        it_var.setFlags(it_var.flags() & ~Qt.ItemIsEditable)
        it_var.setTextAlignment(Qt.AlignCenter)
        self._tbl.setItem(r, 6, it_var)
        
        def make_updater(row_idx, cost_val):
            def _update():
                qty_widget = self._tbl.cellWidget(row_idx, 4)
                act_widget = self._tbl.cellWidget(row_idx, 2)
                
                # Enforce action selection
                if act_widget and not act_widget.currentText().strip():
                    if qty_widget and qty_widget.text():
                        qty_widget.blockSignals(True)
                        qty_widget.setText("")
                        qty_widget.blockSignals(False)
                        act_widget.setFocus()
                        try:
                            from utils.toast import show_toast
                            show_toast(qty_widget.window(), "Please select an ACTION (Add/Subtract) first!", kind="warn")
                        except: pass
                        return
                        
                if qty_widget:
                    try: val = float(qty_widget.text() or 0)
                    except ValueError: val = 0.0
                    var_item = self._tbl.item(row_idx, 6)
                    if var_item: var_item.setText(f"${(val * cost_val):.2f}")
            return _update

        updater = make_updater(r, unit_cost)
        adj_edit.textChanged.connect(updater)
        act_combo.currentIndexChanged.connect(updater)
        self._tbl.setRowHeight(r, 45)
        
        # Focus the action combo box immediately after adding the product
        act_combo.setFocus()

    def _on_submit(self):
        adjustments = []
        for r in range(self._tbl.rowCount()):
            item = self._tbl.item(r, 0)
            if not item: continue # Skip inline search row
            
            qty_edit = self._tbl.cellWidget(r, 4)
            if not qty_edit or not qty_edit.text().strip(): continue
            
            try:
                qty = float(qty_edit.text())
                if qty <= 0: continue
            except ValueError: continue
                
            product_id = item.data(Qt.UserRole)
            unit_cost = item.data(Qt.UserRole + 1)
            
            act_combo = self._tbl.cellWidget(r, 2)
            rsn_combo = self._tbl.cellWidget(r, 3)
            
            adjustments.append({
                "product_id": product_id, "name": item.text(),
                "qty": qty, "action": act_combo.currentText(),
                "reason": rsn_combo.currentText(), "unit_cost": unit_cost
            })
            
        if not adjustments:
            QMessageBox.warning(self, "No Adjustments", "Please enter at least one valid adjustment quantity.")
            return
            
        confirm = QMessageBox.question(self, "Confirm Changes", f"Are you sure you want to save {len(adjustments)} adjustments?", QMessageBox.Yes | QMessageBox.No)
        if confirm != QMessageBox.Yes: return

        try:
            conn = get_connection(); cur = conn.cursor()
            created_by = getattr(self.window(), 'user', {}).get('name', 'Admin') if hasattr(self.window(), 'user') else 'Admin'
            for adj in adjustments:
                adj_qty = adj['qty'] if adj['action'] == "Add" else -adj['qty']
                variance = adj['qty'] * adj['unit_cost']
                
                cur.execute("UPDATE products SET stock = ISNULL(stock, 0) + ? WHERE id = ?", (adj_qty, adj['product_id']))
                doc_no = f"ADJ-{int(time.time())}-{adj['product_id']}"
                
                cur.execute("""
                    INSERT INTO stock_entries (warehouse_id, doc_no, date, date_time, reference, is_paid, synced, created_by)
                    OUTPUT INSERTED.id
                    VALUES (1, ?, GETDATE(), GETDATE(), ?, 1, 0, ?)
                """, (doc_no, adj['reason'], created_by))
                row = cur.fetchone()
                if row:
                    entry_id = int(row[0])
                    cur.execute("INSERT INTO stock_entry_items (parent_id, product_id, qty, cost_price, selling_price) VALUES (?, ?, ?, ?, ?)", 
                                (entry_id, adj['product_id'], adj_qty, adj['unit_cost'], 0))
                    
                if adj['action'] == "Subtract" and adj['reason'] in ["Breakages", "Wastages"]:
                    cur.execute("SELECT id FROM expense_categories WHERE name = ?", (adj['reason'],))
                    cat = cur.fetchone()
                    if not cat:
                        cur.execute("INSERT INTO expense_categories (name) OUTPUT INSERTED.id VALUES (?)", (adj['reason'],))
                        cat = cur.fetchone()
                    
                    exp_no = f"EXP-{int(time.time())}-{adj['product_id']}"
                    exp_name = f"Stock {adj['reason']}: {adj['name']} (Qty: {adj['qty']})"
                    cur.execute("INSERT INTO expenses (name, expense_category_id, amount, paid, expense_number, balance) VALUES (?, ?, ?, 1, ?, 0)", 
                                (exp_name, int(cat[0]), variance, exp_no))
                    
            conn.commit(); conn.close()
            try:
                from utils.toast import show_toast
                show_toast(self, f"Successfully saved {len(adjustments)} adjustments.", duration_ms=3000, kind="success")
            except:
                pass
            if self.parent_screen: self.parent_screen._load_data()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

class StockAdjustmentsScreen(QWidget):
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
        self.report = ReportTemplate("Stock Adjustments", is_report=False, show_date_filter=True, parent=self)
        self.report.set_headers(["Date", "Doc No", "Created By", "Reference / Reason"])
        
        self.report.btn_add.setText(" Add Adjustment")
        self.report.btn_add.clicked.connect(self._open_add_dialog)
        self.report.btn_pdf.clicked.connect(self._export_pdf)
        self.report.btn_excel.clicked.connect(self._export_excel)

        self._tbl = self.report.table
        hh = self._tbl.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hh.setSectionResizeMode(QHeaderView.Stretch)
        
        self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tbl.itemDoubleClicked.connect(self._on_row_double_clicked)
        
        self.report.global_search.textChanged.connect(self._on_search)
        
        main_lay.addWidget(self.report, 1)

    def _on_search(self, text):
        query = text.lower()
        for r in range(self._tbl.rowCount()):
            match = False
            for c in range(self._tbl.columnCount()):
                if item and query in item.text().lower():
                    match = True
                    break
            self._tbl.setRowHidden(r, not match)

    def _on_row_double_clicked(self, item):
        row = item.row()
        first_item = self._tbl.item(row, 0)
        if not first_item: return
        row_data = first_item.data(Qt.UserRole)
        if not row_data: return
        
        from views.dialogs.stock_entry_viewer_dialog import StockEntryViewerDialog
        dlg = StockEntryViewerDialog(self.window(), entry_id=row_data['entry_id'], title="Adjustment Details")
        dlg.exec()

    def _open_add_dialog(self):
        dlg = AddStockAdjustmentDialog(self.window(), self)
        dlg.exec()

    def _load_data(self):
        while self._tbl.rowCount() > 1:
            self._tbl.removeRow(1)
        try:
            sql = """
                SELECT id as entry_id, date, doc_no, reference, created_by
                FROM stock_entries
                ORDER BY date DESC, id DESC
            """
            conn = get_connection(); cur = conn.cursor()
            cur.execute(sql)
            rows = fetchall_dicts(cur)
            conn.close()

            for r, row in enumerate(rows, start=1):
                self._tbl.insertRow(r)
                
                def _item(val):
                    it = QTableWidgetItem(str(val) if val is not None else "")
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    return it

                date_str = str(row['date']).split(".")[0] if row['date'] else ""
                first_item = _item(date_str)
                first_item.setData(Qt.UserRole, row)
                
                self._tbl.setItem(r, 0, first_item)
                self._tbl.setItem(r, 1, _item(row['doc_no']))
                self._tbl.setItem(r, 2, _item(row.get('created_by', 'Admin')))
                self._tbl.setItem(r, 3, _item(row['reference']))
                
        except Exception as e:
            print(f"Error loading adjustments: {e}")

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

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 40px;">
            <div style="text-align:center; margin-bottom: 20px;">
                <h2 style="color: {NAVY}; margin:0;">{c_name}</h2>
                <p style="color: #666; margin:0;">{c_addr}</p>
                <h3 style="color: {ACCENT}; margin-top: 15px;">Stock Adjustments History</h3>
            </div>
            
            <table width="100%" cellpadding="10" cellspacing="0" style="border-collapse: collapse; font-size: 12px;">
                <thead>
                    <tr style="background-color: {NAVY}; color: white; text-align: left;">
        """
        headers = ["Date", "Doc No", "Created By", "Reference / Reason"]
        for h in headers:
            html += f"<th>{h}</th>"
        html += "</tr></thead><tbody>"

        for r in range(self._tbl.rowCount()):
            bg = OFF_WHITE if r % 2 == 0 else WHITE
            html += f"<tr style='background-color: {bg}; border-bottom: 1px solid #ddd;'>"
            for c in range(self._tbl.columnCount()):
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
        export_path = os.path.join(docs, f"Stock_Adjustments_History_{int(time.time())}.pdf")

        printer = QPrinter()
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(export_path)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Landscape)

        doc = QTextDocument()
        doc.setHtml(html)
        doc.print_(printer)

        try:
            dlg = PdfPreviewDialog(export_path, title="Preview: Stock Adjustments History", parent=self)
            dlg.exec()
        except Exception as e:
            QMessageBox.information(self, "PDF Saved", f"Report saved successfully to:\n{export_path}\n(Preview error: {e})")

    def _export_excel(self):
        if self._tbl.rowCount() == 0:
            QMessageBox.information(self, "Empty", "No data to export.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save Excel", 
            os.path.join(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation), f"Stock_Adjustments_History_{int(time.time())}.csv"), 
            "CSV Files (*.csv)")
            
        if not path: return
        
        try:
            import csv
            headers = ["Date", "Doc No", "Created By", "Reference / Reason"]
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for r in range(self._tbl.rowCount()):
                    row = [self._tbl.item(r, c).text() if self._tbl.item(r, c) else "" for c in range(self._tbl.columnCount())]
                    writer.writerow(row)
            QMessageBox.information(self, "Success", f"Data exported successfully to\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export Excel:\n{e}")

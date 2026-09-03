from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit,
    QLineEdit, QDialog, QCompleter
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont
from database.db import get_connection
from views.reports.report_template import ReportTemplate

class DetailedInventoryLedger(ReportTemplate):
    def __init__(self, parent=None):
        super().__init__("Detailed Inventory Ledger", is_report=True, parent=parent)
        self.set_headers([
            "Date", "Voucher No", "Type", "Product", "Prod Status", "In", "Out", "Balance", "Value In", "Value Out"
        ])
        
        # Type Filter
        self.type_filter = QComboBox()
        self.type_filter.addItems([
            "All",
            "Sales Invoice",
            "Credit Note",
            "Purchase Invoices",
            "Purchase Return",
            "Opening Stock",
            "Stck Adjstmnts",
            "Stock Entry",
            "Transfer"
        ])
        self.type_filter.setStyleSheet("padding: 6px; border: 1px solid #c8d8ec; border-radius: 4px; background: white;")
        self.type_filter.setMinimumWidth(150)
        
        # Product Filter (Search)
        self.product_search = QLineEdit()
        self.product_search.setPlaceholderText("Search Product / Part No...")
        self.product_search.setStyleSheet("padding: 6px; border: 1px solid #c8d8ec; border-radius: 4px; background: white;")
        
        self.filters_layout.insertWidget(4, QLabel("Type:"))
        self.filters_layout.insertWidget(5, self.type_filter)
        self.filters_layout.insertWidget(6, QLabel("Product:"))
        self.filters_layout.insertWidget(7, self.product_search)
        self.btn_apply.clicked.connect(self.load_data)
        
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(3, header.ResizeMode.Stretch)
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, header.ResizeMode.ResizeToContents)
        for i in range(5, 10):
            header.setSectionResizeMode(i, header.ResizeMode.Interactive)
            self.table.setColumnWidth(i, 130)
            
        self.table.setColumnHidden(4, True)
            
        self._load_products_for_autocomplete()
        self.load_data()
        
    def _load_products_for_autocomplete(self):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT part_no, name FROM products")
            prods = cur.fetchall()
            conn.close()
            
            words = []
            for p in prods:
                if p[0]: words.append(str(p[0]))
                if p[1]: words.append(str(p[1]))
            
            completer = QCompleter(list(set(words)), self)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            self.product_search.setCompleter(completer)
        except Exception as e:
            print("Error loading autocomplete:", e)
            
    def load_data(self):
        start_date = self.start_date.date().toString("yyyy-MM-dd") + " 00:00:00"
        end_date = self.end_date.date().toString("yyyy-MM-dd") + " 23:59:59"
        filter_type = self.type_filter.currentText()
        prod_filter = self.product_search.text().strip()
        
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        except:
            pass
        
        prod_where = ""
        params = [start_date, end_date]
        if prod_filter:
            prod_where = "AND (p.name LIKE ? OR p.part_no LIKE ?)"
            params.extend([f"%{prod_filter}%", f"%{prod_filter}%"])
            
        entries = []
        try:
            # 1. SALES (Out)
            if filter_type in ["All", "Sales Invoice"]:
                cur.execute(f"""
                    SELECT s.created_at as date, s.invoice_no, 'Sales Invoice' as type, p.name, ISNULL(p.active, 1) as active,
                           0 as qty_in, si.qty as qty_out,
                           0 as val_in, (si.qty * ISNULL(si.price, 0)) as val_out
                    FROM sales s
                    JOIN sale_items si ON s.id = si.sale_id
                    JOIN products p ON si.part_no = p.part_no
                    WHERE s.created_at BETWEEN ? AND ?
                    {prod_where}
                """, params)
                entries.extend(cur.fetchall())
                
            # 2. CREDIT NOTES (In)
            if filter_type in ["All", "Credit Note"]:
                cur.execute(f"""
                    SELECT cn.created_at as date, cn.cn_number as doc_no, 'Credit Note' as type, p.name, ISNULL(p.active, 1) as active,
                           cni.qty as qty_in, 0 as qty_out,
                           (cni.qty * ISNULL(cni.price, 0)) as val_in, 0 as val_out
                    FROM credit_notes cn
                    JOIN credit_note_items cni ON cn.id = cni.credit_note_id
                    JOIN products p ON cni.part_no = p.part_no
                    WHERE cn.created_at BETWEEN ? AND ?
                    {prod_where}
                """, params)
                entries.extend(cur.fetchall())
                
            # 3. PURCHASE INVOICES / ORDERS (In)
            if filter_type in ["All", "Purchase Invoices"]:
                cur.execute("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='purchase_orders'")
                if cur.fetchone():
                    cur.execute(f"""
                        SELECT po.date, 'PO-' + CAST(po.id AS VARCHAR), 'Purchase Invoices' as type, p.name, ISNULL(p.active, 1) as active,
                               poi.qty as qty_in, 0 as qty_out,
                               (poi.qty * ISNULL(poi.cost_price, 0)) as val_in, 0 as val_out
                        FROM purchase_orders po
                        JOIN purchase_order_items poi ON po.id = poi.parent_id
                        JOIN products p ON poi.product_id = p.id
                        WHERE po.date BETWEEN ? AND ?
                        {prod_where}
                    """, params)
                    entries.extend(cur.fetchall())
                
            # 4. STOCK ENTRIES
            if filter_type in ["All", "Opening Stock", "Stck Adjstmnts", "Transfer", "Purchase Invoices", "Purchase Return", "Stock Entry"]:
                cur.execute("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='stock_entries'")
                if cur.fetchone():
                    cur.execute(f"""
                         SELECT se.date, ISNULL(se.doc_no, 'SE-' + CAST(se.id AS VARCHAR)), 
                                CASE 
                                  WHEN se.doc_no LIKE 'PINV-%' THEN 'Purchase Invoice'
                                  WHEN se.doc_no LIKE 'PRET-%' THEN 'Purchase Return'
                                  WHEN se.doc_no LIKE 'OPEN-%' OR se.doc_no LIKE '%Opening%' THEN 'Opening Stock'
                                  WHEN se.doc_no LIKE 'ADJ-%'  OR se.doc_no LIKE '%Adj%' THEN 
                                      CASE 
                                        WHEN se.reference IN ('Adjustment', 'Adjustments', 'Stock Adjustment', NULL) THEN 'Stck Adjstmnts'
                                        ELSE se.reference 
                                      END
                                  ELSE 'Stock Entry'
                                END as type, 
                                p.name,
                                ISNULL(p.active, 1) as active,
                               CASE 
                                 WHEN se.doc_no LIKE 'PRET-%' THEN 0 
                                 WHEN sei.qty < 0 THEN 0
                                 ELSE sei.qty 
                               END as qty_in, 
                               CASE 
                                 WHEN se.doc_no LIKE 'PRET-%' THEN sei.qty 
                                 WHEN sei.qty < 0 THEN ABS(sei.qty)
                                 ELSE 0 
                               END as qty_out,
                               CASE 
                                 WHEN se.doc_no LIKE 'PRET-%' THEN 0 
                                 WHEN sei.qty < 0 THEN 0
                                 ELSE (sei.qty * ISNULL(sei.cost_price, 0)) 
                               END as val_in, 
                               CASE 
                                 WHEN se.doc_no LIKE 'PRET-%' THEN (sei.qty * ISNULL(sei.cost_price, 0)) 
                                 WHEN sei.qty < 0 THEN (ABS(sei.qty) * ISNULL(sei.cost_price, 0))
                                 ELSE 0 
                               END as val_out
                        FROM stock_entries se
                        JOIN stock_entry_items sei ON se.id = sei.parent_id
                        JOIN products p ON sei.product_id = p.id
                        WHERE se.date BETWEEN ? AND ?
                        {prod_where}
                    """, params)
                    entries.extend(cur.fetchall())
                
        except Exception as e:
            print(f"Error loading ledger: {e}")
        finally:
            conn.close()
            
        entries.sort(key=lambda x: str(x[0]))
        
        if filter_type != "All":
            entries = [e for e in entries if str(e[2]) == filter_type]
            
        while self.table.rowCount() > 1:
            self.table.removeRow(1)
            
        running_balances = {}
        total_in = 0.0
        total_out = 0.0
        total_val_in = 0.0
        total_val_out = 0.0
        
        processed_rows = []
        
        for e in entries:
            date_val = e[0].strftime("%Y-%m-%d %H:%M") if hasattr(e[0], 'strftime') else str(e[0])
            voucher = str(e[1] or "")
            t_type = str(e[2])
            prod_name = str(e[3])
            
            q_in = float(e[5] or 0)
            q_out = float(e[6] or 0)
            
            val_in = float(e[7] or 0)
            val_out = float(e[8] or 0)
            
            prod_status = "Active" if e[4] else "Disabled"
            
            if prod_name not in running_balances:
                running_balances[prod_name] = 0.0
            running_balances[prod_name] += (q_in - q_out)
            bal = running_balances[prod_name]
                
            processed_rows.append((date_val, voucher, t_type, prod_name, prod_status, q_in, q_out, bal, val_in, val_out))
            
        processed_rows.reverse()
        
        for pr in processed_rows:
            date_val, voucher, t_type, prod_name, prod_status, q_in, q_out, bal, val_in, val_out = pr
            
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            prod_item = QTableWidgetItem(prod_name)
            prod_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            
            status_item = QTableWidgetItem(prod_status)
            status_item.setTextAlignment(Qt.AlignCenter)
            if prod_status == "Disabled":
                status_item.setForeground(QColor("#c0392b"))
            else:
                status_item.setForeground(QColor("#27ae60"))
            
            self.table.setItem(row, 0, QTableWidgetItem(date_val))
            self.table.setItem(row, 1, QTableWidgetItem(voucher))
            self.table.setItem(row, 2, QTableWidgetItem(t_type))
            self.table.setItem(row, 3, prod_item)
            self.table.setItem(row, 4, status_item)
            
            item_in = QTableWidgetItem(f"{q_in:.2f}" if q_in else "-")
            item_out = QTableWidgetItem(f"{q_out:.2f}" if q_out else "-")
            
            item_bal = QTableWidgetItem(f"{bal:.2f}")
                
            item_val_in = QTableWidgetItem(f"${val_in:.2f}" if val_in else "$0.00")
            item_val_out = QTableWidgetItem(f"${val_out:.2f}" if val_out else "$0.00")
            
            self.table.setItem(row, 5, item_in)
            self.table.setItem(row, 6, item_out)
            self.table.setItem(row, 7, item_bal)
            self.table.setItem(row, 8, item_val_in)
            self.table.setItem(row, 9, item_val_out)
            
            for col in range(5, 10):
                self.table.item(row, col).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
            total_in += q_in
            total_out += q_out
            total_val_in += val_in
            total_val_out += val_out

        self._update_totals()

class DetailedInventoryLedgerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detailed Inventory Ledger")
        self.setMinimumSize(1100, 750)
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setWindowState(Qt.WindowMaximized)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.ledger_widget = DetailedInventoryLedger(self)
        self.layout.addWidget(self.ledger_widget)

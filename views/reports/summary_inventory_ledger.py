from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit,
    QLineEdit, QDialog, QCompleter
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont
from database.db import get_connection
from datetime import datetime
from views.reports.report_template import ReportTemplate

class SummaryInventoryLedger(ReportTemplate):
    def __init__(self, parent=None):
        super().__init__("Summary Inventory Ledger", is_report=True, parent=parent)
        self.set_headers([
            "Item Code", "Item Name", "Prod Status", "Opening", "In", "Out", "Balance"
        ])
        
        # Product Filter (Search)
        self.product_search = QLineEdit()
        self.product_search.setPlaceholderText("Search Product / Part No...")
        self.product_search.setStyleSheet("padding: 6px; border: 1px solid #c8d8ec; border-radius: 4px; background: white;")
        self.product_search.setFixedWidth(250)
        
        self.filters_layout.insertWidget(4, QLabel("Product:"))
        self.filters_layout.insertWidget(5, self.product_search)
        self.btn_apply.clicked.connect(self.load_data)
        
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, header.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 150)
        
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)  # Item Name stretches
        
        for i in [3, 4, 5, 6]:
            header.setSectionResizeMode(i, header.ResizeMode.Interactive)
            self.table.setColumnWidth(i, 120)
            
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
            print("Error loading autocomplete in summary ledger:", e)
        
    def load_data(self):
        d_from = self.start_date.date().toString("yyyy-MM-dd") + " 00:00:00"
        d_to = self.end_date.date().toString("yyyy-MM-dd") + " 23:59:59"
        prod_filter = self.product_search.text().strip()
        
        conn = get_connection()
        if not conn:
            return
            
        cur = conn.cursor()
        try:
            cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        except:
            pass
        
        # We need opening (before d_from), in (between d_from and d_to), out (between d_from and d_to)
        # We will collect transactions as list of tuples: (product_id, part_no, name, type, date, qty_in, qty_out)
        
        prod_where = ""
        params_period = [d_from, d_to]
        params_opening = [d_from]
        
        if prod_filter:
            prod_where = "AND (p.name LIKE ? OR p.part_no LIKE ?)"
            params_period.extend([f"%{prod_filter}%", f"%{prod_filter}%"])
            params_opening.extend([f"%{prod_filter}%", f"%{prod_filter}%"])
            
        entries = []
        try:
            # 1. SALES (Out)
            # Opening (before d_from)
            cur.execute(f"""
                SELECT p.id, p.part_no, p.name, ISNULL(p.active, 1) as active, 0 as qty_in, si.qty as qty_out, 1 as is_opening
                FROM sales s
                JOIN sale_items si ON s.id = si.sale_id
                JOIN products p ON si.part_no = p.part_no
                WHERE s.created_at < ?
                {prod_where}
            """, params_opening)
            entries.extend(cur.fetchall())
            
            # Period (between d_from and d_to)
            cur.execute(f"""
                SELECT p.id, p.part_no, p.name, ISNULL(p.active, 1) as active, 0 as qty_in, si.qty as qty_out, 0 as is_opening
                FROM sales s
                JOIN sale_items si ON s.id = si.sale_id
                JOIN products p ON si.part_no = p.part_no
                WHERE s.created_at BETWEEN ? AND ?
                {prod_where}
            """, params_period)
            entries.extend(cur.fetchall())
            
            # 2. CREDIT NOTES (In)
            cur.execute(f"""
                SELECT p.id, p.part_no, p.name, ISNULL(p.active, 1) as active, cni.qty as qty_in, 0 as qty_out, 1 as is_opening
                FROM credit_notes cn
                JOIN credit_note_items cni ON cn.id = cni.credit_note_id
                JOIN products p ON cni.part_no = p.part_no
                WHERE cn.created_at < ?
                {prod_where}
            """, params_opening)
            entries.extend(cur.fetchall())
            
            cur.execute(f"""
                SELECT p.id, p.part_no, p.name, ISNULL(p.active, 1) as active, cni.qty as qty_in, 0 as qty_out, 0 as is_opening
                FROM credit_notes cn
                JOIN credit_note_items cni ON cn.id = cni.credit_note_id
                JOIN products p ON cni.part_no = p.part_no
                WHERE cn.created_at BETWEEN ? AND ?
                {prod_where}
            """, params_period)
            entries.extend(cur.fetchall())
            
            # 3. PURCHASE INVOICES / ORDERS (In)
            cur.execute("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='purchase_orders'")
            if cur.fetchone():
                cur.execute(f"""
                    SELECT p.id, p.part_no, p.name, ISNULL(p.active, 1) as active, poi.qty as qty_in, 0 as qty_out, 1 as is_opening
                    FROM purchase_orders po
                    JOIN purchase_order_items poi ON po.id = poi.parent_id
                    JOIN products p ON poi.product_id = p.id
                    WHERE po.date < ?
                    {prod_where}
                """, params_opening)
                entries.extend(cur.fetchall())
                
                cur.execute(f"""
                    SELECT p.id, p.part_no, p.name, ISNULL(p.active, 1) as active, poi.qty as qty_in, 0 as qty_out, 0 as is_opening
                    FROM purchase_orders po
                    JOIN purchase_order_items poi ON po.id = poi.parent_id
                    JOIN products p ON poi.product_id = p.id
                    WHERE po.date BETWEEN ? AND ?
                    {prod_where}
                """, params_period)
                entries.extend(cur.fetchall())
                
            # 4. STOCK ENTRIES
            cur.execute("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='stock_entries'")
            if cur.fetchone():
                cur.execute(f"""
                    SELECT p.id, p.part_no, p.name, ISNULL(p.active, 1) as active,
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
                           1 as is_opening
                    FROM stock_entries se
                    JOIN stock_entry_items sei ON se.id = sei.parent_id
                    JOIN products p ON sei.product_id = p.id
                    WHERE se.date < ?
                    {prod_where}
                """, params_opening)
                entries.extend(cur.fetchall())
                
                cur.execute(f"""
                    SELECT p.id, p.part_no, p.name, ISNULL(p.active, 1) as active,
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
                           0 as is_opening
                    FROM stock_entries se
                    JOIN stock_entry_items sei ON se.id = sei.parent_id
                    JOIN products p ON sei.product_id = p.id
                    WHERE se.date BETWEEN ? AND ?
                    {prod_where}
                """, params_period)
                entries.extend(cur.fetchall())
                
        except Exception as e:
            print(f"Error loading summary ledger: {e}")
        finally:
            conn.close()
            
        # Group by product
        # product_id -> {part_no, name, opening, in, out, balance}
        summary = {}
        for e in entries:
            pid = e[0]
            part_no = str(e[1] or "")
            name = str(e[2] or "")
            is_active = e[3]
            q_in = float(e[4] or 0)
            q_out = float(e[5] or 0)
            is_opening = int(e[6] or 0)
            
            if pid not in summary:
                summary[pid] = {
                    "part_no": part_no,
                    "name": name,
                    "active": is_active,
                    "opening": 0.0,
                    "in": 0.0,
                    "out": 0.0,
                    "balance": 0.0
                }
            
            if is_opening:
                summary[pid]["opening"] += (q_in - q_out)
            else:
                summary[pid]["in"] += q_in
                summary[pid]["out"] += q_out
                
        for pid, data in summary.items():
            data["balance"] = data["opening"] + data["in"] - data["out"]
            
        # Sort by product name
        sorted_summary = sorted(summary.values(), key=lambda x: x["name"].lower())
        
        while self.table.rowCount() > 1:
            self.table.removeRow(1)
        
        total_opening = 0.0
        total_in = 0.0
        total_out = 0.0
        total_balance = 0.0
        added_records = 0
        
        for data in sorted_summary:
            # Skip items with 0 for all fields to avoid clutter
            if data["opening"] == 0 and data["in"] == 0 and data["out"] == 0 and data["balance"] == 0:
                continue
                
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            self.table.setItem(row, 0, QTableWidgetItem(data["part_no"]))
            self.table.setItem(row, 1, QTableWidgetItem(data["name"]))
            
            prod_status = "Active" if data.get("active", 1) else "Disabled"
            status_item = QTableWidgetItem(prod_status)
            status_item.setTextAlignment(Qt.AlignCenter)
            if prod_status == "Disabled":
                status_item.setForeground(QColor("#c0392b"))
            else:
                status_item.setForeground(QColor("#27ae60"))
            self.table.setItem(row, 2, status_item)
            
            # Format numbers to handle .0 nicely (e.g. 5 instead of 5.0)
            def fmt(num):
                return f"{int(num)}" if num.is_integer() else f"{num:.2f}"
                
            self.table.setItem(row, 3, QTableWidgetItem(fmt(data["opening"])))
            self.table.setItem(row, 4, QTableWidgetItem(fmt(data["in"])))
            self.table.setItem(row, 5, QTableWidgetItem(fmt(data["out"])))
            
            bal_item = QTableWidgetItem(fmt(data["balance"]))
            font = bal_item.font()
            font.setBold(True)
            bal_item.setFont(font)
            self.table.setItem(row, 6, bal_item)
            
            # Right align numerical columns
            for i in range(3, 7):
                self.table.item(row, i).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
            total_opening += data["opening"]
            total_in += data["in"]
            total_out += data["out"]
            total_balance += data["balance"]
            added_records += 1

        self._update_totals()

class SummaryInventoryLedgerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Summary Inventory Ledger")
        self.setMinimumSize(1000, 700)
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setWindowState(Qt.WindowMaximized)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.ledger_widget = SummaryInventoryLedger(self)
        self.layout.addWidget(self.ledger_widget)

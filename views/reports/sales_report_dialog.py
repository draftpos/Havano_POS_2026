# views/reports/sales_report_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget, QFrame,
    QComboBox, QDateEdit, QGridLayout, QScrollArea
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont
import qtawesome as qta
from database.db import get_connection, fetchall_dicts
from models.company_defaults import get_defaults

# Palette
NAVY = "#1a5fb4"
NAVY_2 = "#162d52"
ACCENT = "#1a5fb4"
WHITE = "#ffffff"
OFF_WHITE = "#f5f8fc"
BORDER = "#c8d8ec"
MUTED = "#5a7a9a"
SUCCESS = "#1a7a3c"

class SalesReportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sales Report")
        self.setWindowState(Qt.WindowMaximized)
        self.setStyleSheet("QDialog { background-color: white; }")
        
        self.filters = {
            "warehouse_id": None,
            "user_id": None,
            "category": "All"
        }
        
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        from views.reports.report_template import ReportTemplate
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.report_template = ReportTemplate(title="Sales Report", is_report=True, parent=self)
        self.report_template.set_headers([
            "Item Code", "Item Name", "Qty Sold", "UoM", 
            "Cost Price", "Selling Price", "Gross Profit", "Warehouse"
        ])
        
        self.report_template.btn_apply.clicked.connect(self._load_data)
        
        filter_btn = QPushButton(" Advanced Filters")
        filter_btn.setIcon(qta.icon("fa5s.filter", color="white"))
        filter_btn.setStyleSheet("""
            QPushButton { background-color: #1a5fb4; color: white; border-radius: 4px; padding: 4px 8px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #1c6dd0; }
        """)
        filter_btn.clicked.connect(self._open_filters)
        
        self.report_template.filters_layout.insertWidget(4, filter_btn)
        
        layout.addWidget(self.report_template)

    def _open_filters(self):
        from views.dialogs.sales_report_filter_dialog import SalesReportFilterDialog
        dlg = SalesReportFilterDialog(self.filters, self)
        if dlg.exec() == QDialog.Accepted:
            self.filters = dlg.get_filters()
            self._load_data()

    def _load_data(self):
        df = self.report_template.start_date.date().toString("yyyy-MM-dd")
        dt = self.report_template.end_date.date().toString("yyyy-MM-dd")
        
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        except:
            pass
        
        query = """
            SELECT 
                si.part_no, si.product_name, SUM(si.qty) as total_qty, si.uom,
                COALESCE(si.cost_price, 0) as cost_price, AVG(si.price) as avg_price,
                w.name as warehouse_name
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            LEFT JOIN warehouses w ON s.warehouse_id = w.id
            LEFT JOIN products p ON si.part_no = p.part_no
            WHERE s.invoice_date >= ? AND s.invoice_date <= ?
        """
        
        params = [df, dt]
        
        if self.filters.get('warehouse_id'):
            query += " AND s.warehouse_id = ?"
            params.append(self.filters['warehouse_id'])
            
        if self.filters.get('user_id'):
            query += " AND s.cashier_id = ?"
            params.append(self.filters['user_id'])
            
        if self.filters.get('category', "All") != "All":
            query += " AND p.category = ?"
            params.append(self.filters['category'])
            
        query += " GROUP BY si.part_no, si.product_name, si.uom, si.cost_price, w.name"
        
        cur.execute(query, params)
        rows = fetchall_dicts(cur)
        conn.close()
        
        data = []
        for row in rows:
            qty = float(row['total_qty'] or 0)
            cost = float(row['cost_price'] or 0)
            sell = float(row['avg_price'] or 0)
            gp = (sell - cost) * qty
            
            data.append([
                row['part_no'] or "",
                row['product_name'] or "",
                f"{qty:.2f}",
                row['uom'] or "Unit",
                f"${cost:.2f}",
                f"${sell:.2f}",
                f"${gp:.2f}",
                row['warehouse_name'] or "Main"
            ])
            
        self.report_template.set_data(data)

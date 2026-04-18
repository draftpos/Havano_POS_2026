from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QDateEdit, QPushButton, QLabel, 
                             QHeaderView, QTabWidget, QWidget)
from PySide6.QtCore import QDate, Qt
import qtawesome as qta
from models.reports import get_sales_items_report
from models.shift import get_shift_reports

class POSReportsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("POS Reports Center")
        self.setMinimumSize(900, 600)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        # Tab 1: X-Report (Shift & Sales History)
        self.tab_x = QWidget()
        self._setup_x_report_tab()
        self.tabs.addTab(self.tab_x, qta.icon("fa5s.chart-bar"), "X-Report (Shifts)")
        
        # Tab 2: Sales Items Report (Requirement 7)
        self.tab_items = QWidget()
        self._setup_items_report_tab()
        self.tabs.addTab(self.tab_items, qta.icon("fa5s.box"), "Sales Items Report")
        
        layout.addWidget(self.tabs)

    # --- X-REPORT TAB SETUP ---
    def _setup_x_report_tab(self):
        lay = QVBoxLayout(self.tab_x)
        filter_row = QHBoxLayout()
        
        self.x_from = QDateEdit(QDate.currentDate())
        self.x_to = QDateEdit(QDate.currentDate())
        btn = QPushButton("Generate X-Report")
        btn.clicked.connect(self._load_x_data)
        
        filter_row.addWidget(QLabel("From:"))
        filter_row.addWidget(self.x_from)
        filter_row.addWidget(QLabel("To:"))
        filter_row.addWidget(self.x_to)
        filter_row.addWidget(btn)
        filter_row.addStretch()
        lay.addLayout(filter_row)
        
        self.table_x = QTableWidget(0, 6)
        self.table_x.setHorizontalHeaderLabels(["Date", "Shift #", "Cashier", "Expected", "Actual", "Variance"])
        self.table_x.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.table_x)

    # --- SALES ITEMS TAB SETUP ---
    def _setup_items_report_tab(self):
        lay = QVBoxLayout(self.tab_items)
        
        ctrls = QHBoxLayout()
        self.items_from = QDateEdit(QDate.currentDate().addDays(-7))
        self.items_to = QDateEdit(QDate.currentDate())
        for d in [self.items_from, self.items_to]:
            d.setCalendarPopup(True); d.setFixedWidth(120)

        btn_load = QPushButton("Generate Items Report")
        btn_load.setStyleSheet(f"background:{ACCENT}; color:{WHITE}; font-weight:bold;")
        btn_load.clicked.connect(self._load_items_data)

        ctrls.addWidget(QLabel("From:")); ctrls.addWidget(self.items_from)
        ctrls.addWidget(QLabel("To:")); ctrls.addWidget(self.items_to)
        ctrls.addWidget(btn_load); ctrls.addStretch()
        lay.addLayout(ctrls)

        self.table_items = QTableWidget(0, 5)
        self.table_items.setHorizontalHeaderLabels(["Product Name", "Part No", "UOM", "Total Qty", "Revenue $"])
        self.table_items.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        lay.addWidget(self.table_items)

    def _load_items_data(self):
        df = self.items_from.date().toPython().isoformat()
        dt = self.items_to.date().toPython().isoformat()
        data = get_sales_items_report(df, dt)
        
        self.table_items.setRowCount(0)
        for d in data:
            r = self.table_items.rowCount()
            self.table_items.insertRow(r)
            self.table_items.setItem(r, 0, QTableWidgetItem(d['product_name']))
            self.table_items.setItem(r, 1, QTableWidgetItem(d['part_no']))
            self.table_items.setItem(r, 2, QTableWidgetItem(d.get('uom', 'Unit')))
            self.table_items.setItem(r, 3, QTableWidgetItem(f"{d['total_qty']:.2f}"))
            self.table_items.setItem(r, 4, QTableWidgetItem(f"{d['total_revenue']:.2f}"))
    

    # --- DATA LOADERS ---
    def _load_x_data(self):
        df = self.x_from.date().toPython().isoformat()
        dt = self.x_to.date().toPython().isoformat()
        shifts = get_shift_reports(df, dt)
        
        self.table_x.setRowCount(0)
        for s in shifts:
            r = self.table_x.rowCount()
            self.table_x.insertRow(r)
            self.table_x.setItem(r, 0, QTableWidgetItem(str(s['created_at'])[:10]))
            self.table_x.setItem(r, 1, QTableWidgetItem(f"#{s['shift_no']}"))
            self.table_x.setItem(r, 2, QTableWidgetItem(str(s['cashier_name'])))
            self.table_x.setItem(r, 3, QTableWidgetItem(f"${s['expected_amount']:.2f}"))
            self.table_x.setItem(r, 4, QTableWidgetItem(f"${s['actual_amount']:.2f}"))
            
            var_item = QTableWidgetItem(f"${s['variance']:.2f}")
            if s['variance'] < 0: var_item.setForeground(Qt.red)
            self.table_x.setItem(r, 5, var_item)

    def _load_items_data(self):
        df = self.items_from.date().toPython().isoformat()
        dt = self.items_to.date().toPython().isoformat()
        data = get_sales_items_report(df, dt)
        
        self.table_items.setRowCount(0)
        for d in data:
            r = self.table_items.rowCount()
            self.table_items.insertRow(r)
            self.table_items.setItem(r, 0, QTableWidgetItem(str(d['part_no'])))
            self.table_items.setItem(r, 1, QTableWidgetItem(str(d['product_name'])))
            self.table_items.setItem(r, 2, QTableWidgetItem(str(d['uom'])))
            self.table_items.setItem(r, 3, QTableWidgetItem(f"{d['total_qty']:.2f}"))
            self.table_items.setItem(r, 4, QTableWidgetItem(f"${d['total_revenue']:.2f}"))
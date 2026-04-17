# =============================================================================
# views/dialogs/pos_reports.py — Requirement 5 (X-Report) & 7 (Sales Items)
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QDateEdit, QPushButton, QLabel, 
    QHeaderView, QTabWidget, QWidget, QMessageBox
)
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor

# Logic Imports
from models.reports import get_sales_items_report
from models.shift import get_shift_reports

# Styling constants to match main_window.py
NAVY = "#0d1f3c"
ACCENT = "#1a5fb4"
WHITE = "#ffffff"
DANGER = "#b02020"
SUCCESS = "#1a7a3c"

class POSReportsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("POS Reports Center")
        self.setMinimumSize(1100, 700) 
        self._build_ui()

    def _build_ui(self):
        # Main vertical layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header Title
        hdr = QLabel("📊 Business Intelligence Reports")
        hdr.setStyleSheet(f"""
            background: {NAVY}; color: {WHITE}; 
            padding: 15px; font-size: 16px; 
            font-weight: bold; border-radius: 5px;
        """)
        layout.addWidget(hdr)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabBar::tab {{ height: 40px; width: 220px; font-weight: bold; }}
            QTabBar::tab:selected {{ color: {ACCENT}; }}
        """)
        
        # Tab 1: X-Report (Requirement 5)
        self.tab_x = QWidget()
        self._setup_x_report_tab()
        self.tabs.addTab(self.tab_x, "📋 X-Report (Shift History)")
        
        # Tab 2: Sales Items Report (Requirement 7)
        self.tab_items = QWidget()
        self._setup_items_report_tab()
        self.tabs.addTab(self.tab_items, "📦 Sales Items Summary")
        
        # ADDED: Stretch factor 1 ensures tabs fill the window
        layout.addWidget(self.tabs, 1) 

    # --- X-REPORT TAB SETUP (Requirement 5) ---
    def _setup_x_report_tab(self):
        lay = QVBoxLayout(self.tab_x)
        
        # Date Range Controls
        ctrls = QHBoxLayout()
        self.x_from = QDateEdit(QDate.currentDate().addDays(-7))
        self.x_to = QDateEdit(QDate.currentDate())
        for d in [self.x_from, self.x_to]:
            d.setCalendarPopup(True)
            d.setFixedWidth(130)
            d.setFixedHeight(35)

        btn_load = QPushButton("Generate X-Report")
        btn_load.setFixedWidth(160)
        btn_load.setFixedHeight(35)
        btn_load.setCursor(Qt.PointingHandCursor)
        btn_load.setStyleSheet(f"background:{ACCENT}; color:{WHITE}; font-weight:bold; border-radius:4px;")
        btn_load.clicked.connect(self._load_x_data)

        ctrls.addWidget(QLabel("From:"))
        ctrls.addWidget(self.x_from)
        ctrls.addWidget(QLabel("To:"))
        ctrls.addWidget(self.x_to)
        ctrls.addSpacing(10)
        ctrls.addWidget(btn_load)
        ctrls.addStretch()
        lay.addLayout(ctrls)

        # Results Table
        self.table_x = QTableWidget(0, 6)
        self.table_x.setHorizontalHeaderLabels([
            "Date", "Shift #", "Cashier", "Expected Total $", "Actual Counted $", "Variance $"
        ])
        self.table_x.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_x.setAlternatingRowColors(True)
        lay.addWidget(self.table_x, 1) # Set stretch factor to 1 to fill space

    def _load_x_data(self):
        """Requirement 5: Fetches shift reconciliation records."""
        df = self.x_from.date().toPython().isoformat()
        dt = self.x_to.date().toPython().isoformat()
        
        try:
            shifts = get_shift_reports(df, dt)
            self.table_x.setRowCount(0)
            for s in shifts:
                r = self.table_x.rowCount()
                self.table_x.insertRow(r)
                
                self.table_x.setItem(r, 0, QTableWidgetItem(str(s['created_at'])[:10]))
                self.table_x.setItem(r, 1, QTableWidgetItem(f"#{s.get('shift_no', s['id'])}"))
                self.table_x.setItem(r, 2, QTableWidgetItem(str(s['cashier_name'])))
                
                exp = float(s.get('expected_amount') or 0)
                act = float(s.get('actual_amount') or 0)
                var = float(s.get('variance') or 0)

                self.table_x.setItem(r, 3, QTableWidgetItem(f"{exp:,.2f}"))
                self.table_x.setItem(r, 4, QTableWidgetItem(f"{act:,.2f}"))
                
                var_item = QTableWidgetItem(f"{var:,.2f}")
                var_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                if var < -0.01:
                    var_item.setForeground(QColor(DANGER)) 
                    f = var_item.font()
                    f.setBold(True)
                    var_item.setFont(f)
                elif var > 0.01:
                    var_item.setForeground(QColor(SUCCESS))
                    
                self.table_x.setItem(r, 5, var_item)
        except Exception as e:
            QMessageBox.warning(self, "Data Error", f"Could not load X-Report: {str(e)}")

    # --- SALES ITEMS TAB SETUP (Requirement 7) ---
    def _setup_items_report_tab(self):
        """Requirement 7: UI for summarized item sales statistics."""
        lay = QVBoxLayout(self.tab_items)
        
        # Controls Row
        ctrls = QHBoxLayout()
        self.item_from = QDateEdit(QDate.currentDate().addDays(-7))
        self.item_to = QDateEdit(QDate.currentDate())
        for d in [self.item_from, self.item_to]:
            d.setCalendarPopup(True)
            d.setFixedWidth(130)
            d.setFixedHeight(35)

        btn_load = QPushButton("📊 Generate Items Summary")
        btn_load.setFixedWidth(210)
        btn_load.setFixedHeight(35)
        btn_load.setCursor(Qt.PointingHandCursor)
        btn_load.setStyleSheet(f"background:{SUCCESS}; color:{WHITE}; font-weight:bold; border-radius:4px;")
        btn_load.clicked.connect(self._load_items_data)

        ctrls.addWidget(QLabel("From:"))
        ctrls.addWidget(self.item_from)
        ctrls.addWidget(QLabel("To:"))
        ctrls.addWidget(self.item_to)
        ctrls.addSpacing(10)
        ctrls.addWidget(btn_load)
        ctrls.addStretch()
        lay.addLayout(ctrls)

        # Items Table
        self.table_items = QTableWidget(0, 5)
        self.table_items.setHorizontalHeaderLabels([
            "Product Name", "Part No", "UOM", "Total Qty Sold", "Total Revenue $"
        ])
        self.table_items.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_items.setAlternatingRowColors(True)
        lay.addWidget(self.table_items, 1) # Set stretch factor to 1 to fill space

    def _load_items_data(self):
        """Requirement 7: Populates table with summarized item sales."""
        df = self.item_from.date().toPython().isoformat()
        dt = self.item_to.date().toPython().isoformat()
        
        try:
            data = get_sales_items_report(df, dt)
            self.table_items.setRowCount(0)
            
            for d in data:
                r = self.table_items.rowCount()
                self.table_items.insertRow(r)
                
                self.table_items.setItem(r, 0, QTableWidgetItem(str(d['product_name'])))
                self.table_items.setItem(r, 1, QTableWidgetItem(str(d['part_no'])))
                self.table_items.setItem(r, 2, QTableWidgetItem(str(d.get('uom', 'Unit'))))
                
                qty_item = QTableWidgetItem(f"{float(d['total_qty']):.2f}")
                qty_item.setTextAlignment(Qt.AlignCenter)
                self.table_items.setItem(r, 3, qty_item)
                
                rev_item = QTableWidgetItem(f"{float(d['total_revenue']):,.2f}")
                rev_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                rev_item.setForeground(QColor(ACCENT))
                self.table_items.setItem(r, 4, rev_item)
                
        except Exception as e:
            QMessageBox.warning(self, "Data Error", f"Could not load items report: {str(e)}")
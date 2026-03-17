# =============================================================================
# views/dialogs/pos_reports.py — Requirement 5 (X-Report) & 7 (Sales Items)
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QDateEdit, QPushButton, QLabel, 
    QHeaderView, QTabWidget, QWidget, QFrame
)
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor

from models.reports import get_sales_items_report
from models.shift import get_shift_reports

# Styling constants to match main_window.py
NAVY = "#0d1f3c"
ACCENT = "#1a5fb4"
WHITE = "#ffffff"
DANGER = "#b02020"

class POSReportsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("POS Reports Center")
        self.setMinimumSize(1000, 650)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header Title
        hdr = QLabel("📊 Business Intelligence Reports")
        hdr.setStyleSheet(f"background:{NAVY}; color:{WHITE}; padding:15px; font-size:16px; font-weight:bold; border-radius:5px;")
        layout.addWidget(hdr)

        self.tabs = QTabWidget()
        
        # Tab 1: X-Report (Requirement 5)
        self.tab_x = QWidget()
        self._setup_x_report_tab()
        self.tabs.addTab(self.tab_x, "📋 X-Report (Shift History)")
        
        # Tab 2: Sales Items Report (Requirement 7)
        self.tab_items = QWidget()
        self._setup_items_report_tab()
        self.tabs.addTab(self.tab_items, "📦 Sales Items Summary")
        
        layout.addWidget(self.tabs)

    # --- X-REPORT TAB SETUP (Requirement 5) ---
    def _setup_x_report_tab(self):
        lay = QVBoxLayout(self.tab_x)
        
        # Date Range Controls
        ctrls = QHBoxLayout()
        self.x_from = QDateEdit(QDate.currentDate().addDays(-7))
        self.x_to = QDateEdit(QDate.currentDate())
        for d in [self.x_from, self.x_to]:
            d.setCalendarPopup(True)
            d.setFixedWidth(120)
            d.setFixedHeight(30)

        btn_load = QPushButton("Generate X-Report")
        btn_load.setFixedWidth(150)
        btn_load.setFixedHeight(30)
        btn_load.setStyleSheet(f"background:{ACCENT}; color:{WHITE}; font-weight:bold; border-radius:4px;")
        btn_load.clicked.connect(self._load_x_data)

        ctrls.addWidget(QLabel("From:"))
        ctrls.addWidget(self.x_from)
        ctrls.addWidget(QLabel("To:"))
        ctrls.addWidget(self.x_to)
        ctrls.addWidget(btn_load)
        ctrls.addStretch()
        lay.addLayout(ctrls)

        # Results Table
        self.table_x = QTableWidget(0, 6)
        self.table_x.setHorizontalHeaderLabels([
            "Date", "Shift #", "Cashier", "Expected $", "Actual $", "Variance $"
        ])
        self.table_x.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_x.setAlternatingRowColors(True)
        lay.addWidget(self.table_x)

    def _load_x_data(self):
        """Fetches shift data from DB and calculates variance visualization"""
        df = self.x_from.date().toPython().isoformat()
        dt = self.x_to.date().toPython().isoformat()
        
        shifts = get_shift_reports(df, dt)
        
        self.table_x.setRowCount(0)
        for s in shifts:
            r = self.table_x.rowCount()
            self.table_x.insertRow(r)
            
            # Populate columns
            self.table_x.setItem(r, 0, QTableWidgetItem(str(s['created_at'])[:10]))
            self.table_x.setItem(r, 1, QTableWidgetItem(f"#{s.get('shift_no', s['id'])}"))
            self.table_x.setItem(r, 2, QTableWidgetItem(str(s['cashier_name'])))
            
            exp = float(s['expected_amount'] or 0)
            act = float(s['actual_amount'] or 0)
            var = float(s['variance'] or 0)

            self.table_x.setItem(r, 3, QTableWidgetItem(f"{exp:.2f}"))
            self.table_x.setItem(r, 4, QTableWidgetItem(f"{act:.2f}"))
            
            var_item = QTableWidgetItem(f"{var:.2f}")
            var_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            # Strategic Variance Highlighting
            if var < -0.01:
                var_item.setForeground(QColor(DANGER)) # Red for shortage
            elif var > 0.01:
                var_item.setForeground(QColor("#1a7a3c")) # Green for surplus
                
            self.table_x.setItem(r, 5, var_item)

    # --- SALES ITEMS TAB SETUP (Requirement 7) ---
    def _setup_items_report_tab(self):
        # We will populate this in Step 7
        lay = QVBoxLayout(self.tab_items)
        lay.addWidget(QLabel("Sales Items Report - Configure in Step 7"))
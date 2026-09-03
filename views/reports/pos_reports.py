from PySide6.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QMessageBox
from PySide6.QtCore import Qt
import qtawesome as qta

from models.reports import get_sales_items_report, get_consumed_bundle_items_report
from models.shift import get_shift_reports
from views.reports.report_template import ReportTemplate

class POSReportsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("POS Reports Center")
        self.setMinimumSize(1000, 700)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        
        # ── Tab 1: X-Report (Shifts) ──
        self.tab_x = ReportTemplate("X-Report (Shifts)", is_report=True, parent=self)
        self.tab_x.set_headers(["Date", "Shift #", "Cashier", "Expected", "Actual", "Variance"])
        self.tab_x.btn_apply.clicked.connect(self._load_x_data)
        self._load_x_data()
        self.tabs.addTab(self.tab_x, qta.icon("fa5s.chart-bar"), "X-Report (Shifts)")
        
        # ── Tab 2: Sales Items Report ──
        self.tab_items = ReportTemplate("Sales Items Report", is_report=True, parent=self)
        self.tab_items.set_headers(["Product Name", "Part No", "UOM", "Total Qty", "Revenue $"])
        self.tab_items.btn_apply.clicked.connect(self._load_items_data)
        self._load_items_data()
        self.tabs.addTab(self.tab_items, qta.icon("fa5s.box"), "Sales Items Report")
        
        # ── Tab 3: Consumed Bundle Items ──
        self.tab_consumed = ReportTemplate("Consumed Bundle Items", is_report=True, parent=self)
        self.tab_consumed.set_headers(["Parent Bundle", "Component Part No", "Component Name", "Consumed Qty"])
        self.tab_consumed.btn_apply.clicked.connect(self._load_consumed_data)
        self._load_consumed_data()
        self.tabs.addTab(self.tab_consumed, qta.icon("fa5s.cubes"), "Consumed Bundle Items")
        
        layout.addWidget(self.tabs)

    def _load_x_data(self):
        df = self.tab_x.start_date.date().toPython().isoformat()
        dt = self.tab_x.end_date.date().toPython().isoformat()
        shifts = get_shift_reports(df, dt)
        
        display_data = []
        for s in shifts:
            display_data.append([
                str(s.get('created_at', ''))[:10],
                f"#{s.get('shift_no', '')}",
                str(s.get('cashier_name', '')),
                f"${s.get('expected_amount', 0):.2f}",
                f"${s.get('actual_amount', 0):.2f}",
                f"${s.get('variance', 0):.2f}"
            ])
            
        self.tab_x.set_data(display_data)
        
        # Colorize variance
        for r in range(1, self.tab_x.table.rowCount() - 1):
            var_item = self.tab_x.table.item(r, 5)
            if var_item and "-" in var_item.text():
                var_item.setForeground(Qt.red)

    def _load_items_data(self):
        df = self.tab_items.start_date.date().toPython().isoformat()
        dt = self.tab_items.end_date.date().toPython().isoformat()
        data = get_sales_items_report(df, dt)
        
        display_data = []
        for d in data:
            display_data.append([
                str(d.get('product_name', '')),
                str(d.get('part_no', '')),
                str(d.get('uom', 'Unit')),
                f"{d.get('total_qty', 0):.2f}",
                f"${d.get('total_revenue', 0):.2f}"
            ])
            
        self.tab_items.set_data(display_data)

    def _load_consumed_data(self):
        df = self.tab_consumed.start_date.date().toPython().isoformat()
        dt = self.tab_consumed.end_date.date().toPython().isoformat()
        data = get_consumed_bundle_items_report(df, dt)
        
        display_data = []
        for d in data:
            display_data.append([
                str(d.get('parent_bundle', '')),
                str(d.get('component_part_no', '')),
                str(d.get('component_name', '')),
                f"{d.get('consumed_qty', 0):.2f}"
            ])
            
        self.tab_consumed.set_data(display_data)

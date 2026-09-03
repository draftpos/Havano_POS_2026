from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from views.reports.report_template import ReportTemplate
from models.reports import get_consumed_bundle_items_report

class ConsumedItemsReportPage(ReportTemplate):
    def __init__(self, parent=None):
        super().__init__("Consumed Bundle Items Report", is_report=True, parent=parent)
        self.set_headers(["Parent Bundle", "Item Code", "Item Name", "Consumed Qty", "Cost Value", "Selling Price", "Profit", "% Profit"])
        
        # Disconnect default filter logic to fetch from DB instead
            
        self.btn_apply.clicked.connect(self._fetch_data)
        
        # Initial load
        self._fetch_data()

    def showEvent(self, event):
        super().showEvent(event)
        self._fetch_data()

    def _fetch_data(self):
        df = self.start_date.date().toPython().isoformat()
        dt = self.end_date.date().toPython().isoformat()
        data = get_consumed_bundle_items_report(df, dt)
        
        display_data = []
        for d in data:
            cost = float(d.get('total_cost', 0.0))
            price = float(d.get('selling_price', 0.0))
            profit = float(d.get('profit', 0.0))
            profit_perc = float(d.get('profit_perc', 0.0))
            
            display_data.append([
                str(d.get('parent_bundle', '')),
                str(d.get('component_part_no', '')),
                str(d.get('component_name', '')),
                f"{d.get('consumed_qty', 0):.2f}",
                f"${cost:.2f}",
                f"${price:.2f}",
                f"${profit:.2f}",
                f"{profit_perc:.1f}%"
            ])
            
        self.set_data(display_data)
        
        # Colorize profit
        for r in range(1, self.table.rowCount() - 1):
            prof_item = self.table.item(r, 6)
            perc_item = self.table.item(r, 7)
            if prof_item and "-" in prof_item.text():
                prof_item.setForeground(Qt.red)
            elif prof_item:
                prof_item.setForeground(Qt.darkGreen)
                
            if perc_item and "-" in perc_item.text():
                perc_item.setForeground(Qt.red)
            elif perc_item:
                perc_item.setForeground(Qt.darkGreen)

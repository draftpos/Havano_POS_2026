from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from views.reports.report_template import ReportTemplate
from models.reports import get_daily_profit_trend

class DailyProfitReportPage(ReportTemplate):
    def __init__(self, parent=None):
        super().__init__("Daily Average Profit Report", is_report=True, parent=parent)
        self.set_headers(["Date", "Invoices", "Avg Profit/Inv ($)", "Avg Profit (%)"])
        
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
        data = get_daily_profit_trend(df, dt)
        
        display_data = []
        for r in data:
            display_data.append([
                str(r.get('date', '')),
                str(r.get('invoices', 0)),
                f"${float(r.get('avg_profit', 0)):.2f}",
                f"{float(r.get('avg_perc', 0)):.1f}%"
            ])
            
        self.set_data(display_data)
        
        for row in range(1, self.table.rowCount() - 1):
            # Center align invoices
            self.table.item(row, 1).setTextAlignment(Qt.AlignCenter)
            # Right align money and percentages
            self.table.item(row, 2).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.item(row, 3).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

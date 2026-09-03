from views.reports.report_template import ReportTemplate
from models.supplier import get_all_suppliers

class SupplierListReport(ReportTemplate):
    def __init__(self, parent=None):
        super().__init__(title="Supplier Balances", is_report=True, parent=parent)
        self.set_headers(["Supplier Name", "Phone", "Balance Owed"])
        self._load()

    def showEvent(self, event):
        super().showEvent(event)
        self._load()

    def _load(self):
        suppliers = get_all_suppliers()
        data = []
        for sup in suppliers:
            try:
                bal = float(sup.get("balance") or 0.0)
            except (ValueError, TypeError):
                bal = 0.0
            data.append([
                sup.get("name", ""),
                sup.get("phone", ""),
                f"${bal:.2f}"
            ])
        self.set_data(data)

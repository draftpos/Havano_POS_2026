import os
import re

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\dialogs\pos_reports.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target_start = '    def _setup_sales_report_ui(self, parent_layout):'
target_end = '    # ── FILTER DIALOG'

start_idx = content.find(target_start)
end_idx = content.find(target_end)

new_ui = '''    def _setup_sales_report_ui(self, parent_layout):
        from views.reports.report_template import ReportTemplate
        import qtawesome as qta
        
        self.sr_report = ReportTemplate("Sales Reports", is_report=True, show_date_filter=True, parent=self)
        self.sr_report.set_headers(["Item Code", "Item Name", "Qty Sold", "UoM", "Cost Price", "Selling Price", "Gross Profit", "Warehouse"])
        self.table_sr = self.sr_report.table
        
        # Override the apply button to use our reload
        try:
            self.sr_report.btn_apply.clicked.disconnect()
        except:
            pass
        self.sr_report.btn_apply.clicked.connect(self._load_sales_report)
        
        # Override PDF button
        try:
            self.sr_report.btn_pdf.clicked.disconnect()
        except:
            pass
        self.sr_report.btn_pdf.clicked.connect(self._export_pdf)
        
        # Keep references to start/end dates
        self.sr_from = self.sr_report.start_date
        self.sr_to = self.sr_report.end_date
        
        self.current_filters = {
            "date_from":    self.sr_from.date().toString("yyyy-MM-dd"),
            "date_to":      self.sr_to.date().toString("yyyy-MM-dd"),
            "warehouse_id": None,
            "user_id":      None,
            "category":     None,
        }

        btn_filter = QPushButton(" Filters...")
        btn_filter.setIcon(qta.icon("fa5s.filter", color="white"))
        btn_filter.setStyleSheet(f"background:{ACCENT}; color:{WHITE}; padding:4px 12px; border-radius:4px; font-weight:bold; font-size:11px;")
        btn_filter.clicked.connect(self._open_filter_dialog)
        
        # Insert filter right next to apply
        self.sr_report.filters_layout.insertWidget(4, btn_filter)

        parent_layout.addWidget(self.sr_report, 1)

        totals = QHBoxLayout()
        self.lbl_total_qty  = QLabel("Total Qty: 0")
        self.lbl_total_cost = QLabel("Total Cost: $0.00")
        self.lbl_total_rev  = QLabel("Total Revenue: $0.00")
        self.lbl_total_gp   = QLabel("Gross Profit: $0.00")
        for lbl in [self.lbl_total_qty, self.lbl_total_cost,
                    self.lbl_total_rev, self.lbl_total_gp]:
            lbl.setStyleSheet(f"color:{NAVY}; font-weight:bold; font-size:13px;")
            totals.addWidget(lbl)
        totals.addStretch()
        parent_layout.addLayout(totals)

'''

if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_ui + content[end_idx:]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Refactored _setup_sales_report_ui')

import os
import re

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\dialogs\pos_reports.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target_start = '    def _setup_consumed_items_ui(self, parent_layout):'
target_end = '    def _load_consumed_items_report(self):'

start_idx = content.find(target_start)
end_idx = content.find(target_end)

new_ui = '''    def _setup_consumed_items_ui(self, parent_layout):
        from views.reports.report_template import ReportTemplate
        import qtawesome as qta
        
        self.ci_report = ReportTemplate("Consumed Bundle Items Report", is_report=True, show_date_filter=True, parent=self)
        self.ci_report.set_headers(["Parent Bundle", "Component Code", "Component Name", "Total Consumed Qty"])
        self.table_ci = self.ci_report.table
        
        # Override apply
        try:
            self.ci_report.btn_apply.clicked.disconnect()
        except:
            pass
        self.ci_report.btn_apply.clicked.connect(self._load_consumed_items_report)
        
        # Override PDF
        try:
            self.ci_report.btn_pdf.clicked.disconnect()
        except:
            pass
        self.ci_report.btn_pdf.clicked.connect(self._export_consumed_pdf)
        
        # Override Excel
        try:
            self.ci_report.btn_excel.clicked.disconnect()
        except:
            pass
        self.ci_report.btn_excel.clicked.connect(self._export_consumed_excel)
        
        # Keep refs
        self.ci_from = self.ci_report.start_date
        self.ci_to = self.ci_report.end_date

        parent_layout.addWidget(self.ci_report, 1)

'''

if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_ui + content[end_idx:]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Refactored _setup_consumed_items_ui')

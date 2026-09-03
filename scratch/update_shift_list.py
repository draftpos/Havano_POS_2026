with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the shift history page 1 UI
start = content.find('# ─── Page 1: Shift History List')
if start == -1: start = content.find('# ┌── Page 1: Shift History List')

end = content.find('self.shift_history_stack.addWidget(page1)', start)
if start != -1 and end != -1:
    new_page1 = '''# ─── Page 1: Shift History List 
        page1 = QWidget()
        p1_lay = QVBoxLayout(page1)
        p1_lay.setContentsMargins(0, 0, 0, 0)
        p1_lay.setSpacing(0)

        from views.reports.report_template import ReportTemplate
        self.shift_history_report = ReportTemplate("Shift Reconciliations History", is_report=False, show_date_filter=False, parent=self)
        self.shift_history_report.set_headers(["Date", "Shift #", "Expected Amount", "Actual Amount", "Variance"])
        
        mod_logs_btn = QPushButton("Modified Reconciliations")
        mod_logs_btn.setStyleSheet("background-color: #f57c00; color: white; border: none; border-radius: 4px; font-weight: bold; padding: 0 16px; height: 34px;")
        mod_logs_btn.clicked.connect(self._on_view_modified_logs_clicked)
        self.shift_history_report.filters_layout.addWidget(mod_logs_btn)

        view_details_btn = QPushButton("View Breakdown")
        view_details_btn.setStyleSheet(f"background-color: {ACCENT}; color: white; border: none; border-radius: 4px; font-weight: bold; padding: 0 16px; height: 34px;")
        view_details_btn.clicked.connect(self._on_view_details_clicked)
        self.shift_history_report.filters_layout.addWidget(view_details_btn)

        self.shift_history_table = self.shift_history_report.table
        hh = self.shift_history_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        self.shift_history_table.setColumnWidth(1, 100)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        self.shift_history_table.setColumnWidth(2, 160)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        self.shift_history_table.setColumnWidth(3, 160)
        hh.setSectionResizeMode(4, QHeaderView.Fixed)
        self.shift_history_table.setColumnWidth(4, 160)

        self.shift_history_table.doubleClicked.connect(self._on_shift_double_clicked)
        
        p1_lay.addWidget(self.shift_history_report, 1)
        self.shift_history_stack.addWidget(page1)
'''

    content = content[:start] + new_page1 + content[end+len('self.shift_history_stack.addWidget(page1)'):]
    with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py', 'w', encoding='utf-8') as f:
        f.write(content)

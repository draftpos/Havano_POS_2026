import os
path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

out = []
i = 0
in_target = False
while i < len(lines):
    line = lines[i]
    if '# ΓöÇΓöÇ Page 1: Shift History List' in line or '# ── Page 1: Shift History List' in line:
        in_target = True
        
        new_block = '''        # ── Page 1: Shift History List ──
        from views.reports.report_template import ReportTemplate
        self.shift_report = ReportTemplate("Shift Reconciliations History", is_report=True, parent=self)
        self.shift_report.set_headers(["Date", "Shift #", "Expected Amount", "Actual Amount", "Variance"])
        self.shift_history_table = self.shift_report.table
        self.shift_history_table.doubleClicked.connect(self._on_shift_double_clicked)
        
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

        # Modified Logs Button
        mod_logs_btn = QPushButton(" Modified Reconciliations")
        mod_logs_btn.setIcon(qta.icon("fa5s.history", color="white"))
        mod_logs_btn.setStyleSheet(f"background:#f57c00; color:white; padding:8px 15px; border-radius:4px; font-weight:bold;")
        mod_logs_btn.clicked.connect(self._on_view_modified_logs_clicked)
        
        view_details_btn = QPushButton(" View Breakdown")
        view_details_btn.setIcon(qta.icon("fa5s.arrow-right", color="white"))
        view_details_btn.setStyleSheet(f"background:{ACCENT}; color:white; padding:8px 15px; border-radius:4px; font-weight:bold;")
        view_details_btn.clicked.connect(self._on_view_details_clicked)
        
        self.shift_report.filters_layout.addWidget(mod_logs_btn)
        self.shift_report.filters_layout.addWidget(view_details_btn)
        
        self.shift_history_stack.addWidget(self.shift_report)
'''
        out.append(new_block)
        
    elif in_target:
        if '# ΓöÇΓöÇ Page 2: Cashier Breakdown Detail Page' in line or '# ── Page 2: Cashier Breakdown Detail Page' in line:
            in_target = False
            out.append(line)
        else:
            pass # skip old page1 lines
    else:
        out.append(line)
    
    i += 1

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(out)
print('Refactored Shift History tab to use ReportTemplate')

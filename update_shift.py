import re

file_path = 'views/main_window.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

new_build = '''        # === Page 1: Shift History List ===
        page1 = QWidget()
        p1_lay = QVBoxLayout(page1)
        p1_lay.setContentsMargins(0, 0, 0, 0)
        p1_lay.setSpacing(0)

        from views.reports.report_template import ReportTemplate
        self.shift_report = ReportTemplate("Shift Reconciliations History", is_report=False, show_date_filter=False, parent=page1)
        self.shift_report.set_headers(["Date", "Shift #", "Expected Amount", "Actual Amount", "Variance"])
        self.shift_history_table = self.shift_report.table

        # Modified Logs Button
        mod_logs_btn = QPushButton(" Modified Reconciliations")
        mod_logs_btn.setIcon(qta.icon("fa5s.history", color="white"))
        mod_logs_btn.setFixedHeight(28)
        mod_logs_btn.setCursor(Qt.PointingHandCursor)
        mod_logs_btn.setStyleSheet("QPushButton { background-color: #f57c00; color: white; border: none; border-radius: 4px; font-size: 11px; font-weight: bold; padding: 0 12px; margin-right: 4px; } QPushButton:hover { background-color: #e65100; }")
        mod_logs_btn.clicked.connect(self._on_view_modified_logs_clicked)

        view_details_btn = QPushButton(" View Breakdown")
        view_details_btn.setIcon(qta.icon("fa5s.arrow-right", color="white"))
        view_details_btn.setFixedHeight(28)
        view_details_btn.setCursor(Qt.PointingHandCursor)
        view_details_btn.setStyleSheet(f"QPushButton {{ background-color: {ACCENT}; color: white; border: none; border-radius: 4px; font-size: 11px; font-weight: bold; padding: 0 12px; }} QPushButton:hover {{ background-color: {ACCENT_H if 'ACCENT_H' in globals() else '#1b4a82'}; }}")
        view_details_btn.clicked.connect(self._on_view_details_clicked)

        self.shift_report.filters_layout.insertWidget(1, mod_logs_btn)
        self.shift_report.filters_layout.insertWidget(2, view_details_btn)

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
        
        p1_lay.addWidget(self.shift_report)
        self.shift_history_stack.addWidget(page1)
'''

pattern = r'        #.*Page 1: Shift History List.*?\n        page1 = QWidget\(\)\n.*?self\.shift_history_stack\.addWidget\(page1\)'

new_content = re.sub(pattern, new_build, content, flags=re.DOTALL)

if new_content != content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Updated views/main_window.py successfully.")
else:
    print("No matches found or no changes made.")

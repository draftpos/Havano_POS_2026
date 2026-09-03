import re

file_path = 'views/dialogs/sales_list_dialog.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace _build_ui of SalesListPage
new_build = '''    def _build_ui(self):
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        from views.reports.report_template import ReportTemplate
        self.report = ReportTemplate("Sales Invoices", is_report=False, show_date_filter=False, parent=self)
        self.report.set_headers([c[0] for c in _COLUMNS])
        
        self.table = self.report.table
        
        hh = self.table.horizontalHeader()
        for i, (_, _, w, _, stretch) in enumerate(_COLUMNS):
            if stretch:
                hh.setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                hh.setSectionResizeMode(i, QHeaderView.Fixed)
                self.table.setColumnWidth(i, w)
                
            if self._is_offline and _COLUMNS[i][1] in ("synced", "frappe_ref"):
                self.table.setColumnHidden(i, True)

        self.table.doubleClicked.connect(self._on_view_details)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)

        # Custom Buttons
        self.view_btn = QPushButton(" View Details")
        self.view_btn.setIcon(qta.icon("fa5s.eye", color="white"))
        self.view_btn.setFixedHeight(28)
        self.view_btn.setStyleSheet(f"QPushButton {{ background-color: {ACCENT}; color: white; border: none; border-radius: 4px; padding: 0 12px; font-weight: bold; font-size: 11px; }} QPushButton:hover {{ background-color: {ACCENT_H}; }} QPushButton:disabled {{ background-color: {MUTED}; }}")
        
        self.delete_btn = QPushButton(" Delete (F4)")
        self.delete_btn.setIcon(qta.icon("fa5s.trash", color="white"))
        self.delete_btn.setFixedHeight(28)
        self.delete_btn.setStyleSheet(f"QPushButton {{ background-color: {DANGER}; color: white; border: none; border-radius: 4px; padding: 0 12px; font-weight: bold; font-size: 11px; }} QPushButton:hover {{ background-color: {DANGER_H}; }} QPushButton:disabled {{ background-color: {MUTED}; }}")
        
        self.sync_btn = QPushButton(" Sync Now")
        self.sync_btn.setIcon(qta.icon("fa5s.sync-alt", color="white"))
        self.sync_btn.setFixedHeight(28)
        self.sync_btn.setStyleSheet(f"QPushButton {{ background-color: {SUCCESS}; color: white; border: none; border-radius: 4px; padding: 0 12px; font-weight: bold; font-size: 11px; }} QPushButton:hover {{ background-color: #1e824c; }}")
        
        self.filter_btn = QPushButton(" Unsynced")
        self.filter_btn.setFixedHeight(28)
        self.filter_btn.setStyleSheet(f"QPushButton {{ background-color: #7d6608; color: white; border: none; border-radius: 4px; padding: 0 12px; font-weight: bold; font-size: 11px; }}")

        if self._is_offline:
            self.sync_btn.hide()
            self.filter_btn.hide()

        self.view_btn.setEnabled(False)
        self.delete_btn.setVisible(False)

        self.view_btn.clicked.connect(self._on_view_details)
        self.delete_btn.clicked.connect(self._on_delete)
        self.sync_btn.clicked.connect(self._on_sync_now)
        self.filter_btn.clicked.connect(self._toggle_unsynced_filter)
        
        try:
            self.report.btn_excel.clicked.disconnect()
            self.report.btn_pdf.clicked.disconnect()
        except:
            pass
        self.report.btn_excel.clicked.connect(self._on_export_list)
        self.report.btn_pdf.clicked.connect(self._on_preview_pdf)

        self.report.filters_layout.insertWidget(1, self.filter_btn)
        self.report.filters_layout.insertWidget(2, self.sync_btn)
        self.report.filters_layout.insertWidget(3, self.view_btn)
        self.report.filters_layout.insertWidget(4, self.delete_btn)

        # summary bar
        summary = QWidget(); summary.setFixedHeight(44)
        summary.setStyleSheet(f"background-color:{NAVY};")
        sl = QHBoxLayout(summary); sl.setContentsMargins(20,0,20,0); sl.setSpacing(32)

        self.count_lbl    = QLabel("Sales: 0")
        self.total_lbl    = QLabel("Total: .00")
        self.tendered_lbl = QLabel("Tendered: .00")
        self.change_lbl   = QLabel("Change: .00")
        self.sync_lbl     = QLabel("")
        if self._is_offline:
            self.sync_lbl.hide()

        for lbl, color in [(self.count_lbl, WHITE),(self.total_lbl, WHITE),
                           (self.tendered_lbl, WHITE),(self.change_lbl, WHITE),
                           (self.sync_lbl, AMBER)]:
            lbl.setStyleSheet(f"font-weight:bold;font-size:13px;color:{color};background:transparent;")
            sl.addWidget(lbl)
        sl.addStretch()
        
        self.report.main_layout.addWidget(summary)
        root.addWidget(self.report)
'''

pattern = r'    def _build_ui\(self\):.*?root\.addWidget\(body\)'
content = re.sub(pattern, new_build, content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated sales_list_dialog.py successfully.")

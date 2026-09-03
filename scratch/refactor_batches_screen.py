import os

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\inventory\batches_screen.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target_start = '    def setup_ui(self):'
target_end = '    def _load_products(self):'

# We want the second setup_ui (which is for BatchesScreen)
first_setup_ui = content.find(target_start)
second_setup_ui = content.find(target_start, first_setup_ui + 1)

end_idx = content.find(target_end, second_setup_ui)

new_ui = '''    def setup_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        
        from views.reports.report_template import ReportTemplate
        self.report = ReportTemplate("Batches", is_report=False, show_date_filter=False, parent=self)
        self.report.set_headers(["Batch #", "Product", "Qty", "Expiry Date", "Notes"])
        
        self.table_batches = self.report.table
        hh = self.table_batches.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for i in [0, 2, 3, 4]: hh.setSectionResizeMode(i, QHeaderView.Fixed)
        self.table_batches.setColumnWidth(0, 150)
        self.table_batches.setColumnWidth(2, 100)
        self.table_batches.setColumnWidth(3, 120)
        self.table_batches.setColumnWidth(4, 200)

        # Filters
        self.combo_product = QComboBox()
        self.combo_product.setFixedWidth(200)
        self.combo_product.addItem("- All Products -", None)
        self.combo_product.currentIndexChanged.connect(self._load_batches)
        self.report.filters_layout.insertWidget(4, self.combo_product)

        # Add Button
        try: self.report.btn_add.clicked.disconnect()
        except: pass
        self.report.btn_add.clicked.connect(self._open_add_dialog)
        
        # Connect PDF & Excel
        try: self.report.btn_pdf.clicked.disconnect()
        except: pass
        self.report.btn_pdf.clicked.connect(self._export_pdf)
        try: self.report.btn_excel.clicked.disconnect()
        except: pass
        self.report.btn_excel.clicked.connect(self._export_excel)

        self.table_batches.itemDoubleClicked.connect(self._on_row_double_clicked)
        main_lay.addWidget(self.report, 1)

'''

if second_setup_ui != -1 and end_idx != -1:
    content = content[:second_setup_ui] + new_ui + content[end_idx:]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully refactored BatchesScreen.")

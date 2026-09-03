import os
import re

dir_path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\inventory'

for filename in os.listdir(dir_path):
    if not filename.endswith('_screen.py'): continue
    path = os.path.join(dir_path, filename)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the class name
    m = re.search(r'class (\w+Screen)\(QWidget\):', content)
    if not m: continue
    cls_name = m.group(1)

    # We want to replace _setup_ui entirely
    start_str = '    def _setup_ui(self):'
    start_idx = content.find(start_str)
    if start_idx == -1: continue

    end_str = '    def _load_data(self):'
    end_idx = content.find(end_str)
    if end_idx == -1:
        end_str = '    def _on_search'
        end_idx = content.find(end_str)
    if end_idx == -1:
        end_idx = content.find('    def _export_pdf')
    if end_idx == -1: continue

    # What's the title?
    title_m = re.search(r'lbl_title = QLabel\("([^"]+)"\)', content[start_idx:end_idx])
    title = title_m.group(1) if title_m else cls_name.replace("Screen", "")
    
    # What are the headers?
    headers_m = re.search(r'setHorizontalHeaderLabels\(\[(.*?)\]\)', content[start_idx:end_idx], re.DOTALL)
    headers = headers_m.group(1) if headers_m else '"ID", "Name"'

    new_ui = f'''    def _setup_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        
        from views.reports.report_template import ReportTemplate
        self.report = ReportTemplate("{title}", is_report=False, show_date_filter=False, parent=self)
        self.report.set_headers([{headers}])
        
        self._tbl = self.report.table
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        
        try:
            self.report.btn_add.clicked.disconnect()
        except: pass
        self.report.btn_add.clicked.connect(self._open_add_dialog)
        
        try:
            self.report.btn_pdf.clicked.disconnect()
        except: pass
        if hasattr(self, '_export_pdf'):
            self.report.btn_pdf.clicked.connect(self._export_pdf)
            
        try:
            self.report.btn_excel.clicked.disconnect()
        except: pass
        if hasattr(self, '_export_excel'):
            self.report.btn_excel.clicked.connect(self._export_excel)
            
        if hasattr(self, '_on_search'):
            self.report.global_search.textChanged.disconnect()
            self.report.global_search.textChanged.connect(self._on_search)
            self._search_input = self.report.global_search

        main_lay.addWidget(self.report, 1)

'''
    
    content = content[:start_idx] + new_ui + content[end_idx:]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Refactored {filename}")

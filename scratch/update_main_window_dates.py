with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update show_date_filter
content = content.replace('show_date_filter=False', 'show_date_filter=True')
content = content.replace('p1_lay.addWidget(self.shift_history_report, 1)', 'self.shift_history_report.btn_apply.clicked.connect(self.load_shift_history)\n        p1_lay.addWidget(self.shift_history_report, 1)')

# 2. Update load_shift_history
old_func = '''    def load_shift_history(self):
        try:
            from models.shift import get_shift_reports
            shifts = get_shift_reports()'''

new_func = '''    def load_shift_history(self):
        try:
            from models.shift import get_shift_reports
            date_from = None
            date_to = None
            if hasattr(self, "shift_history_report"):
                date_from = self.shift_history_report.start_date.date().toString("yyyy-MM-dd") + " 00:00:00"
                date_to = self.shift_history_report.end_date.date().toString("yyyy-MM-dd") + " 23:59:59"
            shifts = get_shift_reports(date_from=date_from, date_to=date_to)'''

content = content.replace(old_func, new_func)

with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py', 'w', encoding='utf-8') as f:
    f.write(content)

with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\inventory\shift_reconciliation_screen.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('show_date_filter=False', 'show_date_filter=True')
content = content.replace('main_lay.addWidget(self.report)', 'self.report.btn_apply.clicked.connect(self._load_data)\n        main_lay.addWidget(self.report)')

load_data_old = '''        try:
            sql = """
                SELECT sr.id, s.shift_number as shift_no, s.created_at, sr.created_at as recon_date,
                       sr.closing_cashier_name, sr.total_expected, sr.total_counted
                FROM shift_reconciliations sr
                JOIN shifts s ON sr.shift_id = s.id
                ORDER BY sr.id DESC
            """
            conn = get_connection(); cur = conn.cursor()
            cur.execute(sql)'''

load_data_new = '''        try:
            start_dt = self.report.start_date.date().toString('yyyy-MM-dd') + ' 00:00:00'
            end_dt = self.report.end_date.date().toString('yyyy-MM-dd') + ' 23:59:59'
            sql = """
                SELECT sr.id, s.shift_number as shift_no, s.created_at, sr.created_at as recon_date,
                       sr.closing_cashier_name, sr.total_expected, sr.total_counted
                FROM shift_reconciliations sr
                JOIN shifts s ON sr.shift_id = s.id
                WHERE sr.created_at BETWEEN ? AND ?
                ORDER BY sr.id DESC
            """
            conn = get_connection(); cur = conn.cursor()
            cur.execute(sql, (start_dt, end_dt))'''

content = content.replace(load_data_old, load_data_new)

with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\inventory\shift_reconciliation_screen.py', 'w', encoding='utf-8') as f:
    f.write(content)

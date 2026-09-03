import os

# 1. expense_list_report.py
fpath = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\reports\expense_list_report.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('show_date_filter=False', 'show_date_filter=True')
content = content.replace('self.filters_layout.insertWidget(1, self.add_btn)', 'self.filters_layout.insertWidget(5, self.add_btn)')

old_load = '''        try:
            cur.execute("""
                SELECT 
                    e.created_at, e.name as descr, 
                    ISNULL(c.name, 'Uncategorized') as category,
                    ISNULL(s.name, '') as supplier,
                    e.paid, e.amount
                FROM expenses e
                LEFT JOIN expense_categories c ON e.expense_category_id = c.id
                LEFT JOIN suppliers s ON e.supplier_id = s.id
                ORDER BY e.created_at DESC
            """)'''

new_load = '''        try:
            date_from = self.start_date.date().toString("yyyy-MM-dd") + " 00:00:00"
            date_to = self.end_date.date().toString("yyyy-MM-dd") + " 23:59:59"
            cur.execute("""
                SELECT 
                    e.created_at, e.name as descr, 
                    ISNULL(c.name, 'Uncategorized') as category,
                    ISNULL(s.name, '') as supplier,
                    e.paid, e.amount
                FROM expenses e
                LEFT JOIN expense_categories c ON e.expense_category_id = c.id
                LEFT JOIN suppliers s ON e.supplier_id = s.id
                WHERE e.created_at BETWEEN ? AND ?
                ORDER BY e.created_at DESC
            """, (date_from, date_to))'''

content = content.replace(old_load, new_load)
with open(fpath, 'w', encoding='utf-8') as f:
    f.write(content)


# 2. purchase_invoices_list_dialog.py
fpath = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\dialogs\purchase_invoices_list_dialog.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('show_date_filter=False', 'show_date_filter=True')

old_inserts = '''            self.filters_layout.insertWidget(0, self._add_btn)
            
            self._edit_btn = _btn("Edit", ACCENT, ACCENT_H, enabled=False)
            self._edit_btn.clicked.connect(self._on_edit)
            self.filters_layout.insertWidget(1, self._edit_btn)
            
            self._delete_btn = _btn("Delete", "#b02020", "#cc2828", enabled=False)
            self._delete_btn.clicked.connect(self._on_delete)
            self.filters_layout.insertWidget(2, self._delete_btn)
        
        view_str = "Select for Return" if self.selection_mode else "View Details"
        self._view_btn = _btn(view_str, "#34495e", "#2c3e50", enabled=False)
        self._view_btn.clicked.connect(self._on_view_details)
        self.filters_layout.insertWidget(3, self._view_btn)'''

new_inserts = '''            self.filters_layout.insertWidget(5, self._add_btn)
            
            self._edit_btn = _btn("Edit", ACCENT, ACCENT_H, enabled=False)
            self._edit_btn.clicked.connect(self._on_edit)
            self.filters_layout.insertWidget(6, self._edit_btn)
            
            self._delete_btn = _btn("Delete", "#b02020", "#cc2828", enabled=False)
            self._delete_btn.clicked.connect(self._on_delete)
            self.filters_layout.insertWidget(7, self._delete_btn)
        
        view_str = "Select for Return" if self.selection_mode else "View Details"
        self._view_btn = _btn(view_str, "#34495e", "#2c3e50", enabled=False)
        self._view_btn.clicked.connect(self._on_view_details)
        self.filters_layout.insertWidget(8, self._view_btn)'''
        
content = content.replace(old_inserts, new_inserts)

old_load = '''            if self.selection_mode:
                prefix = "PINV-%"
            else:
                prefix = "PRET-%" if self.is_return else "PINV-%"
            cur.execute("""
                SELECT id, doc_no, supplier, date_time, balance, is_paid,
                       warehouse_id, address, supplier_invoice_no, reference,
                       (
                            (SELECT ISNULL(SUM(sei.qty), 0) FROM stock_entry_items sei WHERE sei.parent_id = se.id)
                            -
                            (SELECT ISNULL(SUM(ret_sei.qty), 0)
                             FROM stock_entry_items ret_sei
                             JOIN stock_entries ret_se ON ret_se.id = ret_sei.parent_id
                             WHERE ret_se.source_doc_no = se.doc_no)
                       ) as remaining_qty
                FROM stock_entries se
                WHERE se.doc_no LIKE ?
                ORDER BY se.id DESC
            """, (prefix,))'''

new_load = '''            if self.selection_mode:
                prefix = "PINV-%"
            else:
                prefix = "PRET-%" if self.is_return else "PINV-%"
            date_from = self.start_date.date().toString("yyyy-MM-dd") + " 00:00:00"
            date_to = self.end_date.date().toString("yyyy-MM-dd") + " 23:59:59"
            cur.execute("""
                SELECT id, doc_no, supplier, date_time, balance, is_paid,
                       warehouse_id, address, supplier_invoice_no, reference,
                       (
                            (SELECT ISNULL(SUM(sei.qty), 0) FROM stock_entry_items sei WHERE sei.parent_id = se.id)
                            -
                            (SELECT ISNULL(SUM(ret_sei.qty), 0)
                             FROM stock_entry_items ret_sei
                             JOIN stock_entries ret_se ON ret_se.id = ret_sei.parent_id
                             WHERE ret_se.source_doc_no = se.doc_no)
                       ) as remaining_qty
                FROM stock_entries se
                WHERE se.doc_no LIKE ? AND se.date_time BETWEEN ? AND ?
                ORDER BY se.id DESC
            """, (prefix, date_from, date_to))'''

content = content.replace(old_load, new_load)
with open(fpath, 'w', encoding='utf-8') as f:
    f.write(content)


# 3. inventory_list_dialog.py
fpath = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\dialogs\inventory_list_dialog.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('show_date_filter=False', 'show_date_filter=True')
content = content.replace('self.report.filters_layout.insertWidget(1, self.add_stock_btn)', 'self.report.btn_apply.clicked.connect(self._load_data)\n        self.report.filters_layout.insertWidget(5, self.add_stock_btn)')
content = content.replace('self.report.filters_layout.insertWidget(2, self.delete_btn)', 'self.report.filters_layout.insertWidget(6, self.delete_btn)')

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(content)


# 4. settings_dialog.py
fpath = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\dialogs\settings_dialog.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('show_date_filter=False', 'show_date_filter=True')
content = content.replace('self.report.filters_layout.insertWidget(1, self.new_customer_btn)', 'self.report.btn_apply.clicked.connect(self._load_customers)\n        self.report.filters_layout.insertWidget(5, self.new_customer_btn)')

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(content)


# 5. quotation_dialog.py
fpath = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\dialogs\quotation_dialog.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

if 'self.report.btn_apply.clicked.connect(self._load_quotations)' not in content:
    content = content.replace('self.report.table.doubleClicked.connect(self._on_double_click)', 'self.report.table.doubleClicked.connect(self._on_double_click)\n        self.report.btn_apply.clicked.connect(self._load_quotations)')

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(content)

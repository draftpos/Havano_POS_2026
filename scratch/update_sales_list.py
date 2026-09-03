import os

sale_file = r'c:\Users\DELL\New_POS\Havano_POS_2026\models\sale.py'
with open(sale_file, 'r', encoding='utf-8') as f:
    content = f.read()

old_get_all = '''def get_all_sales() -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(_SALE_SELECT + " ORDER BY s.id DESC")
    rows = fetchall_dicts(cur)
    conn.close()
    return [_sale_to_dict(r) for r in rows]'''

new_get_all = '''def get_all_sales(date_from=None, date_to=None) -> list[dict]:
    conn = get_connection()
    cur  = conn.cursor()
    query = _SALE_SELECT
    params = []
    if date_from and date_to:
        query += " WHERE s.created_at BETWEEN ? AND ?"
        params = [date_from, date_to]
    cur.execute(query + " ORDER BY s.id DESC", tuple(params))
    rows = fetchall_dicts(cur)
    conn.close()
    return [_sale_to_dict(r) for r in rows]'''

content = content.replace(old_get_all, new_get_all)
with open(sale_file, 'w', encoding='utf-8') as f:
    f.write(content)

# Now for sales_list_dialog.py
dialog_file = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\dialogs\sales_list_dialog.py'
with open(dialog_file, 'r', encoding='utf-8') as f:
    d_content = f.read()

# 1. Update show_date_filter
d_content = d_content.replace('show_date_filter=False', 'show_date_filter=True')
d_content = d_content.replace('self.table = self.report.table', 'self.report.btn_apply.clicked.connect(self._load_data)\n        self.table = self.report.table')

# 2. Update insertWidget
old_inserts = '''        self.report.filters_layout.insertWidget(1, self.filter_btn)
        self.report.filters_layout.insertWidget(2, self.sync_btn)
        self.report.filters_layout.insertWidget(3, self.view_btn)
        self.report.filters_layout.insertWidget(4, self.delete_btn)'''

new_inserts = '''        self.report.filters_layout.insertWidget(5, self.filter_btn)
        self.report.filters_layout.insertWidget(6, self.sync_btn)
        self.report.filters_layout.insertWidget(7, self.view_btn)
        self.report.filters_layout.insertWidget(8, self.delete_btn)'''

d_content = d_content.replace(old_inserts, new_inserts)

# 3. Remove summary bar
old_summary = '''        # summary bar
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
        
        self.report.main_layout.addWidget(summary)'''

d_content = d_content.replace(old_summary, '# Summary removed')

# 4. _load_data update
old_load = '''    def _load_data(self):
        self._all_sales = get_all_sales()
        self._render_table(self._visible_sales())
        self._update_sync_label()'''

new_load = '''    def _load_data(self):
        date_from = self.report.start_date.date().toString("yyyy-MM-dd") + " 00:00:00"
        date_to = self.report.end_date.date().toString("yyyy-MM-dd") + " 23:59:59"
        self._all_sales = get_all_sales(date_from=date_from, date_to=date_to)
        self._render_table(self._visible_sales())
        self._update_sync_label()'''

d_content = d_content.replace(old_load, new_load)

# 5. Remove label updates in _render_table
old_render_end = '''        self.count_lbl.setText(f"Sales: {len(sales)}")
        self.total_lbl.setText(f"Total: ${total:.2f}")
        self.tendered_lbl.setText(f"Tendered: ${tendered:.2f}")
        self.change_lbl.setText(f"Change: ${change:.2f}")'''

d_content = d_content.replace(old_render_end, '        pass # labels removed')

# 6. _update_sync_label fix
old_sync_update = '''    def _update_sync_label(self):
        if self._is_offline: return
        try:
            synced = sum(1 for s in self._all_sales if s.get("synced"))
            pend = len(self._all_sales) - synced
            self.sync_lbl.setText(f"{synced} synced  ·  {pend} pending")
        except Exception:
            pass'''
new_sync_update = '''    def _update_sync_label(self):
        pass'''

d_content = d_content.replace(old_sync_update, new_sync_update)

with open(dialog_file, 'w', encoding='utf-8') as f:
    f.write(d_content)

print("Updates applied.")

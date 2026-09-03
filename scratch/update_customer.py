with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\dialogs\settings_dialog.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find('class CustomerDialog(QDialog):')
end_idx = content.find('# =============================================================================\n# HardwareDialog', start_idx)

new_class = '''class CustomerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customers")
        self.setMinimumSize(960, 680)
        self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
        self._build()
        self._reload()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(0, 0, 0, 16)
        
        from views.reports.report_template import ReportTemplate
        self.report = ReportTemplate("Customers", is_report=False, show_date_filter=False, parent=self)
        self.report.set_headers(["Name", "Type", "Group", "Phone", "City", "Price List"])
        
        del_btn = navy_btn("Delete", height=34, color=DANGER, hover=DANGER_H)
        del_btn.clicked.connect(self._delete)
        self.report.filters_layout.addWidget(del_btn)
        
        self._tbl = self.report.table
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for ci in [1, 2, 3, 4, 5]: 
            hh.setSectionResizeMode(ci, QHeaderView.Fixed)
            self._tbl.setColumnWidth(ci, 110)
        
        lay.addWidget(self.report, 1)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(20, 0, 20, 0)

        self._status = QLabel("")
        self._status.setStyleSheet(f"font-size:12px; color:{SUCCESS}; background:transparent;")
        bl.addWidget(self._status)

        form = QGridLayout()
        form.setSpacing(8)
        self._f_name  = QLineEdit(); self._f_name.setPlaceholderText("Customer name *"); self._f_name.setFixedHeight(32)
        self._f_type  = QComboBox(); self._f_type.addItems(["", "Individual", "Company"]); self._f_type.setFixedHeight(32)
        self._f_trade = QLineEdit(); self._f_trade.setPlaceholderText("Trade name"); self._f_trade.setFixedHeight(32)
        self._f_phone = QLineEdit(); self._f_phone.setPlaceholderText("Phone"); self._f_phone.setFixedHeight(32)
        self._f_email = QLineEdit(); self._f_email.setPlaceholderText("Email"); self._f_email.setFixedHeight(32)
        self._f_city  = QLineEdit(); self._f_city.setPlaceholderText("City"); self._f_city.setFixedHeight(32)
        self._f_house = QLineEdit(); self._f_house.setPlaceholderText("Address"); self._f_house.setFixedHeight(32)
        self._f_group = QComboBox(); self._f_group.setFixedHeight(32)
        self._f_wh    = QComboBox(); self._f_wh.setFixedHeight(32)
        self._f_cc    = QComboBox(); self._f_cc.setFixedHeight(32)
        self._f_pl    = QComboBox(); self._f_pl.setFixedHeight(32)

        for lbl_txt, widget, r, c in [
            ("Name *",       self._f_name,  0, 0), ("Type",         self._f_type,  0, 2),
            ("Trade Name",   self._f_trade, 1, 0), ("Phone",        self._f_phone, 1, 2),
            ("Email",        self._f_email, 2, 0), ("City",         self._f_city,  2, 2),
            ("Address",      self._f_house, 3, 0), ("Group *",      self._f_group, 3, 2),
            ("Warehouse *",  self._f_wh,    4, 0), ("Cost Center *",self._f_cc,    4, 2),
            ("Price List *", self._f_pl,    5, 0),
        ]:
            form.addWidget(QLabel(lbl_txt, styleSheet="background:transparent;font-size:12px;font-weight:bold;color:#1e293b;"), r, c)
            form.addWidget(widget, r, c + 1)
        bl.addLayout(form)

        br = QHBoxLayout()
        add_btn = navy_btn("Add Customer", height=38, color=SUCCESS, hover=SUCCESS_H)
        add_btn.clicked.connect(self._add)
        cls_btn = navy_btn("Close", height=38)
        cls_btn.clicked.connect(self.accept)
        br.addWidget(add_btn)
        br.addStretch()
        br.addWidget(cls_btn)
        bl.addLayout(br)
        
        lay.addWidget(body)

    def _reload(self):
        self._tbl.setRowCount(0)
        try:
            from models.customer import get_all_customers
            custs = get_all_customers()
        except Exception: custs = []
        self._populate_combos()
        self._populate_table(custs)

    def _do_search(self, query):
        if not query.strip(): self._reload(); return
        try:
            from models.customer import search_customers
            custs = search_customers(query)
        except Exception: custs = []
        self._populate_table(custs)

    def _populate_table(self, custs):
        self._tbl.setRowCount(0)
        for c in custs:
            r = self._tbl.rowCount(); self._tbl.insertRow(r)
            for col, val in enumerate([
                c["customer_name"], c.get("customer_type", ""),
                c.get("customer_group_name", ""), c.get("custom_telephone_number", ""),
                c.get("custom_city", ""), c.get("price_list_name", ""),
            ]):
                it = QTableWidgetItem(str(val)); it.setData(Qt.UserRole, c); self._tbl.setItem(r, col, it)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

    def _populate_combos(self):
        try:
            from models.customer_group import get_all_customer_groups
            from models.warehouse import get_all_warehouses
            from models.cost_center import get_all_cost_centers
            from models.price_list import get_all_price_lists
            groups = get_all_customer_groups(); whs = get_all_warehouses()
            ccs = get_all_cost_centers(); pls = get_all_price_lists()
        except Exception: groups=[]; whs=[]; ccs=[]; pls=[]
        for cb in [self._f_group, self._f_wh, self._f_cc, self._f_pl]: cb.clear()
        for g in groups: self._f_group.addItem(g["name"], g["id"])
        for w in whs: self._f_wh.addItem(f"{w['name']} ({w.get('company_name', '')})", w["id"])
        for cc in ccs: self._f_cc.addItem(f"{cc['name']} ({cc.get('company_name', '')})", cc["id"])
        for pl in pls: self._f_pl.addItem(pl["name"], pl["id"])

    def _add(self):
        name = self._f_name.text().strip()
        if not name: self._status.setText("Customer name required."); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;"); return
        gid = self._f_group.currentData(); wid = self._f_wh.currentData(); ccid = self._f_cc.currentData(); plid = self._f_pl.currentData()
        if not all([gid, wid, ccid, plid]): self._status.setText("Group, Warehouse, Cost Center and Price List are required."); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;"); return
        try:
            from models.customer import create_customer
            create_customer(
                customer_name=name, customer_group_id=gid,
                custom_warehouse_id=wid, custom_cost_center_id=ccid,
                default_price_list_id=plid,
                customer_type=self._f_type.currentText() or None,
                custom_trade_name=self._f_trade.text().strip(),
                custom_telephone_number=self._f_phone.text().strip(),
                custom_email_address=self._f_email.text().strip(),
                custom_city=self._f_city.text().strip(),
                custom_house_no=self._f_house.text().strip(),
            )
            for f in [self._f_name, self._f_trade, self._f_phone, self._f_email, self._f_city, self._f_house]: f.clear()
            self._reload()
            self._status.setText(f"Customer '{name}' added."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")

    def _delete(self):
        row = self._tbl.currentRow()
        if row < 0: self._status.setText("Select a customer first."); return
        c = self._tbl.item(row, 0).data(Qt.UserRole)
        if QMessageBox.question(self, "Delete", f"Delete '{c['customer_name']}'?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes: return
        try:
            from models.customer import delete_customer
            delete_customer(c["id"]); self._reload()
            self._status.setText("Deleted."); self._status.setStyleSheet(f"color:{SUCCESS};font-size:12px;background:transparent;")
        except Exception as e: self._status.setText(_friendly_db_error(e)); self._status.setStyleSheet(f"color:{DANGER};font-size:12px;background:transparent;")

'''

new_content = content[:start_idx] + new_class + '\n\n' + content[end_idx:]
with open(r'c:\Users\DELL\New_POS\Havano_POS_2026\views\dialogs\settings_dialog.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

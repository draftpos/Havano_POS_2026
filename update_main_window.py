import re

file_path = 'views/main_window.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace _build_stock_tab layout and table definition
new_build = '''    def _build_stock_tab(self):
        w = QWidget()
        w.setStyleSheet(f"background:{OFF_WHITE};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # -- TAB 1: Stock on Hand (Using ReportTemplate)
        from views.reports.report_template import ReportTemplate
        self.stock_report = ReportTemplate(title="Inventory List", is_report=False, show_date_filter=False, parent=w)
        self.stock_report.set_headers([
            "No.", "Part No.", "Product Name", "Category",
            "Qty on Hand", "Cost Price", "Sale Price",
            "Value @ Cost", "Value @ Sale"
        ])
        
        # Adjust table headers resize mode
        hh = self.stock_report.table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignCenter)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        for ci, w_ in [(0, 40), (1, 90), (3, 100), (4, 90), (5, 100), (6, 100), (7, 110), (8, 110)]:
            hh.setSectionResizeMode(ci, QHeaderView.Fixed)
            self.stock_report.table.setColumnWidth(ci, w_)
        
        # Remove default search/pdf/excel as we hook into them or use custom ones
        self._stock_search = self.stock_report.global_search
        self._stock_search.textChanged.disconnect() # Disconnect default
        self._stock_search.textChanged.connect(self._filter_stock)
        
        try:
            self.stock_report.btn_excel.clicked.disconnect()
            self.stock_report.btn_pdf.clicked.disconnect()
        except:
            pass
        self.stock_report.btn_excel.clicked.connect(self._export_stock_csv)
        self.stock_report.btn_pdf.clicked.connect(self._preview_stock_pdf)

        # Warehouse filter
        self._stock_wh_cbo = QComboBox()
        self._stock_wh_cbo.setFixedHeight(28)
        self._stock_wh_cbo.setMinimumWidth(180)
        self._stock_wh_cbo.setStyleSheet(f"QComboBox {{ background:white; color:#333; border:1px solid #c8d8ec; border-radius:4px; padding:0 10px; }}")
        self._stock_wh_cbo.addItem("— All Warehouses —", None)
        
        # Cost Center filter
        self._stock_cc_cbo = QComboBox()
        self._stock_cc_cbo.setFixedHeight(28)
        self._stock_cc_cbo.setMinimumWidth(180)
        self._stock_cc_cbo.setStyleSheet(f"QComboBox {{ background:white; color:#333; border:1px solid #c8d8ec; border-radius:4px; padding:0 10px; }}")
        self._stock_cc_cbo.addItem("— All Cost Centers —", None)

        # Load master data
        try:
            from database.db import get_connection, fetchall_dicts
            conn = get_connection(); cur = conn.cursor()
            
            cur.execute("SELECT MIN(id) as id, name FROM warehouses GROUP BY name ORDER BY name")
            for wh in fetchall_dicts(cur):
                self._stock_wh_cbo.addItem(wh["name"], wh["id"])
                
            cur.execute("SELECT MIN(id) as id, name FROM cost_centers GROUP BY name ORDER BY name")
            for cc in fetchall_dicts(cur):
                self._stock_cc_cbo.addItem(cc["name"], cc["id"])
            conn.close()
        except Exception: pass

        # Default selection from user context
        if self.user.get("warehouse_id"):
            idx = self._stock_wh_cbo.findData(self.user["warehouse_id"])
            if idx >= 0: self._stock_wh_cbo.setCurrentIndex(idx)
            
        if self.user.get("cost_center_id"):
            idx = self._stock_cc_cbo.findData(self.user["cost_center_id"])
            if idx >= 0: self._stock_cc_cbo.setCurrentIndex(idx)

        self._stock_wh_cbo.currentIndexChanged.connect(lambda: self._load_stock_data())
        self._stock_cc_cbo.currentIndexChanged.connect(lambda: self._load_stock_data())

        # Insert them right before the search bar
        idx_search = self.stock_report.filters_layout.indexOf(self.stock_report.global_search)
        self.stock_report.filters_layout.insertWidget(idx_search, self._stock_wh_cbo)
        self.stock_report.filters_layout.insertWidget(idx_search+1, self._stock_cc_cbo)

        self._add_stock_btn = QPushButton(" Add Stock")
        self._add_stock_btn.setIcon(qta.icon("fa5s.plus", color="white"))
        self._add_stock_btn.setFixedHeight(28)
        self._add_stock_btn.setCursor(Qt.PointingHandCursor)
        self._add_stock_btn.setStyleSheet(f"QPushButton {{ background-color: {SUCCESS}; color: white; border: none; border-radius: 4px; padding: 0 12px; font-weight: bold; font-size: 11px; }} QPushButton:hover {{ background-color: #1e824c; }}")
        
        self._stock_edit_btn = QPushButton(" Edit")
        self._stock_edit_btn.setIcon(qta.icon("fa5s.edit", color="white"))
        self._stock_edit_btn.setFixedHeight(28)
        self._stock_edit_btn.setCursor(Qt.PointingHandCursor)
        self._stock_edit_btn.setStyleSheet(f"QPushButton {{ background-color: {ACCENT}; color: white; border: none; border-radius: 4px; padding: 0 12px; font-weight: bold; font-size: 11px; }} QPushButton:hover {{ background-color: {ACCENT_H}; }} QPushButton:disabled {{ background-color: {MUTED}; }}")
        self._stock_edit_btn.setVisible(False)

        # Insert into layout
        self.stock_report.filters_layout.insertWidget(1, self._add_stock_btn)
        self.stock_report.filters_layout.insertWidget(2, self._stock_edit_btn)

        def _on_add_stock():
            from views.dialogs.stock_file_dialog import StockEditDialog
            dlg = StockEditDialog(self.parent_window if hasattr(self, "parent_window") else self)
            if dlg.exec() == QDialog.Accepted:
                try:
                    from models.product import create_product, upsert_item_price
                    p = create_product(**dlg.result_data)
                    upsert_item_price(p["part_no"], dlg.result_data.get("price_list", "Standard Selling"), p.get("uom", "Unit"), dlg.result_data["price"])
                    for row in getattr(dlg, "prices_to_save", []):
                        part = row.get("item_code") or p["part_no"]
                        upsert_item_price(part, row.get("price_list", "Standard Selling"), row.get("uom", "Unit"), row.get("price", 0.0))
                    self._load_stock_data()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not create product:\\n{str(e)}")
        
        def _on_edit_stock():
            row = self.stock_report.table.currentRow()
            if row < 0: return
            item = self.stock_report.table.item(row, 0)
            if not item: return
            p_data = item.data(Qt.UserRole)
            if not p_data: return
            
            from views.dialogs.stock_file_dialog import StockEditDialog
            dlg = StockEditDialog(self.parent_window if hasattr(self, "parent_window") else self, product=p_data)
            if dlg.exec() == QDialog.Accepted:
                try:
                    from models.product import update_product, upsert_item_price
                    updated_p = update_product(p_data["id"], **dlg.result_data)
                    upsert_item_price(updated_p["part_no"], dlg.result_data.get("price_list", "Standard Selling"), updated_p.get("uom", "Unit"), dlg.result_data["price"])
                    for row in getattr(dlg, "prices_to_save", []):
                        part = row.get("item_code") or updated_p["part_no"]
                        upsert_item_price(part, row.get("price_list", "Standard Selling"), row.get("uom", "Unit"), row.get("price", 0.0))
                    self._load_stock_data()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not update product:\\n{str(e)}")
                    
        self._add_stock_btn.clicked.connect(_on_add_stock)
        self._stock_edit_btn.clicked.connect(_on_edit_stock)
        self._stock_tbl_edit_conn = _on_edit_stock
        
        def _on_stock_selection_changed():
            has_selection = len(self.stock_report.table.selectedItems()) > 0
            self._stock_edit_btn.setVisible(has_selection)
            
        self.stock_report.table.itemSelectionChanged.connect(_on_stock_selection_changed)
        self.stock_report.table.doubleClicked.connect(self._stock_tbl_edit_conn)

        lay.addWidget(self.stock_report, 1)

        # Totals strip at bottom
        totals_w = QWidget()
        totals_w.setStyleSheet(f"background:{NAVY};")
        totals_w.setFixedHeight(44)
        tl = QHBoxLayout(totals_w)
        tl.setContentsMargins(16, 0, 16, 0)
        tl.setSpacing(32)
        self._lbl_tot_cost = QLabel("Total @ Cost: .00")
        self._lbl_tot_sell = QLabel("Total @ Sale: .00")
        self._lbl_tot_prof = QLabel("Potential Profit: .00")
        for lbl in [self._lbl_tot_cost, self._lbl_tot_sell, self._lbl_tot_prof]:
            lbl.setStyleSheet("color:white; font-size:13px; font-weight:bold; background:transparent;")
        tl.addWidget(self._lbl_tot_cost)
        tl.addWidget(self._lbl_tot_sell)
        tl.addWidget(self._lbl_tot_prof)
        tl.addStretch()
        
        self._stock_count_lbl = QLabel("Loading…")
        self._stock_count_lbl.setStyleSheet("color:#a0aabf; font-size:11px; background:transparent;")
        tl.addWidget(self._stock_count_lbl)
        
        self.stock_report.main_layout.addWidget(totals_w)

        return w
'''

pattern = r'    def _build_stock_tab\(self\):.*?return w'
content = re.sub(pattern, new_build, content, flags=re.DOTALL)

# Now fix references to self._stock_tbl in _render_stock
content = content.replace('self._stock_tbl', 'self.stock_report.table')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated views/main_window.py successfully.")

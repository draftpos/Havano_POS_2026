import os

path = r'c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target_start = '        stock_page.setStyleSheet(f"background:{OFF_WHITE};")'
target_end = '        return stock_page'

start_idx = content.find(target_start)
end_idx = content.find(target_end)

new_stock_code = '''        stock_page.setStyleSheet(f"background:{OFF_WHITE};")
        s_lay = QVBoxLayout(stock_page)
        s_lay.setContentsMargins(0, 0, 0, 0)
        s_lay.setSpacing(0)

        from views.reports.report_template import ReportTemplate
        self.stock_report = ReportTemplate("Inventory Valuation", is_report=False, show_date_filter=False, parent=stock_page)
        self.stock_report.set_headers([
            "Part No.", "Product Name", "Category",
            "Qty on Hand", "Cost Price", "Selling Price",
            "Value @ Cost", "Value @ Selling"
        ])
        
        self._stock_tbl = self.stock_report.table
        hh = self._stock_tbl.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for ci, w_ in [(0, 90), (2, 100), (3, 90), (4, 100), (5, 100), (6, 110), (7, 110)]:
            hh.setSectionResizeMode(ci, QHeaderView.Fixed)
            self._stock_tbl.setColumnWidth(ci, w_)

        # Setup standard search bar functionality
        self._stock_search = self.stock_report.global_search
        self._stock_search.textChanged.disconnect() # Disconnect template's filter
        self._stock_search.textChanged.connect(self._filter_stock)
        self._stock_search.setPlaceholderText("Filter by product name or part number...")
        self._stock_search.setFixedWidth(300)

        # Setup filters (combos)
        self._stock_wh_cbo = QComboBox()
        self._stock_wh_cbo.setMinimumWidth(160)
        self._stock_wh_cbo.addItem("- All Warehouses -", None)
        
        self._stock_cc_cbo = QComboBox()
        self._stock_cc_cbo.setMinimumWidth(160)
        self._stock_cc_cbo.addItem("- All Cost Centers -", None)

        try:
            from database.db import get_connection, fetchall_dicts
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT MIN(id) as id, name FROM warehouses GROUP BY name ORDER BY name")
            for wh in fetchall_dicts(cur): self._stock_wh_cbo.addItem(wh["name"], wh["id"])
            cur.execute("SELECT MIN(id) as id, name FROM cost_centers GROUP BY name ORDER BY name")
            for cc in fetchall_dicts(cur): self._stock_cc_cbo.addItem(cc["name"], cc["id"])
            conn.close()
        except Exception: pass

        if self.user.get("warehouse_id"):
            idx = self._stock_wh_cbo.findData(self.user["warehouse_id"])
            if idx >= 0: self._stock_wh_cbo.setCurrentIndex(idx)
            
        if self.user.get("cost_center_id"):
            idx = self._stock_cc_cbo.findData(self.user["cost_center_id"])
            if idx >= 0: self._stock_cc_cbo.setCurrentIndex(idx)

        self._stock_wh_cbo.currentIndexChanged.connect(lambda: self._load_stock_data())
        self._stock_cc_cbo.currentIndexChanged.connect(lambda: self._load_stock_data())

        self.stock_report.filters_layout.insertWidget(4, self._stock_wh_cbo)
        self.stock_report.filters_layout.insertWidget(5, self._stock_cc_cbo)

        # Connect Excel & PDF directly to the template's buttons
        try: self.stock_report.btn_excel.clicked.disconnect()
        except: pass
        self.stock_report.btn_excel.clicked.connect(self._export_stock_csv)
        
        try: self.stock_report.btn_pdf.clicked.disconnect()
        except: pass
        self.stock_report.btn_pdf.clicked.connect(self._preview_stock_pdf)

        def _on_add_stock():
            from views.dialogs.stock_file_dialog import StockEditDialog
            dlg = StockEditDialog(self.parent_window if hasattr(self, 'parent_window') else self)
            if dlg.exec() == QDialog.Accepted:
                try:
                    from models.product import create_product, upsert_item_price
                    p = create_product(**dlg.result_data)
                    upsert_item_price(p['part_no'], dlg.result_data.get('price_list', 'Standard Selling'), p.get('uom', 'Unit'), dlg.result_data['price'])
                    self._load_stock_data()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not create product:\\n{str(e)}")

        self.stock_report.btn_add.clicked.connect(_on_add_stock)

        self._stock_edit_btn = QPushButton(" Edit")
        import qtawesome as qta
        self._stock_edit_btn.setIcon(qta.icon("fa5s.edit", color="white", scale_factor=0.7))
        self._stock_edit_btn.setFixedHeight(30)
        self._stock_edit_btn.setStyleSheet("""
            QPushButton { background-color: #f57c00; color: white; border: none; border-radius: 4px; padding: 0px 12px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #e65100; }
        """)
        self._stock_edit_btn.setVisible(False)
        self.stock_report.filters_layout.addWidget(self._stock_edit_btn)

        def _on_edit_stock():
            row = self._stock_tbl.currentRow()
            if row < 0: return
            item = self._stock_tbl.item(row, 0)
            if not item: return
            p_data = item.data(Qt.UserRole)
            if not p_data: return
            from views.dialogs.stock_file_dialog import StockEditDialog
            dlg = StockEditDialog(self.parent_window if hasattr(self, 'parent_window') else self, product=p_data)
            if dlg.exec() == QDialog.Accepted:
                try:
                    from models.product import update_product, upsert_item_price
                    updated_p = update_product(p_data['id'], **dlg.result_data)
                    upsert_item_price(updated_p['part_no'], dlg.result_data.get('price_list', 'Standard Selling'), updated_p.get('uom', 'Unit'), dlg.result_data['price'])
                    self._load_stock_data()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not update product:\\n{str(e)}")

        self._stock_edit_btn.clicked.connect(_on_edit_stock)
        self._stock_tbl_edit_conn = _on_edit_stock

        def _on_stock_selection_changed():
            has_selection = len(self._stock_tbl.selectedItems()) > 0
            self._stock_edit_btn.setVisible(has_selection)
            
        self._stock_tbl.itemSelectionChanged.connect(_on_stock_selection_changed)
        self._stock_tbl.doubleClicked.connect(self._stock_tbl_edit_conn)

        s_lay.addWidget(self.stock_report, 1)

        # Totals strip at bottom
        totals_w = QWidget()
        totals_w.setStyleSheet(f"background:#0d1f3c; border-radius:6px;")
        totals_w.setFixedHeight(44)
        tl = QHBoxLayout(totals_w)
        tl.setContentsMargins(16, 0, 16, 0)
        tl.setSpacing(32)
        self._lbl_tot_cost = QLabel("Total @ Cost: $0.00")
        self._lbl_tot_sell = QLabel("Total @ Selling: $0.00")
        self._lbl_tot_prof = QLabel("Potential Profit: $0.00")
        for lbl in [self._lbl_tot_cost, self._lbl_tot_sell, self._lbl_tot_prof]:
            lbl.setStyleSheet("color:white; font-size:14px; font-weight:bold;")
            tl.addWidget(lbl)
        tl.addStretch()
        
        # Add some margin to the totals widget to match template
        totals_container = QWidget()
        tc_lay = QVBoxLayout(totals_container)
        tc_lay.setContentsMargins(15, 0, 15, 15)
        tc_lay.addWidget(totals_w)
        s_lay.addWidget(totals_container)

'''

if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_stock_code + content[end_idx:]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully refactored Inventory Valuation.")

# # =============================================================================
# # views/dialogs/customer_dialog.py
# # =============================================================================

# from PySide6.QtWidgets import (
#     QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget,
#     QPushButton, QLabel, QLineEdit, QComboBox, QTableWidget,
#     QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox
# )
# from PySide6.QtCore import Qt, QTimer
# from PySide6.QtGui import QColor
# import threading

# # Colors
# NAVY      = "#0d1f3c"
# NAVY_2    = "#162d52"
# NAVY_3    = "#1e3d6e"
# ACCENT    = "#1a5fb4"
# ACCENT_H  = "#1c6dd0"
# WHITE     = "#ffffff"
# OFF_WHITE = "#f5f8fc"
# LIGHT     = "#e4eaf4"
# MID       = "#8fa8c8"
# DARK_TEXT = "#0d1f3c"
# MUTED     = "#5a7a9a"
# BORDER    = "#c8d8ec"
# ROW_ALT   = "#edf3fb"
# SUCCESS   = "#1a7a3c"
# SUCCESS_H = "#1f9447"
# DANGER    = "#b02020"
# DANGER_H  = "#cc2828"


# def _friendly_db_error(e: Exception) -> str:
#     msg = str(e)
#     if "REFERENCE constraint" in msg or "FK_" in msg or "foreign key" in msg.lower():
#         return "Cannot delete — record is still linked to other data."
#     if "UNIQUE" in msg or "duplicate key" in msg.lower():
#         return "A record with that name already exists."
#     return msg


# def navy_btn(text, height=36, font_size=12, width=None, color=None, hover=None):
#     bg  = color or NAVY
#     hov = hover or NAVY_2
#     btn = QPushButton(text)
#     btn.setFixedHeight(height)
#     if width:
#         btn.setFixedWidth(width)
#     btn.setCursor(Qt.PointingHandCursor)
#     btn.setStyleSheet(f"""
#         QPushButton {{
#             background-color: {bg}; color: {WHITE}; border: none;
#             border-radius: 5px; font-size: {font_size}px; font-weight: bold; padding: 0 14px;
#         }}
#         QPushButton:hover   {{ background-color: {hov}; }}
#         QPushButton:pressed {{ background-color: {NAVY_3}; }}
#         QPushButton:disabled {{ background-color: {MID}; }}
#     """)
#     return btn


# def hr():
#     from PySide6.QtWidgets import QFrame
#     line = QFrame()
#     line.setFrameShape(QFrame.HLine)
#     line.setStyleSheet(f"background-color: {BORDER}; border: none;")
#     line.setFixedHeight(1)
#     return line


# def _settings_table_style():
#     return f"""
#         QTableWidget {{ background:{WHITE}; border:1px solid {BORDER};
#             gridline-color:{LIGHT}; outline:none; font-size:13px; }}
#         QTableWidget::item           {{ padding:8px; }}
#         QTableWidget::item:selected  {{ background-color:{ACCENT}; color:{WHITE}; }}
#         QTableWidget::item:alternate {{ background-color:{ROW_ALT}; }}
#         QHeaderView::section {{
#             background-color:{NAVY}; color:{WHITE};
#             padding:10px 8px; border:none; border-right:1px solid {NAVY_2};
#             font-size:11px; font-weight:bold;
#         }}
#     """


# class CustomerDialog(QDialog):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("Customer Management")
#         self.setMinimumSize(1000, 750)
#         self.setStyleSheet(f"QDialog {{ background-color:{WHITE}; }}")
#         self._build()
#         self._reload()

#     def _build(self):
#         lay = QVBoxLayout(self)
#         lay.setSpacing(10)
#         lay.setContentsMargins(20, 16, 20, 16)

#         # --- HEADER (DARK BAR) WITH SYNC BUTTON ---
#         hdr = QWidget()
#         hdr.setFixedHeight(50)
#         hdr.setStyleSheet(f"background-color:{NAVY}; border-radius:5px;")
        
#         # Horizontal layout for inside the navy bar
#         hl = QHBoxLayout(hdr)
#         hl.setContentsMargins(16, 0, 16, 0)
        
#         title_lbl = QLabel("Customer Directory")
#         title_lbl.setStyleSheet(f"font-size:16px;font-weight:bold;color:{WHITE};background:transparent;")
#         hl.addWidget(title_lbl)
        
#         hl.addStretch() # Pushes the button to the right

#         self._sync_btn = navy_btn("Sync from Cloud", height=30, color=ACCENT, hover=ACCENT_H)
#         self._sync_btn.clicked.connect(self._on_sync_clicked)
#         hl.addWidget(self._sync_btn)
        
#         lay.addWidget(hdr)

#         # --- SEARCH ROW ---
#         sr = QHBoxLayout()
#         sr.setSpacing(8)
#         self._search = QLineEdit()
#         self._search.setPlaceholderText("Search by name, trade name, or phone...")
#         self._search.setFixedHeight(34)
#         self._search.textChanged.connect(self._do_search)
#         sr.addWidget(self._search)
#         lay.addLayout(sr)

#         # --- CUSTOMER TABLE ---
#         self._tbl = QTableWidget(0, 8)
#         self._tbl.setHorizontalHeaderLabels([
#             "Name", "Type", "Group", "Phone", "Email", "City", "Balance", "Loyalty"
#         ])
#         hh = self._tbl.horizontalHeader()
#         hh.setSectionResizeMode(0, QHeaderView.Stretch)
#         for ci in range(1, 8):
#             hh.setSectionResizeMode(ci, QHeaderView.Fixed)
#             self._tbl.setColumnWidth(ci, 100)
        
#         self._tbl.setColumnWidth(4, 150) # Email wider
#         self._tbl.verticalHeader().setVisible(False)
#         self._tbl.setAlternatingRowColors(True)
#         self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
#         self._tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
#         self._tbl.setStyleSheet(_settings_table_style())
#         lay.addWidget(self._tbl, 1)
        
#         lay.addWidget(hr())

#         # --- FORM FOR ADDING/EDITING ---
#         form = QGridLayout()
#         form.setSpacing(8)

#         labels = [
#             ("Name *", 0, 0), ("Type", 0, 2), ("Trade Name", 1, 0),
#             ("Phone", 1, 2), ("Email", 2, 0), ("City", 2, 2),
#             ("House No.", 3, 0), ("Group *", 3, 2), ("Warehouse *", 4, 0),
#             ("Cost Center *", 4, 2), ("Price List *", 5, 0)
#         ]

#         for text, r, c in labels:
#             lbl = QLabel(text)
#             lbl.setStyleSheet(f"background:transparent;font-size:12px;color:{MUTED};")
#             form.addWidget(lbl, r, c)

#         self._f_name = QLineEdit(); self._f_name.setFixedHeight(30)
#         form.addWidget(self._f_name, 0, 1)

#         self._f_type = QComboBox(); self._f_type.addItems(["", "Individual", "Company"])
#         self._f_type.setFixedHeight(30)
#         form.addWidget(self._f_type, 0, 3)

#         self._f_trade = QLineEdit(); self._f_trade.setFixedHeight(30)
#         form.addWidget(self._f_trade, 1, 1)

#         self._f_phone = QLineEdit(); self._f_phone.setFixedHeight(30)
#         form.addWidget(self._f_phone, 1, 3)

#         self._f_email = QLineEdit(); self._f_email.setFixedHeight(30)
#         form.addWidget(self._f_email, 2, 1)

#         self._f_city = QLineEdit(); self._f_city.setFixedHeight(30)
#         form.addWidget(self._f_city, 2, 3)

#         self._f_house = QLineEdit(); self._f_house.setFixedHeight(30)
#         form.addWidget(self._f_house, 3, 1)

#         self._f_group = QComboBox(); self._f_group.setFixedHeight(30)
#         form.addWidget(self._f_group, 3, 3)

#         self._f_wh = QComboBox(); self._f_wh.setFixedHeight(30)
#         form.addWidget(self._f_wh, 4, 1)

#         self._f_cc = QComboBox(); self._f_cc.setFixedHeight(30)
#         form.addWidget(self._f_cc, 4, 3)

#         self._f_pl = QComboBox(); self._f_pl.setFixedHeight(30)
#         form.addWidget(self._f_pl, 5, 1)

#         lay.addLayout(form)

#         # --- FOOTER BUTTON ROW ---
#         br = QHBoxLayout()
#         br.setSpacing(8)
#         self._status = QLabel("Ready")
#         self._status.setStyleSheet(f"font-size:12px;color:{MUTED};")

#         self.add_btn = navy_btn("Add Customer", height=34, color=SUCCESS, hover=SUCCESS_H)
#         self.edit_btn = navy_btn("Edit Selected", height=34, color=NAVY, hover=NAVY_2)
#         del_btn = navy_btn("Delete", height=34, color=DANGER, hover=DANGER_H)
#         cls_btn = navy_btn("Close", height=34)

#         self.add_btn.clicked.connect(self._add)
#         self.edit_btn.clicked.connect(self._edit)
#         del_btn.clicked.connect(self._delete)
#         cls_btn.clicked.connect(self.accept)

#         br.addWidget(self._status, 1)
#         br.addWidget(self.add_btn)
#         br.addWidget(self.edit_btn)
#         br.addWidget(del_btn)
#         br.addWidget(cls_btn)
#         lay.addLayout(br)

#     def _reload(self):
#         try:
#             from models.customer import get_all_customers
#             custs = get_all_customers()
#         except Exception:
#             custs = []
#         self._populate_combos()
#         self._populate_table(custs)

#     def _do_search(self, query):
#         if not query.strip():
#             self._reload()
#             return
#         try:
#             from models.customer import search_customers
#             custs = search_customers(query)
#         except Exception:
#             custs = []
#         self._populate_table(custs)

#     def _populate_table(self, custs):
#         self._tbl.setRowCount(0)
#         for c in custs:
#             r = self._tbl.rowCount()
#             self._tbl.insertRow(r)
            
#             # Logic for coloring the balance column
#             balance = float(c.get("balance") or 0)
#             balance_text = f"{balance:,.2f}"
#             balance_color = DANGER if balance > 0 else SUCCESS if balance < 0 else DARK_TEXT
            
#             points = int(c.get("loyalty_points") or 0)

#             data_map = [
#                 (c["customer_name"], Qt.AlignLeft),
#                 (c.get("customer_type") or "", Qt.AlignCenter),
#                 (c.get("customer_group_name") or "", Qt.AlignCenter),
#                 (c.get("custom_telephone_number") or "", Qt.AlignCenter),
#                 (c.get("custom_email_address") or "", Qt.AlignLeft),
#                 (c.get("custom_city") or "", Qt.AlignCenter),
#                 (balance_text, Qt.AlignRight | Qt.AlignVCenter),
#                 (str(points), Qt.AlignCenter),
#             ]

#             for col, (val, align) in enumerate(data_map):
#                 it = QTableWidgetItem(str(val))
#                 it.setTextAlignment(align)
#                 if col == 6: # Set balance color
#                     it.setForeground(QColor(balance_color))
#                 it.setData(Qt.UserRole, c) # Store full object in the first cell data
#                 self._tbl.setItem(r, col, it)
#             self._tbl.setRowHeight(r, 38)

#     def _populate_combos(self):
#         try:
#             from models.customer_group import get_all_customer_groups
#             from models.warehouse import get_all_warehouses
#             from models.cost_center import get_all_cost_centers
#             from models.price_list import get_all_price_lists
            
#             groups = get_all_customer_groups()
#             whs = get_all_warehouses()
#             ccs = get_all_cost_centers()
#             pls = get_all_price_lists()
            
#             for cb in [self._f_group, self._f_wh, self._f_cc, self._f_pl]:
#                 cb.clear()
            
#             for g in groups: self._f_group.addItem(g["name"], g["id"])
#             for w in whs: self._f_wh.addItem(w['name'], w["id"])
#             for cc in ccs: self._f_cc.addItem(cc['name'], cc["id"])
#             for pl in pls: self._f_pl.addItem(pl["name"], pl["id"])
#         except: pass

#     # --- CLOUD SYNC LOGIC ---
#     def _on_sync_clicked(self):
#         self._sync_btn.setEnabled(False)
#         self._sync_btn.setText("Syncing...")
#         self._show_status("Connecting to cloud...")
        
#         from services.customer_sync_service import sync_customers
        
#         def run_sync():
#             try:
#                 sync_customers()
#                 QTimer.singleShot(0, self._on_sync_finished)
#             except Exception as e:
#                 QTimer.singleShot(0, lambda: self._show_status(f"Sync failed: {e}", True))
#                 QTimer.singleShot(0, lambda: self._sync_btn.setEnabled(True))
#                 QTimer.singleShot(0, lambda: self._sync_btn.setText("Sync from Cloud"))

#         threading.Thread(target=run_sync, daemon=True).start()

#     def _on_sync_finished(self):
#         self._sync_btn.setEnabled(True)
#         self._sync_btn.setText("Sync from Cloud")
#         self._reload()
#         self._show_status("Sync successful.")

#     def _add(self):
#         name = self._f_name.text().strip()
#         if not name:
#             self._show_status("Name required.", True); return

#         try:
#             from models.customer import create_customer
#             create_customer(
#                 customer_name=name,
#                 customer_group_id=self._f_group.currentData(),
#                 custom_warehouse_id=self._f_wh.currentData(),
#                 custom_cost_center_id=self._f_cc.currentData(),
#                 default_price_list_id=self._f_pl.currentData(),
#                 customer_type=self._f_type.currentText(),
#                 custom_trade_name=self._f_trade.text(),
#                 custom_telephone_number=self._f_phone.text(),
#                 custom_email_address=self._f_email.text(),
#                 custom_city=self._f_city.text(),
#                 custom_house_no=self._f_house.text()
#             )
#             self._clear_form()
#             self._reload()
#             self._show_status(f"Added {name}")
#         except Exception as e:
#             self._show_status(_friendly_db_error(e), True)

#     def _edit(self):
#         row = self._tbl.currentRow()
#         if row < 0:
#             self._show_status("Select a customer.", True); return

#         c = self._tbl.item(row, 0).data(Qt.UserRole)
#         self._f_name.setText(c.get("customer_name", ""))
#         self._f_type.setCurrentText(c.get("customer_type", ""))
#         self._f_trade.setText(c.get("custom_trade_name", ""))
#         self._f_phone.setText(c.get("custom_telephone_number", ""))
#         self._f_email.setText(c.get("custom_email_address", ""))
#         self._f_city.setText(c.get("custom_city", ""))
#         self._f_house.setText(c.get("custom_house_no", ""))

#         self._set_combo_value(self._f_group, c.get("customer_group_id"))
#         self._set_combo_value(self._f_wh, c.get("custom_warehouse_id"))
#         self._set_combo_value(self._f_cc, c.get("custom_cost_center_id"))
#         self._set_combo_value(self._f_pl, c.get("default_price_list_id"))

#         self.edit_btn.setText("Update Selected")
#         self.edit_btn.clicked.disconnect()
#         self.edit_btn.clicked.connect(lambda: self._update(c["id"]))

#     def _update(self, customer_id):
#         try:
#             from models.customer import update_customer
#             update_customer(
#                 customer_id=customer_id,
#                 customer_name=self._f_name.text().strip(),
#                 customer_group_id=self._f_group.currentData(),
#                 custom_warehouse_id=self._f_wh.currentData(),
#                 custom_cost_center_id=self._f_cc.currentData(),
#                 default_price_list_id=self._f_pl.currentData(),
#                 customer_type=self._f_type.currentText(),
#                 custom_trade_name=self._f_trade.text(),
#                 custom_telephone_number=self._f_phone.text(),
#                 custom_email_address=self._f_email.text(),
#                 custom_city=self._f_city.text(),
#                 custom_house_no=self._f_house.text()
#             )
#             self._clear_form()
#             self._reload()
#             self._show_status("Updated.")
#             self._reset_edit_btn()
#         except Exception as e:
#             self._show_status(_friendly_db_error(e), True)

#     def _delete(self):
#         row = self._tbl.currentRow()
#         if row < 0: return
#         c = self._tbl.item(row, 0).data(Qt.UserRole)
#         if QMessageBox.question(self, "Delete", f"Delete {c['customer_name']}?") == QMessageBox.Yes:
#             try:
#                 from models.customer import delete_customer
#                 delete_customer(c["id"])
#                 self._reload()
#             except Exception as e:
#                 self._show_status(_friendly_db_error(e), True)

#     def _set_combo_value(self, combo, value):
#         idx = combo.findData(value)
#         if idx >= 0: combo.setCurrentIndex(idx)

#     def _clear_form(self):
#         for f in [self._f_name, self._f_trade, self._f_phone, self._f_email, self._f_city, self._f_house]:
#             f.clear()
#         self._reset_edit_btn()

#     def _reset_edit_btn(self):
#         self.edit_btn.setText("Edit Selected")
#         try: self.edit_btn.clicked.disconnect()
#         except: pass
#         self.edit_btn.clicked.connect(self._edit)

#     def _show_status(self, msg, error=False):
#         color = DANGER if error else SUCCESS
#         self._status.setStyleSheet(f"font-size:12px;color:{color};")
#         self._status.setText(msg)
#         QTimer.singleShot(4000, lambda: self._status.setText(""))
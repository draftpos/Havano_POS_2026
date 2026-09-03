from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QLineEdit, QCompleter,
    QDoubleSpinBox, QMessageBox, QHeaderView, QAbstractItemView,
    QWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QStringListModel
from PySide6.QtGui import QFont

# ── Palette (mirrors the POS settings style) ─────────────────────────────────
from theme import *


class NewBundleParentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Bundle Parent")
        self.setFixedSize(400, 220)
        self.setStyleSheet(f"""
            QDialog {{ background: {WHITE}; color: {DARK_TEXT}; font-family: 'Segoe UI'; font-size: 13px; }}
            QLabel {{ font-size: 11px; font-weight: bold; color: {MUTED}; text-transform: uppercase; letter-spacing: 0.5px; }}
            QLineEdit, QDoubleSpinBox {{ border: 1px solid {BORDER}; border-radius: 4px; padding: 6px 10px; background: {WHITE}; color: {DARK_TEXT}; font-size: 14px; min-height: 24px; }}
            QLineEdit:focus, QDoubleSpinBox:focus {{ border: 1px solid {ACCENT}; }}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)
        
        # Buttons on top
        top_btns = QHBoxLayout()
        top_btns.setSpacing(10)
        top_btns.addStretch()
        
        cancel = QPushButton("Cancel")
        cancel.setFixedSize(90, 36)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet(f"""
            QPushButton {{ background: {WHITE}; color: {MUTED}; border: 1px solid {BORDER}; border-radius: 4px; font-size: 13px; }}
            QPushButton:hover {{ background: {ROW_ALT}; color: {DARK_TEXT}; }}
        """)
        cancel.clicked.connect(self.reject)
        
        save = QPushButton("Save")
        save.setFixedSize(110, 36)
        save.setCursor(Qt.PointingHandCursor)
        save.setStyleSheet(f"""
            QPushButton {{ background: {SUCCESS}; color: {WHITE}; border: none; border-radius: 4px; font-weight: bold; font-size: 13px; }}
            QPushButton:hover {{ background: {SUCCESS_H}; }}
        """)
        save.clicked.connect(self._save)
        
        top_btns.addWidget(cancel)
        top_btns.addWidget(save)
        root.addLayout(top_btns)
        
        v1 = QVBoxLayout(); v1.setSpacing(4)
        v1.addWidget(QLabel("Bundle Name"))
        self.name_in = QLineEdit()
        v1.addWidget(self.name_in)
        root.addLayout(v1)
        
        v2 = QVBoxLayout(); v2.setSpacing(4)
        v2.addWidget(QLabel("Default Code (SKU)"))
        self.code_in = QLineEdit()
        v2.addWidget(self.code_in)
        root.addLayout(v2)
        
        root.addStretch()
        
    def _save(self):
        n = self.name_in.text().strip()
        c = self.code_in.text().strip()
        p = 0.0 # Price is derived from bundle components
        if not n or not c:
            QMessageBox.warning(self, "Error", "Name and Code are required.")
            return
        
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO products (part_no, name, price, stock, category, uom, is_product_bundle, sync_status)
                VALUES (?, ?, ?, 0, 'Bundles', 'Units', 1, 'pending')
            """, (c, n, p))
            conn.commit()
            conn.close()
            self.created_code = c
            self.created_name = n
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save bundle parent:\n{e}")

class BundleDialog(QDialog):
    bundle_saved = Signal()

    def __init__(self, parent=None, bundle_id=None):
        super().__init__(parent)
        self.bundle_id  = bundle_id
        self.selected_items: list[dict] = []
        self.all_products: list[dict]   = []

        self.setWindowTitle("Bundle" if not bundle_id else "Edit Bundle")
        self.setMinimumSize(820, 580)
        self.showMaximized()
        self.setModal(True)

        self._setup_ui()
        self._load_products()

        if bundle_id:
            self._load_bundle()

    # ─────────────────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────────────────
    def _setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: {WHITE};
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                color: {DARK_TEXT};
            }}
            QLabel {{
                background: transparent;
            }}
            QLineEdit, QDoubleSpinBox {{
                background: {WHITE};
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 13px;
                color: {DARK_TEXT};
            }}
            QLineEdit:focus, QDoubleSpinBox:focus {{
                border: 1px solid {ACCENT};
            }}
            QScrollBar:vertical {{
                background: {LIGHT}; width: 6px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {MID}; border-radius: 3px; min-height: 20px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 18, 20, 16)

        # ── Header bar ───────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background: {NAVY}; border-radius: 6px;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)

        lbl_title = QLabel("Create Bundle" if not self.bundle_id else "Edit Bundle")
        lbl_title.setStyleSheet(f"color: {WHITE}; font-size: 15px; font-weight: bold;")
        lbl_sub   = QLabel("Group products into a sellable bundle")
        lbl_sub.setStyleSheet(f"color: {MID}; font-size: 11px;")

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title_col.addWidget(lbl_sub)
        hl.addLayout(title_col)
        
        hl.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(90, 36)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {NAVY_2}; color: {WHITE};
                border: 1px solid {BORDER}; border-radius: 4px;
                font-size: 13px;
            }}
            QPushButton:hover {{ background: {NAVY_3}; }}
        """)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save Bundle")
        save_btn.setFixedSize(110, 36)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {SUCCESS}; color: {WHITE};
                border: none; border-radius: 4px;
                font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover   {{ background: {SUCCESS_H}; }}
            QPushButton:pressed {{ background: {NAVY_3}; }}
        """)
        save_btn.clicked.connect(self._save)

        hl.addWidget(cancel_btn)
        hl.addWidget(save_btn)

        root.addWidget(hdr)

        # ── Name + Description row ───────────────────────────────────────────
        inf_row = QHBoxLayout()
        inf_row.setSpacing(12)

        nc = QVBoxLayout(); nc.setSpacing(3)
        nc.addWidget(self._sec("PRODUCT BUNDLE"))
        
        bn_row = QHBoxLayout()
        bn_row.setSpacing(4)
        self.bundle_name = QLineEdit()
        self.bundle_name.setFixedHeight(34)
        self.bundle_name.setPlaceholderText("Search or scan product bundle, or type new name...")
        bn_row.addWidget(self.bundle_name)
        
        nc.addLayout(bn_row)
        inf_row.addLayout(nc, 2)

        dc = QVBoxLayout(); dc.setSpacing(3)
        dc.addWidget(self._sec("Description  (optional)"))
        self.bundle_desc = QLineEdit()
        self.bundle_desc.setFixedHeight(34)
        self.bundle_desc.setPlaceholderText("Short note shown on receipts")
        dc.addWidget(self.bundle_desc)
        inf_row.addLayout(dc, 3)

        root.addLayout(inf_row)

        # ── Separator ────────────────────────────────────────────────────────
        root.addWidget(self._hr())

        # ── Items table ──────────────────────────────────────────────────────
        root.addWidget(self._sec("Bundle Items"))

        self.product_search = QLineEdit(self)
        self.product_search.setPlaceholderText("Search product...")
        self.product_search.setStyleSheet("background: transparent !important; background-color: transparent !important; border: none !important; margin: 0; padding: 0; color: #333; font-weight: bold;")
        self.product_search.hide()

        self.table = QTableWidget(15, 4)
        self.table.setHorizontalHeaderLabels(["Product", "Qty", "Unit Price", ""])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 90)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {WHITE};
                border: 1px solid {BORDER};
                border-radius: 4px;
                gridline-color: #b0bec5;
                font-size: 13px;
                outline: none;
                selection-background-color: transparent;
            }}
            QTableWidget::item {{ padding: 0 6px; border-bottom: 1px solid {LIGHT}; color: {DARK_TEXT}; }}
            QTableWidget::item:selected {{ background: #fff8e1; color: {NAVY}; }}
            QHeaderView::section {{
                background: {NAVY}; color: {WHITE};
                padding: 7px 8px; border: none;
                border-right: 1px solid {NAVY_2};
                font-size: 11px; font-weight: bold;
            }}
        """)
        root.addWidget(self.table, 1)
        self.table.cellClicked.connect(self._open_inline_search)
        self.product_search.setParent(self.table.viewport())

        for r in range(15):
            self.table.setRowHeight(r, 40)
            it = QTableWidgetItem("")
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, 0, it)

        # ── Bottom row ───────────────────────────────────────────────────────
        bot = QHBoxLayout()
        bot.setSpacing(8)

        self.total_label = QLabel("Total:  $0.00")
        self.total_label.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {ACCENT};"
        )
        bot.addWidget(self.total_label)
        bot.addStretch()

        root.addLayout(bot)

        self._setup_completer()

    def _create_parent(self):
        pass # Deprecated

    # ── helpers ───────────────────────────────────────────────────────────────
    def _sec(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: bold; color: {MUTED}; letter-spacing: 0.4px;"
        )
        return lbl

    def _hr(self):
        from PySide6.QtWidgets import QFrame
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {BORDER}; border: none;")
        return line

    # ─────────────────────────────────────────────────────────────────────────
    # COMPLETER
    # ─────────────────────────────────────────────────────────────────────────
    def _open_inline_search(self, row, col):
        if col != 0:
            self.product_search.hide()
            return
            
        self._current_row = row
        rect = self.table.visualRect(self.table.model().index(row, 0))
        self.product_search.setGeometry(rect)
        
        existing = self.table.item(row, 0)
        seed = existing.text().strip() if existing else ""
        self.product_search.setText(seed)
        self.product_search.selectAll()
        
        self.product_search.show()
        self.product_search.setFocus()

    def _setup_completer(self):
        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.product_search.setCompleter(self.completer)
        self.product_search.returnPressed.connect(self._add_product)
        

        self.bundle_completer = QCompleter()
        self.bundle_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.bundle_completer.setFilterMode(Qt.MatchContains)
        
        # Configure popup list to look good with highly visible row highlight
        _popup_style = """
            QListView {
                background: #ffffff;
                border: 2px solid #3b82f6;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
                color: #1e293b;
                outline: none;
            }
            QListView::item {
                padding: 10px 14px;
                min-height: 36px;
                border-bottom: 1px solid #f0f4f8;
            }
            QListView::item:hover {
                background-color: #dbeafe;
                color: #1d4ed8;
            }
            QListView::item:selected {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 700;
            }
        """
        for comp in (self.completer, self.bundle_completer):
            popup = comp.popup()
            popup.setStyleSheet(_popup_style)
            popup.setMinimumWidth(400)
        
        self.bundle_name.setCompleter(self.bundle_completer)

    # ─────────────────────────────────────────────────────────────────────────
    # DATA
    # ─────────────────────────────────────────────────────────────────────────
    def _load_products(self):
        from models.product import get_all_products
        self.all_products = get_all_products(include_variants=False)
        
        # Build standard items model
        matches = []
        for p in self.all_products:
            if not p.get('is_product_bundle'):
                matches.append(f"{p['part_no']} - {p['name']}")
        self.completer.setModel(QStringListModel(matches))
        
        # Build bundle items model
        bundle_matches = []
        for p in self.all_products:
            if p.get('is_product_bundle'):
                bundle_matches.append(f"{p['part_no']} - {p['name']}")
        self.bundle_completer.setModel(QStringListModel(bundle_matches))

    def _get_selected_product(self):
        text = self.product_search.text().strip()
        for p in self.all_products:
            if text == f"{p['part_no']} - {p['name']}" or text == p['part_no']:
                return p
        q = text.lower()
        for p in self.all_products:
            if q in p['name'].lower() or q in p['part_no'].lower():
                return p
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # ADD / REMOVE
    # ─────────────────────────────────────────────────────────────────────────
    def _add_product(self):
        product = self._get_selected_product()
        if not product:
            return

        qty = 1.0
        part_no = product['part_no']
        name    = product['name']
        price   = float(product['price'])

        # Check if already added
        for i, item in enumerate(self.selected_items):
            if item['item_code'] == part_no:
                self.product_search.clear()
                self.product_search.hide()
                return

        # Add to selected items
        row = getattr(self, "_current_row", len(self.selected_items))
        if row >= len(self.selected_items):
            self.selected_items.append({
                'item_code': part_no,
                'item_name': name,
                'quantity':  qty,
                'rate':      price
            })
        else:
            self.selected_items.insert(row, {
                'item_code': part_no,
                'item_name': name,
                'quantity':  qty,
                'rate':      price
            })
            
        self._refresh_table()
        self._update_total()
        self.product_search.clear()
        self.product_search.hide()
        
        # Focus the qty widget of the added row
        w = self.table.cellWidget(row, 1)
        if w:
            for child in w.children():
                if isinstance(child, QLineEdit):
                    child.setFocus()
                    child.selectAll()
                    break

    def _remove_item(self, row: int):
        self.selected_items.pop(row)
        self._refresh_table()
        self._update_total()

    def _update_quantity(self, row: int, value: float):
        if row < len(self.selected_items):
            self.selected_items[row]['quantity'] = value
            self._update_total()

    def _update_price(self, row: int, value: float):
        if row < len(self.selected_items):
            self.selected_items[row]['rate'] = value
            self._update_total()

    # ─────────────────────────────────────────────────────────────────────────
    # TABLE
    # ─────────────────────────────────────────────────────────────────────────
    def _refresh_table(self):
        self.table.setRowCount(0)
        self.table.setRowCount(15)
        for row in range(15):
            self.table.setRowHeight(row, 40)
            if row < len(self.selected_items):
                item = self.selected_items[row]
                # Product name
                name_item = QTableWidgetItem(f"{item['item_code']} - {item['item_name']}")
                name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
                name_item.setToolTip(item['item_code'])
                self.table.setItem(row, 0, name_item)

                # Qty
                qty_edit = QLineEdit(f"{item['quantity']:.2f}")
                qty_edit.setAlignment(Qt.AlignCenter)
                qty_edit.setStyleSheet(f"border: none; background: transparent; color: {DARK_TEXT}; font-size: 13px; font-weight: bold;")
                qty_edit.textChanged.connect(lambda t, r=row: self._update_quantity(r, float(t) if t else 0.0))
                
                # Jump to next row inline search on Enter
                def on_qty_enter(r_idx=row):
                    next_r = r_idx + 1
                    if next_r < self.table.rowCount():
                        self.table.setCurrentCell(next_r, 0)
                        self._open_inline_search(next_r, 0)
                
                from PySide6.QtCore import QObject, QEvent
                class QtyEventFilter(QObject):
                    def __init__(self, enter_cb, parent=None):
                        super().__init__(parent)
                        self.enter_cb = enter_cb
                    def eventFilter(self, obj, event):
                        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
                            self.enter_cb()
                            return True
                        ret = super().eventFilter(obj, event)
                        return bool(ret) if ret is not None else False
                
                qef = QtyEventFilter(on_qty_enter, qty_edit)
                qty_edit.installEventFilter(qef)
                qty_edit._filter = qef
                
                qty_wrap = QWidget()
                ql = QHBoxLayout(qty_wrap)
                ql.setContentsMargins(0, 0, 0, 0)
                ql.addWidget(qty_edit)
                self.table.setCellWidget(row, 1, qty_wrap)

                # Price
                price_edit = QLineEdit(f"{item['rate']:.2f}")
                price_edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                price_edit.setStyleSheet(f"border: none; background: transparent; color: {DARK_TEXT}; font-size: 13px;")
                price_edit.textChanged.connect(lambda t, r=row: self._update_price(r, float(t) if t else 0.0))
                
                price_wrap = QWidget()
                pl = QHBoxLayout(price_wrap)
                pl.setContentsMargins(0, 0, 8, 0)
                pl.addWidget(price_edit)
                self.table.setCellWidget(row, 2, price_wrap)

                # Remove button
                rm_btn = QPushButton()
                import qtawesome as qta
                rm_btn.setIcon(qta.icon("fa5s.trash", color="#c0392b"))
                rm_btn.setFixedSize(28, 28)
                rm_btn.setCursor(Qt.PointingHandCursor)
                rm_btn.setStyleSheet("background: transparent; border: none;")
                rm_btn.clicked.connect(lambda _, r=row: self._remove_item(r))
                
                del_lay = QHBoxLayout()
                del_lay.setContentsMargins(0,0,0,0)
                del_lay.addWidget(rm_btn)
                w = QWidget()
                w.setLayout(del_lay)
                self.table.setCellWidget(row, 3, w)
            else:
                it = QTableWidgetItem("")
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, 0, it)
                self.table.removeCellWidget(row, 1)
                self.table.removeCellWidget(row, 2)
                self.table.removeCellWidget(row, 3)

    def _update_total(self):
        total = sum(i['quantity'] * i['rate'] for i in self.selected_items)
        self.total_label.setText(f"Total:  ${total:.2f}")

    # ─────────────────────────────────────────────────────────────────────────
    # LOAD
    # ─────────────────────────────────────────────────────────────────────────
    def _load_bundle(self):
        from database.db import get_connection
        import json
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name, bundle_lines FROM products WHERE part_no = ?", (self.bundle_id,))
        row = cur.fetchone()
        conn.close()
        
        if row:
            self.bundle_name.setText(f"{self.bundle_id} - {row[0]}")
            self.selected_items = []
            
            lines_json = row[1]
            if lines_json:
                try:
                    items = json.loads(lines_json)
                    for item in items:
                        self.selected_items.append({
                            'item_code': item.get('item_code', ''),
                            'item_name': item.get('item_name') or item.get('item_code', ''),
                            'quantity': float(item.get('quantity') or 1),
                            'rate': float(item.get('rate') or item.get('sale_price') or 0.0),
                            'uom': item.get('uom', 'Units')
                        })
                except Exception as e:
                    print(f"Failed to load bundle lines: {e}")
            self._refresh_table()
            self._update_total()

    # ─────────────────────────────────────────────────────────────────────────
    # SAVE
    # ─────────────────────────────────────────────────────────────────────────
    def _save(self):
        bundle_name_input = self.bundle_name.text().strip()
        description = self.bundle_desc.text().strip()

        if not bundle_name_input:
            QMessageBox.warning(self, "Missing Name", "Please select a bundle parent item.")
            self.bundle_name.setFocus()
            return
            
        # Try to extract just the bundle name if they selected from completer
        bundle_name = bundle_name_input
        if " - " in bundle_name_input:
            bundle_name = bundle_name_input.split(" - ", 1)[0].strip() # Use code instead of name

        if not self.selected_items:
            QMessageBox.warning(self, "No Items",
                                "Please add at least one product to the bundle.")
            return

        from database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        
        total_price = 0.0
        total_cost = 0.0
        for i in self.selected_items:
            qty = float(i['quantity'])
            c_code = i['item_code']
            cur.execute("SELECT cost_price, price FROM products WHERE part_no = ?", (c_code,))
            crow = cur.fetchone()
            if crow:
                c_cost = float(crow[0] or 0)
                c_price = float(crow[1] or 0)
                if c_price <= 0:
                    c_price = float(i['rate'] or 0)
            else:
                c_cost = 0.0
                c_price = float(i['rate'] or 0)
            total_price += qty * c_price
            total_cost += qty * c_cost

        cur.execute("SELECT part_no FROM products WHERE name = ? OR part_no = ?", (bundle_name, bundle_name))
        row = cur.fetchone()
        
        if not row:
            # Auto-create the product bundle parent
            part_no = bundle_name.upper()
            name = bundle_name_input # Use the full text
            try:
                cur.execute("""
                    INSERT INTO products (part_no, name, price, cost_price, stock, category, uom, is_product_bundle, track_stock, sync_status)
                    VALUES (?, ?, ?, ?, 0, 'Bundles', 'Units', 1, 0, 'pending')
                """, (part_no, name, total_price, total_cost))
                parent_part_no = part_no
            except Exception as e:
                conn.close()
                QMessageBox.warning(self, "Error", f"Failed to create bundle parent: {e}")
                return
        else:
            parent_part_no = row[0]
        import json

        items_to_save = [
            {'item_code': i['item_code'], 'quantity': float(i['quantity']),
             'rate': float(i['rate']), 'uom': 'Units'}
            for i in self.selected_items
        ]
        
        # We store the total rate to use as a list price if we push to Odoo later

        reply = QMessageBox.question(
            self, "Confirm",
            f"Save bundle lines into {parent_part_no} with {len(items_to_save)} item(s)?\n"
            f"Calculated Cost: ${total_cost:.2f} | Selling Price: ${total_price:.2f}",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                lines_json = json.dumps(items_to_save)
                cur.execute("""
                    UPDATE products 
                    SET bundle_lines = ?, sync_status = 'pending', is_product_bundle = 1,
                        price = ?, cost_price = ?,
                        bundle_cost_total = ?, bundle_sale_total = ?
                    WHERE part_no = ?
                """, (lines_json, total_price, total_cost, total_cost, total_price, parent_part_no))
                
                cur.execute("""
                    UPDATE item_prices
                    SET price = ?
                    WHERE part_no = ? AND price <= 0
                """, (total_price, parent_part_no))
                
                conn.commit()
                
                self.bundle_saved.emit()
                self.accept()
            except Exception as e:
                conn.rollback()
                QMessageBox.critical(self, "Save Failed", str(e))
            finally:
                conn.close()
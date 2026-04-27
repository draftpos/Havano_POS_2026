from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QLineEdit, QCompleter,
    QDoubleSpinBox, QMessageBox, QHeaderView, QAbstractItemView,
    QWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QStringListModel
from PySide6.QtGui import QFont

# ── Palette (mirrors the POS settings style) ─────────────────────────────────
NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
NAVY_3    = "#1e3d6e"
ACCENT    = "#1a5fb4"
ACCENT_H  = "#1c6dd0"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
LIGHT     = "#e4eaf4"
MID       = "#8fa8c8"
DARK_TEXT = "#0d1f3c"
MUTED     = "#5a7a9a"
BORDER    = "#c8d8ec"
ROW_ALT   = "#edf3fb"
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"


class BundleDialog(QDialog):
    bundle_saved = Signal()

    def __init__(self, parent=None, bundle_id=None):
        super().__init__(parent)
        self.bundle_id  = bundle_id
        self.selected_items: list[dict] = []
        self.all_products: list[dict]   = []

        self.setWindowTitle("Bundle" if not bundle_id else "Edit Bundle")
        self.setMinimumSize(820, 580)
        self.resize(860, 620)
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
        title_col.addWidget(lbl_title)
        title_col.addWidget(lbl_sub)
        hl.addLayout(title_col)
        root.addWidget(hdr)

        # ── Name + Description row ───────────────────────────────────────────
        inf_row = QHBoxLayout()
        inf_row.setSpacing(12)

        nc = QVBoxLayout(); nc.setSpacing(3)
        nc.addWidget(self._sec("Bundle Name"))
        self.bundle_name = QLineEdit()
        self.bundle_name.setFixedHeight(34)
        self.bundle_name.setPlaceholderText("e.g. Breakfast Combo")
        nc.addWidget(self.bundle_name)
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

        # ── Add product row ──────────────────────────────────────────────────
        add_row = QHBoxLayout()
        add_row.setSpacing(8)

        add_row.addWidget(self._sec("Add Product:"))

        self.product_search = QLineEdit()
        self.product_search.setFixedHeight(34)
        self.product_search.setPlaceholderText("Search by name or part number…")
        add_row.addWidget(self.product_search, 1)

        qty_lbl = QLabel("Qty:")
        qty_lbl.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        add_row.addWidget(qty_lbl)

        self.qty_input = QLineEdit()
        self.qty_input.setFixedSize(64, 34)
        self.qty_input.setAlignment(Qt.AlignCenter)
        self.qty_input.setPlaceholderText("1")
        self.qty_input.setText("1")
        self.qty_input.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {BORDER}; border-radius: 4px;
                font-size: 13px; font-weight: bold;
                color: {DARK_TEXT}; background: {WHITE};
                padding: 4px;
            }}
            QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
        """)
        add_row.addWidget(self.qty_input)

        add_btn = QPushButton("Add")
        add_btn.setFixedSize(70, 34)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: {WHITE};
                border: none; border-radius: 4px;
                font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover   {{ background: {ACCENT_H}; }}
            QPushButton:pressed {{ background: {NAVY_3}; }}
        """)
        add_btn.clicked.connect(self._add_product)
        add_row.addWidget(add_btn)

        root.addLayout(add_row)

        # ── Items table ──────────────────────────────────────────────────────
        root.addWidget(self._sec("Bundle Items"))

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Product", "Qty", "Unit Price", ""])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 90)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {WHITE};
                border: 1px solid {BORDER};
                border-radius: 4px;
                gridline-color: {LIGHT};
                font-size: 13px;
                outline: none;
            }}
            QTableWidget::item {{ padding: 0 6px; border: none; }}
            QTableWidget::item:selected {{ background: {ACCENT}; color: {WHITE}; }}
            QTableWidget::item:alternate {{ background: {ROW_ALT}; }}
            QHeaderView::section {{
                background: {NAVY}; color: {WHITE};
                padding: 7px 8px; border: none;
                border-right: 1px solid {NAVY_2};
                font-size: 11px; font-weight: bold;
            }}
        """)
        root.addWidget(self.table, 1)

        # ── Bottom row ───────────────────────────────────────────────────────
        bot = QHBoxLayout()
        bot.setSpacing(8)

        self.total_label = QLabel("Total:  $0.00")
        self.total_label.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {ACCENT};"
        )
        bot.addWidget(self.total_label)
        bot.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(90, 36)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {WHITE}; color: {MUTED};
                border: 1px solid {BORDER}; border-radius: 4px;
                font-size: 13px;
            }}
            QPushButton:hover {{ background: {LIGHT}; color: {DARK_TEXT}; }}
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

        bot.addWidget(cancel_btn)
        bot.addWidget(save_btn)
        root.addLayout(bot)

        self._setup_completer()

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
    def _setup_completer(self):
        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.product_search.setCompleter(self.completer)
        self.product_search.textChanged.connect(self._update_suggestions)
        self.product_search.returnPressed.connect(self._add_product)
        self.qty_input.returnPressed.connect(self._add_product)

    # ─────────────────────────────────────────────────────────────────────────
    # DATA
    # ─────────────────────────────────────────────────────────────────────────
    def _load_products(self):
        from models.product import get_all_products
        self.all_products = get_all_products(include_variants=False)
        self._update_suggestions()

    def _update_suggestions(self):
        text = self.product_search.text().lower()
        matches = []
        for p in self.all_products:
            if text in p['name'].lower() or text in p['part_no'].lower():
                matches.append(f"{p['part_no']} - {p['name']}")
        self.completer.setModel(QStringListModel(matches[:20]))

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
            QMessageBox.warning(self, "Not Found",
                                "No matching product found. Refine your search.")
            return

        # parse qty
        try:
            qty = float(self.qty_input.text().strip() or "1")
            if qty <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Invalid Qty", "Please enter a valid quantity.")
            self.qty_input.setFocus()
            return

        part_no = product['part_no']
        name    = product['name']
        price   = float(product['price'])

        # bump quantity if already added
        for i, item in enumerate(self.selected_items):
            if item['item_code'] == part_no:
                self.selected_items[i]['quantity'] += qty
                self._refresh_table()
                self._update_total()
                self.qty_input.setText("1")
                self.product_search.clear()
                return

        self.selected_items.append({
            'item_code': part_no,
            'item_name': name,
            'quantity':  qty,
            'rate':      price
        })
        self._refresh_table()
        self._update_total()
        self.qty_input.setText("1")
        self.product_search.clear()

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
        for row, item in enumerate(self.selected_items):
            self.table.insertRow(row)
            self.table.setRowHeight(row, 40)

            # Product name
            name_item = QTableWidgetItem(item['item_name'])
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            name_item.setToolTip(item['item_code'])
            self.table.setItem(row, 0, name_item)

            # Qty spinbox — no arrows visible via stylesheet, looks like a plain field
            qty_spin = QDoubleSpinBox()
            qty_spin.setRange(0.01, 9999)
            qty_spin.setDecimals(2)
            qty_spin.setValue(item['quantity'])
            qty_spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
            qty_spin.setAlignment(Qt.AlignCenter)
            qty_spin.setStyleSheet(f"""
                QDoubleSpinBox {{
                    border: 1px solid {BORDER}; border-radius: 3px;
                    padding: 3px 6px; font-size: 13px;
                    background: {WHITE}; color: {DARK_TEXT};
                }}
                QDoubleSpinBox:focus {{ border: 1px solid {ACCENT}; }}
                QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                    width: 0; height: 0; border: none;
                }}
            """)
            qty_spin.valueChanged.connect(lambda v, r=row: self._update_quantity(r, v))

            qty_wrap = QWidget()
            ql = QHBoxLayout(qty_wrap)
            ql.setContentsMargins(4, 3, 4, 3)
            ql.addWidget(qty_spin)
            self.table.setCellWidget(row, 1, qty_wrap)

            # Price spinbox
            price_spin = QDoubleSpinBox()
            price_spin.setRange(0, 999999)
            price_spin.setDecimals(2)
            price_spin.setPrefix("$")
            price_spin.setValue(item['rate'])
            price_spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
            price_spin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            price_spin.setStyleSheet(f"""
                QDoubleSpinBox {{
                    border: 1px solid {BORDER}; border-radius: 3px;
                    padding: 3px 6px; font-size: 13px;
                    background: {WHITE}; color: {DARK_TEXT};
                }}
                QDoubleSpinBox:focus {{ border: 1px solid {ACCENT}; }}
                QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                    width: 0; height: 0; border: none;
                }}
            """)
            price_spin.valueChanged.connect(lambda v, r=row: self._update_price(r, v))

            price_wrap = QWidget()
            pl = QHBoxLayout(price_wrap)
            pl.setContentsMargins(4, 3, 4, 3)
            pl.addWidget(price_spin)
            self.table.setCellWidget(row, 2, price_wrap)

            # Remove button
            rm_btn = QPushButton("Remove")
            rm_btn.setCursor(Qt.PointingHandCursor)
            rm_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {WHITE}; color: {DANGER};
                    border: 1px solid {BORDER}; border-radius: 3px;
                    font-size: 11px; font-weight: bold;
                    margin: 5px 6px;
                }}
                QPushButton:hover {{
                    background: {DANGER}; color: {WHITE}; border-color: {DANGER};
                }}
            """)
            rm_btn.clicked.connect(lambda _, r=row: self._remove_item(r))
            self.table.setCellWidget(row, 3, rm_btn)

    def _update_total(self):
        total = sum(i['quantity'] * i['rate'] for i in self.selected_items)
        self.total_label.setText(f"Total:  ${total:.2f}")

    # ─────────────────────────────────────────────────────────────────────────
    # LOAD
    # ─────────────────────────────────────────────────────────────────────────
    def _load_bundle(self):
        from models.product_bundle import get_bundle_by_id
        bundle = get_bundle_by_id(self.bundle_id)
        if bundle:
            self.bundle_name.setText(bundle['name'])
            self.bundle_desc.setText(bundle.get('description', '') or '')
            self.selected_items = []
            for item in bundle.get('items', []):
                self.selected_items.append({
                    'item_code': item['item_code'],
                    'item_name': item.get('item_name', item['item_code']),
                    'quantity':  item['quantity'],
                    'rate':      item['rate']
                })
            self._refresh_table()
            self._update_total()

    # ─────────────────────────────────────────────────────────────────────────
    # SAVE
    # ─────────────────────────────────────────────────────────────────────────
    def _save(self):
        bundle_name = self.bundle_name.text().strip()
        description = self.bundle_desc.text().strip()

        if not bundle_name:
            QMessageBox.warning(self, "Missing Name", "Please enter a bundle name.")
            self.bundle_name.setFocus()
            return
        if not self.selected_items:
            QMessageBox.warning(self, "No Items",
                                "Please add at least one product to the bundle.")
            return

        from models.product_bundle import create_bundle, update_bundle, get_bundle_by_name

        # Duplicate name check
        existing = get_bundle_by_name(bundle_name)
        if existing and existing['id'] != self.bundle_id:
            QMessageBox.warning(
                self, "Name Already Exists",
                f'A bundle named "{bundle_name}" already exists.\n'
                "Please choose a different name."
            )
            self.bundle_name.setFocus()
            self.bundle_name.selectAll()
            return

        items_to_save = [
            {'item_code': i['item_code'], 'quantity': i['quantity'],
             'rate': i['rate'], 'uom': 'Nos'}
            for i in self.selected_items
        ]
        total = sum(i['quantity'] * i['rate'] for i in self.selected_items)

        reply = QMessageBox.question(
            self, "Confirm",
            f"Save '{bundle_name}' with {len(items_to_save)} item(s)?\n"
            f"Total: ${total:.2f}",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                if self.bundle_id:
                    update_bundle(self.bundle_id, bundle_name, items_to_save, description)
                else:
                    create_bundle(bundle_name, items_to_save, description)
                self.bundle_saved.emit()
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Save Failed", str(e))
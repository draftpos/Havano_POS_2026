# =============================================================================
# INVENTORY LIST DIALOG
# =============================================================================
class InventoryListDialog(QDialog):
    """Simple inventory list dialog showing products with stock levels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Inventory List")
        self.setMinimumSize(900, 600)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background-color: {WHITE}; }}")
        self._build()
        self._load_data()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(44)
        hdr.setStyleSheet(f"background-color: {NAVY}; border-radius: 5px;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        title = QLabel("📦  Inventory List")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {WHITE}; background: transparent;")
        hl.addWidget(title)
        layout.addWidget(hdr)

        # Search bar
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Search by product name or part number...")
        self._search.setFixedHeight(34)
        self._search.textChanged.connect(self._do_search)
        search_row.addWidget(self._search, 1)
        
        refresh_btn = QPushButton("🔄  Refresh")
        refresh_btn.setFixedHeight(34)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY_2}; color: {WHITE}; border: none;
                border-radius: 4px; font-size: 11px; font-weight: bold; padding: 0 12px;
            }}
            QPushButton:hover {{ background-color: {NAVY_3}; }}
        """)
        refresh_btn.clicked.connect(self._load_data)
        search_row.addWidget(refresh_btn)
        
        layout.addLayout(search_row)

        # Table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Part No.", "Product Name", "Category", "Stock", "Price"])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed); self._table.setColumnWidth(0, 100)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed); self._table.setColumnWidth(2, 120)
        hh.setSectionResizeMode(3, QHeaderView.Fixed); self._table.setColumnWidth(3, 80)
        hh.setSectionResizeMode(4, QHeaderView.Fixed); self._table.setColumnWidth(4, 100)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background: {WHITE}; border: 1px solid {BORDER};
                gridline-color: {LIGHT}; outline: none;
            }}
            QTableWidget::item           {{ padding: 6px 8px; }}
            QTableWidget::item:selected  {{ background-color: {ACCENT}; color: {WHITE}; }}
            QTableWidget::item:alternate {{ background-color: {ROW_ALT}; }}
            QHeaderView::section {{
                background-color: {NAVY}; color: {WHITE};
                padding: 8px; border: none; border-right: 1px solid {NAVY_2};
                font-size: 11px; font-weight: bold;
            }}
        """)
        layout.addWidget(self._table, 1)

        # Status bar
        self._status = QLabel("Loading...")
        self._status.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent; padding: 4px;")
        layout.addWidget(self._status)

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(36)
        close_btn.setFixedWidth(100)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {NAVY}; color: {WHITE}; border: none;
                border-radius: 4px; font-size: 12px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {NAVY_2}; }}
        """)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _load_data(self):
        """Load all products from database."""
        try:
            from models.product import get_all_products
            products = get_all_products()
            self._all_products = products
            self._populate_table(products)
            self._status.setText(f"Total products: {len(products)}")
        except Exception as e:
            self._status.setText(f"Error loading products: {e}")
            self._all_products = []
            self._populate_table([])

    def _do_search(self, query: str):
        """Filter products based on search query."""
        if not hasattr(self, '_all_products'):
            return
        
        if not query.strip():
            self._populate_table(self._all_products)
            self._status.setText(f"Total products: {len(self._all_products)}")
            return
        
        ql = query.lower()
        filtered = [
            p for p in self._all_products
            if ql in (p.get("part_no", "") or "").lower()
            or ql in (p.get("name", "") or "").lower()
            or ql in (p.get("category", "") or "").lower()
        ]
        self._populate_table(filtered)
        self._status.setText(f"Found {len(filtered)} products")

    def _populate_table(self, products: list):
        """Fill table with product data."""
        self._table.setRowCount(0)
        
        for p in products:
            row = self._table.rowCount()
            self._table.insertRow(row)
            
            # Part No.
            part_no_item = QTableWidgetItem(p.get("part_no", ""))
            part_no_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 0, part_no_item)
            
            # Product Name
            name_item = QTableWidgetItem(p.get("name", ""))
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._table.setItem(row, 1, name_item)
            
            # Category
            cat_item = QTableWidgetItem(p.get("category", ""))
            cat_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 2, cat_item)
            
            # Stock
            stock = float(p.get("stock", 0) or 0)
            stock_item = QTableWidgetItem(f"{stock:.2f}" if stock != int(stock) else f"{int(stock)}")
            stock_item.setTextAlignment(Qt.AlignCenter)
            if stock <= 5:
                stock_item.setForeground(QColor(DANGER))
            elif stock <= 10:
                stock_item.setForeground(QColor(AMBER))
            else:
                stock_item.setForeground(QColor(SUCCESS))
            self._table.setItem(row, 3, stock_item)
            
            # Price
            price = float(p.get("price", 0) or 0)
            price_item = QTableWidgetItem(f"${price:.2f}")
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            price_item.setForeground(QColor(ACCENT))
            self._table.setItem(row, 4, price_item)
            
            # Store full product data in first column for reference
            part_no_item.setData(Qt.UserRole, p)
            
            self._table.setRowHeight(row, 32)
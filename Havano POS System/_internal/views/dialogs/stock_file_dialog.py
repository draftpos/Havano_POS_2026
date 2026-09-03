# =============================================================================
# views/dialogs/stock_file_dialog.py  —  Updated for UOM & Conversion
# =============================================================================

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QComboBox, QFrame, QGroupBox,
    QMessageBox, QSizePolicy, QFormLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QDoubleValidator

from models.product import (
    get_all_products,
    search_products,
    get_categories,
    create_product,
    update_product,
)

# ── colours ───────────────────────────────────────────────────────────────────
NAVY      = "#0d1f3c"
NAVY_2    = "#162d52"
NAVY_3    = "#1e3d6e"
ACCENT    = "#1a5fb4"
ACCENT_H  = "#1c6dd0"
WHITE     = "#ffffff"
OFF_WHITE = "#f5f8fc"
LIGHT     = "#e4eaf4"
BORDER    = "#c8d8ec"
DARK_TEXT = "#0d1f3c"
MUTED     = "#5a7a9a"
SUCCESS   = "#1a7a3c"
SUCCESS_H = "#1f9447"
DANGER    = "#b02020"
DANGER_H  = "#cc2828"
ROW_SEL   = "#1a5fb4"
ROW_ALT   = "#edf3fb"

# =============================================================================
# HELPERS
# =============================================================================

def _hr():
    ln = QFrame()
    ln.setFrameShape(QFrame.HLine)
    ln.setStyleSheet(f"background: {BORDER}; border: none;")
    ln.setFixedHeight(1)
    return ln

def _btn(text, bg, hov, w=100, h=64):
    b = QPushButton(text)
    b.setFixedSize(w, h)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: {WHITE}; border: none;
            border-radius: 8px; font-size: 11px; font-weight: bold; text-align: center;
        }}
        QPushButton:hover   {{ background-color: {hov}; }}
        QPushButton:pressed {{ background-color: {NAVY_3}; }}
        QPushButton:disabled {{ background-color: {LIGHT}; color: {MUTED}; }}
    """)
    return b

def _combo():
    c = QComboBox()
    c.setFixedHeight(28)
    c.setStyleSheet(f"""
        QComboBox {{
            background-color: {WHITE}; color: {DARK_TEXT};
            border: 1px solid {BORDER}; border-radius: 4px;
            padding: 2px 8px; font-size: 12px;
        }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
        QComboBox QAbstractItemView {{
            background: {WHITE}; border: 1px solid {BORDER};
            selection-background-color: {ACCENT}; selection-color: {WHITE};
        }}
    """)
    return c

# =============================================================================
# EDIT DIALOG (Requirement 6: UOM & Conversion)
# =============================================================================
class StockEditDialog(QDialog):
    def __init__(self, parent=None, product=None):
        super().__init__(parent)
        self.product = product # None if new
        self.setWindowTitle("Edit Product" if product else "New Product")
        self.setFixedWidth(450)
        self.result_data = {}
        self._build_ui()
        if product:
            self._load_product()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.f_part = QLineEdit()
        self.f_name = QLineEdit()
        self.f_price = QLineEdit("0.00")
        self.f_stock = QLineEdit("0")
        self.f_cat = QComboBox()
        self.f_cat.setEditable(True)
        self.f_cat.addItems(get_categories())
        
        # New UOM fields
        self.f_uom = QComboBox()
        self.f_uom.setEditable(True)
        self.f_uom.addItems(["Unit", "Kg", "Litre", "Meter", "Box", "Pack"])
        
        self.f_conv = QLineEdit("1.0")
        self.f_conv.setValidator(QDoubleValidator(0, 1000, 4))

        form.addRow("Part Number:", self.f_part)
        form.addRow("Product Name:", self.f_name)
        form.addRow("Category:", self.f_cat)
        form.addRow("Unit of Measure:", self.f_uom)
        form.addRow("Conv. Factor:", self.f_conv)
        form.addRow("Retail Price ($):", self.f_price)
        form.addRow("Initial Stock:", self.f_stock)
        
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        save = QPushButton("Save")
        save.clicked.connect(self._on_save)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(save)
        layout.addLayout(btns)

    def _load_product(self):
        self.f_part.setText(self.product['part_no'])
        self.f_name.setText(self.product['name'])
        self.f_price.setText(f"{self.product['price']:.2f}")
        self.f_stock.setText(str(self.product['stock']))
        self.f_cat.setCurrentText(self.product['category'])
        self.f_uom.setCurrentText(self.product.get('uom', 'Unit'))
        self.f_conv.setText(str(self.product.get('conversion_factor', 1.0)))

    def _on_save(self):
        if not self.f_part.text() or not self.f_name.text():
            QMessageBox.warning(self, "Error", "Part No and Name are required.")
            return
            
        self.result_data = {
            "part_no": self.f_part.text(),
            "name": self.f_name.text(),
            "price": float(self.f_price.text() or 0),
            "stock": float(self.f_stock.text() or 0),
            "category": self.f_cat.currentText(),
            "uom": self.f_uom.currentText(),
            "conversion_factor": float(self.f_conv.text() or 1.0)
        }
        self.accept()

# =============================================================================
# MAIN STOCK FILE DIALOG
# =============================================================================
class StockFileDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stock File")
        self.setMinimumSize(1000, 650)
        self.setModal(True)
        self._all_products = []
        
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        title = QLabel("📦 Stock File & Inventory Management")
        title.setFixedHeight(40)
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {WHITE}; background: {NAVY}; border-radius: 6px; padding-left: 15px;")
        root.addWidget(title)

        # Search Bar
        search_box = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search by Part No or Name...")
        self._search_input.textChanged.connect(self._do_search)
        
        self._category_combo = _combo()
        self._category_combo.currentTextChanged.connect(self._apply_category_filter)
        
        search_box.addWidget(QLabel("Search:"))
        search_box.addWidget(self._search_input, 1)
        search_box.addWidget(QLabel("Category:"))
        search_box.addWidget(self._category_combo)
        root.addLayout(search_box)

        # Table Updated with UOM column
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Part No.", "Details", "UOM", "Stock", "Retail $"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_modify)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        root.addWidget(self.table)

        # Actions
        btn_row = QHBoxLayout()
        self._new_btn = _btn("➕\nNew", ACCENT, ACCENT_H)
        self._modify_btn = _btn("✏️\nModify", SUCCESS, SUCCESS_H)
        self._clone_btn = _btn("📋\nClone", NAVY_2, NAVY_3)
        self._close_btn = _btn("✕\nClose", DANGER, DANGER_H)

        self._new_btn.clicked.connect(self._on_new)
        self._modify_btn.clicked.connect(self._on_modify)
        self._close_btn.clicked.connect(self.reject)

        btn_row.addWidget(self._new_btn)
        btn_row.addWidget(self._modify_btn)
        btn_row.addWidget(self._clone_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._close_btn)
        root.addLayout(btn_row)

    def _load_data(self):
        self._all_products = get_all_products()
        self._category_combo.blockSignals(True)
        self._category_combo.clear()
        self._category_combo.addItem("All")
        self._category_combo.addItems(get_categories())
        self._category_combo.blockSignals(False)
        self._render_table(self._all_products)

    def _render_table(self, products):
        self.table.setRowCount(len(products))
        for r, p in enumerate(products):
            self.table.setItem(r, 0, QTableWidgetItem(p['part_no']))
            self.table.setItem(r, 1, QTableWidgetItem(p['name']))
            self.table.setItem(r, 2, QTableWidgetItem(p.get('uom', 'Unit')))
            self.table.setItem(r, 3, QTableWidgetItem(str(p['stock'])))
            
            price_item = QTableWidgetItem(f"{p['price']:.2f}")
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 4, price_item)
            
            self.table.item(r, 0).setData(Qt.UserRole, p)

    def _do_search(self):
        query = self._search_input.text().strip()
        self._render_table(search_products(query) if query else self._all_products)

    def _apply_category_filter(self, cat):
        if cat == "All":
            self._render_table(self._all_products)
        else:
            filtered = [p for p in self._all_products if p['category'] == cat]
            self._render_table(filtered)

    def _on_selection(self):
        has_sel = len(self.table.selectionModel().selectedRows()) > 0
        self._modify_btn.setEnabled(has_sel)
        self._clone_btn.setEnabled(has_sel)

    def _get_selected(self):
        rows = self.table.selectionModel().selectedRows()
        return self.table.item(rows[0].row(), 0).data(Qt.UserRole) if rows else None

    def _on_new(self):
        dlg = StockEditDialog(self)
        if dlg.exec() == QDialog.Accepted:
            create_product(**dlg.result_data)
            self._load_data()

    def _on_modify(self):
        p = self._get_selected()
        if not p: return
        dlg = StockEditDialog(self, product=p)
        if dlg.exec() == QDialog.Accepted:
            update_product(p['id'], **dlg.result_data)
            self._load_data()
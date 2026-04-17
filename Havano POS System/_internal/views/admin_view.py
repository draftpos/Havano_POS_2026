# views/admin_view.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QMessageBox
)
from models.product import get_all_products, add_product, update_product, delete_product

class AdminView(QWidget):
    """Like a Django admin — list, add, edit, delete products."""

    def __init__(self):
        super().__init__()
        self._build_ui()
        self._load_table()

    def _build_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(QLabel("Admin — Manage Products"))

        # Form to add a product
        form = QHBoxLayout()
        self.name_input     = QLineEdit(); self.name_input.setPlaceholderText("Name")
        self.price_input    = QLineEdit(); self.price_input.setPlaceholderText("Price")
        self.stock_input    = QLineEdit(); self.stock_input.setPlaceholderText("Stock")
        self.category_input = QLineEdit(); self.category_input.setPlaceholderText("Category")

        add_btn = QPushButton("Add Product")
        add_btn.clicked.connect(self._add_product)

        for w in [self.name_input, self.price_input,
                  self.stock_input, self.category_input, add_btn]:
            form.addWidget(w)

        root.addLayout(form)

        # Table — like Django admin list view
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Price", "Stock", "Category"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)  # read only
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        root.addWidget(self.table)

        # Edit / Delete buttons
        btn_row = QHBoxLayout()
        edit_btn   = QPushButton("Edit Selected")
        delete_btn = QPushButton("Delete Selected")
        edit_btn.clicked.connect(self._edit_product)
        delete_btn.clicked.connect(self._delete_product)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(delete_btn)
        root.addLayout(btn_row)

    def _load_table(self):
        """Refresh table from DB — like queryset re-fetch."""
        products = get_all_products()
        self.table.setRowCount(len(products))
        for row_idx, p in enumerate(products):
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(p["id"])))
            self.table.setItem(row_idx, 1, QTableWidgetItem(p["name"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(f"{p['price']:.2f}"))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(p["stock"])))
            self.table.setItem(row_idx, 4, QTableWidgetItem(p["category"]))

    def _add_product(self):
        name     = self.name_input.text().strip()
        price    = self.price_input.text().strip()
        stock    = self.stock_input.text().strip()
        category = self.category_input.text().strip()

        if not all([name, price, stock, category]):
            QMessageBox.warning(self, "Error", "Fill in all fields.")
            return

        add_product(name, float(price), int(stock), category)
        self._load_table()

        # Clear form inputs
        for w in [self.name_input, self.price_input,
                  self.stock_input, self.category_input]:
            w.clear()

    def _edit_product(self):
        row = self.table.currentRow()
        if row == -1:
            QMessageBox.warning(self, "Error", "Select a product first.")
            return

        # Pre-fill form with selected row
        self.name_input.setText(self.table.item(row, 1).text())
        self.price_input.setText(self.table.item(row, 2).text())
        self.stock_input.setText(self.table.item(row, 3).text())
        self.category_input.setText(self.table.item(row, 4).text())

        product_id = int(self.table.item(row, 0).text())

        # Swap Add button behavior to save edit
        save_btn = QPushButton("Save Edit")
        save_btn.clicked.connect(
            lambda: self._save_edit(product_id)
        )

    def _save_edit(self, product_id):
        update_product(
            product_id,
            self.name_input.text(),
            float(self.price_input.text()),
            int(self.stock_input.text()),
            self.category_input.text()
        )
        self._load_table()

    def _delete_product(self):
        row = self.table.currentRow()
        if row == -1:
            QMessageBox.warning(self, "Error", "Select a product first.")
            return

        name = self.table.item(row, 1).text()
        confirm = QMessageBox.question(
            self, "Confirm", f"Delete '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            product_id = int(self.table.item(row, 0).text())
            delete_product(product_id)
            self._load_table()
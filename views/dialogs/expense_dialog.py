from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QComboBox, QLineEdit, QMessageBox, QInputDialog, QWidget
)
from PySide6.QtCore import Qt
from models.expense import get_expense_categories, create_expense_category, create_expense
from models.supplier import get_all_suppliers

# We try to import the toggle pill from main_window, else fallback to QCheckBox
try:
    from views.main_window import _ToggleSwitch
except ImportError:
    from PySide6.QtWidgets import QCheckBox as _ToggleSwitch

class ProcessExpenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Process Expenses")
        self.setMinimumSize(950, 500)
        self.setStyleSheet("QDialog { background-color: #ffffff; }")
        
        self.categories = []
        self.suppliers = []
        
        self._build()
        self._load_data()

    def _build(self):
        layout = QVBoxLayout(self)
        
        # Header (Now with all action buttons)
        hdr_widget = QWidget()
        hdr_widget.setStyleSheet("background-color: #1a5fb4; border-radius: 5px;")
        hl = QHBoxLayout(hdr_widget)
        hl.setContentsMargins(16, 10, 16, 10)
        
        title = QLabel("Process Expenses")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        hl.addWidget(title)
        
        hl.addStretch()
        
        add_cat_btn = QPushButton("Add Category")
        add_cat_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a5fb4; color: white; border: none;
                border-radius: 4px; padding: 6px 12px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #1c6dd0; }
        """)
        add_cat_btn.clicked.connect(self._add_category)
        hl.addWidget(add_cat_btn)
        
        add_row_btn = QPushButton("Add Row")
        add_row_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a5fb4; color: white; border: none;
                border-radius: 4px; padding: 6px 12px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #1c6dd0; }
        """)
        add_row_btn.clicked.connect(self._add_row)
        hl.addWidget(add_row_btn)
        
        save_btn = QPushButton("Save Expenses")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a7a3c; color: white; border: none;
                border-radius: 4px; padding: 6px 12px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #1f9447; }
        """)
        save_btn.clicked.connect(self._save_expenses)
        hl.addWidget(save_btn)
        
        layout.addWidget(hdr_widget)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Expense Name", "Category", "Amount", "Supplier", "Paid?"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet("""
            QTableWidget { gridline-color: #e4eaf4; border: 1px solid #c8d8ec; }
            QHeaderView::section { background-color: #f0e8d0; padding: 8px; border: none; border-right: 1px solid #c8d8ec; font-weight: bold; font-size: 13px; color: #1a5fb4;}
        """)
        layout.addWidget(self.table)
        
        # Total Label
        self.total_label = QLabel("Total: $0.00")
        self.total_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a7a3c; margin-top: 10px; margin-right: 10px;")
        self.total_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.total_label)
        
    def _load_data(self):
        self.categories = get_expense_categories()
        self.suppliers = get_all_suppliers()
        if self.table.rowCount() == 0:
            self._add_row()

    def _add_category(self):
        name, ok = QInputDialog.getText(self, "Add Category", "Category Name:")
        if ok and name.strip():
            create_expense_category(name.strip())
            self._load_data()
            for r in range(self.table.rowCount()):
                combo = self.table.cellWidget(r, 1)
                if combo:
                    combo.clear()
                    for c in self.categories:
                        combo.addItem(c['name'], c['id'])

    def _add_row(self):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setRowHeight(r, 45) # Make rows taller for the toggle pill
        
        name_edit = QLineEdit()
        name_edit.setStyleSheet("padding: 5px; font-size: 13px; border: 1px solid #c8d8ec; border-radius: 3px;")
        self.table.setCellWidget(r, 0, name_edit)
        
        cat_combo = QComboBox()
        cat_combo.setStyleSheet("padding: 5px; font-size: 13px; border: 1px solid #c8d8ec; border-radius: 3px;")
        for c in self.categories:
            cat_combo.addItem(c['name'], c['id'])
        self.table.setCellWidget(r, 1, cat_combo)
        
        amount_edit = QLineEdit("0.00")
        amount_edit.setStyleSheet("padding: 5px; font-size: 13px; border: 1px solid #c8d8ec; border-radius: 3px;")
        amount_edit.textChanged.connect(self._update_total)
        self.table.setCellWidget(r, 2, amount_edit)
        
        sup_combo = QComboBox()
        sup_combo.setStyleSheet("padding: 5px; font-size: 13px; border: 1px solid #c8d8ec; border-radius: 3px;")
        sup_combo.addItem("None", None)
        for s in self.suppliers:
            sup_combo.addItem(s['name'], s['id'])
        self.table.setCellWidget(r, 3, sup_combo)
        
        paid_pill = _ToggleSwitch("Paid")
        paid_pill.setChecked(True)
        # Center the pill
        w = QWidget()
        wl = QHBoxLayout(w)
        wl.addWidget(paid_pill)
        wl.setAlignment(Qt.AlignCenter)
        wl.setContentsMargins(0,0,0,0)
        self.table.setCellWidget(r, 4, w)

    def _update_total(self):
        total = 0.0
        for r in range(self.table.rowCount()):
            amount_w = self.table.cellWidget(r, 2)
            if amount_w:
                try:
                    total += float(amount_w.text())
                except ValueError:
                    pass
        self.total_label.setText(f"Total: ${total:,.2f}")

    def _save_expenses(self):
        saved = 0
        for r in range(self.table.rowCount()):
            name_w = self.table.cellWidget(r, 0)
            if not name_w or not name_w.text().strip():
                continue
            name = name_w.text().strip()
            
            cat_w = self.table.cellWidget(r, 1)
            cat_id = cat_w.currentData() if cat_w else None
            if not cat_id:
                continue
                
            amount_w = self.table.cellWidget(r, 2)
            try:
                amount = float(amount_w.text())
            except ValueError:
                amount = 0.0
            
            if amount <= 0:
                continue
                
            sup_w = self.table.cellWidget(r, 3)
            sup_id = sup_w.currentData() if sup_w else None
            
            w_box = self.table.cellWidget(r, 4)
            if w_box:
                pill = w_box.layout().itemAt(0).widget()
                paid = pill.isChecked()
            else:
                paid = True
            
            create_expense(name, cat_id, amount, sup_id, paid)
            saved += 1
            
        if saved > 0:
            QMessageBox.information(self, "Success", f"{saved} expenses saved successfully!")
            self.accept()
        else:
            QMessageBox.warning(self, "Warning", "No valid expenses found to save.")

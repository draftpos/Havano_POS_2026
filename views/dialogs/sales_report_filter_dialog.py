from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
    QComboBox, QDateEdit, QPushButton, QLabel
)
from PySide6.QtCore import Qt, QDate
from database.db import get_connection, fetchall_dicts

class SalesReportFilterDialog(QDialog):
    def __init__(self, current_filters, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filter Sales Report")
        self.setFixedSize(400, 300)
        self.current_filters = current_filters
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        
        form = QFormLayout()
        
        self.f_date_from = QDateEdit()
        self.f_date_from.setCalendarPopup(True)
        self.f_date_from.setDate(QDate.fromString(self.current_filters['date_from'], "yyyy-MM-dd"))
        
        self.f_date_to = QDateEdit()
        self.f_date_to.setCalendarPopup(True)
        self.f_date_to.setDate(QDate.fromString(self.current_filters['date_to'], "yyyy-MM-dd"))
        
        self.f_warehouse = QComboBox()
        self.f_warehouse.addItem("All Warehouses", None)
        
        self.f_user = QComboBox()
        self.f_user.addItem("All Users", None)
        
        self.f_category = QComboBox()
        self.f_category.addItem("All", None)
        
        form.addRow("From Date:", self.f_date_from)
        form.addRow("To Date:", self.f_date_to)
        form.addRow("Warehouse:", self.f_warehouse)
        form.addRow("User:", self.f_user)
        form.addRow("Category:", self.f_category)
        
        root.addLayout(form)
        
        btn_lay = QHBoxLayout()
        btn_lay.addStretch()
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_lay.addWidget(btn_cancel)
        
        btn_apply = QPushButton("Apply Filters")
        btn_apply.setStyleSheet("background-color: #1a5fb4; color: white; font-weight: bold;")
        btn_apply.clicked.connect(self.accept)
        btn_lay.addWidget(btn_apply)
        
        root.addLayout(btn_lay)

    def _load_data(self):
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT id, name FROM warehouses")
        for w in fetchall_dicts(cur):
            self.f_warehouse.addItem(w['name'], w['id'])
            if self.current_filters['warehouse_id'] == w['id']:
                self.f_warehouse.setCurrentIndex(self.f_warehouse.count() - 1)
                
        cur.execute("SELECT id, username FROM users")
        for u in fetchall_dicts(cur):
            self.f_user.addItem(u['username'], u['id'])
            if self.current_filters['user_id'] == u['id']:
                self.f_user.setCurrentIndex(self.f_user.count() - 1)
                
        cur.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != ''")
        for c in cur.fetchall():
            self.f_category.addItem(c[0], c[0])
            if self.current_filters['category'] == c[0]:
                self.f_category.setCurrentIndex(self.f_category.count() - 1)
                
        conn.close()

    def get_filters(self):
        return {
            "date_from": self.f_date_from.date().toString("yyyy-MM-dd"),
            "date_to": self.f_date_to.date().toString("yyyy-MM-dd"),
            "warehouse_id": self.f_warehouse.currentData(),
            "user_id": self.f_user.currentData(),
            "category": self.f_category.currentData()
        }

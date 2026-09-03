from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QMessageBox, QLineEdit, QFormLayout
)
from PySide6.QtCore import Qt
from models.supplier import get_all_suppliers, create_supplier, delete_supplier

class AddSupplierDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Supplier")
        self.setMinimumSize(400, 250)
        self.setStyleSheet("QDialog { background-color: #ffffff; }")
        
        layout = QVBoxLayout(self)
        
        title = QLabel("New Supplier")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a5fb4;")
        layout.addWidget(title)
        
        form = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Supplier Name")
        form.addRow("Name *:", self.name_edit)
        
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("Phone Number")
        form.addRow("Phone:", self.phone_edit)
        
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("Email Address")
        form.addRow("Email:", self.email_edit)
        
        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText("Physical Address")
        form.addRow("Address:", self.address_edit)
        
        layout.addLayout(form)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("background-color: #1a5fb4; color: white; font-weight: bold; padding: 6px 16px;")
        save_btn.clicked.connect(self._save)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        
    def _save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Supplier name is required.")
            return
            
        self.supplier_data = {
            "name": name,
            "phone": self.phone_edit.text().strip(),
            "email": self.email_edit.text().strip(),
            "address": self.address_edit.text().strip()
        }
        self.accept()

class SupplierDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Suppliers")
        self.setWindowState(Qt.WindowMaximized)
        self.setStyleSheet("QDialog { background-color: #f5f8fc; }")
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        from views.reports.report_template import ReportTemplate
        self.report = ReportTemplate("Suppliers Master", is_report=False, show_date_filter=True, parent=self)
        self.report.set_headers(["Name", "Phone", "Email", "Balance"])
        
        self.report.btn_add.setText(" Add Supplier")
        self.report.btn_add.clicked.connect(self._on_add)
        
        self.table = self.report.table
        layout.addWidget(self.report, 1)

    def _load(self):
        while self.table.rowCount() > 1:
            self.table.removeRow(1)
        suppliers = get_all_suppliers()
        for sup in suppliers:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(sup.get("name", "")))
            self.table.setItem(r, 1, QTableWidgetItem(sup.get("phone", "")))
            self.table.setItem(r, 2, QTableWidgetItem(sup.get("email", "")))
            bal = float(sup.get("balance", 0.0))
            self.table.setItem(r, 3, QTableWidgetItem(f"${bal:.2f}"))

    def _on_add(self):
        dlg = AddSupplierDialog(self)
        if dlg.exec():
            data = dlg.supplier_data
            create_supplier(
                name=data["name"],
                phone=data["phone"],
                email=data["email"],
                address=data["address"]
            )
            self._load()

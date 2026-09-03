from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator, QFont

class ButcheryAmountDialog(QDialog):
    def __init__(self, parent=None, product_name="Butchery Item"):
        super().__init__(parent)
        self.setWindowTitle("Enter Amount")
        self.setFixedSize(400, 250)
        self.setModal(True)
        # Modern styling without emojis
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
                border-radius: 8px;
            }
            QLabel#title {
                font-size: 20px;
                font-weight: bold;
                color: #2c3e50;
            }
            QLabel#subtitle {
                font-size: 14px;
                color: #7f8c8d;
            }
            QLineEdit {
                padding: 12px;
                font-size: 24px;
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                background-color: #ffffff;
                color: #2c3e50;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
            QPushButton {
                padding: 10px 20px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 6px;
                border: none;
            }
            QPushButton#confirm {
                background-color: #27ae60;
                color: white;
            }
            QPushButton#confirm:hover {
                background-color: #2ecc71;
            }
            QPushButton#cancel {
                background-color: #e74c3c;
                color: white;
            }
            QPushButton#cancel:hover {
                background-color: #c0392b;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        # Title
        lbl_title = QLabel("Total Amount")
        lbl_title.setObjectName("title")
        lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_title)

        # Subtitle (Product Name)
        lbl_subtitle = QLabel(f"Enter cash amount for {product_name}")
        lbl_subtitle.setObjectName("subtitle")
        lbl_subtitle.setAlignment(Qt.AlignCenter)
        lbl_subtitle.setWordWrap(True)
        layout.addWidget(lbl_subtitle)

        # Input Field
        self.input_amount = QLineEdit()
        self.input_amount.setAlignment(Qt.AlignCenter)
        self.input_amount.setPlaceholderText("0.00")
        
        # Validator for doubles
        validator = QDoubleValidator(0.0, 1000000.0, 2, self)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.input_amount.setValidator(validator)
        
        # Increase font specifically for input
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        self.input_amount.setFont(font)
        self.input_amount.returnPressed.connect(self.accept)
        
        layout.addWidget(self.input_amount)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_confirm = QPushButton("Confirm")
        self.btn_confirm.setObjectName("confirm")
        self.btn_confirm.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_confirm)
        
        layout.addLayout(btn_layout)

    def get_amount(self):
        text = self.input_amount.text().strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0

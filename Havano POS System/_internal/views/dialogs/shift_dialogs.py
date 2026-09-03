from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PySide6.QtCore import Qt
from models.shift import save_shift_report

class CloseShiftDialog(QDialog):
    def __init__(self, parent=None, expected_amount=0.0):
        super().__init__(parent)
        self.expected = expected_amount
        self.setWindowTitle("Close Shift")
        self.setFixedSize(350, 250)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        
        lay.addWidget(QLabel(f"Expected Amount: ${self.expected:.2f}"))
        
        lay.addWidget(QLabel("Actual Amount in Drawer:"))
        self.actual_input = QLineEdit()
        self.actual_input.setPlaceholderText("0.00")
        self.actual_input.setFixedHeight(40)
        self.actual_input.setStyleSheet("font-size: 18px; font-weight: bold;")
        lay.addWidget(self.actual_input)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Confirm & Close Shift")
        save_btn.clicked.connect(self._handle_save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        lay.addLayout(btn_row)

    def _handle_save(self):
        try:
            actual = float(self.actual_input.text() or 0)
            # Retrieve user info from parent
            user = self.parent().user
            save_shift_report(user.get("id"), user.get("username"), self.expected, actual, {})
            QMessageBox.information(self, "Success", f"Shift closed. Variance: ${actual - self.expected:.2f}")
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Error", "Please enter a valid amount.")
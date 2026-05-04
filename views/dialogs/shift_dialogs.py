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
        
        # Check maintenance setting for expected visibility
        self.show_expected = True
        try:
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT setting_value FROM pos_settings WHERE setting_key = 'show_expected_in_reconciliation'")
            row = cur.fetchone()
            if row:
                self.show_expected = (str(row[0]) == "1")
            conn.close()
        except:
            self.show_expected = True

        if self.show_expected:
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
        lay.addStretch()

    def _handle_save(self):
        try:
            actual = float(self.actual_input.text() or 0)
            # Retrieve user info from parent
            user = self.parent().user
            save_shift_report(user.get("id"), user.get("username"), self.expected, actual, {})
            
            msg = "Shift closed successfully."
            if self.show_expected:
                msg += f" Variance: ${actual - self.expected:.2f}"
                
            QMessageBox.information(self, "Success", msg)
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Error", "Please enter a valid amount.")
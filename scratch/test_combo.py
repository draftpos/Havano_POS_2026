import sys
from PySide6.QtWidgets import QApplication, QDialog, QComboBox, QVBoxLayout, QLineEdit, QCompleter
from PySide6.QtCore import Qt

class TestDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(300, 200)

        layout = QVBoxLayout(self)
        self.cb = QComboBox()
        self.cb.addItems(["Item 1", "Item 2", "Item 3"])
        
        # Uncomment to fix:
        # self.cb.view().window().setAttribute(Qt.WA_TranslucentBackground, False)
        
        layout.addWidget(self.cb)

        self.le = QLineEdit()
        self.comp = QCompleter(["Cat 1", "Cat 2", "Cat 3"])
        self.le.setCompleter(self.comp)
        
        # Uncomment to fix:
        # self.comp.popup().window().setAttribute(Qt.WA_TranslucentBackground, False)
        
        layout.addWidget(self.le)

        self.setStyleSheet("background: white;")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    d = TestDialog()
    d.show()
    sys.exit(app.exec())

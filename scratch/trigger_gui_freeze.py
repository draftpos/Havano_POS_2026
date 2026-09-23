import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import Qt

class FreezeTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Havano POS - Freeze Test Window")
        self.resize(450, 200)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignCenter)

        label = QLabel("Click the button below to freeze the window for 7 seconds.\nThis triggers Windows '(Not Responding)' status.")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        btn = QPushButton("🥶 Simulate 7-Second Freeze (ProcDump & Bugsink Test)")
        btn.setStyleSheet("font-size: 14px; padding: 12px; font-weight: bold; background-color: #dc2626; color: white; border-radius: 6px;")
        btn.clicked.connect(self._freeze)
        layout.addWidget(btn)

        self.setCentralWidget(container)

    def _freeze(self):
        print("\n[FreezeTest] Freezing UI thread for 7 seconds now...")
        print("[FreezeTest] Try clicking the window: Windows will mark it '(Not Responding)'.")
        time.sleep(7.0)
        print("[FreezeTest] UI thread resumed!\n")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = FreezeTestWindow()
    win.show()
    sys.exit(app.exec())

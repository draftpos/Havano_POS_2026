import sys, os
sys.path.insert(0, os.path.abspath("."))
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)
try:
    import main
    from views.main_window import MainWindow
    win = MainWindow(user={"username": "James Madison", "role": "admin"})
    print("SUCCESS: MainWindow initialized without errors!")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("ERROR:", e)
    sys.exit(1)

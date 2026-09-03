import sys, os
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

app = QApplication.instance() or QApplication(sys.argv)

from views.dialogs.start_shift_dialog import StartShiftDialog

dlg = StartShiftDialog(user={"id": 1, "username": "admin"})
print("StartShiftDialog initialized successfully.")
print("Base currency:", dlg._base_ccy)
print("Default float:", dlg.float_edit.text())
